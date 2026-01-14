from __future__ import annotations

"""
auto_risk_replay.py - 自动降风险闭环离线回放评估（阈值校准工具）

用途：
- 用历史研究数据（02_qlib_research/qlib_data/.../*.pkl）做“时间滚动回放”
- 将 auto_risk 的输出（warn/crit/禁新开/风险折扣）转换为可量化的统计摘要
- 用于校准 `04_shared/config/trading_system.yaml` 中 auto_risk 的阈值/窗口/频率

为什么需要它：
- 仅“能看到漂移/制度”不够，关键在于：
  - 是否误触太多（导致 0 trades / 过度保守）？
  - 是否触发太少（失去保护效果）？
  - crit 的持续时间分布是否合理（是否需要加/减 recover_ok_checks）？

注意：
- 本脚本默认不写出大量 event 文件（AUTO_RISK_PERSIST=false），避免回放产生海量 artifacts。
- 本脚本会在进程内强制启用 auto_risk（AUTO_RISK_ENABLED=true），仅影响本次运行。
"""

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd


_REPO_ROOT = Path(__file__).resolve().parents[2]


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="离线回放 auto_risk，输出触发率/连续 crit 时长/禁新开次数等统计。")

    p.add_argument("--pair", default="", help="单个交易对（例如 \"BTC/USDT:USDT\"）。")
    p.add_argument(
        "--pairs",
        nargs="*",
        default=None,
        help="交易对列表（留空则读取 04_shared/config/symbols.yaml 的 pairs）。",
    )
    p.add_argument("--exchange", default="", help="交易所名（默认从配置读取）。")
    p.add_argument("--timeframe", default="4h", help="时间周期（默认 4h）。")
    p.add_argument("--datafile", default="", help="显式指定数据集 .pkl（仅当回放单一 pair 时使用）。")

    p.add_argument(
        "--model-root",
        default="artifacts/auto_risk_replay/models",
        help="回放用的模型根目录（用于写入 feature_baseline.json 等临时产物，默认写到 artifacts/）。",
    )
    p.add_argument(
        "--model-version",
        default="replay_auto_risk",
        help="回放用的模型版本号（用于构造临时模型目录，默认 replay_auto_risk）。",
    )

    p.add_argument(
        "--feature-set",
        default="ml_core",
        help="用于漂移/制度评估的特征集（来自 04_shared/config/factors.yaml 的 factor_sets）。默认 ml_core。",
    )

    # baseline（训练分布）取样：默认跳过 warmup 后取 60%
    p.add_argument("--baseline-pct", type=float, default=0.60, help="baseline 取样占比（默认 0.60）。")
    p.add_argument("--baseline-rows", type=int, default=0, help="baseline 行数（>0 则覆盖 baseline-pct）。")

    # 回放范围
    p.add_argument("--start", default="", help="回放起始时间（ISO8601，例如 2022-01-01）。留空自动选择。")
    p.add_argument("--end", default="", help="回放结束时间（ISO8601）。留空表示到最后。")

    # 输出
    p.add_argument("--out", default="", help="输出 JSON 报告路径（可选）。默认写到 artifacts/auto_risk_replay/ 下。")
    p.add_argument("--persist", action="store_true", help="允许写出 auto_risk event 文件（默认关闭）。")
    p.add_argument("--side", choices=["long", "short", "both"], default="long", help="评估方向（默认 long）。")

    return p.parse_args()


def _estimate_warmup(features: list[str]) -> int:
    max_n = 0
    for name in features:
        parts = str(name).split("_")
        if not parts:
            continue
        try:
            n = int(parts[-1])
        except Exception:
            n = 0
        max_n = max(max_n, n)
    return int(max(max_n, 60))


def _parse_ts(s: str) -> pd.Timestamp | None:
    raw = str(s or "").strip()
    if not raw:
        return None
    ts = pd.to_datetime(raw, utc=True, errors="coerce")
    if ts is None or (isinstance(ts, pd.Timestamp) and pd.isna(ts)):
        return None
    return ts


def _default_report_path(*, symbol: str, timeframe: str) -> Path:
    root = (_REPO_ROOT / "artifacts" / "auto_risk_replay").resolve()
    root.mkdir(parents=True, exist_ok=True)
    stamp = pd.Timestamp.utcnow().strftime("%Y%m%d_%H%M%S")
    return (root / f"auto_risk_replay_{symbol}_{timeframe}_{stamp}.json").resolve()


