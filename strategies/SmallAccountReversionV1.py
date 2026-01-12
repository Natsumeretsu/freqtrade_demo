from __future__ import annotations

import talib.abstract as ta
from pandas import DataFrame

from freqtrade.strategy import IStrategy, IntParameter


class SmallAccountReversionV1(IStrategy):
    """
    小资金（10USDT 起）现货均值回归策略 v1

    设计目标：
    - 尽量避免 1m 级别的高频噪声与手续费吞噬
    - 通过“趋势过滤 + 回调买入 + 均值回归退出”获得更稳定的期望值
    - 以工程可迭代为第一优先级：参数可控、逻辑可解释

    核心逻辑（1h）：
    - 趋势过滤：价格在 EMA200 上方（不在大熊市里硬抄底）
    - 回调入场：RSI 低位 + 价格回落到布林中轨下方（但仍在大趋势上方）
    - 回归退出：RSI 回升或触及布林上轨（避免“回归后继续贪”）
    """

    INTERFACE_VERSION = 3

    timeframe = "1h"
    startup_candle_count = 240

    # ROI 用于“到点就走”，避免小资金被长时间占用
    minimal_roi = {
        "0": 0.03,     # 目标 3%
        "48": 0.015,   # 2 天后接受 1.5%
        "168": 0.0,    # 1 周后允许 breakeven 退出（由 exit 信号兜底）
    }

    # 黑天鹅兜底止损（均值回归不能无止损）
    stoploss = -0.06

    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False

    # --- 可调参数（保守范围，避免过拟合）---
    buy_rsi = IntParameter(20, 40, default=30, space="buy", optimize=True)
    sell_rsi = IntParameter(45, 70, default=55, space="sell", optimize=True)

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["ema200"] = ta.EMA(dataframe, timeperiod=200)
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)

        bb = ta.BBANDS(dataframe, timeperiod=20, nbdevup=2.0, nbdevdn=2.0, matype=0)
        dataframe["bb_upper"] = bb["upperband"]
        dataframe["bb_middle"] = bb["middleband"]
        dataframe["bb_lower"] = bb["lowerband"]

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["enter_long"] = 0

        # 趋势过滤：只在 EMA200 之上考虑做多
        trend_ok = dataframe["close"] > dataframe["ema200"]

        # 回调条件：低 RSI + 跌破下轨（更深的回撤，降低“追跌”概率）
        dip_ok = (dataframe["rsi"] < self.buy_rsi.value) & (dataframe["close"] < dataframe["bb_lower"])

        dataframe.loc[
            trend_ok & dip_ok & (dataframe["volume"] > 0),
            "enter_long",
        ] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["exit_long"] = 0

        # 回归退出：回到中轨之上或 RSI 回升到阈值（更快落袋，适配小资金）
        exit_ok = (dataframe["close"] > dataframe["bb_middle"]) | (dataframe["rsi"] > self.sell_rsi.value)

        dataframe.loc[
            exit_ok & (dataframe["volume"] > 0),
            "exit_long",
        ] = 1

        return dataframe
