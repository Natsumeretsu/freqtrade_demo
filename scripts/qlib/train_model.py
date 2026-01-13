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
from trading_system.infrastructure.ml.features import build_supervised_dataset


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
) -> tuple[pd.DataFrame, pd.Series, list[str]]:
    """构建特征与标签（复用 trading_system.infrastructure.ml.features，保证训练/预测一致）。"""
    work = df.copy()
    if "date" in work.columns:
        work["date"] = pd.to_datetime(work["date"], utc=True, errors="coerce")
        work = work.dropna(subset=["date"]).sort_values("date")

    X, y, cols = build_supervised_dataset(
        work,
        horizon=int(horizon),
        threshold=float(threshold),
        feature_cols=feature_cols,
    )
    return X, y, cols


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
    X, y, feature_cols = _build_features(
        df,
        horizon=int(args.horizon),
        threshold=float(args.threshold),
        feature_cols=selected_cols,
    )
    X_train, X_valid, y_train, y_valid = _time_split(X, y, valid_pct=float(args.valid_pct))

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

    model_version = str(args.model_version or "").strip() or cfg.model_version
    outdir = (
        Path(str(args.outdir)).expanduser()
        if str(args.outdir or "").strip()
        else (cfg.qlib_model_dir / model_version / exchange / timeframe / spec.symbol)
    ).resolve()
    outdir.mkdir(parents=True, exist_ok=True)

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
                "features": feature_cols,
                "target": {"horizon": int(args.horizon), "threshold": float(args.threshold)},
                "feature_spec": feature_spec | {"version": 2},
                "factor_weights": weights,
                "metrics": {
                    "base": base_metrics,
                    "calibrated": cal_metrics,
                },
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
