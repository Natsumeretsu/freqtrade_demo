from __future__ import annotations

import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd


_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "03_integration"))


from trading_system.infrastructure.freqtrade_data import (  # noqa: E402
    build_macro_sma_informative_dataframe,
    cut_dataframe_upto_time,
)


class _DummyDP:
    def __init__(self, df: pd.DataFrame) -> None:
        self._df = df

    def get_pair_dataframe(self, *, pair: str, timeframe: str, candle_type: str | None = None):
        # 模拟 freqtrade dp.get_pair_dataframe 的最小行为
        return self._df


class TestFreqtradeData(unittest.TestCase):
    def test_cut_dataframe_upto_time_handles_date(self) -> None:
        df = pd.DataFrame(
            {
                "date": pd.to_datetime(["2020-01-01", "2020-01-02", "2020-01-03"], utc=True),
                "close": [1.0, 2.0, 3.0],
            }
        )
        out = cut_dataframe_upto_time(df, datetime(2020, 1, 2, tzinfo=timezone.utc))
        self.assertEqual(len(out), 2)

    def test_build_macro_sma_informative_dataframe(self) -> None:
        df = pd.DataFrame(
            {
                "date": pd.to_datetime(["2020-01-01", "2020-01-02", "2020-01-03"], utc=True),
                "close": [10.0, 20.0, 30.0],
                "volume": [1.0, 1.0, 1.0],
            }
        )
        dp = _DummyDP(df)
        out = build_macro_sma_informative_dataframe(dp, pair="BTC/USDT", timeframe="1d", sma_period=2)
        self.assertIsNotNone(out)
        assert out is not None
        self.assertEqual(list(out.columns), ["date", "macro_close", "macro_sma"])
        self.assertTrue(np.isfinite(float(out["macro_close"].iloc[-1])))
        # rolling(2).mean()：最后一行 (20+30)/2=25
        self.assertAlmostEqual(float(out["macro_sma"].iloc[-1]), 25.0, places=6)

    def test_build_macro_sma_informative_dataframe_missing_columns(self) -> None:
        df = pd.DataFrame({"close": [1.0, 2.0, 3.0]})
        dp = _DummyDP(df)
        out = build_macro_sma_informative_dataframe(dp, pair="BTC/USDT", timeframe="1d", sma_period=2)
        self.assertIsNone(out)


if __name__ == "__main__":
    unittest.main()

