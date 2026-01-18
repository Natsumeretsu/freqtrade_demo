"""
简化的策略模板 - MVP版本

只使用经过验证的因子，避免过度复杂的逻辑。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
from freqtrade.strategy import IStrategy

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from integration.factor_library import FactorLibrary


class SimpleMVPStrategy(IStrategy):
    """
    简化的MVP策略模板

    设计原则：
    1. 只使用经过验证的因子
    2. 逻辑清晰，易于调试
    3. 避免过度优化
    4. 支持动态因子加载
    """

    INTERFACE_VERSION = 3
    can_short = False  # 现货市场不支持做空

    timeframe = "15m"
    startup_candle_count = 100

    # 简单的风险管理
    minimal_roi = {"0": 0.05}  # 5% 止盈
    stoploss = -0.03  # 3% 止损

    def __init__(self, config: dict) -> None:
        """初始化策略"""
        super().__init__(config)
        # 初始化因子库
        self.factor_lib = FactorLibrary()
        # 使用评估通过的波动率因子
        self.factor_names = ["bb_width_20", "hist_vol_20", "keltner_width_20"]

    def populate_indicators(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        """计算因子 - 使用因子库动态加载"""
        dataframe = self.factor_lib.calculate_factors(dataframe, self.factor_names)
        return dataframe

    def populate_entry_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        """
        入场信号 - 基于波动率因子的简单规则

        逻辑：高波动率预示价格波动加大，适合入场
        做多条件: 波动率因子平均值 > 阈值
        """
        # 计算三个波动率因子的平均值（标准化后）
        dataframe['volatility_score'] = (
            dataframe['bb_width_20'] +
            dataframe['hist_vol_20'] +
            dataframe['keltner_width_20']
        ) / 3

        # 使用滚动分位数作为动态阈值
        dataframe['vol_threshold'] = dataframe['volatility_score'].rolling(100).quantile(0.7)

        dataframe.loc[
            (
                (dataframe['volatility_score'] > dataframe['vol_threshold']) &
                (dataframe['volume'] > 0)
            ),
            'enter_long'] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        """
        出场信号 - 基于波动率回落的简单规则

        逻辑：波动率回落预示价格波动减小，适合出场
        平多条件: 波动率因子平均值 < 阈值
        """
        # 使用滚动分位数作为动态阈值
        dataframe['vol_exit_threshold'] = dataframe['volatility_score'].rolling(100).quantile(0.3)

        dataframe.loc[
            (
                dataframe['volatility_score'] < dataframe['vol_exit_threshold']
            ),
            'exit_long'] = 1

        return dataframe
