"""并行化因子计算单元测试"""
from __future__ import annotations

import sys
import time
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "03_integration"))

from trading_system.infrastructure.factor_engines.parallel_computer import (
    ParallelConfig,
    ParallelFactorComputer,
)


def _mock_compute_func(data: pd.DataFrame, factor_name: str) -> pd.Series:
    """模拟因子计算函数"""
    # 模拟计算延迟
    time.sleep(0.01)

    if factor_name == "ema_10":
        return data["close"].ewm(span=10, adjust=False).mean()
    elif factor_name == "ema_20":
        return data["close"].ewm(span=20, adjust=False).mean()
    elif factor_name == "ret_1":
        return data["close"].pct_change(1)
    elif factor_name == "vol_20":
        ret = data["close"].pct_change(1)
        return ret.rolling(20).std()
    elif factor_name == "rsi_14":
        # 简化的 RSI 计算
        delta = data["close"].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss.replace(0, np.nan)
        return 100 - (100 / (1 + rs))
    else:
        return pd.Series(index=data.index, dtype=float)


class TestParallelFactorComputer(unittest.TestCase):
    def setUp(self) -> None:
        """准备测试数据"""
        np.random.seed(42)
        dates = pd.date_range("2024-01-01", periods=100, freq="1h")
        self.data = pd.DataFrame({
            "close": 100 + np.cumsum(np.random.randn(100) * 0.5),
            "high": 101 + np.cumsum(np.random.randn(100) * 0.5),
            "low": 99 + np.cumsum(np.random.randn(100) * 0.5),
            "volume": np.random.randint(1000, 10000, 100),
        }, index=dates)

    def test_serial_computation(self) -> None:
        """测试串行计算"""
        config = ParallelConfig(enabled=False)
        computer = ParallelFactorComputer(config)

        factor_names = ["ema_10", "ema_20", "ret_1"]
        results = computer.compute_parallel(self.data, factor_names, _mock_compute_func)

        self.assertEqual(len(results), 3)
        self.assertIn("ema_10", results)
        self.assertIn("ema_20", results)
        self.assertIn("ret_1", results)
        self.assertEqual(len(results["ema_10"]), 100)


if __name__ == "__main__":
    unittest.main()
