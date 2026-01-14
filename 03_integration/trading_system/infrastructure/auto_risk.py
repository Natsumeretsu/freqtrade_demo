from __future__ import annotations

"""
auto_risk.py - 自动降风险闭环（制度层 + 概念漂移）

目标：把“可观测”升级为“可执行”的风控反馈闭环：

1) 制度层（market regime）
   - 用 OHLCV 衍生特征把市场状态归类为：bull_trend / bear_trend / range / crisis / unknown
   - 将 regime 映射为仓位/杠杆风险折扣（软过滤），并可选在 crisis 时做硬过滤

2) 概念漂移/数据质量（feature drift）
   - 对比“最近窗口”的特征分布 vs 训练导出的 feature_baseline.json
   - 输出 ok / warn / crit，并映射为：
     - warn：降仓（软过滤）
     - crit：禁止新开仓（硬过滤）+ 强降仓（软过滤兜底）
    - 提供简单的恢复滞回（crit 后需要连续 ok 才恢复开仓），避免状态抖动

3) 市场代理/外溢风险（market context）
   - 以 BTC 作为市场代理（CMKT proxy）
   - 监控 BTC ↔ pair 的相关性/β 断裂，并做“软缩放”（仅影响 stake/leverage，不新增禁新开）

说明：
- 本模块不直接依赖 freqtrade 包，仅通过 dp 的 duck-typing 获取 dataframe。
- 风控动作仅能影响“新开仓”的 stake/leverage；无法改变已开的仓位（交易系统通用限制）。
"""

import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from trading_system.domain.symbols import freqtrade_pair_to_symbol
from trading_system.infrastructure.config_loader import ConfigManager, get_config
from trading_system.infrastructure.freqtrade_data import (
    get_analyzed_dataframe_upto_time,
    get_last_candle_timestamp,
    get_pair_dataframe_upto_time,
)
from trading_system.infrastructure.ml.drift import DriftThresholds, evaluate_feature_drift
from trading_system.infrastructure.ml.features import compute_features
from trading_system.infrastructure.ml.model_loader import ModelCache


def _parse_bool(v: Any, *, default: bool = False) -> bool:
    if v is None:
        return bool(default)
    if isinstance(v, bool):
        return bool(v)
    s = str(v).strip().lower()
    if s in {"1", "true", "yes", "y", "on"}:
        return True
    if s in {"0", "false", "no", "n", "off"}:
        return False
    return bool(default)


def _clamp01(x: float, *, default: float = 1.0) -> float:
    try:
        v = float(x)
    except Exception:
        return float(default)
    if not np.isfinite(v):
        return float(default)
    return float(max(0.0, min(1.0, v)))


def _safe_int(x: Any, *, default: int) -> int:
    try:
        v = int(x)
    except Exception:
        return int(default)
    return int(v) if v > 0 else int(default)


def _safe_float(x: Any, *, default: float) -> float:
    try:
        v = float(x)
    except Exception:
        return float(default)
    return float(v) if np.isfinite(v) else float(default)


def _estimate_warmup(features: list[str]) -> int:
    """
    根据特征名粗略估计滚动窗口所需预热长度。

    约定：窗口参数通常以 `_N` 结尾（ret_12 / vol_12 / skew_72 / volume_z_72 ...）。
    """
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


def _normalize_market_pair(*, market_pair: str, pair: str) -> str:
    """
    让 market_pair 尽量与当前 pair 的“合约后缀”一致。

    例：pair="ETH/USDT:USDT"，market_pair="BTC/USDT" -> "BTC/USDT:USDT"
    """
    mp = str(market_pair or "").strip()
    if not mp:
        return ""
    if ":" in mp:
        return mp
    raw_pair = str(pair or "").strip()
    if ":" not in raw_pair:
        return mp
    suffix = raw_pair.split(":", 1)[1].strip()
    return f"{mp}:{suffix}" if suffix else mp


def _aligned_returns(*, asset_df: pd.DataFrame, market_df: pd.DataFrame) -> pd.DataFrame | None:
    """
    对齐两者的收益序列，返回包含 date/asset_ret/market_ret 的 DataFrame。

    - 需要两者都包含：date/close
    - 会自动 dropna/inf
    """
    if asset_df is None or asset_df.empty or market_df is None or market_df.empty:
        return None
    if "date" not in asset_df.columns or "close" not in asset_df.columns:
        return None
    if "date" not in market_df.columns or "close" not in market_df.columns:
        return None

    a = asset_df[["date", "close"]].copy()
    m = market_df[["date", "close"]].copy()

    a_close = a["close"].astype("float64").replace([np.inf, -np.inf], np.nan)
    m_close = m["close"].astype("float64").replace([np.inf, -np.inf], np.nan)

    a["asset_ret"] = a_close.pct_change()
    m["market_ret"] = m_close.pct_change()

    out = pd.merge(a[["date", "asset_ret"]], m[["date", "market_ret"]], on="date", how="inner")
    out = out.replace([np.inf, -np.inf], np.nan).dropna()
    return None if out.empty else out


