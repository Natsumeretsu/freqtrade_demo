from __future__ import annotations

from datetime import datetime
from math import isfinite, log1p

from pandas import DataFrame

from freqtrade.constants import Config
from freqtrade.optimize.hyperopt import IHyperOptLoss


def _extract_backtest_stats(args: tuple[object, ...], kwargs: dict) -> dict:
    """
    从 Freqtrade 传入参数中提取 backtest_stats。

    说明：
    - Freqtrade 版本/接口演进会导致 backtest_stats 以 kwargs 或 args 形式传入。
    - 这里做“最小、健壮”的兜底提取，避免因签名变化导致自定义 loss 失效。
    """
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


class CompounderCalmarSortinoLoss(IHyperOptLoss):
    """
    Profile A（Compounder）的自定义 HyperOptLoss：

    目标：
    - 强约束：最大相对回撤 <= 15%
    - 优化方向：Calmar / Sortino 为主，并兼顾总收益（避免“低交易数 + 极小回撤”导致 Calmar 虚高）
    """

    MAX_RELATIVE_DRAWDOWN = 0.15
    MIN_TRADES_TOTAL = 30

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

        # --- 硬性约束：最大回撤 ---
        if max_dd > CompounderCalmarSortinoLoss.MAX_RELATIVE_DRAWDOWN:
            # 直接强惩罚，避免优化器浪费时间在“明显违规”的区域
            return 1_000_000.0 + (max_dd - CompounderCalmarSortinoLoss.MAX_RELATIVE_DRAWDOWN) * 10_000.0

        # --- 约束：交易数量不能太少（防止“极少交易 + 小回撤”被误判为优秀）---
        if trade_count < CompounderCalmarSortinoLoss.MIN_TRADES_TOTAL:
            return 10_000.0 + (CompounderCalmarSortinoLoss.MIN_TRADES_TOTAL - trade_count) * 100.0

        calmar = _safe_float(stats.get("calmar"), default=0.0)
        sortino = _safe_float(stats.get("sortino"), default=0.0)
        sharpe = _safe_float(stats.get("sharpe"), default=0.0)

        # sortino 在某些情况下会出现哨兵值（例如 -100），这里按“很差”处理
        if sortino < 0:
            sortino = 0.0
        if calmar < 0:
            calmar = 0.0
        if sharpe < 0:
            sharpe = 0.0
        # profit_total 允许为负，用于显式惩罚亏损；但要防止 log1p(-1) 的数学域错误
        profit_total = max(-0.99, profit_total)

        # --- 综合打分（压缩极端值，避免 calmar 因极小 dd 爆炸）---
        score = (
            6.0 * log1p(profit_total)
            + 2.0 * log1p(calmar)
            + 1.0 * log1p(sortino)
            + 0.5 * log1p(sharpe)
        )

        # hyperopt 是“最小化”，因此返回负分数
        return -score
