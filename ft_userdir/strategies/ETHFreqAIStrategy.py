"""
ETH FreqAI 机器学习策略

设计理念：
1. 使用 FreqAI 自动学习市场模式
2. 特征工程基于学术研究（动量、波动率、成交量、市场微观结构）
3. 让模型自动适应不同市场环境
4. 避免人工参数优化的过拟合
"""

from __future__ import annotations

import logging
from functools import reduce

import numpy as np
import pandas as pd
import talib.abstract as ta
from pandas import DataFrame
from freqtrade.strategy import IStrategy, merge_informative_pair

logger = logging.getLogger(__name__)


class ETHFreqAIStrategy(IStrategy):
    """
    ETH FreqAI 机器学习策略 - 分类模型版本

    核心特性：
    1. 使用 LightGBM 分类器预测交易结果
    2. 预测目标：能否在不触发止损的情况下达到盈利目标
    3. 特征包含：动量、波动率、成交量、价格模式
    4. 自动学习市场状态，无需人工 regime 识别
    5. 滚动训练，适应市场变化
    """

    INTERFACE_VERSION = 3
    can_short = False

    timeframe = "5m"
    startup_candle_count = 100

    # 禁用出场信号（历史证明有害）
    use_exit_signal = False

    # 快速止盈目标
    minimal_roi = {
        "0": 0.03,   # 3% 快速止盈
        "10": 0.02,  # 10分钟后 2%
        "30": 0.01   # 30分钟后 1%
    }

    # 止损
    stoploss = -0.05  # 5% 止损
    trailing_stop = False

    # FreqAI 配置
    process_only_new_candles = True

    def feature_engineering_expand_all(self, dataframe: DataFrame, period: int,
                                       metadata: dict, **kwargs) -> DataFrame:
        """
        特征工程 - 扩展所有周期的特征

        基于学术研究的特征：
        1. 动量指标（ROC、RSI、MACD）
        2. 波动率指标（ATR、历史波动率、布林带宽度）
        3. 成交量指标（成交量变化率、OBV）
        4. 价格模式（EMA 关系、布林带位置）
        """

        # 1. 动量特征
        dataframe[f"%-roc-{period}"] = ta.ROC(dataframe, timeperiod=period)
        dataframe[f"%-rsi-{period}"] = ta.RSI(dataframe, timeperiod=period)

        # MACD
        macd = ta.MACD(dataframe, fastperiod=12, slowperiod=26, signalperiod=9)
        dataframe[f"%-macd-{period}"] = macd['macd']
        dataframe[f"%-macdsignal-{period}"] = macd['macdsignal']
        dataframe[f"%-macdhist-{period}"] = macd['macdhist']

        # 2. 波动率特征
        dataframe[f"%-atr-{period}"] = ta.ATR(dataframe, timeperiod=period)
        dataframe[f"%-natr-{period}"] = ta.NATR(dataframe, timeperiod=period)  # 标准化 ATR

        # 历史波动率
        dataframe[f"%-hist_vol-{period}"] = dataframe['close'].pct_change().rolling(period).std()

        # 布林带宽度
        bollinger = ta.BBANDS(dataframe, timeperiod=period, nbdevup=2.0, nbdevdn=2.0)
        dataframe[f"%-bb_width-{period}"] = (
            (bollinger['upperband'] - bollinger['lowerband']) / bollinger['middleband']
        )
        dataframe[f"%-bb_position-{period}"] = (
            (dataframe['close'] - bollinger['lowerband']) /
            (bollinger['upperband'] - bollinger['lowerband'])
        )

        # 3. 成交量特征
        dataframe[f"%-volume_change-{period}"] = dataframe['volume'].pct_change(period)
        dataframe[f"%-obv-{period}"] = ta.OBV(dataframe)

        # 成交量加权平均价格偏离
        dataframe[f"%-vwap_diff-{period}"] = (
            dataframe['close'] -
            (dataframe['close'] * dataframe['volume']).rolling(period).sum() /
            dataframe['volume'].rolling(period).sum()
        ) / dataframe['close']

        # 4. 价格模式特征
        dataframe[f"%-ema_fast-{period}"] = ta.EMA(dataframe, timeperiod=int(period/2))
        dataframe[f"%-ema_slow-{period}"] = ta.EMA(dataframe, timeperiod=period)
        dataframe[f"%-ema_diff-{period}"] = (
            dataframe[f"%-ema_fast-{period}"] - dataframe[f"%-ema_slow-{period}"]
        ) / dataframe[f"%-ema_slow-{period}"]

        # 5. 市场微观结构代理指标
        # 价格范围（high-low）作为流动性代理
        dataframe[f"%-price_range-{period}"] = (
            (dataframe['high'] - dataframe['low']) / dataframe['close']
        )

        # 收盘价相对位置（接近 high 还是 low）
        dataframe[f"%-close_position-{period}"] = (
            (dataframe['close'] - dataframe['low']) /
            (dataframe['high'] - dataframe['low'] + 1e-10)
        )

        return dataframe

    def feature_engineering_expand_basic(self, dataframe: DataFrame, metadata: dict, **kwargs) -> DataFrame:
        """
        基础特征工程 - 不依赖周期的特征
        """

        # 基础价格特征
        dataframe["%-pct_change"] = dataframe["close"].pct_change()
        dataframe["%-raw_volume"] = dataframe["volume"]
        dataframe["%-raw_price"] = dataframe["close"]

        return dataframe

    def feature_engineering_standard(self, dataframe: DataFrame, metadata: dict, **kwargs) -> DataFrame:
        """
        标准特征工程 - 使用多个周期
        """

        # 使用多个周期捕捉不同时间尺度的模式
        periods = [5, 10, 20, 40]

        for period in periods:
            dataframe = self.feature_engineering_expand_all(dataframe, period, metadata, **kwargs)

        return dataframe

    def set_freqai_targets(self, dataframe: DataFrame, metadata: dict, **kwargs) -> DataFrame:
        """
        设置预测目标 - 交易结果二分类

        二分类目标：
        - 'reaches_target': 能在不触发止损的情况下达到ROI目标（+1%）
        - 'not_reaches_target': 触发止损或未达到目标

        向前查看40期（200分钟），检查价格路径
        """

        # 计算未来40期内的最高价和最低价
        dataframe['future_max'] = dataframe['high'].shift(-1).rolling(40).max()
        dataframe['future_min'] = dataframe['low'].shift(-1).rolling(40).min()

        # ROI目标：最低1%（保守）
        roi_target = 0.01
        # 止损：-5%
        stoploss_level = -0.05

        # 计算达到目标和止损的价格
        dataframe['target_price'] = dataframe['close'] * (1 + roi_target)
        dataframe['stoploss_price'] = dataframe['close'] * (1 + stoploss_level)

        # 判断交易结果
        # 先检查是否达到目标
        reaches_target = dataframe['future_max'] >= dataframe['target_price']
        # 再检查是否触发止损
        hits_stoploss = dataframe['future_min'] <= dataframe['stoploss_price']

        # 二分类逻辑：只有在达到目标且未触发止损时才标记为成功
        dataframe['&s-trade_outcome'] = 'not_reaches_target'
        dataframe.loc[reaches_target & ~hits_stoploss, '&s-trade_outcome'] = 'reaches_target'

        return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        填充指标 - FreqAI 会自动调用特征工程方法
        """

        # FreqAI 会自动处理特征工程
        dataframe = self.freqai.start(dataframe, metadata, self)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        入场信号 - 基于 FreqAI 分类预测

        当模型预测为'reaches_target'时入场
        """

        # 使用模型预测的交易结果类别
        # FreqAI 会在 dataframe 中添加 'do_predict' 和 '&s-trade_outcome' 列
        dataframe.loc[
            (
                (dataframe['do_predict'] == 1) &  # FreqAI 准备好预测
                (dataframe['&s-trade_outcome'] == 'reaches_target')  # 预测为成功
            ),
            'enter_long'
        ] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        出场信号 - 禁用（只依赖 ROI + 止损）
        """
        return dataframe