def _delta_score(*, delta: float, warn: float, crit: float) -> float:
    """
    将任意“偏离量 delta”映射为 0~1 的风险分数。

    - delta <= warn => 0
    - delta >= crit => 1
    - 其余线性插值
    """
    if not (np.isfinite(delta) and np.isfinite(warn) and np.isfinite(crit)):
        return 0.0
    warn_v = float(max(0.0, warn))
    crit_v = float(max(warn_v + 1e-12, crit))
    if float(delta) <= warn_v:
        return 0.0
    if float(delta) >= crit_v:
        return 1.0
    return float(max(0.0, min(1.0, (float(delta) - warn_v) / (crit_v - warn_v))))


def _score_level(score: float) -> str:
    if not np.isfinite(score) or score < 0:
        return "unknown"
    if score <= 0:
        return "ok"
    if score >= 1:
        return "crit"
    return "warn"


def _beta(*, y: pd.Series, x: pd.Series) -> float:
    var = float(x.var(ddof=1))
    if not np.isfinite(var) or var <= 0:
        return float("nan")
    cov = float(y.cov(x))
    if not np.isfinite(cov):
        return float("nan")
    return float(cov / var)


def _compute_market_context(
    *,
    asset_df: pd.DataFrame,
    market_df: pd.DataFrame,
    cfg: dict[str, Any],
    pair: str,
    market_pair: str,
) -> tuple[str, float, dict[str, Any] | None, list[str]]:
    """
    基于 market_pair（默认 BTC）评估“外溢/传染风险”并输出软缩放。

    设计目标：尽量降低误触（fail-open），并把关键数值落盘用于复盘/校准。
    """
    window = _safe_int(cfg.get("window", 72), default=72)
    ref_window = _safe_int(cfg.get("reference_window", cfg.get("ref_window", 500)), default=500)
    ref_window = int(max(ref_window, window))
    min_periods = _safe_int(cfg.get("min_periods", min(50, window)), default=min(50, window))
    min_scale = _clamp01(_safe_float(cfg.get("min_scale", 0.85), default=0.85), default=0.85)

    corr_warn = _safe_float(cfg.get("corr_delta_warn", 0.25), default=0.25)
    corr_crit = _safe_float(cfg.get("corr_delta_crit", 0.50), default=0.50)
    beta_warn = _safe_float(cfg.get("beta_delta_warn", 0.50), default=0.50)
    beta_crit = _safe_float(cfg.get("beta_delta_crit", 1.00), default=1.00)

    aligned = _aligned_returns(asset_df=asset_df, market_df=market_df)
    if aligned is None or aligned.empty:
        return "unknown", 1.0, {"status": "unknown", "error": "aligned_returns_empty", "pair": pair, "market_pair": market_pair}, [
            "market_context_no_overlap",
        ]

    aligned = aligned.tail(ref_window).copy()
    if int(len(aligned)) < int(min_periods):
        return (
            "unknown",
            1.0,
            {
                "status": "unknown",
                "error": "insufficient_rows",
                "pair": pair,
                "market_pair": market_pair,
                "rows": int(len(aligned)),
                "min_periods": int(min_periods),
            },
            ["market_context_insufficient_data"],
        )

    short = aligned.tail(window)
    if int(len(short)) < int(min_periods):
        return (
            "unknown",
            1.0,
            {
                "status": "unknown",
                "error": "insufficient_short_window",
                "pair": pair,
                "market_pair": market_pair,
                "rows": int(len(aligned)),
                "short_rows": int(len(short)),
                "min_periods": int(min_periods),
            },
            ["market_context_insufficient_data"],
        )

    x_long = aligned["market_ret"].astype("float64")
    y_long = aligned["asset_ret"].astype("float64")
    x_short = short["market_ret"].astype("float64")
    y_short = short["asset_ret"].astype("float64")

    corr_long = float(y_long.corr(x_long))
    corr_short = float(y_short.corr(x_short))
    beta_long = float(_beta(y=y_long, x=x_long))
    beta_short = float(_beta(y=y_short, x=x_short))

    if not (np.isfinite(corr_long) and np.isfinite(corr_short) and np.isfinite(beta_long) and np.isfinite(beta_short)):
        return (
            "unknown",
            1.0,
            {
                "status": "unknown",
                "error": "invalid_metrics",
                "pair": pair,
                "market_pair": market_pair,
                "corr": {"short": corr_short, "long": corr_long},
                "beta": {"short": beta_short, "long": beta_long},
                "rows": int(len(aligned)),
                "short_rows": int(len(short)),
            },
            ["market_context_invalid_metrics"],
        )

    corr_delta = float(abs(corr_short - corr_long))
    beta_delta = float(abs(beta_short - beta_long))

    corr_score = _delta_score(delta=corr_delta, warn=corr_warn, crit=corr_crit)
    beta_score = _delta_score(delta=beta_delta, warn=beta_warn, crit=beta_crit)
    score = float(max(corr_score, beta_score))

    level = _score_level(score)
    scale = float(1.0 - float(score) * float(1.0 - float(min_scale)))
    scale = _clamp01(scale, default=1.0)

    reasons: list[str] = []
    corr_level = _score_level(corr_score)
    beta_level = _score_level(beta_score)
    if corr_level in {"warn", "crit"}:
        reasons.append(f"market_context_corr_{corr_level}")
    if beta_level in {"warn", "crit"}:
        reasons.append(f"market_context_beta_{beta_level}")
    if level in {"warn", "crit"}:
        reasons.append(f"market_context_{level}")

    mkt_vol = float(x_short.std(ddof=1))
    mkt_ret_sum = float(x_short.sum())
    asset_ret_sum = float(y_short.sum())

    report: dict[str, Any] = {
        "status": str(level),
        "scale": float(scale),
        "pair": str(pair),
        "market_pair": str(market_pair),
        "window": int(window),
        "reference_window": int(ref_window),
        "min_periods": int(min_periods),
        "rows": int(len(aligned)),
        "short_rows": int(len(short)),
        "market": {"ret_sum": float(mkt_ret_sum), "vol": float(mkt_vol)},
        "asset": {"ret_sum": float(asset_ret_sum)},
        "corr": {
            "short": float(corr_short),
            "long": float(corr_long),
            "delta": float(corr_delta),
            "warn": float(corr_warn),
            "crit": float(corr_crit),
            "score": float(corr_score),
        },
        "beta": {
            "short": float(beta_short),
            "long": float(beta_long),
            "delta": float(beta_delta),
            "warn": float(beta_warn),
            "crit": float(beta_crit),
            "score": float(beta_score),
        },
    }

    return str(level), float(scale), report, reasons


