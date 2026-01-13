from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd


_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "03_integration"))


from trading_system.infrastructure.ml.features import build_supervised_dataset, compute_features  # noqa: E402
from trading_system.infrastructure.ml.features import DEFAULT_FEATURE_COLUMNS, DEFAULT_FEATURE_SET_NAME  # noqa: E402
from trading_system.application.factor_sets import get_factor_templates, render_factor_names  # noqa: E402


def _sample_ohlcv(n: int = 200) -> pd.DataFrame:
    rng = np.random.default_rng(123)
    close = 100 + np.cumsum(rng.normal(0, 0.5, size=n))
    high = close * (1.0 + np.abs(rng.normal(0.001, 0.001, size=n)))
    low = close * (1.0 - np.abs(rng.normal(0.001, 0.001, size=n)))
    vol = rng.uniform(100, 1000, size=n)
    return pd.DataFrame({"close": close, "high": high, "low": low, "volume": vol})


class TestMlFeatures(unittest.TestCase):
    def test_compute_features_contains_cta_risk_columns(self) -> None:
        df = _sample_ohlcv(200)
        feats = compute_features(df)

        for col in ["ret_1", "ret_3", "ret_12", "vol_12", "skew_72", "kurt_72", "hl_range", "volume_z_72"]:
            self.assertIn(col, feats.columns)
        self.assertIn("ema_spread", feats.columns)

        arr = feats.astype("float64").to_numpy()
        self.assertFalse(np.isinf(arr).any())

    def test_default_features_follow_factor_set(self) -> None:
        templates = get_factor_templates(DEFAULT_FEATURE_SET_NAME)
        expected = render_factor_names(templates, {})
        self.assertEqual(DEFAULT_FEATURE_COLUMNS, expected)

    def test_build_supervised_dataset_with_cta_core(self) -> None:
        df = _sample_ohlcv(250)
        feature_cols = ["ret_1", "ret_3", "ret_12", "vol_12", "skew_72", "kurt_72", "volume_z_72", "hl_range"]
        X, y, cols = build_supervised_dataset(df, horizon=1, threshold=0.0, feature_cols=feature_cols)
        self.assertEqual(cols, feature_cols)
        self.assertFalse(X.empty)
        self.assertFalse(y.empty)


if __name__ == "__main__":
    unittest.main()
