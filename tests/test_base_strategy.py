"""策略基类单元测试"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "01_freqtrade"))

from strategies.base_strategy import BaseStrategy, TrendStrategy


class TestBaseStrategy(unittest.TestCase):
    def test_base_strategy_attributes(self) -> None:
        """测试基类属性"""
        # 创建一个简单的子类用于测试
        class TestStrategy(BaseStrategy):
            timeframe = "1h"

            def populate_indicators(self, dataframe, metadata):
                return dataframe

            def populate_entry_trend(self, dataframe, metadata):
                dataframe["enter_long"] = 0
                return dataframe

            def populate_exit_trend(self, dataframe, metadata):
                dataframe["exit_long"] = 0
                return dataframe

        config = {"stake_currency": "USDT"}
        strategy = TestStrategy(config)

        # 验证公共属性
        self.assertEqual(strategy.INTERFACE_VERSION, 3)
        self.assertEqual(strategy.minimal_roi, {"0": 100})
        self.assertEqual(strategy.stoploss, -0.10)
        self.assertTrue(strategy.use_exit_signal)
        self.assertFalse(strategy.exit_profit_only)


if __name__ == "__main__":
    unittest.main()
