from __future__ import annotations

from datetime import datetime
from math import isfinite

from pandas import DataFrame

from freqtrade.constants import Config
from freqtrade.optimize.hyperopt import IHyperOptLoss


def _extract_backtest_stats(args: tuple[object, ...], kwargs: dict) -> dict:
    candidate = kwargs.get("backtest_stats")
    if isinstance(candidate, dict):
        return candidate

    for arg in args:
        if isinstance(arg, dict) and ("profit_total" in arg or "max_relative_drawdown" in arg):
            return arg

    return {}


def _safe_float(value: object, default: float) -> float:
    try:
        num = float(value)  # type: ignore[arg-type]
    except Exception:
        return default
    return num if isfinite(num) else default


class MoonshotProfitFrequencyLoss(IHyperOptLoss):
    """
    Profile B（Moonshot）的自定义 HyperOptLoss：

    目标：
    - 强约束：最大相对回撤 <= 30%
    - 软约束：鼓励 trades/day 接近目标（不应压过收益信号）
    - 优化方向：以总收益为主（更激进），同时避免高回撤方案
    """

    MAX_RELATIVE_DRAWDOWN = 0.30
    TARGET_TRADES_PER_DAY = 3.0
    FREQ_PENALTY_WEIGHT = 1.0
    NEGATIVE_PROFIT_PENALTY = 1000.0

    @staticmethod
    def hyperopt_loss_function(
        results: DataFrame,
        trade_count: int,
        min_date: datetime,
        max_date: datetime,
        config: Config,
        processed: dict[str, DataFrame],
        *args,
        **kwargs,
    ) -> float:
        stats = _extract_backtest_stats(args, kwargs)

        fallback_profit_total = float(results["profit_ratio"].sum()) if "profit_ratio" in results.columns else 0.0
        profit_total = _safe_float(stats.get("profit_total"), default=fallback_profit_total)
        max_dd = _safe_float(stats.get("max_relative_drawdown"), default=1.0)
        trades_per_day = _safe_float(stats.get("trades_per_day"), default=0.0)

        # 如果没提供 trades_per_day，则用时间跨度兜底计算
        if trades_per_day <= 0:
            days = max(1.0, (max_date - min_date).total_seconds() / 86400.0)
            trades_per_day = float(trade_count) / days

        # --- 约束：最大回撤 ---
        if max_dd > MoonshotProfitFrequencyLoss.MAX_RELATIVE_DRAWDOWN:
            return 1_000_000.0 + (max_dd - MoonshotProfitFrequencyLoss.MAX_RELATIVE_DRAWDOWN) * 10_000.0

        # --- 软约束：交易频次（引导策略变得更高频，但不会把收益信号“淹没”）---
        freq_gap = max(0.0, MoonshotProfitFrequencyLoss.TARGET_TRADES_PER_DAY - trades_per_day)
        freq_penalty = MoonshotProfitFrequencyLoss.FREQ_PENALTY_WEIGHT * freq_gap

        # 注意：profit_total 通常是 ratio（例如 0.0918 = 9.18%），将其放大到“百分比”尺度后再与频次惩罚组合。
        profit_pct = profit_total * 100.0

        # --- 目标：最大化收益（percent）---
        # 负收益方案直接打大惩罚，避免“为了凑频次而亏钱”的最优解。
        if profit_pct <= 0:
            return MoonshotProfitFrequencyLoss.NEGATIVE_PROFIT_PENALTY + (-profit_pct) + freq_penalty

        return (-profit_pct) + freq_penalty
