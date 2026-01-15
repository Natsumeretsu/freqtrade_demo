"""
test_data_quality.py - 数据质量检查模块单元测试
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "03_integration"))

from trading_system.infrastructure.data_quality import (
    DataQualityChecker,
    QualityConfig,
)


class TestDataQualityChecker(unittest.TestCase):
    def test_empty_dataframe(self) -> None:
        checker = DataQualityChecker()
        report = checker.check(pd.DataFrame())
        self.assertFalse(report.passed)
        self.assertEqual(len(report.issues), 1)
        self.assertEqual(report.issues[0].category, "empty")

    def test_missing_columns(self) -> None:
        df = pd.DataFrame({"open": [1, 2], "close": [1, 2]})
        checker = DataQualityChecker()
        report = checker.check(df)
        self.assertFalse(report.passed)
        schema_issues = [i for i in report.issues if i.category == "schema"]
        self.assertEqual(len(schema_issues), 1)

    def test_valid_ohlcv(self) -> None:
        idx = pd.date_range("2024-01-01", periods=100, freq="1h", tz="UTC")
        df = pd.DataFrame({
            "open": np.random.randn(100) + 100,
            "high": np.random.randn(100) + 101,
            "low": np.random.randn(100) + 99,
            "close": np.random.randn(100) + 100,
            "volume": np.abs(np.random.randn(100)) * 1000,
        }, index=idx)
        checker = DataQualityChecker()
        report = checker.check(df)
        self.assertTrue(report.passed)

    def test_missing_values_warning(self) -> None:
        idx = pd.date_range("2024-01-01", periods=100, freq="1h", tz="UTC")
        df = pd.DataFrame({
            "open": [1.0] * 100,
            "high": [2.0] * 100,
            "low": [0.5] * 100,
            "close": [1.5] * 98 + [np.nan, np.nan],
            "volume": [100.0] * 100,
        }, index=idx)
        checker = DataQualityChecker()
        report = checker.check(df)
        missing_issues = [i for i in report.issues if i.category == "missing"]
        self.assertGreater(len(missing_issues), 0)

    def test_duplicate_timestamps(self) -> None:
        idx = pd.to_datetime(["2024-01-01", "2024-01-01", "2024-01-02"])
        df = pd.DataFrame({
            "open": [1, 2, 3],
            "high": [2, 3, 4],
            "low": [0, 1, 2],
            "close": [1.5, 2.5, 3.5],
            "volume": [100, 200, 300],
        }, index=idx)
        checker = DataQualityChecker()
        report = checker.check(df)
        dup_issues = [i for i in report.issues if i.category == "duplicate"]
        self.assertEqual(len(dup_issues), 1)


if __name__ == "__main__":
    unittest.main()
