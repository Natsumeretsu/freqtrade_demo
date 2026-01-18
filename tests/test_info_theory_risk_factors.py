"""测试信息论/风险/流动性因子（来源：docs/knowledge）"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "03_integration"))

from trading_system.infrastructure.factor_engines.talib_engine import TalibFactorEngine


class TestInfoTheoryRiskFactors(unittest.TestCase):
    """测试新增的信息论/风险/流动性因子"""

    @classmethod
    def setUpClass(cls) -> None:
        np.random.seed(42)
        n = 200
        dates = pd.date_range("2024-01-01", periods=n, freq="1h")
        close = 100 + np.cumsum(np.random.randn(n) * 0.5)
        high = close + np.abs(np.random.randn(n) * 0.3)
        low = close - np.abs(np.random.randn(n) * 0.3)
        open_price = close + np.random.randn(n) * 0.2
        volume = np.abs(np.random.randn(n) * 1000 + 5000)

        cls.data = pd.DataFrame(
            {
                "open": open_price,
                "high": high,
                "low": low,
                "close": close,
                "volume": volume,
            },
            index=dates,
        )
        cls.engine = TalibFactorEngine()

    def test_bucket_entropy_supported(self) -> None:
        self.assertTrue(self.engine.supports("bucket_entropy_24"))
        self.assertTrue(self.engine.supports("bucket_entropy_72"))

    def test_hurst_supported(self) -> None:
        self.assertTrue(self.engine.supports("hurst_48"))
        self.assertTrue(self.engine.supports("hurst_96"))

    def test_gap_supported(self) -> None:
        self.assertTrue(self.engine.supports("gap_24"))

    def test_tail_ratio_supported(self) -> None:
        self.assertTrue(self.engine.supports("tail_ratio_48"))
        self.assertTrue(self.engine.supports("tail_ratio_96"))

    def test_price_impact_supported(self) -> None:
        self.assertTrue(self.engine.supports("price_impact_24"))
        self.assertTrue(self.engine.supports("price_impact_72"))

    def test_bucket_entropy_compute(self) -> None:
        result = self.engine.compute(self.data, ["bucket_entropy_24", "bucket_entropy_72"])
        self.assertEqual(len(result.columns), 2)
        self.assertIn("bucket_entropy_24", result.columns)
        self.assertIn("bucket_entropy_72", result.columns)
        # 熵值应在 [0, 1] 范围内
        valid = result["bucket_entropy_24"].dropna()
        self.assertTrue(len(valid) > 0)
        self.assertTrue((valid >= 0).all() and (valid <= 1).all())

    def test_hurst_compute(self) -> None:
        result = self.engine.compute(self.data, ["hurst_48", "hurst_96"])
        self.assertEqual(len(result.columns), 2)
        valid = result["hurst_48"].dropna()
        self.assertTrue(len(valid) > 0)
        # Hurst 指数通常在 (0, 1) 范围内
        self.assertTrue((valid > 0).all() and (valid < 1.5).all())

    def test_gap_compute(self) -> None:
        result = self.engine.compute(self.data, ["gap_24"])
        self.assertEqual(len(result.columns), 1)
        valid = result["gap_24"].dropna()
        self.assertTrue(len(valid) > 0)

    def test_tail_ratio_compute(self) -> None:
        result = self.engine.compute(self.data, ["tail_ratio_48", "tail_ratio_96"])
        self.assertEqual(len(result.columns), 2)
        valid = result["tail_ratio_48"].dropna()
        self.assertTrue(len(valid) > 0)
        # 尾部比率应为正数
        self.assertTrue((valid > 0).all())

    def test_price_impact_compute(self) -> None:
        result = self.engine.compute(self.data, ["price_impact_24", "price_impact_72"])
        self.assertEqual(len(result.columns), 2)
        valid = result["price_impact_24"].dropna()
        self.assertTrue(len(valid) > 0)
        # 价格冲击应为正数
        self.assertTrue((valid >= 0).all())

    def test_all_new_factors_together(self) -> None:
        factors = [
            "bucket_entropy_24",
            "bucket_entropy_72",
            "hurst_48",
            "hurst_96",
            "gap_24",
            "tail_ratio_48",
            "tail_ratio_96",
            "price_impact_24",
            "price_impact_72",
        ]
        result = self.engine.compute(self.data, factors)
        self.assertEqual(len(result.columns), len(factors))
        for f in factors:
            self.assertIn(f, result.columns)


if __name__ == "__main__":
    unittest.main()
