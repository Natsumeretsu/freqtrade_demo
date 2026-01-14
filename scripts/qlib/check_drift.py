"""
check_drift.py - 概念漂移/数据质量快速体检（研究层）

用途：
- 对比“当前窗口”的特征分布 vs 训练时导出的 feature_baseline.json
- 输出 PSI / 均值漂移 / 缺失率 等指标，帮助你判断模型/因子是否走出适用域

用法示例：
  # 1) 先训练导出（会生成 feature_baseline.json）
  uv run python -X utf8 scripts/qlib/train_model.py --pair "BTC/USDT:USDT" --timeframe "4h"

  # 2) 再做漂移体检（默认窗口 500）
  uv run python -X utf8 scripts/qlib/check_drift.py --pair "BTC/USDT:USDT" --timeframe "4h" --window 500
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# 确保可导入 03_integration/trading_system（脚本以文件路径运行时，sys.path[0] 会变为 scripts/qlib）
_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "03_integration"))

from trading_system.domain.symbols import freqtrade_pair_to_symbol  # noqa: E402
from trading_system.infrastructure.config_loader import get_config  # noqa: E402
from trading_system.infrastructure.ml.drift import DriftThresholds, evaluate_feature_drift  # noqa: E402
from trading_system.infrastructure.ml.features import compute_features  # noqa: E402


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="对比当前窗口特征分布与训练基线，检测概念漂移。")
    p.add_argument("--pair", default="BTC/USDT:USDT", help="交易对（用于推导 symbol），例如 \"BTC/USDT:USDT\"。")
    p.add_argument("--exchange", default="", help="交易所名（默认从配置读取）。")
    p.add_argument("--timeframe", default="4h", help="时间周期（默认 4h）。")
    p.add_argument("--model-version", default="", help="模型版本号（默认读取 QLIB_MODEL_VERSION / v1）。")
    p.add_argument("--model-dir", default="", help="显式指定模型目录（优先级最高）。")
    p.add_argument("--datafile", default="", help="显式指定数据集 .pkl 路径（优先级最高）。")
    p.add_argument("--window", type=int, default=500, help="用于对比的最近窗口行数（默认 500）。")
    p.add_argument("--warmup", type=int, default=200, help="额外预热行数（用于滚动窗口特征计算，默认 200）。")
    p.add_argument("--out", default="", help="输出报告 JSON 路径（可选）。")

    # 阈值（经验值，可按资产/周期调参）
    p.add_argument("--psi-warn", type=float, default=0.30, help="PSI 警告阈值（默认 0.30）。")
    p.add_argument("--psi-crit", type=float, default=1.00, help="PSI 严重阈值（默认 1.00）。")
    p.add_argument("--mean-z-warn", type=float, default=3.0, help="均值漂移 z 分数警告阈值（默认 3.0）。")
    p.add_argument("--mean-z-crit", type=float, default=6.0, help="均值漂移 z 分数严重阈值（默认 6.0）。")
    p.add_argument("--missing-warn", type=float, default=0.05, help="缺失率警告阈值（默认 0.05）。")
    p.add_argument("--missing-crit", type=float, default=0.20, help="缺失率严重阈值（默认 0.20）。")
    return p.parse_args()


def _resolve_model_dir(*, cfg, model_dir: str, model_version: str, exchange: str, timeframe: str, symbol: str) -> Path:
    if str(model_dir or "").strip():
        p = Path(str(model_dir)).expanduser().resolve()
        if not p.is_dir():
            raise FileNotFoundError(f"模型目录不存在：{p.as_posix()}")
        return p

    v = str(model_version or "").strip() or cfg.model_version
    p = (cfg.qlib_model_dir / v / exchange / timeframe / symbol).resolve()
    if not p.is_dir():
        raise FileNotFoundError(
            "未找到模型目录，请先训练：\n"
            f"- 期望路径：{p.as_posix()}\n"
            "示例：uv run python -X utf8 scripts/qlib/train_model.py --pair \"BTC/USDT:USDT\" --timeframe \"4h\""
        )
    return p


def _resolve_datafile(*, cfg, datafile: str, exchange: str, timeframe: str, symbol: str) -> Path:
    if str(datafile or "").strip():
        p = Path(str(datafile)).expanduser().resolve()
        if not p.is_file():
            raise FileNotFoundError(f"未找到数据集：{p.as_posix()}")
        return p

    p = (cfg.qlib_data_dir / exchange / timeframe / f"{symbol}.pkl").resolve()
    if not p.is_file():
        raise FileNotFoundError(
            "未找到数据集，请先运行转换脚本：\n"
            f"- 期望路径：{p.as_posix()}\n"
            "示例：uv run python -X utf8 scripts/qlib/convert_freqtrade_to_qlib.py --timeframe 4h"
        )
    return p


def _load_features(model_dir: Path) -> list[str]:
    fpath = model_dir / "features.json"
    if not fpath.is_file():
        raise FileNotFoundError(f"未找到 features.json：{fpath.as_posix()}")

    data = json.loads(fpath.read_text(encoding="utf-8"))
    feats = data.get("features") or data.get("feature_columns") or []
    if not isinstance(feats, list) or not feats:
        raise ValueError("features.json 中未找到 features 列表")
    return [str(x).strip() for x in feats if str(x).strip()]


def _estimate_warmup(features: list[str]) -> int:
    """
    根据特征名粗略估计滚动窗口所需预热长度。

    说明：这里不是严格解析器，只用于避免因为历史不足导致整窗 NaN。
    """
    max_n = 0
    for name in features:
        # 约定：大多数窗口参数以 `_N` 结尾（ret_12/vol_12/skew_72/ema_50/...）
        parts = str(name).split("_")
        if not parts:
            continue
        try:
            n = int(parts[-1])
        except Exception:
            n = 0
        max_n = max(max_n, n)

    # MACD 默认 slow=26，ema_spread 默认 50
    return int(max(max_n, 60))


def main() -> int:
    args = _parse_args()
    cfg = get_config()

    exchange = str(args.exchange or "").strip() or cfg.freqtrade_exchange
    timeframe = str(args.timeframe or "").strip()
    if not timeframe:
        raise ValueError("timeframe 不能为空")

    symbol = freqtrade_pair_to_symbol(str(args.pair))
    if not symbol:
        raise ValueError("pair 无法解析为 symbol")

    model_dir = _resolve_model_dir(
        cfg=cfg,
        model_dir=str(args.model_dir),
        model_version=str(args.model_version),
        exchange=exchange,
        timeframe=timeframe,
        symbol=symbol,
    )
    datafile = _resolve_datafile(cfg=cfg, datafile=str(args.datafile), exchange=exchange, timeframe=timeframe, symbol=symbol)

    baseline_path = model_dir / "feature_baseline.json"
    if not baseline_path.is_file():
        raise FileNotFoundError(
            f"未找到训练基线：{baseline_path.as_posix()}\n"
            "提示：请使用新版训练脚本重新训练导出 feature_baseline.json。"
        )

    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    features = _load_features(model_dir)

    df = pd.read_pickle(datafile)
    if df is None or df.empty:
        raise ValueError("数据集为空")

    # 统一时间排序（避免窗口取样错位）
    work = df.copy()
    if "date" in work.columns:
        work["date"] = pd.to_datetime(work["date"], utc=True, errors="coerce")
        work = work.dropna(subset=["date"]).sort_values("date")

    window = int(args.window)
    if window <= 0:
        raise ValueError("window 必须为正整数")

    warmup = max(int(args.warmup), _estimate_warmup(features))
    take_n = int(window + warmup)
    if len(work) > take_n:
        work = work.iloc[-take_n:].copy()

    feats = compute_features(work, feature_cols=features)
    if feats is None or feats.empty:
        raise ValueError("特征计算结果为空：请检查数据列是否齐全（close/high/low/volume）")

    # 只对比最后 window 行（但特征计算基于 warmup 预热）
    X_window = feats[features].iloc[-window:].copy()
    valid_rows = int(len(X_window.dropna()))

    thresholds = DriftThresholds(
        psi_warn=float(args.psi_warn),
        psi_crit=float(args.psi_crit),
        mean_z_warn=float(args.mean_z_warn),
        mean_z_crit=float(args.mean_z_crit),
        missing_warn=float(args.missing_warn),
        missing_crit=float(args.missing_crit),
    )
    report = evaluate_feature_drift(X_window, baseline=baseline, thresholds=thresholds)

    # 人性化摘要：列出最可能的 bottleneck（PSI 最大/缺失率最大）
    rows = report.get("features") or {}
    items = []
    for name, r in rows.items():
        if not isinstance(r, dict):
            continue
        items.append(
            {
                "name": name,
                "status": r.get("status", ""),
                "psi": float(r.get("psi")) if r.get("psi") is not None else float("nan"),
                "missing_rate": float(r.get("missing_rate", 0.0)),
                "mean_z": float(r.get("mean_z")) if r.get("mean_z") is not None else float("nan"),
            }
        )

    def _sort_key(x: dict) -> tuple:
        psi = x.get("psi", float("nan"))
        psi2 = psi if np.isfinite(psi) else -1.0
        miss = x.get("missing_rate", 0.0)
        mz = x.get("mean_z", float("nan"))
        mz2 = abs(mz) if np.isfinite(mz) else 0.0
        return (miss, psi2, mz2)

    top = sorted(items, key=_sort_key, reverse=True)[:10]

    print("")
    print("=== 概念漂移体检（feature drift）===")
    print(f"- model_dir: {model_dir.as_posix()}")
    print(f"- baseline: {baseline_path.as_posix()}")
    print(f"- datafile: {datafile.as_posix()}")
    print(f"- timeframe: {timeframe}")
    print(f"- window: {window} (有效样本行数：{valid_rows})")
    print(f"- status: {report.get('status')}")

    # 与实盘自动风控（auto_risk）的“整体判定口径”对齐的摘要（可执行视角）
    try:
        drift_cfg = cfg.get("trading_system.auto_risk.drift", {}) or {}
        drift_cfg = drift_cfg if isinstance(drift_cfg, dict) else {}
        agg_cfg = drift_cfg.get("aggregate") or {}
        agg_cfg = agg_cfg if isinstance(agg_cfg, dict) else {}

        gate = drift_cfg.get("gate_features")
        if isinstance(gate, list) and gate:
            gate_features = [str(x).strip() for x in gate if str(x).strip()]
        else:
            gate_features = list(features)

        feat_reports = report.get("features") or {}
        if isinstance(feat_reports, dict):
            gate_features = [f for f in gate_features if f in feat_reports]

        total = 0
        warn_cnt = 0
        crit_cnt = 0
        missing_col = 0
        for name in gate_features:
            r = (feat_reports or {}).get(name) if isinstance(feat_reports, dict) else None
            if not isinstance(r, dict):
                continue
            st = str(r.get("status") or "").strip()
            if not st:
                continue

            if st == "missing_column":
                missing_col += 1
                total += 1
                continue
            if st == "warn":
                warn_cnt += 1
                total += 1
                continue
            if st == "crit":
                crit_cnt += 1
                total += 1
                continue
            if st == "ok":
                total += 1
                continue

        def _safe_int(v, default: int) -> int:
            try:
                n = int(v)
            except Exception:
                return int(default)
            return int(n) if n > 0 else int(default)

        def _safe_ratio(v, default: float) -> float:
            try:
                x = float(v)
            except Exception:
                return float(default)
            if not np.isfinite(x):
                return float(default)
            return float(max(0.0, min(1.0, x)))

        crit_min_count = _safe_int(agg_cfg.get("crit_min_count", 2), 2)
        warn_min_count = _safe_int(agg_cfg.get("warn_min_count", 1), 1)
        crit_min_ratio = _safe_ratio(agg_cfg.get("crit_min_ratio", 0.05), 0.05)
        warn_min_ratio = _safe_ratio(agg_cfg.get("warn_min_ratio", 0.05), 0.05)

        crit_required = int(max(crit_min_count, int(math.ceil(float(total) * float(crit_min_ratio))))) if total > 0 else 0
        warn_required = int(max(warn_min_count, int(math.ceil(float(total) * float(warn_min_ratio))))) if total > 0 else 0

        agg_status = "unknown"
        if total > 0:
            if missing_col > 0:
                agg_status = "crit"
            elif crit_cnt >= crit_required and crit_required > 0:
                agg_status = "crit"
            elif (crit_cnt + warn_cnt) >= warn_required and warn_required > 0:
                agg_status = "warn"
            else:
                agg_status = "ok"

        print(
            "- auto_risk_status: "
            f"{agg_status} (gate={len(gate_features)}, crit={crit_cnt}/{total}, warn={warn_cnt}/{total}, "
            f"missing_column={missing_col}, crit_required={crit_required}, warn_required={warn_required})"
        )
    except Exception:
        pass
    print("")
    print("Top 10 风险因子（按缺失率/PSI/均值漂移排序）：")
    for x in top:
        print(
            f"- {x['name']}: status={x['status']}, missing={x['missing_rate']:.3f}, psi={x['psi']:.3f}, |mean_z|={abs(x['mean_z']):.3f}"
        )

    if str(args.out or "").strip():
        out = Path(str(args.out)).expanduser().resolve()
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print("")
        print(f"已写入报告：{out.as_posix()}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
