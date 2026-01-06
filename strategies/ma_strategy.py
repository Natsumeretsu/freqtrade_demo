import talib.abstract as ta
from freqtrade.strategy import IStrategy
from pandas import DataFrame


class MAStrategy(IStrategy):
    """简单的双均线策略：
    短期均线上穿长期均线，买入
    短期均线下穿长期均线，卖出"""

    timeframe = "1h"

    # 初始止损设置为 -10%
    stoploss = -0.10

    stoploss = -0.1  # 表示最大止损为-10%

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # 计算短期和长期均线
        dataframe["ma_short"] = ta.EMA(dataframe["close"], timeperiod=5) # type: ignore
        dataframe["ma_long"] = ta.EMA(dataframe["close"], timeperiod=10) # type: ignore
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # 短均线上穿长均线→买入
        dataframe.loc[
            (dataframe["ma_short"] > dataframe["ma_long"])
            & (dataframe["ma_short"].shift(1) <= dataframe["ma_long"].shift(1)),
            "enter_long",
        ] = 1
        return dataframe

    def populate_exit_trend(
        self, dataframe: DataFrame, metadata: dict
    ) -> DataFrame:  # 短均线下穿长均线→卖出
        dataframe.loc[
            (dataframe["ma_short"] < dataframe["ma_long"])
            & (dataframe["ma_short"].shift(1) >= dataframe["ma_long"].shift(1)),
            "exit_long",
        ] = 1
        return dataframe
