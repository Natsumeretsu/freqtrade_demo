"""
简化的策略模板 - MVP版本

只使用经过验证的因子，避免过度复杂的逻辑。
"""

from __future__ import annotations

from freqtrade.strategy import IStrategy
import pandas as pd

# 导入简化的因子模块
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "03_integration"))

from simple_factors.basic_factors import calculate_all_factors


class SimpleMVPStrategy(IStrategy):
    """
    简化的MVP策略模板

    设计原则：
    1. 只使用经过验证的因子
    2. 逻辑清晰，易于调试
    3. 避免过度优化
    """

    INTERFACE_VERSION = 3
    can_short = True

    timeframe = "15m"
    startup_candle_count = 100

    # 简单的风险管理
    minimal_roi = {"0": 0.05}  # 5% 止盈
    stoploss = -0.03  # 3% 止损

    def populate_indicators(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        """计算因子"""
        dataframe = calculate_all_factors(dataframe)
        return dataframe

    def populate_entry_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        """入场信号 - 待实现"""
        # TODO: 根据验证通过的因子实现入场逻辑
        dataframe['enter_long'] = 0
        dataframe['enter_short'] = 0
        return dataframe

    def populate_exit_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        """出场信号 - 待实现"""
        dataframe['exit_long'] = 0
        dataframe['exit_short'] = 0
        return dataframe