def _drift_feature_counts(feature_reports: dict[str, Any]) -> dict[str, int]:
    total = 0
    warn = 0
    crit = 0
    missing_column = 0
    other = 0

    for _, r in feature_reports.items():
        if not isinstance(r, dict):
            continue
        status = str(r.get("status") or "").strip()
        if not status:
            continue

        if status == "missing_column":
            missing_column += 1
            total += 1
            continue

        if status == "warn":
            warn += 1
            total += 1
            continue

        if status == "crit":
            crit += 1
            total += 1
            continue

        if status == "ok":
            total += 1
            continue

        other += 1

    return {
        "total": int(total),
        "warn": int(warn),
        "crit": int(crit),
        "missing_column": int(missing_column),
        "other": int(other),
    }


def _aggregate_drift_status(
    drift_report: dict[str, Any],
    *,
    agg_cfg: dict[str, Any],
) -> tuple[str, dict[str, int]]:
    """
    将“逐特征漂移报告”聚合为整体状态（ok/warn/crit）。

    设计动机：
    - 逐特征的“最坏值聚合”（any-crit => crit）在加密市场上过于敏感：
      单一噪声特征（例如趋势价差）就可能让整体长期处于 crit。
    - 实盘风控更需要“可执行”的信号：用“crit 特征占比/数量”做整体判定，
      让系统更稳健，避免频繁误触硬禁开仓。

    聚合规则：
    - 只要出现 missing_column：整体直接 crit（schema 不一致）
    - 否则：
      - crit：crit_features >= max(crit_min_count, ceil(total * crit_min_ratio))
      - warn：(warn+crit) >= max(warn_min_count, ceil(total * warn_min_ratio))
      - 否则 ok
    """
    fallback = str((drift_report or {}).get("status") or "unknown")
    feats = (drift_report or {}).get("features")
    if not isinstance(feats, dict) or not feats:
        return fallback, {"total": 0, "warn": 0, "crit": 0, "missing_column": 0, "other": 0}

    counts = _drift_feature_counts(feats)
    total = int(counts.get("total", 0))
    if int(counts.get("missing_column", 0)) > 0:
        return "crit", counts
    if total <= 0:
        return fallback, counts

    crit_min_count = _safe_int(agg_cfg.get("crit_min_count", 2), default=2)
    warn_min_count = _safe_int(agg_cfg.get("warn_min_count", 2), default=2)
    crit_min_ratio = _clamp01(_safe_float(agg_cfg.get("crit_min_ratio", 0.05), default=0.05), default=0.05)
    warn_min_ratio = _clamp01(_safe_float(agg_cfg.get("warn_min_ratio", 0.05), default=0.05), default=0.05)

    crit_required = int(max(crit_min_count, int(np.ceil(float(total) * float(crit_min_ratio)))))
    warn_required = int(max(warn_min_count, int(np.ceil(float(total) * float(warn_min_ratio)))))

    crit_cnt = int(counts.get("crit", 0))
    warn_cnt = int(counts.get("warn", 0))

    if crit_cnt >= crit_required:
        return "crit", counts
    if (crit_cnt + warn_cnt) >= warn_required:
        return "warn", counts
    return "ok", counts


