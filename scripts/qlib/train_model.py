"""
train_model.py - 基于研究层数据集训练模型，并导出为“Freqtrade 可加载”的目录格式

输出格式（与 remp_research/qlib_model_wrapper.py 对齐）：
- model.pkl            : joblib 保存的 sklearn 模型（建议包含 predict_proba）
- features.json        : 特征列清单（{"features": [...], "target": {...}}）
- model_info.json      : 训练元信息（区间、样本数、验证集指标等）

默认路径：
- 数据集：02_qlib_research/qlib_data/<exchange>/<timeframe>/<symbol>.pkl
- 模型：02_qlib_research/models/qlib/<model_version>/<exchange>/<timeframe>/<symbol>/

用法：
    uv run python -X utf8 scripts/qlib/train_model.py --help
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from joblib import dump
from sklearn.calibration import CalibratedClassifierCV
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, brier_score_loss, log_loss, roc_auc_score
from sklearn.model_selection import TimeSeriesSplit
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

# 确保可导入 03_integration/trading_system（脚本以文件路径运行时，sys.path[0] 会变为 scripts/qlib）
_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "03_integration"))

from trading_system.application.factor_sets import get_factor_templates, render_factor_names
from trading_system.domain.symbols import freqtrade_pair_to_symbol
from trading_system.infrastructure.config_loader import get_config
from trading_system.infrastructure.ml.drift import build_feature_baseline
from trading_system.infrastructure.ml.features import build_supervised_dataset, compute_features


@dataclass(frozen=True)
class DatasetSpec:
    exchange: str
    timeframe: str
    symbol: str
    path: Path


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="训练一个轻量方向模型（示例：LogisticRegression）。")
    p.add_argument("--pair", default="BTC/USDT:USDT", help="交易对（用于推导 symbol），例如 \"BTC/USDT:USDT\"。")
    p.add_argument("--exchange", default="", help="交易所名（默认从配置读取）。")
    p.add_argument("--timeframe", default="4h", help="时间周期（默认 4h）。")
    p.add_argument(
        "--datafile",
        default="",
        help="直接指定数据集 .pkl 路径（优先级最高）。留空则按默认目录推断。",
    )
    p.add_argument("--model-version", default="", help="模型版本号（默认读取 QLIB_MODEL_VERSION / v1）。")
    p.add_argument("--valid-pct", type=float, default=0.2, help="按时间切分验证集比例（默认 0.2）。")
    p.add_argument("--horizon", type=int, default=1, help="预测目标的未来 K 线步数（默认 1）。")
    p.add_argument(
        "--threshold",
        type=float,
        default=0.0,
        help="目标阈值：future_return > threshold 视为 1（默认 0.0）。可用于覆盖手续费阈值。",
    )
    p.add_argument(
        "--feature-set",
        default="",
        help="特征集名称（来自 04_shared/config/factors.yaml 的 factor_sets）。例如 \"cta_core\"。留空则使用默认特征列。",
    )
    p.add_argument("--outdir", default="", help="模型输出目录（留空则按默认目录推断）。")
    return p.parse_args()


def _resolve_dataset(*, cfg, pair: str, exchange: str, timeframe: str, datafile: str) -> DatasetSpec:
    symbol = freqtrade_pair_to_symbol(pair)
    if not symbol:
        raise ValueError("pair 无法解析为 symbol")

    if str(datafile or "").strip():
        p = Path(str(datafile)).expanduser().resolve()
        if not p.is_file():
            raise FileNotFoundError(f"未找到数据集：{p.as_posix()}")
        return DatasetSpec(exchange=exchange, timeframe=timeframe, symbol=symbol, path=p)

    p = (cfg.qlib_data_dir / exchange / timeframe / f"{symbol}.pkl").resolve()
    if not p.is_file():
        raise FileNotFoundError(
            "未找到数据集，请先运行转换脚本：\n"
            f"- 期望路径：{p.as_posix()}\n"
            "示例：uv run python -X utf8 scripts/qlib/convert_freqtrade_to_qlib.py --timeframe 4h"
        )
    return DatasetSpec(exchange=exchange, timeframe=timeframe, symbol=symbol, path=p)


def _build_features(
    df: pd.DataFrame,
    *,
    horizon: int,
    threshold: float,
    feature_cols: list[str] | None,
) -> tuple[pd.DataFrame, pd.Series, list[str], pd.Series | None, pd.DataFrame]:
    """构建特征与标签（复用 trading_system.infrastructure.ml.features，保证训练/预测一致）。"""
    work = df.copy()
    date_index: pd.Series | None = None
    if "date" in work.columns:
        work["date"] = pd.to_datetime(work["date"], utc=True, errors="coerce")
        work = work.dropna(subset=["date"]).sort_values("date")
        date_index = work["date"]

    X, y, cols = build_supervised_dataset(
        work,
        horizon=int(horizon),
        threshold=float(threshold),
        feature_cols=feature_cols,
    )
    return X, y, cols, date_index, work


def _time_split(X: pd.DataFrame, y: pd.Series, valid_pct: float) -> tuple[pd.DataFrame, pd.DataFrame, pd.Series, pd.Series]:
    n = int(len(X))
    if n < 100:
        raise ValueError(f"样本数过少（n={n}），不建议训练；请换更长周期或更高频数据。")

    pct = float(valid_pct)
    if not np.isfinite(pct) or pct <= 0 or pct >= 0.5:
        raise ValueError("valid_pct 必须在 (0, 0.5) 内")

    cut = int(n * (1.0 - pct))
    X_train, X_valid = X.iloc[:cut], X.iloc[cut:]
    y_train, y_valid = y.iloc[:cut], y.iloc[cut:]
    return X_train, X_valid, y_train, y_valid


def _resolve_feature_cols(*, feature_set: str) -> tuple[list[str] | None, dict]:
    """
    解析特征列：
    - 未指定 feature_set：返回 None（使用 features.py 默认列）
    - 指定 feature_set：从 factors.yaml 的 factor_sets.<name> 读取（支持 @ 引用）
    """
    name = str(feature_set or "").strip()
    if not name:
        return None, {
            "source": "trading_system.infrastructure.ml.features.DEFAULT_FEATURE_COLUMNS",
            "feature_set": "",
        }

    templates = get_factor_templates(name)
    cols = render_factor_names(templates, {})
    cols = [str(c).strip() for c in cols if str(c).strip()]
    if not cols:
        raise ValueError(f"feature_set 为空或不存在：{name}")

    return cols, {
        "source": "04_shared/config/factors.yaml",
        "feature_set": name,
        "templates": templates,
    }


def _extract_logreg_weights(model: Pipeline, feature_cols: list[str]) -> dict:
    """
    从标准化+逻辑回归中提取“因子权重”（系数）。

    注意：
    - 这里的 coef 是在 StandardScaler 标准化空间下的权重（更接近“可比权重”）。
    - 仅作为研究/归因输出，不直接用于实盘信号。
    """
    try:
        clf = getattr(model, "named_steps", {}).get("clf")
        if clf is None or not hasattr(clf, "coef_"):
            return {"method": "logreg", "weights": []}

        coef = np.asarray(clf.coef_, dtype="float64")
        if coef.ndim == 2:
            coef = coef[0]
        if int(coef.shape[0]) != int(len(feature_cols)):
            return {"method": "logreg", "weights": []}

        abs_sum = float(np.sum(np.abs(coef)))
        rows = []
        for name, w in zip(feature_cols, coef):
            w = float(w)
            rows.append(
                {
                    "name": str(name),
                    "coef": w,
                    "abs_norm": float(abs(w) / abs_sum) if abs_sum > 0 else 0.0,
                }
            )
        rows.sort(key=lambda x: float(x.get("abs_norm", 0.0)), reverse=True)

        intercept = None
        if hasattr(clf, "intercept_"):
            try:
                intercept_arr = np.asarray(clf.intercept_, dtype="float64")
                intercept = float(intercept_arr.reshape(-1)[0])
            except Exception:
                intercept = None

        return {"method": "logreg_standardized", "intercept": intercept, "weights": rows}
    except Exception:
        return {"method": "logreg", "weights": []}


def _regime_labels_for_evaluation(
    work: pd.DataFrame,
    *,
    indices: pd.Index,
    train_indices: pd.Index,
) -> tuple[pd.Series, dict]:
    """
    为训练/验证样本构造“制度标签”（用于分桶评估）。

    说明：
    - 这里只用于评估，不直接作为交易信号。
    - 规则是“可解释优先”的轻量版本：用少量 OHLCV 衍生特征近似刻画制度。
    """
    need = ["ret_12", "vol_12", "ema_spread"]
    feats = compute_features(work, feature_cols=need)
    feats = feats.reindex(indices)

    ret12 = feats.get("ret_12", pd.Series(index=indices, dtype="float64")).astype("float64")
    vol12 = feats.get("vol_12", pd.Series(index=indices, dtype="float64")).astype("float64")
    spread = feats.get("ema_spread", pd.Series(index=indices, dtype="float64")).astype("float64")

    ret12 = ret12.replace([np.inf, -np.inf], np.nan)
    vol12 = vol12.replace([np.inf, -np.inf], np.nan)
    spread = spread.replace([np.inf, -np.inf], np.nan)

    ti = indices.intersection(train_indices)
    if len(ti) <= 0:
        ti = indices

    vol_q90 = float(vol12.loc[ti].quantile(0.90))
    spread_abs_q70 = float(spread.loc[ti].abs().quantile(0.70))

    strength = (ret12.abs() / vol12.replace(0, np.nan)).replace([np.inf, -np.inf], np.nan)
    strength_q70 = float(strength.loc[ti].quantile(0.70))

    is_valid = vol12.notna() & spread.notna() & ret12.notna()
    is_crisis = is_valid & (vol12 >= vol_q90)
    is_trend = is_valid & (~is_crisis) & (spread.abs() >= spread_abs_q70) & (strength >= strength_q70)

    labels = pd.Series("range", index=indices, dtype="object")
    labels[~is_valid] = "unknown"
    labels[is_crisis] = "crisis"
    labels[is_trend & (spread > 0)] = "bull_trend"
    labels[is_trend & (spread < 0)] = "bear_trend"

    return labels, {
        "version": 1,
        "features": need,
        "thresholds": {
            "vol_12_q90": vol_q90,
            "ema_spread_abs_q70": spread_abs_q70,
            "trend_strength_q70": strength_q70,
        },
        "notes": "crisis=高波动；trend=价差结构+强度；其余为 range。仅用于评估分桶。",
    }


def _bucket_metrics(y_true: pd.Series, proba: np.ndarray, pred: np.ndarray, labels: pd.Series) -> dict:
    work = pd.DataFrame(
        {
            "y": y_true.astype("int64").to_numpy(copy=False),
            "proba": np.asarray(proba, dtype="float64"),
            "pred": np.asarray(pred, dtype="int64"),
            "regime": labels.astype("object").to_numpy(copy=False),
        },
        index=y_true.index,
    )

    out: dict[str, dict] = {}
    for regime in sorted({str(x) for x in work["regime"].dropna().unique()}):
        part = work.loc[work["regime"] == regime].copy()
        if part.empty:
            continue

        yv = part["y"].to_numpy(dtype="int64", copy=False)
        pv = part["proba"].to_numpy(dtype="float64", copy=False)
        pr = part["pred"].to_numpy(dtype="int64", copy=False)

        m: dict[str, float] = {
            "rows": int(len(part)),
            "pos_rate": float(np.mean(yv)) if len(yv) > 0 else float("nan"),
            "accuracy": float(accuracy_score(yv, pr)) if len(yv) > 0 else float("nan"),
            "brier": float(brier_score_loss(yv, pv)) if len(yv) > 0 else float("nan"),
        }
        try:
            if len(np.unique(yv)) >= 2:
                m["auc"] = float(roc_auc_score(yv, pv))
        except Exception:
            pass
        try:
            if len(np.unique(yv)) >= 2:
                m["logloss"] = float(log_loss(yv, pv, labels=[0, 1]))
        except Exception:
            pass

        out[regime] = m

    return out


def main() -> int:
    args = _parse_args()
    cfg = get_config()

    exchange = str(args.exchange or "").strip() or cfg.freqtrade_exchange
    timeframe = str(args.timeframe or "").strip()
    if not timeframe:
        raise ValueError("timeframe 不能为空")

    spec = _resolve_dataset(
        cfg=cfg,
        pair=str(args.pair),
        exchange=exchange,
        timeframe=timeframe,
        datafile=str(args.datafile),
    )

    df = pd.read_pickle(spec.path)
    selected_cols, feature_spec = _resolve_feature_cols(feature_set=str(args.feature_set))
    X, y, feature_cols, date_index, work = _build_features(
        df,
        horizon=int(args.horizon),
        threshold=float(args.threshold),
        feature_cols=selected_cols,
    )
    X_train, X_valid, y_train, y_valid = _time_split(X, y, valid_pct=float(args.valid_pct))

    train_range: dict[str, str] = {}
    valid_range: dict[str, str] = {}
    if date_index is not None:
        train_dates = date_index.reindex(X_train.index).dropna()
        valid_dates = date_index.reindex(X_valid.index).dropna()
        if not train_dates.empty:
            train_range = {"start": str(train_dates.min()), "end": str(train_dates.max())}
        if not valid_dates.empty:
            valid_range = {"start": str(valid_dates.min()), "end": str(valid_dates.max())}

    # 轻量基线：标准化 + 逻辑回归（便于输出概率）
    base_model = Pipeline(
        steps=[
            ("scaler", StandardScaler(with_mean=True, with_std=True)),
            (
                "clf",
                LogisticRegression(
                    max_iter=500,
                    class_weight="balanced",
                    random_state=42,
                ),
            ),
        ]
    )
    base_model.fit(X_train, y_train)

    base_proba = base_model.predict_proba(X_valid)[:, 1]
    base_pred = (base_proba >= 0.5).astype("int64")

    base_metrics: dict[str, float] = {
        "valid_accuracy": float(accuracy_score(y_valid, base_pred)),
        "valid_brier": float(brier_score_loss(y_valid, base_proba)),
        "valid_logloss": float(log_loss(y_valid, base_proba, labels=[0, 1])),
        "valid_pos_rate": float(np.mean(y_valid.values)),
        "valid_pred_pos_rate": float(np.mean(base_pred)),
    }
    try:
        if len(np.unique(y_valid.values)) >= 2:
            base_metrics["valid_auc"] = float(roc_auc_score(y_valid, base_proba))
    except Exception:
        pass

    # 概率校准（业界常用：sigmoid/Platt scaling）
    # 用 TimeSeriesSplit 在训练集内做校准，避免把验证集“用来拟合”导致指标失真。
    tscv = TimeSeriesSplit(n_splits=3)
    calibrated_model = CalibratedClassifierCV(estimator=base_model, method="sigmoid", cv=tscv, ensemble="auto")
    calibrated_model.fit(X_train, y_train)

    cal_proba = calibrated_model.predict_proba(X_valid)[:, 1]
    cal_pred = (cal_proba >= 0.5).astype("int64")
    cal_metrics: dict[str, float] = {
        "valid_accuracy": float(accuracy_score(y_valid, cal_pred)),
        "valid_brier": float(brier_score_loss(y_valid, cal_proba)),
        "valid_logloss": float(log_loss(y_valid, cal_proba, labels=[0, 1])),
        "valid_pos_rate": float(np.mean(y_valid.values)),
        "valid_pred_pos_rate": float(np.mean(cal_pred)),
    }
    try:
        if len(np.unique(y_valid.values)) >= 2:
            cal_metrics["valid_auc"] = float(roc_auc_score(y_valid, cal_proba))
    except Exception:
        pass

    # 制度分桶评估：避免只看全样本平均指标，忽略制度切换导致的“静默衰减”
    regime_labels, regime_def = _regime_labels_for_evaluation(work, indices=X.index, train_indices=X_train.index)
    train_regime = regime_labels.reindex(X_train.index)
    valid_regime = regime_labels.reindex(X_valid.index)
    regime_eval = {
        "definition": regime_def,
        "train_counts": {str(k): int(v) for k, v in train_regime.value_counts(dropna=False).to_dict().items()},
        "valid_counts": {str(k): int(v) for k, v in valid_regime.value_counts(dropna=False).to_dict().items()},
        "metrics": {
            "base": _bucket_metrics(y_valid, base_proba, base_pred, valid_regime),
            "calibrated": _bucket_metrics(y_valid, cal_proba, cal_pred, valid_regime),
        },
    }

    model_version = str(args.model_version or "").strip() or cfg.model_version
    outdir = (
        Path(str(args.outdir)).expanduser()
        if str(args.outdir or "").strip()
        else (cfg.qlib_model_dir / model_version / exchange / timeframe / spec.symbol)
    ).resolve()
    outdir.mkdir(parents=True, exist_ok=True)

    # 训练特征分布基线：用于后续漂移检测（概念漂移/数据质量监控）
    baseline = build_feature_baseline(
        X_train,
        quantile_bins=10,
        metadata={
            "model_version": model_version,
            "exchange": exchange,
            "timeframe": timeframe,
            "pair": str(args.pair),
            "symbol": spec.symbol,
            "dataset_path": spec.path.as_posix(),
            "rows_train": int(len(X_train)),
            "rows_valid": int(len(X_valid)),
            "feature_spec": feature_spec | {"version": 2},
            "train_range": train_range,
            "valid_range": valid_range,
        },
    )

    dump(calibrated_model, outdir / "model.pkl")
    weights = _extract_logreg_weights(base_model, feature_cols)
    (outdir / "factor_weights.json").write_text(
        json.dumps(weights, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (outdir / "features.json").write_text(
        json.dumps(
            {
                "features": feature_cols,
                "target": {"horizon": int(args.horizon), "threshold": float(args.threshold)},
                "feature_spec": feature_spec | {"version": 2},
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (outdir / "feature_baseline.json").write_text(
        json.dumps(baseline, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (outdir / "model_info.json").write_text(
        json.dumps(
            {
                "version": model_version,
                "exchange": exchange,
                "timeframe": timeframe,
                "pair": str(args.pair),
                "symbol": spec.symbol,
                "dataset_path": spec.path.as_posix(),
                "rows_total": int(len(df)),
                "rows_train": int(len(X_train)),
                "rows_valid": int(len(X_valid)),
                "train_range": train_range,
                "valid_range": valid_range,
                "features": feature_cols,
                "target": {"horizon": int(args.horizon), "threshold": float(args.threshold)},
                "feature_spec": feature_spec | {"version": 2},
                "feature_baseline_file": "feature_baseline.json",
                "factor_weights": weights,
                "metrics": {
                    "base": base_metrics,
                    "calibrated": cal_metrics,
                },
                "regime_evaluation": regime_eval,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print("")
    print(cfg.display())
    print("")
    print(f"已输出模型：{outdir.as_posix()}")
    print(f"- base_valid_auc: {base_metrics.get('valid_auc', float('nan')):.4f}")
    print(f"- base_valid_brier: {base_metrics.get('valid_brier', float('nan')):.6f}")
    print(f"- calibrated_valid_auc: {cal_metrics.get('valid_auc', float('nan')):.4f}")
    print(f"- calibrated_valid_brier: {cal_metrics.get('valid_brier', float('nan')):.6f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
