"""因子计算器单元测试"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "03_integration"))

from trading_system.infrastructure.factor_engines.factor_computer import (
    FactorComputerRegistry,
)
from trading_system.infrastructure.factor_engines.ema_computer import EMAFactorComputer
from trading_system.infrastructure.factor_engines.momentum_computer import MomentumFactorComputer
from trading_system.infrastructure.factor_engines.volatility_computer import VolatilityFactorComputer
from trading_system.infrastructure.factor_engines.technical_computer import TechnicalFactorComputer
from trading_system.infrastructure.factor_engines.bollinger_computer import BollingerFactorComputer
from trading_system.infrastructure.factor_engines.volume_computer import VolumeFactorComputer


def _sample_ohlcv(n: int = 200) -> pd.DataFrame:
    rng = np.random.default_rng(7)
    close = 100 + np.cumsum(rng.normal(0, 0.5, size=n))
    high = close * (1.0 + np.abs(rng.normal(0.001, 0.001, size=n)))
    low = close * (1.0 - np.abs(rng.normal(0.001, 0.001, size=n)))
    vol = rng.uniform(100, 1000, size=n)
    return pd.DataFrame({"close": close, "high": high, "low": low, "volume": vol})


class TestFactorComputers(unittest.TestCase):
    def test_ema_computer(self) -> None:
        """测试 EMA 因子计算器"""
        df = _sample_ohlcv(200)
        computer = EMAFactorComputer()

        # 测试 can_compute
        self.assertTrue(computer.can_compute("ema_short_10"))
        self.assertTrue(computer.can_compute("ema_long_50"))
        self.assertTrue(computer.can_compute("ema_20"))
        self.assertTrue(computer.can_compute("ema_spread"))
        self.assertFalse(computer.can_compute("ret_1"))

        # 测试 compute
        result = computer.compute(df, "ema_short_10")
        self.assertEqual(len(result), len(df))
        self.assertFalse(np.isinf(result.dropna()).any())

    def test_momentum_computer(self) -> None:
        """测试动量因子计算器"""
        df = _sample_ohlcv(200)
        computer = MomentumFactorComputer()

        # 测试 can_compute
        self.assertTrue(computer.can_compute("ret_1"))
        self.assertTrue(computer.can_compute("ret_5"))
        self.assertTrue(computer.can_compute("roc_10"))
        self.assertFalse(computer.can_compute("ema_10"))

        # 测试 compute
        result = computer.compute(df, "ret_1")
        self.assertEqual(len(result), len(df))
        self.assertFalse(np.isinf(result.dropna()).any())

    def test_technical_computer(self) -> None:
        """测试技术指标因子计算器"""
        df = _sample_ohlcv(200)
        computer = TechnicalFactorComputer()

        # 测试 can_compute
        self.assertTrue(computer.can_compute("rsi_14"))
        self.assertTrue(computer.can_compute("cci_20"))
        self.assertTrue(computer.can_compute("mfi_14"))
        self.assertFalse(computer.can_compute("ema_10"))

        # 测试 compute
        result = computer.compute(df, "rsi_14")
        self.assertEqual(len(result), len(df))
        self.assertFalse(np.isinf(result.dropna()).any())

    def test_bollinger_computer(self) -> None:
        """测试布林带因子计算器"""
        df = _sample_ohlcv(200)
        computer = BollingerFactorComputer()

        # 测试 can_compute
        self.assertTrue(computer.can_compute("bb_width_20_2"))
        self.assertTrue(computer.can_compute("bb_percent_b_20_2"))
        self.assertFalse(computer.can_compute("ema_10"))

        # 测试 compute
        result = computer.compute(df, "bb_width_20_2")
        self.assertEqual(len(result), len(df))
        self.assertFalse(np.isinf(result.dropna()).any())

    def test_volume_computer(self) -> None:
        """测试成交量因子计算器"""
        df = _sample_ohlcv(200)
        computer = VolumeFactorComputer()

        # 测试 can_compute
        self.assertTrue(computer.can_compute("volume_ratio"))
        self.assertTrue(computer.can_compute("volume_z_20"))
        self.assertTrue(computer.can_compute("rel_vol_10"))
        self.assertFalse(computer.can_compute("ema_10"))

        # 测试 compute
        result = computer.compute(df, "volume_z_20")
        self.assertEqual(len(result), len(df))
        self.assertFalse(np.isinf(result.dropna()).any())


if __name__ == "__main__":
    unittest.main()
