# pragma pylint: disable=missing-docstring, invalid-name, pointless-string-statement
# flake8: noqa: F401
# isort: skip_file
# --- 请勿删除这些导入 ---

from __future__ import annotations

from pandas import DataFrame

import talib.abstract as ta

from freqtrade.strategy import (
    BooleanParameter,
    DecimalParameter,
    IStrategy,
    IntParameter,
)


class MacdHistogramMomentumReversalStrategy(IStrategy):
    """
    基于 MACD 柱状图“动量背离”的趋势反转策略（现货版，默认只做多）

    参考文档：
    `strategies_ref_docs/动量背离趋势反转量化策略基于MACD柱状图-Momentum-Divergence-Trend-Reversal-Quantitative-Strategy-Based-on-MACD-Histogram.md`

    核心逻辑（尽量贴近参考 PineScript）：
    - 做空信号（用于“平多”，现货不直接做空）：
      1) 当前 K 线为阳线（close > open）
      2) 当前实体大于上一根 K 线实体（abs(close-open) > abs(close[1]-open[1])）
      3) MACD 柱状图连续 3 根下降：hist[2] > hist[1] > hist[0]
    - 做多信号：
      1) 当前 K 线为阴线（close < open）
      2) 当前实体大于上一根 K 线实体
      3) MACD 柱状图连续 3 根上升：hist[2] < hist[1] < hist[0]
    - 仓位管理：出现“对手信号”就平仓（不设置止盈止损，完全靠信号）

    提示：
    - 若你以后要在合约里做空，可把 `can_short` 改为 True，并在配置里启用 futures。
    """

    INTERFACE_VERSION = 3

    # 参考实现使用 1h，这里保持一致；你也可以在命令行用 -i 覆盖
    timeframe = "1h"

    # 现货默认只做多（做空信号用于“平多”）
    can_short: bool = False

    process_only_new_candles = True

    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False

    # 参考策略不设置止盈/止损：用极高 ROI + 极低止损来避免干扰（可自行改回）
    minimal_roi = {"0": 999}
    stoploss = -0.99

    # 预热：MACD(26,9) + 连续 3 根判断，留足余量
    startup_candle_count: int = 60

    # --- 可选：趋势过滤（文档的“优化方向”之一） ---
    # 默认关闭：尽量贴近原策略；打开后仅在长期均线之上才允许做多，减少震荡市假信号
    trend_filter_enabled = BooleanParameter(default=False, space="buy")
    trend_sma_length = IntParameter(50, 300, default=200, space="buy")

    # --- 额外可调参数（用于改进信号稳定性） ---
    # 参考实现固定为 3 根，这里允许 2~5 根（越大越“严格”，信号更少）
    entry_hist_bars = IntParameter(2, 5, default=3, space="buy")
    exit_hist_bars = IntParameter(2, 5, default=3, space="sell")

    # K 线实体“变大”阈值：body_size > prev_body_size * body_multiplier
    body_multiplier = DecimalParameter(1.0, 3.0, default=1.0, decimals=2, space="buy")

    # 可选：要求做多时 MACD 柱为负（更贴近“空头动能衰减 -> 反转做多”的解释）
    entry_hist_must_be_negative = BooleanParameter(default=False, space="buy")

    def informative_pairs(self):
        return []

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # === MACD 计算（与参考 PineScript 默认参数一致）===
        macd = ta.MACD(dataframe, fastperiod=12, slowperiod=26, signalperiod=9) # type: ignore
        dataframe["macd"] = macd["macd"]
        dataframe["macdsignal"] = macd["macdsignal"]
        dataframe["macdhist"] = macd["macdhist"]

        # === K 线实体大小 ===
        dataframe["body_size"] = (dataframe["close"] - dataframe["open"]).abs()
        dataframe["prev_body_size"] = (
            dataframe["close"].shift(1) - dataframe["open"].shift(1)
        ).abs()
        dataframe["candle_bigger"] = dataframe["body_size"] > dataframe[
            "prev_body_size"
        ] * float(self.body_multiplier.value)

        dataframe["is_bullish"] = dataframe["close"] > dataframe["open"]
        dataframe["is_bearish"] = dataframe["close"] < dataframe["open"]

        # === MACD 柱动量变化（连续 N 根单调）===
        hist = dataframe["macdhist"]
        dataframe["hist_is_negative"] = hist < 0

        # 2 根：hist[1] > hist[0]
        dataframe["hist_decreasing_2"] = hist.shift(1) > hist
        dataframe["hist_increasing_2"] = hist.shift(1) < hist

        # 3 根：hist[2] > hist[1] > hist[0]
        dataframe["hist_decreasing_3"] = (hist.shift(2) > hist.shift(1)) & (
            hist.shift(1) > hist
        )
        dataframe["hist_increasing_3"] = (hist.shift(2) < hist.shift(1)) & (
            hist.shift(1) < hist
        )

        # 4 根：hist[3] > hist[2] > hist[1] > hist[0]
        dataframe["hist_decreasing_4"] = (
            (hist.shift(3) > hist.shift(2))
            & (hist.shift(2) > hist.shift(1))
            & (hist.shift(1) > hist)
        )
        dataframe["hist_increasing_4"] = (
            (hist.shift(3) < hist.shift(2))
            & (hist.shift(2) < hist.shift(1))
            & (hist.shift(1) < hist)
        )

        # 5 根：hist[4] > hist[3] > hist[2] > hist[1] > hist[0]
        dataframe["hist_decreasing_5"] = (
            (hist.shift(4) > hist.shift(3))
            & (hist.shift(3) > hist.shift(2))
            & (hist.shift(2) > hist.shift(1))
            & (hist.shift(1) > hist)
        )
        dataframe["hist_increasing_5"] = (
            (hist.shift(4) < hist.shift(3))
            & (hist.shift(3) < hist.shift(2))
            & (hist.shift(2) < hist.shift(1))
            & (hist.shift(1) < hist)
        )

        # 可选趋势过滤：长期均线
        dataframe["trend_sma"] = ta.SMA( # type: ignore
            dataframe, timeperiod=int(self.trend_sma_length.value)
        )

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        entry_hist_bars = int(self.entry_hist_bars.value)
        if entry_hist_bars == 2:
            hist_increasing = dataframe["hist_increasing_2"]
        elif entry_hist_bars == 4:
            hist_increasing = dataframe["hist_increasing_4"]
        elif entry_hist_bars == 5:
            hist_increasing = dataframe["hist_increasing_5"]
        else:
            hist_increasing = dataframe["hist_increasing_3"]

        # 做多：阴线 + 实体变大 + hist 连续 3 根上升（动量衰减 -> 反转预期）
        enter_long_cond = (
            (dataframe["volume"] > 0)
            & dataframe["candle_bigger"]
            & dataframe["is_bearish"]
            & hist_increasing
        )

        if bool(self.trend_filter_enabled.value):
            enter_long_cond &= dataframe["trend_sma"].notna() & (
                dataframe["close"] > dataframe["trend_sma"]
            )

        if bool(self.entry_hist_must_be_negative.value):
            enter_long_cond &= dataframe["hist_is_negative"]

        dataframe.loc[enter_long_cond, "enter_long"] = 1
        dataframe.loc[enter_long_cond, "enter_tag"] = "MACD柱_动量衰减_做多"

        # 如需合约做空，可开启 can_short 并放开下方 enter_short（与参考实现一致）
        """
        enter_short_cond = (
            (dataframe["volume"] > 0)
            & dataframe["candle_bigger"]
            & dataframe["is_bullish"]
            & dataframe["hist_decreasing_3"]
        )
        dataframe.loc[enter_short_cond, "enter_short"] = 1
        dataframe.loc[enter_short_cond, "enter_tag"] = "MACD柱_动量衰减_做空"
        """

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        exit_hist_bars = int(self.exit_hist_bars.value)
        if exit_hist_bars == 2:
            hist_decreasing = dataframe["hist_decreasing_2"]
        elif exit_hist_bars == 4:
            hist_decreasing = dataframe["hist_decreasing_4"]
        elif exit_hist_bars == 5:
            hist_decreasing = dataframe["hist_decreasing_5"]
        else:
            hist_decreasing = dataframe["hist_decreasing_3"]

        # 平多：出现“对手信号”（参考实现：enterShort 出现就 close Long）
        exit_long_cond = (
            (dataframe["volume"] > 0)
            & dataframe["candle_bigger"]
            & dataframe["is_bullish"]
            & hist_decreasing
        )

        dataframe.loc[exit_long_cond, "exit_long"] = 1
        dataframe.loc[exit_long_cond, "exit_tag"] = "MACD柱_对手信号_平多"

        # 如需合约做空：出现做多信号时平空（对应参考实现 close Short）
        """
        exit_short_cond = (
            (dataframe["volume"] > 0)
            & dataframe["candle_bigger"]
            & dataframe["is_bearish"]
            & dataframe["hist_increasing_3"]
        )
        dataframe.loc[exit_short_cond, "exit_short"] = 1
        dataframe.loc[exit_short_cond, "exit_tag"] = "MACD柱_对手信号_平空"
        """

        return dataframe
