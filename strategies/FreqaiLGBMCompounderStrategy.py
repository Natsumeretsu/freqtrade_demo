from __future__ import annotations

from freqtrade.strategy import BooleanParameter, DecimalParameter

from freqai_lgbm_trend_strategy import FreqaiLGBMTrendStrategy


class FreqaiLGBMCompounderStrategy(FreqaiLGBMTrendStrategy):
    """
    Profile A: The Compounder（大资金、低频、低回撤）。

    目标：
    - 偏稳定收益，强调回撤约束（Max DD < 15%）
    - 优先优化 Calmar / Sortino（建议配合自定义 HyperOptLoss）
    """

    # 宏观过滤（BTC 1d SMA200）：熊市提高入场阈值，减少 Beta 拖累
    btc_regime_bear_pred_threshold_multiplier = 2.5
    btc_regime_bear_pred_threshold_min = 0.02

    buy_pred_threshold = DecimalParameter(0.008, 0.06, default=0.018, decimals=3, space="buy", optimize=True)

    buy_use_trend_filter = BooleanParameter(default=True, space="buy", optimize=False)
    buy_use_fast_trend_filter = BooleanParameter(default=True, space="buy", optimize=False)
    buy_use_ema_short_slope_filter = BooleanParameter(default=True, space="buy", optimize=False)
    buy_use_ema_long_slope_filter = BooleanParameter(default=True, space="buy", optimize=False)

    buy_use_max_atr_pct_filter = BooleanParameter(default=True, space="buy", optimize=False)
    buy_max_atr_pct = DecimalParameter(0.005, 0.08, default=0.040, decimals=3, space="buy", optimize=True)

    sell_sl_max = DecimalParameter(0.03, 0.12, default=0.06, decimals=3, space="sell", optimize=True)
    sell_trailing_stop_positive = DecimalParameter(0.005, 0.08, default=0.02, decimals=3, space="sell", optimize=True)
    sell_trailing_stop_offset = DecimalParameter(0.010, 0.12, default=0.03, decimals=3, space="sell", optimize=True)
