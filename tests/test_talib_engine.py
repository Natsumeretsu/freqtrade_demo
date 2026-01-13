from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd


_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "03_integration"))


from trading_system.infrastructure.factor_engines.talib_engine import TalibFactorEngine  # noqa: E402


def _sample_ohlcv(n: int = 200) -> pd.DataFrame:
    rng = np.random.default_rng(7)
    close = 100 + np.cumsum(rng.normal(0, 0.5, size=n))
    high = close * (1.0 + np.abs(rng.normal(0.001, 0.001, size=n)))
    low = close * (1.0 - np.abs(rng.normal(0.001, 0.001, size=n)))
    vol = rng.uniform(100, 1000, size=n)
    return pd.DataFrame({"close": close, "high": high, "low": low, "volume": vol})


class TestTalibFactorEngine(unittest.TestCase):
    def test_compute_outputs_expected_columns(self) -> None:
        df = _sample_ohlcv(200)
        engine = TalibFactorEngine()

        factors = engine.compute(
            df,
            [
                "ema_short_10",
                "ema_long_20",
                "adx",
                "atr",
                "atr_pct",
                "macdhist",
                "volume_ratio_72",
            ],
        )

        self.assertIn("ema_short_10", factors.columns)
        self.assertIn("ema_long_20", factors.columns)
        self.assertIn("adx", factors.columns)
        self.assertIn("atr", factors.columns)
        self.assertIn("atr_pct", factors.columns)
        self.assertIn("macd", factors.columns)
        self.assertIn("macdsignal", factors.columns)
        self.assertIn("macdhist", factors.columns)
        self.assertIn("volume_ratio", factors.columns)

        arr = factors.astype("float64").to_numpy()
        self.assertFalse(np.isinf(arr).any())

    def test_compute_cta_core_factors(self) -> None:
        df = _sample_ohlcv(200)
        engine = TalibFactorEngine()

        factor_names = ["ret_1", "ret_3", "ret_12", "vol_12", "skew_72", "kurt_72", "volume_z_72", "hl_range"]
        factors = engine.compute(df, factor_names)

        for name in factor_names:
            self.assertTrue(engine.supports(name))
            self.assertIn(name, factors.columns)

        arr = factors.astype("float64").to_numpy()
        self.assertFalse(np.isinf(arr).any())

    def test_compute_ema_spread_factor(self) -> None:
        df = _sample_ohlcv(200)
        engine = TalibFactorEngine()

        self.assertTrue(engine.supports("ema_spread"))
        factors = engine.compute(df, ["ema_spread"])
        self.assertIn("ema_spread", factors.columns)

        arr = factors.astype("float64").to_numpy()
        self.assertFalse(np.isinf(arr).any())

    def test_missing_required_columns_raises(self) -> None:
        engine = TalibFactorEngine()
        with self.assertRaises(ValueError):
            engine.compute(pd.DataFrame({"close": [1.0]}), ["adx"])


if __name__ == "__main__":
    unittest.main()