@dataclass(frozen=True)
class _ReplaySummary:
    rows_total: int
    rows_replayed: int
    drift_counts: dict[str, int]
    regime_counts: dict[str, int]
    market_context_counts: dict[str, int]
    blocked_entries: int
    crit_streaks: list[int]
    mean_stake_scale: float
    mean_leverage_scale: float
    mean_market_context_scale: float


def _streaks(flags: list[bool]) -> list[int]:
    out: list[int] = []
    cur = 0
    for f in flags:
        if f:
            cur += 1
        else:
            if cur > 0:
                out.append(cur)
                cur = 0
    if cur > 0:
        out.append(cur)
    return out


def _summarize(
    *,
    decisions: list[dict],
    total_rows: int,
) -> _ReplaySummary:
    drift_counts: dict[str, int] = {}
    regime_counts: dict[str, int] = {}
    market_counts: dict[str, int] = {}
    blocked = 0
    stake_scales: list[float] = []
    lev_scales: list[float] = []
    market_scales: list[float] = []

    is_crit: list[bool] = []
    for d in decisions:
        drift = str(d.get("drift_status", "unknown"))
        regime = str(d.get("regime", "unknown"))
        market_status = str(d.get("market_context_status", "unknown"))
        allow = bool(d.get("allow_entry", True))

        drift_counts[drift] = int(drift_counts.get(drift, 0)) + 1
        regime_counts[regime] = int(regime_counts.get(regime, 0)) + 1
        market_counts[market_status] = int(market_counts.get(market_status, 0)) + 1
        if not allow:
            blocked += 1

        s = float(d.get("stake_scale", 1.0))
        l = float(d.get("leverage_scale", 1.0))
        m = float(d.get("market_context_scale", 1.0))
        if np.isfinite(s):
            stake_scales.append(float(s))
        if np.isfinite(l):
            lev_scales.append(float(l))
        if np.isfinite(m):
            market_scales.append(float(m))

        is_crit.append(drift == "crit")

    crit_streaks = _streaks(is_crit)

    def _mean(xs: list[float]) -> float:
        if not xs:
            return float("nan")
        return float(np.mean(np.asarray(xs, dtype="float64")))

    return _ReplaySummary(
        rows_total=int(total_rows),
        rows_replayed=int(len(decisions)),
        drift_counts=drift_counts,
        regime_counts=regime_counts,
        market_context_counts=market_counts,
        blocked_entries=int(blocked),
        crit_streaks=crit_streaks,
        mean_stake_scale=_mean(stake_scales),
        mean_leverage_scale=_mean(lev_scales),
        mean_market_context_scale=_mean(market_scales),
    )


