from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd


_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "03_integration"))


from trading_system.application.risk_scaling import (  # noqa: E402
    clamp01,
    linear_scale_down,
    linear_scale_up,
    macro_sma_soft_scale,
    step_max,
    step_min,
)


class TestRiskScaling(unittest.TestCase):
    def test_clamp01(self) -> None:
        self.assertEqual(clamp01(1.2), 1.0)
        self.assertEqual(clamp01(-0.1), 0.0)
        self.assertEqual(clamp01(float("nan"), default=0.7), 0.7)

    def test_step_min_and_step_max(self) -> None:
        self.assertEqual(step_min(value=0.5, min_value=1.0, floor=0.4), 0.4)
        self.assertEqual(step_min(value=1.0, min_value=1.0, floor=0.4), 1.0)
        self.assertEqual(step_max(value=1.5, max_value=1.0, floor=0.4), 0.4)
        self.assertEqual(step_max(value=1.0, max_value=1.0, floor=0.4), 1.0)

    def test_linear_scale_up(self) -> None:
        self.assertEqual(linear_scale_up(value=0.5, min_value=1.0, target_value=2.0, floor=0.2), 0.2)
        self.assertEqual(linear_scale_up(value=2.0, min_value=1.0, target_value=2.0, floor=0.2), 1.0)
        mid = linear_scale_up(value=1.5, min_value=1.0, target_value=2.0, floor=0.2)
        self.assertTrue(np.isfinite(mid))
        self.assertAlmostEqual(mid, 0.6, places=6)

    def test_linear_scale_down(self) -> None:
        self.assertEqual(linear_scale_down(value=0.5, start_value=1.0, end_value=2.0, floor=0.3), 1.0)
        self.assertEqual(linear_scale_down(value=2.0, start_value=1.0, end_value=2.0, floor=0.3), 0.3)
        mid = linear_scale_down(value=1.5, start_value=1.0, end_value=2.0, floor=0.3)
        self.assertTrue(np.isfinite(mid))
        self.assertAlmostEqual(mid, 0.65, places=6)

        # end<=start：视为不启用
        self.assertEqual(linear_scale_down(value=10.0, start_value=1.0, end_value=1.0, floor=0.3), 1.0)

    def test_macro_sma_soft_scale_long(self) -> None:
        df = pd.DataFrame(
            {
                "macro_close_1d": [100.0, 100.0, 110.0],
                "macro_sma_1d": [100.0, 100.0, 102.5],  # slope=2.5%
            }
        )

        scale = macro_sma_soft_scale(
            df,
            macro_close_col="macro_close_1d",
            macro_sma_col="macro_sma_1d",
            is_long=True,
            floor=0.2,
            slope_lookback=1,
            min_slope=0.05,
        )
        # strength=0.025，插值：0.2 + 0.8*(0.025/0.05)=0.6
        self.assertAlmostEqual(scale, 0.6, places=6)

        # 体制不符合（close<=sma）→ floor
        df2 = pd.DataFrame({"macro_close_1d": [100.0], "macro_sma_1d": [100.0]})
        scale2 = macro_sma_soft_scale(
            df2,
            macro_close_col="macro_close_1d",
            macro_sma_col="macro_sma_1d",
            is_long=True,
            floor=0.3,
            slope_lookback=20,
            min_slope=0.05,
        )
        self.assertAlmostEqual(scale2, 0.3, places=6)

    def test_macro_sma_soft_scale_short(self) -> None:
        df = pd.DataFrame(
            {
                "macro_close_1d": [100.0, 100.0, 90.0],
                "macro_sma_1d": [100.0, 100.0, 95.0],  # slope=-5%
            }
        )
        scale = macro_sma_soft_scale(
            df,
            macro_close_col="macro_close_1d",
            macro_sma_col="macro_sma_1d",
            is_long=False,
            floor=0.3,
            slope_lookback=1,
            min_slope=0.05,
        )
        # short：strength=max(0,-slope)=0.05 → 满额
        self.assertAlmostEqual(scale, 1.0, places=6)


if __name__ == "__main__":
    unittest.main()

