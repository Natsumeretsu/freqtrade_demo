from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd


_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "03_integration"))


from trading_system.application.signal_ops import (  # noqa: E402
    bear_mode,
    bull_mode,
    crossed_above,
    crossed_below,
    reentry_event,
)


class TestSignalOps(unittest.TestCase):
    def test_crossed_above_and_below(self) -> None:
        a = pd.Series([1.0, 3.0, 4.0])
        b = pd.Series([2.0, 2.0, 2.0])
        up = crossed_above(a, b)
        self.assertEqual(up.tolist(), [False, True, False])

        c = pd.Series([3.0, 1.0, 0.5])
        down = crossed_below(c, b)
        self.assertEqual(down.tolist(), [False, True, False])

    def test_bull_and_bear_mode(self) -> None:
        close = pd.Series([100.0, 110.0])
        ema_l = pd.Series([100.0, 100.0])
        bull = bull_mode(close, ema_l, offset=0.05)  # 105
        self.assertEqual(bull.tolist(), [False, True])

        bear = bear_mode(close, ema_l, offset=0.05)  # 95
        self.assertEqual(bear.tolist(), [False, False])

    def test_reentry_event_long(self) -> None:
        close = pd.Series([100.0, 105.0])
        ema_s = pd.Series([101.0, 102.0])
        ema_l = pd.Series([100.0, 100.0])
        spread = pd.Series([0.0, 0.02])

        re = reentry_event(
            close,
            ema_s,
            ema_l,
            side="long",
            min_long_offset=0.02,
            spread_metric=spread,
            min_spread=0.01,
        )
        self.assertEqual(re.tolist(), [False, True])

    def test_reentry_event_short(self) -> None:
        close = pd.Series([100.0, 95.0])
        ema_s = pd.Series([99.0, 98.0])
        ema_l = pd.Series([100.0, 100.0])
        spread = pd.Series([0.0, 0.02])

        re = reentry_event(
            close,
            ema_s,
            ema_l,
            side="short",
            min_long_offset=0.02,
            spread_metric=spread,
            min_spread=0.01,
        )
        self.assertEqual(re.tolist(), [False, True])

        arr = pd.concat([re.astype("int64")], axis=1).to_numpy(dtype="float64")
        self.assertFalse(np.isinf(arr).any())


if __name__ == "__main__":
    unittest.main()