def main() -> int:
    args = _parse_args()

    # 默认：启用 auto_risk，但不写海量事件文件（仅回放统计）
    os.environ["AUTO_RISK_ENABLED"] = "true"
    if not bool(args.persist):
        os.environ["AUTO_RISK_PERSIST"] = "false"

    # 若显式指定 exchange，则在初始化 get_config 前写入 env，确保路径/目录一致
    if str(args.exchange or "").strip():
        os.environ["FREQTRADE_EXCHANGE"] = str(args.exchange).strip()

    # 将回放的 baseline/model 产物写到 artifacts/（避免污染 02_qlib_research/models/）
    model_root = (_REPO_ROOT / Path(str(args.model_root))).resolve()
    model_root.mkdir(parents=True, exist_ok=True)
    os.environ["QLIB_MODEL_DIR"] = model_root.as_posix()
    os.environ["QLIB_MODEL_VERSION"] = str(args.model_version).strip() or "replay_auto_risk"

    # trading_system 模块需要从 03_integration 导入
    sys.path.insert(0, str(_REPO_ROOT / "03_integration"))

    # 延迟导入（避免在 import 阶段提前初始化全局 get_config）
    from trading_system.application.factor_sets import get_factor_templates, render_factor_names
    from trading_system.domain.symbols import freqtrade_pair_to_symbol
    from trading_system.infrastructure.auto_risk import AutoRiskService
    from trading_system.infrastructure.config_loader import get_config
    from trading_system.infrastructure.ml.drift import build_feature_baseline
    from trading_system.infrastructure.ml.features import compute_features

    cfg = get_config()

    exchange = str(args.exchange or "").strip() or cfg.freqtrade_exchange
    timeframe = str(args.timeframe or "").strip()
    if not timeframe:
        raise ValueError("timeframe 不能为空")

    pairs: list[str] = []
    if args.pairs is not None:
        pairs = [str(p).strip() for p in (args.pairs or []) if str(p).strip()]
    if not pairs and str(args.pair or "").strip():
        pairs = [str(args.pair).strip()]
    if not pairs:
        pairs = cfg.pairs()
    if not pairs:
        raise ValueError("pairs 为空：请传 --pair/--pairs 或配置 04_shared/config/symbols.yaml")

    if str(args.datafile or "").strip() and len(pairs) != 1:
        raise ValueError("--datafile 仅支持单个 pair 回放")

    templates = get_factor_templates(str(args.feature_set))
    features = render_factor_names(templates, {})
    if not features:
        raise ValueError(f"feature_set 为空或不存在：{args.feature_set}")

    # 统一确保含制度判断需要的列（auto_risk 内部会用）
    for need in ("ret_12", "vol_12", "ema_spread"):
        if need not in features:
            features.append(need)

    warmup_est = _estimate_warmup(features)

    start_ts = _parse_ts(str(args.start))
    end_ts = _parse_ts(str(args.end))

    sides = ["long", "short"] if str(args.side).lower() == "both" else [str(args.side).lower()]

    # 伪造一个最小“模型加载器”，避免依赖真实 model.pkl（回放只需要 baseline + 特征列名 + regime 阈值）
    class _StubLoader:
        def __init__(self, *, feature_list: list[str], model_info: dict) -> None:
            self.features = list(feature_list)
            self.model_info = dict(model_info)

    class _StubModelCache:
        def __init__(self, loader: _StubLoader) -> None:
            self._loader = loader

        def get(self, model_dir: str | Path) -> _StubLoader:
            return self._loader

    # 使用一个 service 实例（内部会按 side 缓存状态）
    # 注意：这里使用 StubModelCache，确保 drift 模块可运行但不要求 model.pkl。
    stub_loader = _StubLoader(feature_list=features, model_info={"feature_baseline_file": "feature_baseline.json"})
    service = AutoRiskService(cfg=cfg, model_cache=_StubModelCache(stub_loader))

    # 记录本次回放实际使用的 auto_risk 配置（便于跨设备复现结论）
    auto_risk_cfg = cfg.get("trading_system.auto_risk", {}) or {}
    auto_risk_cfg = auto_risk_cfg if isinstance(auto_risk_cfg, dict) else {}
    drift_cfg_snapshot = cfg.get("trading_system.auto_risk.drift", {}) or {}
    drift_cfg_snapshot = drift_cfg_snapshot if isinstance(drift_cfg_snapshot, dict) else {}
    regime_cfg_snapshot = cfg.get("trading_system.auto_risk.regime", {}) or {}
    regime_cfg_snapshot = regime_cfg_snapshot if isinstance(regime_cfg_snapshot, dict) else {}
    market_cfg_snapshot = cfg.get("trading_system.auto_risk.market_context", {}) or {}
    market_cfg_snapshot = market_cfg_snapshot if isinstance(market_cfg_snapshot, dict) else {}

    reports: dict[str, Any] = {
        "version": 1,
        "generated_at": pd.Timestamp.utcnow().isoformat(),
        "exchange": exchange,
        "timeframe": timeframe,
        "pairs": pairs,
        "feature_set": str(args.feature_set),
        "features": list(features),
        "auto_risk_config": {
            "auto_risk": auto_risk_cfg,
            "drift": drift_cfg_snapshot,
            "regime": regime_cfg_snapshot,
            "market_context": market_cfg_snapshot,
        },
        "warmup_est": int(warmup_est),
        "baseline": {"pct": float(args.baseline_pct), "rows": int(args.baseline_rows)},
        "range": {"start": str(start_ts) if start_ts is not None else "", "end": str(end_ts) if end_ts is not None else ""},
        "by_pair": {},
    }

    t0 = time.time()

    # market_context 数据集缓存：key=market_symbol（避免每个 pair 重复读盘）
    market_cache: dict[str, pd.DataFrame] = {}

    for pair in pairs:
        symbol = freqtrade_pair_to_symbol(pair)
        if not symbol:
            continue

        if str(args.datafile or "").strip():
            datafile = Path(str(args.datafile)).expanduser().resolve()
        else:
            datafile = (cfg.qlib_data_dir / exchange / timeframe / f"{symbol}.pkl").resolve()
        if not datafile.is_file():
            reports["by_pair"][pair] = {"error": f"未找到数据集：{datafile.as_posix()}"}
            continue

        df = pd.read_pickle(datafile)
        if df is None or df.empty:
            reports["by_pair"][pair] = {"error": "数据集为空"}
            continue

        if "date" not in df.columns:
            reports["by_pair"][pair] = {"error": "数据集缺少 date 列"}
            continue

        work = df.copy()
        work["date"] = pd.to_datetime(work["date"], utc=True, errors="coerce")
        work = work.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)

        # 裁剪回放时间范围（先裁剪再做 baseline/特征计算，避免不必要开销）
        if start_ts is not None:
            work = work.loc[work["date"] >= start_ts].copy()
        if end_ts is not None:
            work = work.loc[work["date"] <= end_ts].copy()
        work = work.reset_index(drop=True)

        if work.empty:
            reports["by_pair"][pair] = {"error": "按 start/end 裁剪后数据为空"}
            continue

        # market_context：尝试加载市场代理（默认 BTC）数据（用于 corr/β 断裂的软缩放）
        market_df: pd.DataFrame | None = None
        market_dates: np.ndarray | None = None
        market_pair_eff = ""
        if bool(market_cfg_snapshot.get("enabled", False)):
            raw_market_pair = str(market_cfg_snapshot.get("market_pair", "BTC/USDT")).strip()
            if raw_market_pair:
                if ":" in str(pair) and ":" not in raw_market_pair:
                    suffix = str(pair).split(":", 1)[1].strip()
                    market_pair_eff = f"{raw_market_pair}:{suffix}" if suffix else raw_market_pair
                else:
                    market_pair_eff = raw_market_pair

            if market_pair_eff and market_pair_eff != str(pair):
                market_symbol = freqtrade_pair_to_symbol(market_pair_eff)
                if market_symbol:
                    if market_symbol in market_cache:
                        market_df = market_cache[market_symbol]
                    else:
                        m_file = (cfg.qlib_data_dir / exchange / timeframe / f"{market_symbol}.pkl").resolve()
                        if m_file.is_file():
                            m_raw = pd.read_pickle(m_file)
                            if m_raw is not None and not m_raw.empty and "date" in m_raw.columns:
                                m_work = m_raw.copy()
                                m_work["date"] = pd.to_datetime(m_work["date"], utc=True, errors="coerce")
                                m_work = m_work.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
                                # 同步回放时间范围裁剪，保证对齐
                                if start_ts is not None:
                                    m_work = m_work.loc[m_work["date"] >= start_ts].copy()
                                if end_ts is not None:
                                    m_work = m_work.loc[m_work["date"] <= end_ts].copy()
                                m_work = m_work.reset_index(drop=True)
                                market_cache[market_symbol] = m_work
                                market_df = m_work
                    if market_df is not None and not market_df.empty:
                        # numpy 不支持 tz-aware datetime64；统一转换为“UTC tz-naive”的 datetime64[ns]
                        market_dates = (
                            pd.to_datetime(market_df["date"], utc=True, errors="coerce")
                            .dt.tz_localize(None)
                            .to_numpy(dtype="datetime64[ns]")
                        )

        # 先全量算一次特征（回放中复用，避免每根K线重复计算）
        feats = compute_features(work, feature_cols=features)
        if feats is None or feats.empty:
            reports["by_pair"][pair] = {"error": "特征计算结果为空"}
            continue

        enriched = work.copy()
        for c in feats.columns:
            enriched[c] = feats[c]

        # baseline 取样：默认从 warmup_est 之后开始
        usable = int(len(enriched) - warmup_est)
        if usable <= 0:
            reports["by_pair"][pair] = {"error": f"数据长度不足（len={len(enriched)}, warmup={warmup_est}）"}
            continue

        baseline_rows = int(args.baseline_rows) if int(args.baseline_rows) > 0 else int(usable * float(args.baseline_pct))
        baseline_rows = int(max(200, baseline_rows))
        baseline_start = int(warmup_est)
        baseline_end = int(min(len(enriched), baseline_start + baseline_rows))

        if baseline_end - baseline_start < 200:
            reports["by_pair"][pair] = {"error": f"baseline 样本不足：{baseline_end - baseline_start} 行"}
            continue

        baseline_X = enriched[features].iloc[baseline_start:baseline_end].copy()
        baseline = build_feature_baseline(
            baseline_X,
            quantile_bins=10,
            metadata={
                "pair": pair,
                "symbol": symbol,
                "exchange": exchange,
                "timeframe": timeframe,
                "baseline_start": str(enriched['date'].iloc[baseline_start]),
                "baseline_end": str(enriched['date'].iloc[baseline_end - 1]),
                "baseline_rows": int(baseline_end - baseline_start),
                "feature_set": str(args.feature_set),
            },
        )

        # 将 baseline 写到 auto_risk 期望的路径，确保 drift 真正可执行
        model_dir = service.model_dir(pair=pair, timeframe=timeframe)
        model_dir.mkdir(parents=True, exist_ok=True)
        (model_dir / "feature_baseline.json").write_text(
            json.dumps(baseline, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        # regime 阈值：按 baseline 段分位数估计（避免 look-ahead）
        r = enriched["ret_12"].iloc[baseline_start:baseline_end].astype("float64").replace([np.inf, -np.inf], np.nan)
        v = enriched["vol_12"].iloc[baseline_start:baseline_end].astype("float64").replace([np.inf, -np.inf], np.nan)
        s = enriched["ema_spread"].iloc[baseline_start:baseline_end].astype("float64").replace([np.inf, -np.inf], np.nan)
        strength = (r.abs() / v.replace(0, np.nan)).replace([np.inf, -np.inf], np.nan)

        def _q(series: pd.Series, q: float) -> float:
            z = series.dropna()
            if z.empty:
                return float("nan")
            return float(z.quantile(q))

        regime_thresholds = {
            "vol_12_q90": _q(v, 0.90),
            "ema_spread_abs_q70": _q(s.abs(), 0.70),
            "trend_strength_q70": _q(strength, 0.70),
        }
        # 注入到 stub_loader.model_info，确保 auto_risk 使用训练侧阈值（避免 look-ahead）
        stub_loader.model_info["regime_evaluation"] = {"definition": {"thresholds": regime_thresholds}}

        # 回放起点：确保窗口完全在 baseline 之后（避免“训练数据混入窗口”导致漂移被稀释）
        drift_cfg = cfg.get("trading_system.auto_risk.drift", {}) or {}
        window = int((drift_cfg.get("window") or 500))
        warmup_cfg = int((drift_cfg.get("warmup") or 200))
        take_n = int(window + max(warmup_cfg, warmup_est))

        # market_context 也需要更长窗口（reference_window），确保 slice 覆盖
        if bool(market_cfg_snapshot.get("enabled", False)):
            mc_window = int(market_cfg_snapshot.get("window") or 72)
            mc_ref = int(market_cfg_snapshot.get("reference_window") or market_cfg_snapshot.get("ref_window") or 500)
            mc_need = int(max(mc_window, mc_ref) + 5)
            take_n = int(max(take_n, mc_need))

        replay_start = int(baseline_end + window)
        if replay_start >= len(enriched):
            reports["by_pair"][pair] = {"error": "数据长度不足：baseline_end + window 已超过数据末尾"}
            continue

        # 本次回放“整体漂移判定”实际参与的特征列（与 auto_risk.py 的 gate_features 语义保持一致）
        gate = drift_cfg.get("gate_features")
        if isinstance(gate, list) and gate:
            gate_list = [str(x).strip() for x in gate if str(x).strip()]
            gate_set = set(gate_list)
            drift_eval_features = [c for c in features if c in gate_set]
            if not drift_eval_features:
                drift_eval_features = list(features)
        else:
            drift_eval_features = list(features)

        by_side: dict[str, Any] = {}
        for side in sides:
            decisions: list[dict] = []
            for i in range(replay_start, len(enriched)):
                slice_start = int(max(0, i - take_n + 1))
                chunk = enriched.iloc[slice_start : i + 1]

                candle_ts = pd.to_datetime(enriched["date"].iloc[i], utc=True, errors="coerce")
                if candle_ts is None or (isinstance(candle_ts, pd.Timestamp) and pd.isna(candle_ts)):
                    continue

                market_chunk: pd.DataFrame | None = None
                if market_df is not None and market_dates is not None:
                    candle_key = candle_ts.tz_localize(None).to_datetime64()
                    mi = int(np.searchsorted(market_dates, candle_key, side="right") - 1)
                    if mi >= 0:
                        m_start = int(max(0, mi - take_n + 1))
                        market_chunk = market_df.iloc[m_start : mi + 1]

                d = service.decision_with_df(
                    df=chunk,
                    market_df=market_chunk,
                    pair=pair,
                    timeframe=timeframe,
                    current_time=candle_ts.to_pydatetime(),
                    side=side,
                )
                decisions.append(
                    {
                        "date": str(candle_ts),
                        "allow_entry": bool(d.allow_entry),
                        "stake_scale": float(d.stake_scale),
                        "leverage_scale": float(d.leverage_scale),
                        "regime": str(d.regime),
                        "drift_status": str(d.drift_status),
                        "market_context_status": str(getattr(d, "market_context_status", "unknown")),
                        "market_context_scale": float(getattr(d, "market_context_scale", 1.0)),
                    }
                )

            summary = _summarize(decisions=decisions, total_rows=len(enriched))
            by_side[side] = {
                "rows_total": summary.rows_total,
                "rows_replayed": summary.rows_replayed,
                "baseline_range": {
                    "start": str(enriched["date"].iloc[baseline_start]),
                    "end": str(enriched["date"].iloc[baseline_end - 1]),
                    "rows": int(baseline_end - baseline_start),
                },
                "replay_range": {"start": str(enriched["date"].iloc[replay_start]), "end": str(enriched["date"].iloc[-1])},
                "drift_counts": summary.drift_counts,
                "regime_counts": summary.regime_counts,
                "market_context_counts": summary.market_context_counts,
                "blocked_entries": summary.blocked_entries,
                "crit_streaks": summary.crit_streaks,
                "crit_streak_max": int(max(summary.crit_streaks) if summary.crit_streaks else 0),
                "crit_streak_p95": int(np.percentile(summary.crit_streaks, 95) if summary.crit_streaks else 0),
                "mean_stake_scale": float(summary.mean_stake_scale),
                "mean_leverage_scale": float(summary.mean_leverage_scale),
                "mean_market_context_scale": float(summary.mean_market_context_scale),
                "regime_thresholds": regime_thresholds,
            }

        reports["by_pair"][pair] = {
            "datafile": datafile.as_posix(),
            "rows_total": int(len(enriched)),
            "features": list(features),
            "drift_eval_features": list(drift_eval_features),
            "by_side": by_side,
        }

        print("")
        print(f"=== auto_risk 回放摘要：{pair} ({symbol}) {exchange}/{timeframe} ===")
        for side, r in by_side.items():
            drift_counts = r.get("drift_counts", {}) or {}
            market_counts = r.get("market_context_counts", {}) or {}
            blocked_entries = int(r.get("blocked_entries", 0))
            rows_replayed = int(r.get("rows_replayed", 0))
            crit_max = int(r.get("crit_streak_max", 0))
            crit_p95 = int(r.get("crit_streak_p95", 0))
            warn = int(drift_counts.get("warn", 0))
            crit = int(drift_counts.get("crit", 0))
            ok = int(drift_counts.get("ok", 0))
            unk = int(drift_counts.get("unknown", 0))
            denom = float(rows_replayed) if rows_replayed > 0 else 1.0

            print(f"- side={side}: rows={rows_replayed}")
            print(
                "  drift_rate: "
                f"ok={ok/denom:.1%}, warn={warn/denom:.1%}, crit={crit/denom:.1%}, unknown={unk/denom:.1%}"
            )
            if bool(market_cfg_snapshot.get("enabled", False)):
                m_ok = int(market_counts.get("ok", 0))
                m_warn = int(market_counts.get("warn", 0))
                m_crit = int(market_counts.get("crit", 0))
                m_unk = int(market_counts.get("unknown", 0)) + int(market_counts.get("disabled", 0))
                m_mean = float(r.get("mean_market_context_scale", float("nan")))
                print(
                    "  market_context_rate: "
                    f"ok={m_ok/denom:.1%}, warn={m_warn/denom:.1%}, crit={m_crit/denom:.1%}, unknown={m_unk/denom:.1%}"
                    f"  (mean_scale={m_mean:.3f})"
                )
            print(f"  blocked_entries_rate: {blocked_entries/denom:.1%}  (count={blocked_entries})")
            print(f"  crit_streak: max={crit_max} candles, p95={crit_p95} candles")

    dt = time.time() - t0
    reports["elapsed_sec"] = float(dt)

    out_path = Path(str(args.out)).expanduser().resolve() if str(args.out or "").strip() else _default_report_path(symbol="multi", timeframe=timeframe)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(reports, ensure_ascii=False, indent=2), encoding="utf-8")

    print("")
    print(f"已写入报告：{out_path.as_posix()}")
    print(f"耗时：{dt:.2f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