def _classify_regime(
    *,
    ret12: float | None,
    vol12: float | None,
    ema_spread: float | None,
    thresholds: dict[str, float],
) -> str:
    """
    轻量制度划分（与 scripts/qlib/train_model.py 的评估口径对齐）。

    - crisis：高波动（vol_12 >= q90）
    - bull_trend / bear_trend：价差结构足够强 + 趋势强度足够高
    - 其余：range
    """
    if ret12 is None or vol12 is None or ema_spread is None:
        return "unknown"
    if not (np.isfinite(ret12) and np.isfinite(vol12) and np.isfinite(ema_spread)):
        return "unknown"
    if float(vol12) <= 0:
        return "unknown"

    vol_q90 = float(thresholds.get("vol_12_q90", float("nan")))
    spread_abs_q70 = float(thresholds.get("ema_spread_abs_q70", float("nan")))
    strength_q70 = float(thresholds.get("trend_strength_q70", float("nan")))
    if not (np.isfinite(vol_q90) and np.isfinite(spread_abs_q70) and np.isfinite(strength_q70)):
        return "unknown"

    is_crisis = float(vol12) >= float(vol_q90)
    if is_crisis:
        return "crisis"

    strength = abs(float(ret12)) / float(vol12) if float(vol12) > 0 else float("nan")
    is_trend = (abs(float(ema_spread)) >= float(spread_abs_q70)) and (np.isfinite(strength) and strength >= strength_q70)
    if not is_trend:
        return "range"
    return "bull_trend" if float(ema_spread) > 0 else "bear_trend"


def _compute_regime_thresholds_from_history(feats: pd.DataFrame) -> dict[str, float]:
    """
    从历史样本估计制度阈值（当没有训练侧阈值可用时的 fallback）。
    """
    ret12 = feats.get("ret_12")
    vol12 = feats.get("vol_12")
    spread = feats.get("ema_spread")
    if ret12 is None or vol12 is None or spread is None:
        return {}

    ret12 = ret12.astype("float64").replace([np.inf, -np.inf], np.nan)
    vol12 = vol12.astype("float64").replace([np.inf, -np.inf], np.nan)
    spread = spread.astype("float64").replace([np.inf, -np.inf], np.nan)

    strength = (ret12.abs() / vol12.replace(0, np.nan)).replace([np.inf, -np.inf], np.nan)

    def _q(s: pd.Series, q: float) -> float:
        v = s.dropna()
        if v.empty:
            return float("nan")
        return float(v.quantile(q))

    return {
        "vol_12_q90": _q(vol12, 0.90),
        "ema_spread_abs_q70": _q(spread.abs(), 0.70),
        "trend_strength_q70": _q(strength, 0.70),
    }


@dataclass(frozen=True)
class AutoRiskDecision:
    """自动风控输出：策略侧用于“禁新开 + 降仓/降杠杆”的统一结果。"""

    enabled: bool
    allow_entry: bool
    stake_scale: float
    leverage_scale: float
    regime: str
    drift_status: str
    market_context_status: str
    market_context_scale: float
    reasons: list[str]


@dataclass
class _AutoRiskState:
    last_seen_candle_ts: pd.Timestamp | None = None
    seen_candles: int = 0
    last_checked_candle_ts: pd.Timestamp | None = None
    last_decision: AutoRiskDecision | None = None

    # 漂移滞回：crit 后需要连续 ok 才恢复
    blocked: bool = False
    ok_streak: int = 0

    last_persist_key: str = ""


