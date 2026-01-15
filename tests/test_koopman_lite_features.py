from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "03_integration"))

from trading_system.infrastructure.koopman_lite import compute_koopman_lite_features  # noqa: E402
from trading_system.infrastructure.factor_engines.talib_engine import TalibEngineParams, TalibFactorEngine  # noqa: E402


def _sample_ohlcv(n: int = 400) -> pd.DataFrame:
    rng = np.random.default_rng(7)
    close = 100 + np.cumsum(rng.normal(0, 0.6, size=n))
    high = close * (1.0 + np.abs(rng.normal(0.001, 0.001, size=n)))
    low = close * (1.0 - np.abs(rng.normal(0.001, 0.001, size=n)))
    vol = rng.uniform(100, 1000, size=n)
    return pd.DataFrame({"close": close, "high": high, "low": low, "volume": vol})


class TestKoopmanLiteFeatures(unittest.TestCase):
    def test_compute_koopman_lite_features_basic(self) -> None:
        df = _sample_ohlcv(500)
        feats = compute_koopman_lite_features(
            close=df["close"],
            window=96,
            embed_dim=8,
            stride=5,
            ridge=1e-3,
            pred_horizons=[1, 4],
            fft_window=96,
            fft_topk=6,
        )

        for col in [
            "fft_hp_logp",
            "fft_lp_slope",
            "fft_lp_energy_ratio",
            "koop_spectral_radius",
            "koop_fit_rmse",
            "koop_pred_ret_h1",
            "koop_pred_ret_h4",
        ]:
            self.assertIn(col, feats.columns)

        arr = feats.astype("float64").to_numpy()
        self.assertFalse(np.isinf(arr).any())

        # 过了窗口后应出现可用值（至少有一列出现有限数）
        tail = feats.iloc[200:].astype("float64")
        self.assertTrue(np.isfinite(tail.to_numpy()).any())

    def test_talib_engine_supports_and_compute_koopman_lite(self) -> None:
        df = _sample_ohlcv(500)
        engine = TalibFactorEngine(
            params=TalibEngineParams(
                koop_window=96,
                koop_embed_dim=8,
                koop_stride=5,
                koop_ridge=1e-3,
                fft_window=96,
                fft_topk=6,
            )
        )

        names = ["koop_spectral_radius", "koop_fit_rmse", "fft_lp_slope", "koop_pred_ret_h4"]
        for n in names:
            self.assertTrue(engine.supports(n))

        out = engine.compute(df, names)
        for n in names:
            self.assertIn(n, out.columns)
        self.assertEqual(len(out), len(df))


if __name__ == "__main__":
    unittest.main()

