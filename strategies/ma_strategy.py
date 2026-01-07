import talib.abstract as ta
from freqtrade.strategy import IStrategy
from pandas import DataFrame
from technical import qtpylib


class MAStrategy(IStrategy):
    """简单的双均线策略：
    短期均线上穿长期均线，买入
    短期均线下穿长期均线，卖出"""

    timeframe = "1h"

    # 硬止损兜底
    stoploss = -0.10

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # 计算短期和长期均线
        dataframe["ma_short"] = ta.EMA(dataframe["close"], timeperiod=5) # type: ignore
        dataframe["ma_long"] = ta.EMA(dataframe["close"], timeperiod=10) # type: ignore
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # 短均线上穿长均线→买入
        dataframe.loc[
            qtpylib.crossed_above(dataframe["ma_short"], dataframe["ma_long"])
            & (dataframe["volume"] > 0),
            "enter_long",
        ] = 1
        return dataframe

    def populate_exit_trend(
        self, dataframe: DataFrame, metadata: dict
    ) -> DataFrame:  # 短均线下穿长均线→卖出
        dataframe.loc[
            qtpylib.crossed_below(dataframe["ma_short"], dataframe["ma_long"])
            & (dataframe["volume"] > 0),
            "exit_long",
        ] = 1
        return dataframe
