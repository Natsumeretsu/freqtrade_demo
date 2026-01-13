from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd


_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "03_integration"))


from trading_system.application.factor_usecase import FactorComputationUseCase  # noqa: E402
from trading_system.infrastructure.factor_engines.talib_engine import TalibFactorEngine  # noqa: E402


def _sample_ohlcv(n: int = 200) -> pd.DataFrame:
    rng = np.random.default_rng(42)
    close = 100 + np.cumsum(rng.normal(0, 0.5, size=n))
    high = close * (1.0 + np.abs(rng.normal(0.001, 0.001, size=n)))
    low = close * (1.0 - np.abs(rng.normal(0.001, 0.001, size=n)))
    vol = rng.uniform(100, 1000, size=n)
    return pd.DataFrame({"close": close, "high": high, "low": low, "volume": vol})


class TestFactorUsecase(unittest.TestCase):
    def test_execute_overwrites_existing_columns(self) -> None:
        df = _sample_ohlcv(200)
        df["ema_short_10"] = 0.0

        engine = TalibFactorEngine()
        uc = FactorComputationUseCase(engine)
        out = uc.execute(df, ["ema_short_10"])
        expected = engine.compute(df, ["ema_short_10"])

        self.assertIn("ema_short_10", out.columns)
        self.assertTrue(out["ema_short_10"].equals(expected["ema_short_10"]))

    def test_execute_unsupported_raises(self) -> None:
        df = _sample_ohlcv(50)
        engine = TalibFactorEngine()
        uc = FactorComputationUseCase(engine)
        with self.assertRaises(ValueError):
            uc.execute(df, ["unsupported_factor_name"])


if __name__ == "__main__":
    unittest.main()

