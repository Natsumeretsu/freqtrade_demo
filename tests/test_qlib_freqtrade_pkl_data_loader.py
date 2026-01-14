from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd


# 让测试可直接导入 03_integration/trading_system（不依赖额外环境变量）
_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "03_integration"))


from trading_system.infrastructure.qlib.freqtrade_pkl_data_loader import FreqtradePklDataLoader  # noqa: E402


class TestFreqtradePklDataLoader(unittest.TestCase):
    def test_loader_returns_expected_multiindex(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve()
            exchange = "okx"
            timeframe = "4h"
            symbol = "BTC_USDT"

            outdir = (root / exchange / timeframe).resolve()
            outdir.mkdir(parents=True, exist_ok=True)

            n = 300
            dates = pd.date_range("2024-01-01", periods=n, freq="4h", tz="UTC")
            x = np.linspace(0.0, 12.0 * np.pi, num=n)
            close = 100.0 + 5.0 * np.sin(x)
            close = close + np.random.default_rng(42).normal(0.0, 0.2, size=n)
            close = np.maximum(1.0, close)

            open_ = np.roll(close, 1)
            open_[0] = close[0]
            high = np.maximum(open_, close) * (1.0 + 0.002)
            low = np.minimum(open_, close) * (1.0 - 0.002)
            vol = np.random.default_rng(1).uniform(100.0, 1000.0, size=n)

            df = pd.DataFrame(
                {
                    "date": dates,
                    "open": open_,
                    "high": high,
                    "low": low,
                    "close": close,
                    "volume": vol,
                }
            )
            df.to_pickle(outdir / f"{symbol}.pkl")

            loader = FreqtradePklDataLoader(
                data_root=root,
                exchange=exchange,
                timeframe=timeframe,
                feature_set="ml_core",
                feature_vars={},
                horizon=1,
                threshold=0.0,
                drop_na=True,
                label_name="LABEL0",
            )

            data = loader.load(instruments=[symbol])
            self.assertFalse(data.empty)

            self.assertTrue(isinstance(data.index, pd.MultiIndex))
            self.assertEqual(list(data.index.names), ["datetime", "instrument"])
            self.assertIn(symbol, set(data.index.get_level_values("instrument")))

            self.assertTrue(isinstance(data.columns, pd.MultiIndex))
            self.assertEqual(int(data.columns.nlevels), 2)
            self.assertIn("feature", set(data.columns.get_level_values(0)))
            self.assertIn("label", set(data.columns.get_level_values(0)))
            self.assertIn(("label", "LABEL0"), set(data.columns))

            y = data[("label", "LABEL0")].astype("float64")
            self.assertTrue(bool(y.notna().all()))
            self.assertTrue(bool(y.isin([0.0, 1.0]).all()))
