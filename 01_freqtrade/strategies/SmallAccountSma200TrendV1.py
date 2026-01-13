from __future__ import annotations

import talib.abstract as ta
from pandas import DataFrame
from technical import qtpylib

from freqtrade.strategy import IStrategy


class SmallAccountSma200TrendV1(IStrategy):
    """
    小资金现货趋势策略 v1（SMA200 过滤）

    思路：
    - 只做多，核心是“上车牛市、下车熊市”
    - 用日线 SMA200 作为大趋势分界：
      - 收盘价上穿 SMA200 -> 入场
      - 收盘价下穿 SMA200 -> 退出

    适用场景：
    - 小资金阶段先追求“活下来 + 可复现的正收益”
    - 交易频率低，手续费占比低，逻辑极其可解释
    """

    INTERFACE_VERSION = 3

    timeframe = "1d"
    startup_candle_count = 210

    minimal_roi = {"0": 100}
    stoploss = -0.25

    use_exit_signal = True

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["sma200"] = ta.SMA(dataframe, timeperiod=200)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["enter_long"] = 0

        dataframe.loc[
            (
                qtpylib.crossed_above(dataframe["close"], dataframe["sma200"])
                & (dataframe["volume"] > 0)
            ),
            "enter_long",
        ] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["exit_long"] = 0

        dataframe.loc[
            (
                qtpylib.crossed_below(dataframe["close"], dataframe["sma200"])
                & (dataframe["volume"] > 0)
            ),
            "exit_long",
        ] = 1

        return dataframe

