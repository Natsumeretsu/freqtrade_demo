"""
train_model.py - 用真实 Qlib 的 Dataset/DataHandler 组织数据，并训练方向模型后导出为“Freqtrade 可加载”格式

本脚本完成两件事：
1) 通过 Qlib 的 DataHandler/DataSet 统一组织研究层数据（避免各脚本各写一套读数逻辑）
2) 训练一个二分类模型（未来上涨=1 / 否则=0），并导出为策略侧可加载的目录结构
3) （默认）对概率做时间序列校准（TimeSeriesSplit + sigmoid），让 proba 更适合做“连续权重/软过滤”

输出格式（与 03_integration/trading_system/infrastructure/ml/model_loader.py 对齐）：
- model.pkl              : joblib 保存的 sklearn 风格模型（需支持 predict_proba 或至少 predict）
- features.json          : {"features":[...], "target": {...}, "feature_spec": {...}}
- model_info.json        : 训练元信息（区间、样本数、验证集指标等）
  - metrics.base / metrics.calibrated：分别记录校准前/后的 valid_* 指标
  - calibration：记录校准方法、分割信息与执行状态
- feature_baseline.json  : 训练特征分布基线（用于漂移检测与 auto_risk）

默认路径：
- 数据集：02_qlib_research/qlib_data/<exchange>/<timeframe>/<symbol>.pkl
- 模型：  02_qlib_research/models/qlib/<model_version>/<exchange>/<timeframe>/<symbol>/

用法：
  uv run python -X utf8 scripts/qlib/train_model.py --help
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from joblib import dump
from lightgbm import LGBMClassifier
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import accuracy_score, brier_score_loss, log_loss, roc_auc_score
from sklearn.model_selection import TimeSeriesSplit

from qlib.data.dataset import DatasetH
from qlib.data.dataset.handler import DataHandler

# 确保可导入 03_integration/trading_system（脚本以文件路径运行时，sys.path[0] 会变为 scripts/qlib）
_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "03_integration"))

from trading_system.domain.symbols import freqtrade_pair_to_symbol  # noqa: E402
from trading_system.infrastructure.config_loader import get_config  # noqa: E402
from trading_system.infrastructure.ml.drift import build_feature_baseline  # noqa: E402
from trading_system.infrastructure.qlib.freqtrade_pkl_data_loader import FreqtradePklDataLoader  # noqa: E402


@dataclass(frozen=True)
class DatasetSpec:
    exchange: str
    timeframe: str
    symbol: str


def _parse_key_value(s: str) -> tuple[str, str] | None:
    raw = str(s or "").strip()
    if not raw:
        return None
    if "=" not in raw:
        return None
    k, v = raw.split("=", 1)
    k = k.strip()
    v = v.strip()
    if not k:
        return None
    return k, v


def _coerce_json_scalar(v: str) -> Any:
    s = str(v).strip()
    if not s:
        return ""
    # 尝试解析为 JSON 标量（数字/true/false/null），失败则保留字符串
    try:
        obj = json.loads(s)
    except Exception:
        return s
    if isinstance(obj, (str, int, float, bool)) or obj is None:
        return obj
    return s


def _load_feature_vars(strategy_params_path: str, extra_vars: list[str]) -> dict[str, Any]:
    """
    变量渲染规则：
    - 从策略参数 JSON 提取：buy_xxx / sell_xxx -> xxx（覆盖 factors.yaml 的 {xxx} 占位符）
    - 额外 --var key=value 覆盖同名变量
    """
    out: dict[str, Any] = {}

    p = str(strategy_params_path or "").strip()
    if p:
        path = Path(p).expanduser()
        if not path.is_absolute():
            path = (_REPO_ROOT / path).resolve()
        if not path.is_file():
            raise FileNotFoundError(f"未找到策略参数文件：{path.as_posix()}")

        data = json.loads(path.read_text(encoding="utf-8"))
        params = data.get("params", {}) if isinstance(data, dict) else {}
        if isinstance(params, dict):
            for scope in ("buy", "sell"):
                block = params.get(scope, {})
                if not isinstance(block, dict):
                    continue
                for k, v in block.items():
                    kk = str(k).strip()
                    if not kk:
                        continue
                    prefix = f"{scope}_"
                    if kk.startswith(prefix):
                        out[kk[len(prefix) :]] = v

    for item in extra_vars or []:
        kv = _parse_key_value(item)
        if kv is None:
            continue
        k, v = kv
        out[k] = _coerce_json_scalar(v)

    return out


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="基于 Qlib DatasetH 训练一个方向模型（默认：LightGBM binary）。")
    p.add_argument("--pair", default="BTC/USDT:USDT", help="交易对（用于推导 symbol），例如 \"BTC/USDT:USDT\"。")
    p.add_argument("--exchange", default="", help="交易所名（默认从配置读取）。")
    p.add_argument("--timeframe", default="4h", help="时间周期（默认 4h）。")
    p.add_argument("--model-version", default="", help="模型版本号（默认读取配置 QLIB_MODEL_VERSION / v1）。")

    p.add_argument("--horizon", type=int, default=1, help="预测目标的未来 K 线步数（默认 1）。")
    p.add_argument("--threshold", type=float, default=0.0, help="future_return > threshold 视为 1（默认 0.0）。")
    p.add_argument("--valid-pct", type=float, default=0.2, help="按时间切分验证集比例（默认 0.2）。")

    p.add_argument(
        "--feature-set",
        default="ml_core",
        help="特征集名称（来自 04_shared/config/factors.yaml 的 factor_sets），默认 ml_core。",
    )
    p.add_argument(
        "--strategy-params",
        default="",
        help="策略参数 JSON（可选）：用于渲染 factors.yaml 的 {var} 占位符。",
    )
    p.add_argument(
        "--var",
        action="append",
        default=[],
        help="额外渲染变量（可重复），格式 key=value；会覆盖 strategy-params 的同名变量。",
    )

    p.add_argument("--outdir", default="", help="模型输出目录（留空则按默认目录推断）。")

    # LightGBM 参数（保守默认，避免在小样本上过拟合）
    p.add_argument("--lgbm-num-leaves", type=int, default=31, help="LightGBM num_leaves（默认 31）。")
    p.add_argument("--lgbm-max-depth", type=int, default=-1, help="LightGBM max_depth（默认 -1，不限制）。")
    p.add_argument("--lgbm-learning-rate", type=float, default=0.05, help="LightGBM learning_rate（默认 0.05）。")
    p.add_argument("--lgbm-n-estimators", type=int, default=500, help="LightGBM n_estimators（默认 500）。")
    p.add_argument("--seed", type=int, default=42, help="随机种子（默认 42）。")
    return p.parse_args()


def _resolve_dataset_spec(*, pair: str, exchange: str, timeframe: str) -> DatasetSpec:
    symbol = freqtrade_pair_to_symbol(pair)
    if not symbol:
        raise ValueError("pair 无法解析为 symbol")
    return DatasetSpec(exchange=str(exchange).strip(), timeframe=str(timeframe).strip(), symbol=str(symbol).strip())


def _split_segments_from_index(dt_index: list[Any], valid_pct: float) -> dict[str, tuple[Any, Any]]:
    if not dt_index:
        raise ValueError("数据为空：无法切分 train/valid")

    dates = sorted(set(dt_index))
    n = int(len(dates))
    if n < 20:
        raise ValueError("样本过少：请确保数据覆盖足够的历史区间（建议至少几十根 K 线）。")

    pct = float(valid_pct)
    if not (0.05 <= pct <= 0.5):
        raise ValueError("valid_pct 建议在 [0.05, 0.5]，避免切分过小或过大。")

    cut = int(math.floor(n * (1.0 - pct)))
    cut = max(1, min(n - 1, cut))

    train_start = dates[0]
    train_end = dates[cut - 1]
    valid_start = dates[cut]
    valid_end = dates[-1]
    return {"train": (train_start, train_end), "valid": (valid_start, valid_end)}


def _metrics(*, y_true: np.ndarray, proba: np.ndarray) -> dict[str, float]:
    y_true_i = np.asarray(y_true, dtype="int64")
    p = np.asarray(proba, dtype="float64")
    p = np.clip(p, 1e-9, 1 - 1e-9)
    pred = (p >= 0.5).astype("int64")
    out: dict[str, float] = {
        "accuracy": float(accuracy_score(y_true_i, pred)),
        "brier": float(brier_score_loss(y_true_i, p)),
        "logloss": float(log_loss(y_true_i, p, labels=[0, 1])),
        "pos_rate": float(np.mean(y_true_i)),
        "pred_pos_rate": float(np.mean(pred)),
    }
    try:
        if len(np.unique(y_true_i)) >= 2:
            out["auc"] = float(roc_auc_score(y_true_i, p))
    except Exception:
        pass
    return out


def _valid_metrics(*, y_true: np.ndarray, proba: np.ndarray) -> dict[str, float]:
    m = _metrics(y_true=y_true, proba=proba)
    out: dict[str, float] = {
        "valid_accuracy": float(m.get("accuracy", float("nan"))),
        "valid_brier": float(m.get("brier", float("nan"))),
        "valid_logloss": float(m.get("logloss", float("nan"))),
        "valid_pos_rate": float(m.get("pos_rate", float("nan"))),
        "valid_pred_pos_rate": float(m.get("pred_pos_rate", float("nan"))),
    }
    if "auc" in m:
        out["valid_auc"] = float(m.get("auc", float("nan")))
    return out


def _make_lgbm(*, args: argparse.Namespace, seed: int) -> LGBMClassifier:
    return LGBMClassifier(
        objective="binary",
        n_estimators=int(args.lgbm_n_estimators),
        learning_rate=float(args.lgbm_learning_rate),
        num_leaves=int(args.lgbm_num_leaves),
        max_depth=int(args.lgbm_max_depth),
        subsample=0.8,
        colsample_bytree=0.9,
        random_state=int(seed),
        n_jobs=-1,
    )


def _try_fit_sigmoid_calibration_model(
    *,
    X_train: Any,
    y_train: np.ndarray,
    args: argparse.Namespace,
    seed: int,
) -> tuple[Any | None, dict[str, Any]]:
    """
    使用 sklearn 现成的 CalibratedClassifierCV（sigmoid）做时间序列校准：
    - cv=TimeSeriesSplit：避免随机切分导致的未来信息泄漏
    - ensemble=False：训练集上最终只有一个 base estimator（更适合线上推理/模型体积更可控）

    返回：
    - model：成功则为 CalibratedClassifierCV，否则 None
    - meta：用于写入 model_info.json 的校准元信息
    """
    y = np.asarray(y_train, dtype="int64")
    n = int(len(y))
    meta: dict[str, Any] = {
        "method": "CalibratedClassifierCV",
        "calibration_method": "sigmoid",
        "ensemble": False,
        "cv": {"type": "TimeSeriesSplit"},
        "status": "skipped",
    }

    if n < 200:
        meta["reason"] = "too_few_rows"
        return None, meta
    if len(np.unique(y)) < 2:
        meta["reason"] = "single_class_train"
        return None, meta

    n_splits = 5
    meta["cv"]["n_splits"] = int(n_splits)

    try:
        tss = TimeSeriesSplit(n_splits=n_splits)
        base = _make_lgbm(args=args, seed=int(seed))
        model = CalibratedClassifierCV(estimator=base, method="sigmoid", cv=tss, ensemble=False)
        model.fit(X_train, y_train)
    except Exception as e:
        meta["status"] = "failed"
        meta["reason"] = f"calibration_failed: {type(e).__name__}"
        return None, meta

    meta = {
        "method": "CalibratedClassifierCV",
        "calibration_method": "sigmoid",
        "ensemble": False,
        "cv": {"type": "TimeSeriesSplit", "n_splits": int(n_splits)},
        "status": "ok",
    }
    return model, meta


def main() -> int:
    args = _parse_args()
    cfg = get_config()

    exchange = str(args.exchange or "").strip() or cfg.freqtrade_exchange
    timeframe = str(args.timeframe or "").strip()
    if not timeframe:
        raise ValueError("timeframe 不能为空")

    spec = _resolve_dataset_spec(pair=str(args.pair), exchange=exchange, timeframe=timeframe)
    feature_vars = _load_feature_vars(str(args.strategy_params), list(args.var or []))

    # 1) 构造 Qlib handler（底层用本仓库 pkl 数据源 + 因子引擎计算特征）
    loader = FreqtradePklDataLoader(
        data_root=cfg.qlib_data_dir,
        exchange=exchange,
        timeframe=timeframe,
        feature_set=str(args.feature_set or "ml_core").strip() or "ml_core",
        feature_vars=feature_vars,
        horizon=int(args.horizon),
        threshold=float(args.threshold),
        drop_na=True,
        label_name="LABEL0",
    )
    handler = DataHandler(
        instruments=[spec.symbol],
        start_time=None,
        end_time=None,
        data_loader=loader,
        init_data=True,
        fetch_orig=True,
    )

    raw = handler.fetch(col_set=DataHandler.CS_RAW)
    if raw is None or raw.empty:
        raise ValueError("未能从数据集中加载到任何样本：请先运行 convert_freqtrade_to_qlib.py 生成 pkl 数据。")

    dt_index = list(raw.index.get_level_values("datetime").unique())
    segments = _split_segments_from_index(dt_index, valid_pct=float(args.valid_pct))

    dataset = DatasetH(handler=handler, segments=segments)
    train_df = dataset.prepare("train", col_set=["feature", "label"], data_key=DataHandler.DK_R)
    valid_df = dataset.prepare("valid", col_set=["feature", "label"], data_key=DataHandler.DK_R)
    if train_df.empty or valid_df.empty:
        raise ValueError("train/valid 数据为空：请检查数据区间、horizon、rolling 窗口等。")

    # prepare() 返回的是 (datetime,instrument) multi-index，确保按时间排序，避免切分/校准出现“倒序泄漏”
    train_df = train_df.sort_index()
    valid_df = valid_df.sort_index()

    X_train = train_df["feature"]
    y_train = train_df["label"].iloc[:, 0].astype("int64").to_numpy()
    X_valid = valid_df["feature"]
    y_valid = valid_df["label"].iloc[:, 0].astype("int64").to_numpy()

    # 2) 训练模型（LightGBM binary）
    base_model = _make_lgbm(args=args, seed=int(args.seed))
    base_model.fit(X_train, y_train)

    base_valid_proba = base_model.predict_proba(X_valid)[:, 1]
    base_valid_metrics = _valid_metrics(y_true=y_valid, proba=base_valid_proba)

    # 2.1) 时间序列概率校准（TimeSeriesSplit + sigmoid），让 proba 更可用于“连续权重”
    cal_model, calibrator_meta = _try_fit_sigmoid_calibration_model(X_train=X_train, y_train=y_train, args=args, seed=int(args.seed))
    if cal_model is not None:
        cal_valid_proba = np.asarray(cal_model.predict_proba(X_valid)[:, 1], dtype="float64")
        model_to_export: Any = cal_model
    else:
        cal_valid_proba = np.asarray(base_valid_proba, dtype="float64")
        model_to_export = base_model

    cal_valid_metrics = _valid_metrics(y_true=y_valid, proba=cal_valid_proba)

    # 3) 导出（保持策略侧加载约定）
    model_version = str(args.model_version or "").strip() or cfg.model_version
    outdir = (
        Path(str(args.outdir)).expanduser()
        if str(args.outdir or "").strip()
        else (cfg.qlib_model_dir / model_version / exchange / timeframe / spec.symbol)
    ).resolve()
    outdir.mkdir(parents=True, exist_ok=True)

    # 漂移基线（仅基于训练集特征，避免混入验证集分布）
    baseline = build_feature_baseline(
        X_train,
        quantile_bins=10,
        metadata={
            "model_version": model_version,
            "exchange": exchange,
            "timeframe": timeframe,
            "pair": str(args.pair),
            "symbol": spec.symbol,
            "rows_train": int(len(X_train)),
            "rows_valid": int(len(X_valid)),
            "target": {"horizon": int(args.horizon), "threshold": float(args.threshold)},
            "feature_set": str(args.feature_set or "ml_core"),
            "feature_vars": feature_vars,
            "segments": {k: [str(v[0]), str(v[1])] for k, v in segments.items()},
            "seed": int(args.seed),
        },
    )

    dump(model_to_export, outdir / "model.pkl")
    (outdir / "features.json").write_text(
        json.dumps(
            {
                "features": list(X_train.columns),
                "target": {"horizon": int(args.horizon), "threshold": float(args.threshold)},
                "feature_spec": {"feature_set": str(args.feature_set or "ml_core"), "feature_vars": feature_vars, "version": 3},
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (outdir / "feature_baseline.json").write_text(json.dumps(baseline, ensure_ascii=False, indent=2), encoding="utf-8")
    (outdir / "model_info.json").write_text(
        json.dumps(
            {
                "version": model_version,
                "exchange": exchange,
                "timeframe": timeframe,
                "pair": str(args.pair),
                "symbol": spec.symbol,
                "rows_train": int(len(X_train)),
                "rows_valid": int(len(X_valid)),
                "segments": {k: [str(v[0]), str(v[1])] for k, v in segments.items()},
                "features": list(X_train.columns),
                "target": {"horizon": int(args.horizon), "threshold": float(args.threshold)},
                "feature_spec": {"feature_set": str(args.feature_set or "ml_core"), "feature_vars": feature_vars, "version": 3},
                "feature_baseline_file": "feature_baseline.json",
                "metrics": {"base": base_valid_metrics, "calibrated": cal_valid_metrics},
                "calibration": calibrator_meta,
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
    print(
        f"- base.valid_auc: {base_valid_metrics.get('valid_auc', float('nan')):.4f} | "
        f"cal.valid_auc: {cal_valid_metrics.get('valid_auc', float('nan')):.4f}"
    )
    print(
        f"- base.valid_brier: {base_valid_metrics.get('valid_brier', float('nan')):.6f} | "
        f"cal.valid_brier: {cal_valid_metrics.get('valid_brier', float('nan')):.6f}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
