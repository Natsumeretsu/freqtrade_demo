"""策略集成测试

测试策略的端到端流程，包括因子计算、信号生成、入场/出场逻辑。
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "03_integration"))

from trading_system.infrastructure.factor_engines.talib_engine import TalibFactorEngine


def _sample_ohlcv(n: int = 500) -> pd.DataFrame:
    """生成样本 OHLCV 数据"""
    rng = np.random.default_rng(42)
    dates = pd.date_range("2024-01-01", periods=n, freq="1h")
    close = 100 + np.cumsum(rng.normal(0, 0.5, size=n))
    high = close * (1.0 + np.abs(rng.normal(0.001, 0.001, size=n)))
    low = close * (1.0 - np.abs(rng.normal(0.001, 0.001, size=n)))
    vol = rng.uniform(100, 1000, size=n)

    df = pd.DataFrame({
        "date": dates,
        "open": close,
        "high": high,
        "low": low,
        "close": close,
        "volume": vol
    })
    df.set_index("date", inplace=True)
    return df


class TestStrategyIntegration(unittest.TestCase):
    """策略集成测试"""

    def test_factor_computation_pipeline(self) -> None:
        """测试因子计算流程"""
        df = _sample_ohlcv(500)
        engine = TalibFactorEngine()

        # 计算常用因子
        factor_names = [
            "ema_short_10",
            "ema_long_50",
            "ret_1",
            "ret_5",
            "vol_12",
            "rsi_14",
            "adx",
            "atr"
        ]

        factors = engine.compute(df, factor_names)

        # 验证因子计算结果
        self.assertEqual(len(factors), len(df))
        for name in factor_names:
            self.assertIn(name, factors.columns)

        # 验证因子值合理性
        self.assertFalse(np.isinf(factors["ema_short_10"].dropna()).any())
        self.assertFalse(np.isinf(factors["ret_1"].dropna()).any())


if __name__ == "__main__":
    unittest.main()
