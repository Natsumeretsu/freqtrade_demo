from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd


_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "03_integration"))


from trading_system.application.entry_gates import (  # noqa: E402
    atr_pct_range_ok,
    ema_trend_ok,
    macro_sma_regime_ok,
    momentum_ok,
    price_not_too_far_from_ema,
    volume_ratio_min_ok,
)


class TestEntryGates(unittest.TestCase):
    def test_ema_trend_ok_up_and_down(self) -> None:
        ema = pd.Series([10.0, 10.5, 11.0, 11.6])
        up = ema_trend_ok(ema, lookback=1, min_slope=0.02, direction="up")
        self.assertEqual(bool(up.iloc[-1]), True)

        down_ema = pd.Series([10.0, 9.8, 9.6, 9.4])
        down = ema_trend_ok(down_ema, lookback=1, min_slope=0.01, direction="down")
        self.assertEqual(bool(down.iloc[-1]), True)

    def test_atr_pct_range_ok_min_and_max(self) -> None:
        df = pd.DataFrame({"atr_pct": [0.001, 0.01, 0.05]})
        ok = atr_pct_range_ok(df, min_pct=0.004, use_max_filter=True, max_pct=0.02)
        self.assertEqual(ok.tolist(), [False, True, False])

    def test_volume_ratio_min_ok(self) -> None:
        df = pd.DataFrame({"volume_ratio": [0.5, 0.9, 1.1]})
        ok = volume_ratio_min_ok(df, enabled=True, min_ratio=0.8, require_column=True, fail_open=False)
        self.assertEqual(ok.tolist(), [False, True, True])

        # 未启用：全 True
        ok2 = volume_ratio_min_ok(df, enabled=False, min_ratio=0.8, require_column=True, fail_open=False)
        self.assertTrue(all(bool(x) for x in ok2.tolist()))

        # 缺列：按 require_column + fail_open 决定
        df2 = pd.DataFrame({"close": [1.0, 2.0]})
        ok3 = volume_ratio_min_ok(df2, enabled=True, min_ratio=0.8, require_column=True, fail_open=False)
        self.assertEqual(ok3.tolist(), [False, False])

    def test_macro_sma_regime_ok(self) -> None:
        df = pd.DataFrame({"macro_close_1d": [100.0, 110.0], "macro_sma_1d": [100.0, 105.0]})
        long_ok = macro_sma_regime_ok(
            df,
            enabled=True,
            macro_close_col="macro_close_1d",
            macro_sma_col="macro_sma_1d",
            is_long=True,
            require_columns=True,
            slope_lookback=0,
            min_slope=0.0,
            fail_open=False,
        )
        self.assertEqual(long_ok.tolist(), [False, True])

        short_ok = macro_sma_regime_ok(
            df,
            enabled=True,
            macro_close_col="macro_close_1d",
            macro_sma_col="macro_sma_1d",
            is_long=False,
            require_columns=True,
            slope_lookback=0,
            min_slope=0.0,
            fail_open=False,
        )
        self.assertEqual(short_ok.tolist(), [False, False])

        # 缺列：strict -> 全 False；fail-open -> 全 True
        df2 = pd.DataFrame({"x": [1, 2, 3]})
        strict = macro_sma_regime_ok(
            df2,
            enabled=True,
            macro_close_col="macro_close_1d",
            macro_sma_col="macro_sma_1d",
            is_long=True,
            require_columns=True,
            slope_lookback=0,
            min_slope=0.0,
            fail_open=False,
        )
        self.assertTrue(all(not bool(x) for x in strict.tolist()))

        fail_open = macro_sma_regime_ok(
            df2,
            enabled=True,
            macro_close_col="macro_close_1d",
            macro_sma_col="macro_sma_1d",
            is_long=True,
            require_columns=True,
            slope_lookback=0,
            min_slope=0.0,
            fail_open=True,
        )
        self.assertTrue(all(bool(x) for x in fail_open.tolist()))

    def test_price_not_too_far_and_momentum(self) -> None:
        close = pd.Series([100.0, 101.0, 110.0])
        ema_s = pd.Series([100.0, 100.5, 101.0])
        ok = price_not_too_far_from_ema(close, ema_s, max_offset=0.05, side="long")
        self.assertEqual(ok.tolist(), [True, True, False])

        mom = momentum_ok(close, side="long")
        self.assertEqual(mom.tolist(), [False, True, True])

        # 确保不产生 inf
        arr = pd.concat([ok.astype("int64"), mom.astype("int64")], axis=1).to_numpy(dtype="float64")
        self.assertFalse(np.isinf(arr).any())


if __name__ == "__main__":
    unittest.main()