class AutoRiskService:
    """
    自动风控服务（进程内缓存）。

    - 对同一交易对/周期：同一根K线只计算一次，避免在 stake/leverage/confirm 多处重复计算。
    - 产物落盘默认写到 artifacts/auto_risk/（gitignore），用于复盘与追溯。
    """

    def __init__(self, *, cfg: ConfigManager | None = None, model_cache: ModelCache | None = None) -> None:
        self._cfg = cfg or get_config()
        self._model_cache = model_cache or ModelCache()
        # 缓存粒度必须包含 side：regime 的“顺/逆风折扣”与可选 crisis 拦截是方向相关的
        self._state: dict[tuple[str, str, str], _AutoRiskState] = {}

    def _enabled(self) -> bool:
        env = os.getenv("AUTO_RISK_ENABLED", "")
        if str(env).strip() != "":
            return _parse_bool(env, default=False)
        return _parse_bool(self._cfg.get("trading_system.auto_risk.enabled", False), default=False)

    def _cfg_auto_risk(self) -> dict[str, Any]:
        v = self._cfg.get("trading_system.auto_risk", {}) or {}
        return v if isinstance(v, dict) else {}

    def _cfg_regime(self) -> dict[str, Any]:
        v = (self._cfg_auto_risk().get("regime") or {}) if isinstance(self._cfg_auto_risk(), dict) else {}
        return v if isinstance(v, dict) else {}

    def _cfg_drift(self) -> dict[str, Any]:
        v = (self._cfg_auto_risk().get("drift") or {}) if isinstance(self._cfg_auto_risk(), dict) else {}
        return v if isinstance(v, dict) else {}

    def _cfg_market_context(self) -> dict[str, Any]:
        v = (self._cfg_auto_risk().get("market_context") or {}) if isinstance(self._cfg_auto_risk(), dict) else {}
        return v if isinstance(v, dict) else {}

    def _persist_enabled(self) -> bool:
        env = os.getenv("AUTO_RISK_PERSIST", "")
        if str(env).strip() != "":
            return _parse_bool(env, default=True)
        cfg = self._cfg_auto_risk()
        persist = (cfg.get("persist") or {}) if isinstance(cfg, dict) else {}
        if isinstance(persist, dict):
            return _parse_bool(persist.get("enabled", True), default=True)
        return True

    def _persist_dir(self) -> Path:
        cfg = self._cfg_auto_risk()
        persist = (cfg.get("persist") or {}) if isinstance(cfg, dict) else {}
        if isinstance(persist, dict):
            raw = str(persist.get("dir", "")).strip()
            if raw:
                return (self._cfg.repo_root / Path(raw)).resolve()
        return (self._cfg.repo_root / "artifacts" / "auto_risk").resolve()

    def _persist_report(self, *, key: str, payload: dict[str, Any]) -> None:
        if not self._persist_enabled():
            return
        try:
            root = self._persist_dir()
            root.mkdir(parents=True, exist_ok=True)
            path = (root / f"{key}.json").resolve()
            path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            # 记录失败不应影响交易
            return

    def model_dir(self, *, pair: str, timeframe: str) -> Path:
        version = str(self._cfg.model_version).strip() or "v1"
        exchange = str(self._cfg.freqtrade_exchange).strip() or "okx"
        symbol = freqtrade_pair_to_symbol(pair)
        return (self._cfg.qlib_model_dir / version / exchange / str(timeframe) / str(symbol)).resolve()

    def decision(
        self,
        *,
        dp: Any,
        pair: str,
        timeframe: str,
        current_time: datetime,
        side: str,
    ) -> AutoRiskDecision:
        df = get_analyzed_dataframe_upto_time(dp, pair=str(pair), timeframe=str(timeframe), current_time=current_time)
        return self.decision_with_df(
            df=df,
            dp=dp,
            pair=str(pair),
            timeframe=str(timeframe),
            current_time=current_time,
            side=str(side),
        )

    def decision_with_df(
        self,
        *,
        df: pd.DataFrame | None,
        dp: Any | None = None,
        market_df: pd.DataFrame | None = None,
        pair: str,
        timeframe: str,
        current_time: datetime,
        side: str,
    ) -> AutoRiskDecision:
        enabled = bool(self._enabled())
        if not enabled:
            return AutoRiskDecision(
                enabled=False,
                allow_entry=True,
                stake_scale=1.0,
                leverage_scale=1.0,
                regime="unknown",
                drift_status="unknown",
                market_context_status="disabled",
                market_context_scale=1.0,
                reasons=[],
            )

        side_l = str(side or "").strip().lower()
        if side_l not in {"long", "short"}:
            return AutoRiskDecision(
                enabled=True,
                allow_entry=True,
                stake_scale=1.0,
                leverage_scale=1.0,
                regime="unknown",
                drift_status="unknown",
                market_context_status="unknown",
                market_context_scale=1.0,
                reasons=["side_invalid"],
            )

        if df is None or df.empty:
            return AutoRiskDecision(
                enabled=True,
                allow_entry=True,
                stake_scale=1.0,
                leverage_scale=1.0,
                regime="unknown",
                drift_status="unknown",
                market_context_status="unknown",
                market_context_scale=1.0,
                reasons=["no_dataframe"],
            )

        candle_ts = get_last_candle_timestamp(df)
        cache_key = (str(pair), str(timeframe), side_l)
        state = self._state.get(cache_key)
        if state is None:
            state = _AutoRiskState()
            self._state[cache_key] = state

        # 计数：每根K线只计一次，用于 check_interval_candles
        if candle_ts is not None and candle_ts != state.last_seen_candle_ts:
            state.last_seen_candle_ts = candle_ts
            state.seen_candles += 1

        drift_cfg = self._cfg_drift()
        interval = _safe_int(drift_cfg.get("check_interval_candles", 1), default=1)

        # 同一根K线：直接复用（避免重复计算）
        if candle_ts is not None and candle_ts == state.last_checked_candle_ts and state.last_decision is not None:
            return state.last_decision

        # 未到检测周期：复用上次决策（没有上次则放行）
        if interval > 1 and state.seen_candles > 0 and (state.seen_candles % interval) != 0:
            if state.last_decision is not None:
                return state.last_decision
            return AutoRiskDecision(
                enabled=True,
                allow_entry=True,
                stake_scale=1.0,
                leverage_scale=1.0,
                regime="unknown",
                drift_status="unknown",
                market_context_status="unknown",
                market_context_scale=1.0,
                reasons=["skip_check_interval"],
            )

        allow_entry = True
        stake_scale = 1.0
        leverage_scale = 1.0
        reasons: list[str] = []

        # --- 2) 概念漂移/数据质量（优先级更高：可直接触发禁新开） ---
        drift_status = "unknown"
        drift_report: dict[str, Any] | None = None
        baseline_path: Path | None = None
        if _parse_bool(drift_cfg.get("enabled", True), default=True):
            model_dir = self.model_dir(pair=str(pair), timeframe=str(timeframe))
            fail_open = _parse_bool(drift_cfg.get("fail_open", True), default=True)

            loader = None
            try:
                loader = self._model_cache.get(model_dir)
            except Exception:
                loader = None

            baseline = None
            features: list[str] = []
            if loader is not None and isinstance(getattr(loader, "model_info", None), dict):
                features = list(getattr(loader, "features", []) or [])
                baseline_file = str(loader.model_info.get("feature_baseline_file") or "feature_baseline.json").strip()
                baseline_path = (model_dir / baseline_file).resolve()
                if baseline_path.is_file():
                    try:
                        baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
                    except Exception:
                        baseline = None

            if baseline is None or not features:
                drift_status = "unknown"
                reasons.append("drift_baseline_missing")
                if not fail_open:
                    allow_entry = False
                    reasons.append("drift_fail_closed")
            else:
                # 可选：仅用“门控特征”做整体漂移判定，避免噪声特征（高阶矩、价差）导致长期 crit。
                gate = drift_cfg.get("gate_features")
                if isinstance(gate, list) and gate:
                    gate_list = [str(x).strip() for x in gate if str(x).strip()]
                    gate_set = set(gate_list)
                    eval_features = [c for c in features if c in gate_set]
                    if not eval_features:
                        eval_features = list(features)
                        reasons.append("drift_gate_features_empty_fallback_all")
                else:
                    eval_features = list(features)

                window = _safe_int(drift_cfg.get("window", 500), default=500)
                warmup = _safe_int(drift_cfg.get("warmup", 200), default=200)
                warmup = int(max(warmup, _estimate_warmup(eval_features)))
                take_n = int(window + warmup)

                work = df.copy()
                if int(len(work)) > take_n:
                    work = work.iloc[-take_n:].copy()

                # 优先复用 dataframe 中已存在的特征列（策略侧通常已通过 factor_usecase 预计算）
                present = [c for c in eval_features if c in work.columns]
                missing = [c for c in eval_features if c not in work.columns]
                feats = pd.DataFrame()
                try:
                    if not missing:
                        feats = work[eval_features].copy()
                    else:
                        computed = compute_features(work, feature_cols=missing)
                        feats = pd.concat([work[present], computed], axis=1)
                        feats = feats[eval_features]
                except Exception:
                    feats = pd.DataFrame()

                if feats is None or feats.empty:
                    drift_status = "unknown"
                    reasons.append("drift_features_empty")
                    if not fail_open:
                        allow_entry = False
                        reasons.append("drift_fail_closed")
                else:
                    X_window = feats[eval_features].iloc[-window:].copy()
                    th_cfg = (drift_cfg.get("thresholds") or {}) if isinstance(drift_cfg.get("thresholds"), dict) else {}
                    thresholds = DriftThresholds(
                        psi_warn=_safe_float(th_cfg.get("psi_warn", 0.20), default=0.20),
                        psi_crit=_safe_float(th_cfg.get("psi_crit", 0.50), default=0.50),
                        mean_z_warn=_safe_float(th_cfg.get("mean_z_warn", 3.0), default=3.0),
                        mean_z_crit=_safe_float(th_cfg.get("mean_z_crit", 6.0), default=6.0),
                        missing_warn=_safe_float(th_cfg.get("missing_warn", 0.05), default=0.05),
                        missing_crit=_safe_float(th_cfg.get("missing_crit", 0.20), default=0.20),
                    )

                    # baseline 中可能包含多余列；这里按 features 交集裁剪，避免误判 missing_column
                    base_feats = (baseline.get("features") or {}) if isinstance(baseline, dict) else {}
                    if isinstance(base_feats, dict):
                        keep = [c for c in eval_features if c in base_feats]
                        if keep:
                            baseline = dict(baseline)
                            baseline["features"] = {k: base_feats[k] for k in keep}
                            X_window = X_window[keep]

                    drift_report = evaluate_feature_drift(X_window, baseline=baseline, thresholds=thresholds)
                    agg_cfg = (drift_cfg.get("aggregate") or {}) if isinstance(drift_cfg.get("aggregate"), dict) else {}
                    drift_status, drift_counts = _aggregate_drift_status(drift_report, agg_cfg=agg_cfg)
                    if int(drift_counts.get("total", 0)) > 0:
                        reasons.append(
                            "drift_agg:"
                            f"crit={int(drift_counts.get('crit', 0))}/{int(drift_counts.get('total', 0))},"
                            f"warn={int(drift_counts.get('warn', 0))}/{int(drift_counts.get('total', 0))},"
                            f"missing_column={int(drift_counts.get('missing_column', 0))}"
                        )

                    warn_scale = _clamp01(_safe_float(drift_cfg.get("warn_scale", 0.75), default=0.75))
                    crit_scale = _clamp01(_safe_float(drift_cfg.get("crit_scale", 0.30), default=0.30))
                    crit_block = _parse_bool(drift_cfg.get("crit_block_entries", True), default=True)
                    recover_ok = _safe_int(drift_cfg.get("recover_ok_checks", 3), default=3)

                    if drift_status == "warn":
                        stake_scale *= warn_scale
                        leverage_scale *= warn_scale
                        reasons.append("drift_warn")
                        state.ok_streak = 0
                    elif drift_status == "crit":
                        stake_scale *= crit_scale
                        leverage_scale *= crit_scale
                        reasons.append("drift_crit")
                        state.blocked = True
                        state.ok_streak = 0
                        if crit_block:
                            allow_entry = False
                            reasons.append("drift_block_entries")
                    elif drift_status == "ok":
                        if state.blocked:
                            state.ok_streak += 1
                            reasons.append(f"drift_recover_ok_streak={state.ok_streak}/{recover_ok}")
                            if state.ok_streak < recover_ok:
                                allow_entry = False
                                reasons.append("drift_block_recovering")
                            else:
                                state.blocked = False
                                state.ok_streak = 0
                        else:
                            state.ok_streak = 0
                    else:
                        # unknown：不清空 blocked；若已经处于 blocked，则继续禁止新开仓（更安全）
                        reasons.append("drift_unknown")
                        if state.blocked:
                            allow_entry = False
                            reasons.append("drift_block_unknown")

        # --- 1) 制度层：按 regime 做风险折扣（软过滤为主） ---
        regime = "unknown"
        regime_cfg = self._cfg_regime()
        if _parse_bool(regime_cfg.get("enabled", True), default=True):
            need = ["ret_12", "vol_12", "ema_spread"]

            # 优先复用 df 中已有列（若不存在再计算），减少重复计算
            has_cols = all(c in df.columns for c in need)
            feats = df[need].copy() if has_cols else pd.DataFrame()
            if feats.empty:
                try:
                    feats = compute_features(df, feature_cols=need)
                except Exception:
                    feats = pd.DataFrame()

            if feats is not None and not feats.empty and all(c in feats.columns for c in need):
                last = feats.iloc[-1]
                ret12 = float(last.get("ret_12", np.nan))
                vol12 = float(last.get("vol_12", np.nan))
                spread = float(last.get("ema_spread", np.nan))

                thresholds: dict[str, float] = {}
                prefer_model = _parse_bool(regime_cfg.get("prefer_model_thresholds", True), default=True)
                if prefer_model:
                    # 尝试复用训练侧阈值（model_info.json.regime_evaluation.definition.thresholds）
                    try:
                        model_dir = self.model_dir(pair=str(pair), timeframe=str(timeframe))
                        loader = self._model_cache.get(model_dir)
                        info = getattr(loader, "model_info", {}) or {}
                        thresholds = (
                            (((info.get("regime_evaluation") or {}).get("definition") or {}).get("thresholds") or {})
                            if isinstance(info, dict)
                            else {}
                        )
                        thresholds = thresholds if isinstance(thresholds, dict) else {}
                    except Exception:
                        thresholds = {}

                if not thresholds:
                    thresholds = _compute_regime_thresholds_from_history(feats.tail(1500))

                regime = _classify_regime(ret12=ret12, vol12=vol12, ema_spread=spread, thresholds=thresholds)

                scale_map = (regime_cfg.get("scale") or {}) if isinstance(regime_cfg.get("scale"), dict) else {}
                against_trend_scale = _clamp01(_safe_float(scale_map.get("against_trend", scale_map.get("range", 0.85)), default=0.85))

                def _regime_scale(label: str) -> float:
                    return _clamp01(_safe_float(scale_map.get(label, scale_map.get("unknown", 0.85)), default=0.85))

                if regime in {"bull_trend", "bear_trend"}:
                    favorable = (regime == "bull_trend" and side_l == "long") or (regime == "bear_trend" and side_l == "short")
                    r_scale = _regime_scale(regime) if favorable else against_trend_scale
                else:
                    r_scale = _regime_scale(regime)

                stake_scale *= float(r_scale)
                leverage_scale *= float(r_scale)

                crisis_block = _parse_bool(regime_cfg.get("crisis_block_entries", False), default=False)
                if regime == "crisis" and crisis_block:
                    allow_entry = False
                    reasons.append("regime_crisis_block_entries")
            else:
                reasons.append("regime_features_missing")

        # --- 3) 市场代理/外溢风险：BTC 相关性/β 断裂仅做软缩放 ---
        market_context_status = "disabled"
        market_context_scale = 1.0
        market_context_report: dict[str, Any] | None = None

        market_cfg = self._cfg_market_context()
        if _parse_bool(market_cfg.get("enabled", False), default=False):
            market_context_status = "unknown"
            raw_market_pair = str(market_cfg.get("market_pair", "BTC/USDT")).strip()
            eff_market_pair = _normalize_market_pair(market_pair=raw_market_pair, pair=str(pair))
            if not eff_market_pair:
                reasons.append("market_context_market_pair_missing")
            elif str(eff_market_pair) == str(pair):
                market_context_status = "ok"
                market_context_scale = 1.0
                market_context_report = {
                    "status": "ok",
                    "scale": 1.0,
                    "pair": str(pair),
                    "market_pair": str(eff_market_pair),
                    "note": "pair_is_market_pair",
                }
            else:
                if market_df is None and dp is not None:
                    market_df = get_pair_dataframe_upto_time(
                        dp,
                        pair=str(eff_market_pair),
                        timeframe=str(timeframe),
                        current_time=current_time,
                    )
                if market_df is None or market_df.empty:
                    reasons.append("market_context_market_df_missing")
                    market_context_status = "unknown"
                else:
                    try:
                        level, m_scale, report, r = _compute_market_context(
                            asset_df=df,
                            market_df=market_df,
                            cfg=market_cfg,
                            pair=str(pair),
                            market_pair=str(eff_market_pair),
                        )
                        market_context_status = str(level)
                        market_context_scale = float(m_scale)
                        market_context_report = report
                        if r:
                            reasons.extend(list(r))
                        if np.isfinite(market_context_scale) and market_context_scale > 0:
                            stake_scale *= float(market_context_scale)
                            leverage_scale *= float(market_context_scale)
                    except Exception:
                        # 取数/对齐失败时 fail-open，不影响交易
                        reasons.append("market_context_error")
                        market_context_status = "unknown"
                        market_context_scale = 1.0
                        market_context_report = {"status": "unknown", "error": "exception", "pair": str(pair), "market_pair": str(eff_market_pair)}

        stake_scale = _clamp01(stake_scale, default=1.0)
        leverage_scale = _clamp01(leverage_scale, default=1.0)

        decision = AutoRiskDecision(
            enabled=True,
            allow_entry=bool(allow_entry),
            stake_scale=float(stake_scale),
            leverage_scale=float(leverage_scale),
            regime=str(regime),
            drift_status=str(drift_status),
            market_context_status=str(market_context_status),
            market_context_scale=float(market_context_scale),
            reasons=reasons,
        )

        state.last_checked_candle_ts = candle_ts
        state.last_decision = decision

        now_status = f"{decision.regime}/{decision.drift_status}/{decision.market_context_status}/{int(decision.allow_entry)}"
        need_persist = (
            (decision.drift_status in {"warn", "crit"})
            or (decision.market_context_status in {"warn", "crit"})
            or (not decision.allow_entry)
        )
        changed = (state.last_persist_key != now_status)

        if need_persist and changed:
            symbol = freqtrade_pair_to_symbol(str(pair))
            ts_key = candle_ts.isoformat().replace(":", "").replace("+", "").replace("Z", "") if candle_ts is not None else ""
            key = f"{symbol}_{timeframe}_{side_l}_{ts_key}".strip("_")
            payload: dict[str, Any] = {
                "pair": str(pair),
                "symbol": str(symbol),
                "timeframe": str(timeframe),
                "side": side_l,
                "current_time": str(current_time),
                "candle_ts": str(candle_ts) if candle_ts is not None else None,
                "decision": {
                    "allow_entry": bool(decision.allow_entry),
                    "stake_scale": float(decision.stake_scale),
                    "leverage_scale": float(decision.leverage_scale),
                    "regime": decision.regime,
                    "drift_status": decision.drift_status,
                    "market_context_status": decision.market_context_status,
                    "market_context_scale": float(decision.market_context_scale),
                    "reasons": list(decision.reasons),
                },
                "drift_report": drift_report,
                "baseline_path": str(baseline_path.as_posix()) if baseline_path is not None else None,
                "market_context": market_context_report,
            }
            self._persist_report(key=key, payload=payload)
            state.last_persist_key = now_status

        return decision
