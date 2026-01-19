"""
ETH 高频交易策略 - 市场状态自适应

设计理念：
1. 快进快出 scalping 风格
2. 优化 Expectancy 和 Profit Factor（不是最小化回撤）
3. 市场状态自适应（趋势市 vs 震荡市）
4. 动态 ATR 止损
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import talib.abstract as ta
from freqtrade.strategy import IStrategy

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from integration.factor_library import FactorLibrary


class ETHHighFreqStrategy(IStrategy):
    """
    ETH 高频交易策略 - 市场状态自适应

    特性：
    1. ADX 市场状态过滤（震荡市 vs 趋势市）
    2. 震荡市：均值回归 + 布林带反弹
    3. 趋势市：动量突破 + ROC 指标
    4. 动态 ATR 止损
    5. 快速止盈（1-3%）
    """

    INTERFACE_VERSION = 3
    can_short = False

    timeframe = "5m"
    startup_candle_count = 100

    # 禁用出场信号，只依赖 ROI + 止损
    use_exit_signal = False

    # 快速止盈目标
    minimal_roi = {
        "0": 0.03,   # 3% 快速止盈
        "10": 0.02,  # 10分钟后 2%
        "30": 0.01   # 30分钟后 1%
    }

    # 动态止损（将在 custom_stoploss 中实现）
    stoploss = -0.05  # 初始止损 5%
    trailing_stop = False

    # 市场状态阈值
    adx_trend_threshold = 25  # ADX > 25 为趋势市

    # 布林带参数（震荡市）
    bb_period = 20
    bb_std = 2.0

    # ROC 参数（趋势市）
    roc_period = 9

    def __init__(self, config: dict) -> None:
        """初始化策略"""
        super().__init__(config)
        self.factor_lib = FactorLibrary()

    def populate_indicators(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        """计算指标"""

        # 1. 市场状态指标：ADX
        dataframe['adx'] = ta.ADX(dataframe, timeperiod=14)

        # 2. 震荡市指标：布林带
        bollinger = ta.BBANDS(dataframe, timeperiod=self.bb_period, nbdevup=self.bb_std, nbdevdn=self.bb_std)
        dataframe['bb_upper'] = bollinger['upperband']
        dataframe['bb_middle'] = bollinger['middleband']
        dataframe['bb_lower'] = bollinger['lowerband']
        dataframe['bb_width'] = (dataframe['bb_upper'] - dataframe['bb_lower']) / dataframe['bb_middle']

        # 3. 震荡市指标：RSI
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)

        # 4. 趋势市指标：ROC（价格变化率）
        dataframe['roc'] = ta.ROC(dataframe, timeperiod=self.roc_period)

        # 5. 趋势市指标：EMA
        dataframe['ema_fast'] = ta.EMA(dataframe, timeperiod=8)
        dataframe['ema_slow'] = ta.EMA(dataframe, timeperiod=21)

        # 6. 动态止损：ATR
        dataframe['atr'] = ta.ATR(dataframe, timeperiod=14)

        # 7. 成交量确认
        dataframe['volume_ma'] = dataframe['volume'].rolling(20).mean()

        return dataframe

    def populate_entry_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        """
        入场信号 - 市场状态自适应
        """

        # 震荡市条件（ADX < 25）：均值回归策略
        rangebound_conditions = (
            (dataframe['adx'] < self.adx_trend_threshold) &
            (dataframe['rsi'] < 30) &  # 超卖
            (dataframe['close'] < dataframe['bb_lower']) &  # 价格触及下轨
            (dataframe['volume'] > dataframe['volume_ma'] * 0.8)  # 成交量确认
        )

        # 趋势市条件（ADX >= 25）：动量突破策略
        trending_conditions = (
            (dataframe['adx'] >= self.adx_trend_threshold) &
            (dataframe['roc'] > 0.5) &  # ROC 正向突破
            (dataframe['ema_fast'] > dataframe['ema_slow']) &  # 快线上穿慢线
            (dataframe['close'] > dataframe['ema_fast']) &  # 价格在快线上方
            (dataframe['volume'] > dataframe['volume_ma'] * 1.2)  # 成交量放大
        )

        # 合并入场条件
        dataframe.loc[
            rangebound_conditions | trending_conditions,
            'enter_long'
        ] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        """
        出场信号 - 市场状态自适应
        """

        # 震荡市出场：价格回归中轨或超买
        rangebound_exit = (
            (dataframe['adx'] < self.adx_trend_threshold) &
            (
                (dataframe['rsi'] > 70) |  # 超买
                (dataframe['close'] > dataframe['bb_middle'])  # 回归中轨
            )
        )

        # 趋势市出场：动量衰减或趋势反转
        trending_exit = (
            (dataframe['adx'] >= self.adx_trend_threshold) &
            (
                (dataframe['roc'] < -0.3) |  # ROC 转负
                (dataframe['ema_fast'] < dataframe['ema_slow'])  # 快线下穿慢线
            )
        )

        # 合并出场条件
        dataframe.loc[
            rangebound_exit | trending_exit,
            'exit_long'
        ] = 1

        return dataframe

    def custom_stoploss(self, pair: str, trade: 'Trade', current_time: 'datetime',
                       current_rate: float, current_profit: float, **kwargs) -> float:
        """
        动态止损 - 基于 ATR

        止损距离 = ATR × 1.5
        """
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        last_candle = dataframe.iloc[-1].squeeze()

        if 'atr' in last_candle:
            atr = last_candle['atr']
            # 动态止损：ATR 的 1.5 倍
            stop_loss_distance = (atr / current_rate) * 1.5
            return -stop_loss_distance

        # 如果 ATR 不可用，使用默认止损
        return self.stoploss
