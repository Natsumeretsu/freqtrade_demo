from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd


_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "03_integration"))


from trading_system.application.factor_audit import (  # noqa: E402
    bars_per_day,
    choose_factor_direction,
    cross_section_audit,
    parse_timeframe_minutes,
)


class TestFactorAudit(unittest.TestCase):
    def test_timeframe_parsing(self) -> None:
        self.assertEqual(parse_timeframe_minutes("15m"), 15)
        self.assertEqual(parse_timeframe_minutes("1h"), 60)
        self.assertEqual(parse_timeframe_minutes("4h"), 240)
        self.assertEqual(parse_timeframe_minutes("1d"), 1440)
        self.assertIsNone(parse_timeframe_minutes(""))
        self.assertIsNone(parse_timeframe_minutes("abc"))

        self.assertEqual(bars_per_day("15m"), 96)
        self.assertEqual(bars_per_day("1h"), 24)
        self.assertEqual(bars_per_day("4h"), 6)
        self.assertIsNone(bars_per_day("7m"))  # 1440 不能整除

    def test_cross_section_audit_perfect_monotonic(self) -> None:
        idx = pd.date_range("2024-01-01", periods=5, freq="4h", tz="UTC")
        x = pd.DataFrame({"A": 1.0, "B": 2.0, "C": 3.0}, index=idx)
        y = pd.DataFrame({"A": -0.01, "B": 0.0, "C": 0.01}, index=idx)

        ic, ret = cross_section_audit(
            x_wide=x,
            y_wide=y,
            quantiles=3,
            weights={},
            fee_rate=0.0,
            slippage_rate=0.0,
        )

        self.assertEqual(len(ic), len(idx))
        self.assertTrue((ic.dropna() > 0.99).all())

        # top=C, bottom=A => 0.01 - (-0.01) = 0.02
        self.assertTrue(np.allclose(ret["ls_ret"].dropna().to_numpy(), 0.02))

        # 首期 turnover 为空，后续应为 0（持仓不变）
        self.assertTrue(np.isnan(ret["turnover_top"].iloc[0]))
        self.assertTrue(np.isnan(ret["turnover_bottom"].iloc[0]))
        self.assertTrue((ret["turnover_top"].iloc[1:].fillna(0.0) == 0.0).all())
        self.assertTrue((ret["turnover_bottom"].iloc[1:].fillna(0.0) == 0.0).all())

        # 成本列应存在；首期为 NaN，后续为 0（fee=0）
        self.assertIn("cost_top", ret.columns)
        self.assertIn("cost_bottom", ret.columns)
        self.assertTrue(np.isnan(ret["cost_top"].iloc[0]))
        self.assertTrue(np.isnan(ret["cost_bottom"].iloc[0]))
        self.assertTrue((ret["cost_top"].iloc[1:].fillna(0.0) == 0.0).all())
        self.assertTrue((ret["cost_bottom"].iloc[1:].fillna(0.0) == 0.0).all())

        # 成本为 0，ls_ret_net 除首期外应等于 ls_ret
        self.assertTrue(np.isnan(ret["ls_ret_net"].iloc[0]))
        self.assertTrue(np.allclose(ret["ls_ret_net"].iloc[1:].to_numpy(), ret["ls_ret"].iloc[1:].to_numpy()))

        # bottom_ret_net / top_ret_net 在成本为 0 时应等于原始收益（除首期 NaN）
        self.assertIn("bottom_ret_net", ret.columns)
        self.assertTrue(np.isnan(ret["top_ret_net"].iloc[0]))
        self.assertTrue(np.isnan(ret["bottom_ret_net"].iloc[0]))
        self.assertTrue(np.allclose(ret["top_ret_net"].iloc[1:].to_numpy(), ret["top_ret"].iloc[1:].to_numpy()))
        self.assertTrue(np.allclose(ret["bottom_ret_net"].iloc[1:].to_numpy(), ret["bottom_ret"].iloc[1:].to_numpy()))

    def test_choose_factor_direction_can_flip_negative(self) -> None:
        idx = pd.date_range("2024-01-01", periods=5, freq="4h", tz="UTC")
        x = pd.DataFrame({"A": 1.0, "B": 2.0, "C": 3.0}, index=idx)
        # 与 x 完全反向：原始方向应是负相关；选择 neg 后应变为正相关/正收益
        y = pd.DataFrame({"A": 0.01, "B": 0.0, "C": -0.01}, index=idx)

        direction, ic, ret = choose_factor_direction(
            x_wide=x,
            y_wide=y,
            quantiles=3,
            weights={},
            fee_rate=0.0,
            slippage_rate=0.0,
            timeframe="4h",
            rolling_days=[30, 60],
        )

        self.assertEqual(direction, "neg")
        self.assertTrue((ic.dropna() > 0.99).all())
        self.assertTrue(np.allclose(ret["ls_ret"].dropna().to_numpy(), 0.02))

    def test_market_return_weighted(self) -> None:
        idx = pd.date_range("2024-01-01", periods=3, freq="1h", tz="UTC")
        x = pd.DataFrame({"A": [1, 1, 1], "B": [2, 2, 2], "C": [3, 3, 3]}, index=idx, dtype="float64")
        y = pd.DataFrame({"A": -0.01, "B": 0.0, "C": 0.01}, index=idx)

        ic, ret = cross_section_audit(
            x_wide=x,
            y_wide=y,
            quantiles=3,
            weights={"A": 0.5, "B": 0.3, "C": 0.2},
            fee_rate=0.0,
            slippage_rate=0.0,
        )

        self.assertTrue((ic.dropna() > 0.99).all())

        # market_ret = -0.01*0.5 + 0*0.3 + 0.01*0.2 = -0.003
        self.assertTrue(np.allclose(ret["market_ret"].to_numpy(), -0.003))
        # top_alpha = 0.01 - (-0.003) = 0.013
        self.assertTrue(np.allclose(ret["top_alpha"].to_numpy(), 0.013))


if __name__ == "__main__":
    unittest.main()
