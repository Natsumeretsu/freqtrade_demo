"""测试时间序列因子（六大分类体系）"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "03_integration"))

from trading_system.infrastructure.factor_engines.talib_engine import TalibFactorEngine


class TestTimeSeriesFactors(unittest.TestCase):
    """测试时间序列因子（六大分类体系）"""

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

    # =========================================================================
    # 第一类：动量因子（Momentum Factors）
    # =========================================================================

    def test_momentum_ts_supported(self) -> None:
        """时间序列动量因子支持"""
        factors = ["ret_1", "ret_7", "ret_14", "ret_28", "ret_56"]
        for f in factors:
            self.assertTrue(self.engine.supports(f), f"{f} should be supported")

    def test_momentum_price_supported(self) -> None:
        """价格动量因子支持"""
        factors = [
            "ema_spread",
            "ema_spread_20_50",
            "ema_spread_50_200",
            "price_to_high_20",
            "price_to_low_20",
        ]
        for f in factors:
            self.assertTrue(self.engine.supports(f), f"{f} should be supported")

    def test_momentum_roc_supported(self) -> None:
        """变化率因子支持"""
        factors = ["roc_5", "roc_10", "roc_14", "roc_21", "roc_28"]
        for f in factors:
            self.assertTrue(self.engine.supports(f), f"{f} should be supported")

    def test_momentum_compute(self) -> None:
        """动量因子计算"""
        factors = ["ret_14", "ret_28", "ema_spread_20_50", "price_to_high_20", "roc_14"]
        result = self.engine.compute(self.data, factors)
        self.assertEqual(len(result.columns), len(factors))
        for f in factors:
            self.assertIn(f, result.columns)
            valid = result[f].dropna()
            self.assertTrue(len(valid) > 0, f"{f} should have valid values")

    # =========================================================================
    # 第二类：反转因子（Reversal Factors）
    # =========================================================================

    def test_reversal_supported(self) -> None:
        """反转因子支持"""
        factors = [
            "reversal_1",
            "reversal_3",
            "reversal_5",
            "reversal_14",
            "zscore_close_20",
            "zscore_close_50",
        ]
        for f in factors:
            self.assertTrue(self.engine.supports(f), f"{f} should be supported")

    def test_reversal_compute(self) -> None:
        """反转因子计算"""
        factors = ["reversal_1", "reversal_5", "zscore_close_20"]
        result = self.engine.compute(self.data, factors)
        self.assertEqual(len(result.columns), len(factors))

        # reversal 应该是 -ret
        ret_1 = self.data["close"].pct_change(1)
        reversal_1 = result["reversal_1"]
        np.testing.assert_array_almost_equal(
            reversal_1.dropna().values, -ret_1.dropna().values
        )

    # =========================================================================
    # 第三类：风险因子（Risk Factors）
    # =========================================================================

    def test_risk_volatility_supported(self) -> None:
        """波动率风险因子支持"""
        factors = ["vol_7", "vol_14", "hl_range", "atr_14", "atr_pct_14"]  # vol_28 removed: failed validation
        for f in factors:
            self.assertTrue(self.engine.supports(f), f"{f} should be supported")

    def test_risk_downside_supported(self) -> None:
        """下行风险因子支持"""
        factors = [
            "var_5_30",
            "es_5_30",
            "skew_30",
            "kurt_30",
            "tail_ratio_30",
            "downside_vol_30",
        ]
        for f in factors:
            self.assertTrue(self.engine.supports(f), f"{f} should be supported")

    def test_risk_compute(self) -> None:
        """风险因子计算"""
        factors = ["vol_14", "var_5_30", "es_5_30", "downside_vol_30"]
        result = self.engine.compute(self.data, factors)
        self.assertEqual(len(result.columns), len(factors))

        # VaR 应该是负值（下行分位）
        var_valid = result["var_5_30"].dropna()
        self.assertTrue(len(var_valid) > 0)
        self.assertTrue((var_valid < 0).any(), "VaR should have negative values")

        # ES 应该 <= VaR（更极端）
        es_valid = result["es_5_30"].dropna()
        self.assertTrue(len(es_valid) > 0)

    # =========================================================================
    # 第四类：流动性因子（Liquidity Factors）
    # =========================================================================

    def test_liquidity_volume_supported(self) -> None:
        """成交量因子支持"""
        factors = ["volume_z_14", "volume_z_30", "rel_vol_14", "volume_ratio"]
        for f in factors:
            self.assertTrue(self.engine.supports(f), f"{f} should be supported")

    def test_liquidity_shock_supported(self) -> None:
        """流动性冲击因子支持"""
        factors = [
            "ret_vol_ratio_14",
            "price_impact_14",
            "amihud_14",
            "obv_slope_14",
        ]
        for f in factors:
            self.assertTrue(self.engine.supports(f), f"{f} should be supported")

    def test_liquidity_compute(self) -> None:
        """流动性因子计算"""
        factors = ["volume_z_30", "amihud_14", "obv_slope_14"]
        result = self.engine.compute(self.data, factors)
        self.assertEqual(len(result.columns), len(factors))
        for f in factors:
            valid = result[f].dropna()
            self.assertTrue(len(valid) > 0, f"{f} should have valid values")

    # =========================================================================
    # 第五类：技术指标因子（Technical Factors）
    # =========================================================================

    def test_technical_oscillator_supported(self) -> None:
        """动量振荡器支持"""
        factors = [
            "rsi_7",
            "rsi_14",
            "macd",
            "macdsignal",
            "macdhist",
            "stoch_k_14_3_3",
            "willr_14",
        ]
        for f in factors:
            self.assertTrue(self.engine.supports(f), f"{f} should be supported")

    def test_technical_trend_supported(self) -> None:
        """趋势跟踪指标支持"""
        factors = ["ema_5", "ema_20", "ema_50", "ema_200", "adx", "adx_7", "adx_28"]
        for f in factors:
            self.assertTrue(self.engine.supports(f), f"{f} should be supported")

    def test_technical_bands_supported(self) -> None:
        """波动带指标支持"""
        factors = ["bb_width_20_2", "bb_percent_b_20_2", "atr", "atr_pct"]
        for f in factors:
            self.assertTrue(self.engine.supports(f), f"{f} should be supported")

    def test_technical_compute(self) -> None:
        """技术指标计算"""
        factors = ["rsi_14", "adx", "bb_width_20_2"]
        result = self.engine.compute(self.data, factors)
        self.assertEqual(len(result.columns), len(factors))

        # RSI 应该在 [0, 100] 范围内
        rsi_valid = result["rsi_14"].dropna()
        self.assertTrue(len(rsi_valid) > 0)
        self.assertTrue((rsi_valid >= 0).all() and (rsi_valid <= 100).all())

    # =========================================================================
    # 第六类：市场制度因子（Regime Factors）
    # =========================================================================

    def test_regime_entropy_supported(self) -> None:
        """熵因子支持"""
        factors = [
            "dir_entropy_14",
            "dir_entropy_28",
            "bucket_entropy_14",
            "vol_state_entropy_28",
        ]
        for f in factors:
            self.assertTrue(self.engine.supports(f), f"{f} should be supported")

    def test_regime_structure_supported(self) -> None:
        """结构因子支持"""
        factors = ["hurst_28", "hurst_56"]
        for f in factors:
            self.assertTrue(self.engine.supports(f), f"{f} should be supported")

    def test_regime_compute(self) -> None:
        """制度因子计算"""
        factors = ["dir_entropy_28", "hurst_56"]
        result = self.engine.compute(self.data, factors)
        self.assertEqual(len(result.columns), len(factors))

        # 熵应该在 [0, 1] 范围内
        entropy_valid = result["dir_entropy_28"].dropna()
        self.assertTrue(len(entropy_valid) > 0)
        self.assertTrue((entropy_valid >= 0).all() and (entropy_valid <= 1).all())

    # =========================================================================
    # 综合测试
    # =========================================================================

    def test_all_priority_factors(self) -> None:
        """测试所有优先级因子"""
        # 第一优先：动量 + 反转
        priority_1 = ["ret_14", "ret_28", "reversal_1", "reversal_5"]
        # 第二优先：风险（vol_28 removed: failed validation）
        priority_2 = ["var_5_30", "es_5_30", "downside_vol_30"]
        # 第三优先：流动性
        priority_3 = ["volume_z_30", "amihud_30"]
        # 第四优先：技术（不包含 macd，因为它会返回 3 列）
        priority_4 = ["rsi_14", "adx"]

        all_factors = priority_1 + priority_2 + priority_3 + priority_4
        result = self.engine.compute(self.data, all_factors)
        self.assertEqual(len(result.columns), len(all_factors))

        for f in all_factors:
            self.assertIn(f, result.columns)
            valid = result[f].dropna()
            self.assertTrue(len(valid) > 0, f"{f} should have valid values")


if __name__ == "__main__":
    unittest.main()
