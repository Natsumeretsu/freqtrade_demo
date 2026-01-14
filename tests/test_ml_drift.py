from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd


_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "03_integration"))


from trading_system.infrastructure.ml.drift import DriftThresholds, build_feature_baseline, evaluate_feature_drift  # noqa: E402


class TestMlDrift(unittest.TestCase):
    def test_build_feature_baseline_has_bins_and_ref(self) -> None:
        rng = np.random.default_rng(123)
        X = pd.DataFrame({"x": rng.normal(0, 1, size=500)})
        baseline = build_feature_baseline(X, quantile_bins=10, metadata={"foo": "bar"})

        self.assertEqual(baseline.get("version"), 1)
        self.assertIn("created_at", baseline)
        self.assertEqual(baseline.get("quantile_bins"), 10)
        self.assertEqual(baseline.get("metadata", {}).get("foo"), "bar")

        feat = baseline.get("features", {}).get("x", {})
        self.assertGreaterEqual(int(feat.get("count", 0)), 400)
        self.assertIsInstance(feat.get("psi_bins"), list)
        self.assertIsInstance(feat.get("psi_ref"), list)
        self.assertGreaterEqual(len(feat.get("psi_bins", [])), 2)
        self.assertEqual(len(feat.get("psi_bins", [])) - 1, len(feat.get("psi_ref", [])))

    def test_evaluate_feature_drift_detects_mean_shift(self) -> None:
        rng = np.random.default_rng(1)
        X_train = pd.DataFrame({"x": rng.normal(0, 1, size=800)})
        baseline = build_feature_baseline(X_train, quantile_bins=10)

        # 明显均值漂移
        X_now = pd.DataFrame({"x": rng.normal(5, 1, size=400)})
        report = evaluate_feature_drift(X_now, baseline=baseline)

        fx = report.get("features", {}).get("x", {})
        self.assertIn(fx.get("status"), {"warn", "crit"})
        self.assertIsNotNone(fx.get("psi"))

    def test_evaluate_feature_drift_detects_missing_rate(self) -> None:
        rng = np.random.default_rng(7)
        X_train = pd.DataFrame({"x": rng.normal(0, 1, size=500)})
        baseline = build_feature_baseline(X_train, quantile_bins=10)

        # 缺失率触发
        x = rng.normal(0, 1, size=200).astype("float64")
        x[:120] = np.nan
        X_now = pd.DataFrame({"x": x})

        th = DriftThresholds(missing_warn=0.05, missing_crit=0.20)
        report = evaluate_feature_drift(X_now, baseline=baseline, thresholds=th)
        fx = report.get("features", {}).get("x", {})
        self.assertEqual(fx.get("status"), "crit")

    def test_evaluate_feature_drift_missing_column_is_crit(self) -> None:
        rng = np.random.default_rng(9)
        X_train = pd.DataFrame({"x": rng.normal(0, 1, size=400), "y": rng.normal(0, 1, size=400)})
        baseline = build_feature_baseline(X_train, quantile_bins=10)

        X_now = pd.DataFrame({"x": rng.normal(0, 1, size=100)})
        report = evaluate_feature_drift(X_now, baseline=baseline)

        self.assertEqual(report.get("status"), "crit")
        fy = report.get("features", {}).get("y", {})
        self.assertEqual(fy.get("status"), "missing_column")


if __name__ == "__main__":
    unittest.main()
