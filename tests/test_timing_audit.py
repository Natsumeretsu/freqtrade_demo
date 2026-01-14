from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd


_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "03_integration"))


from trading_system.application.timing_audit import (  # noqa: E402
    TimingAuditParams,
    choose_timing_direction,
    choose_timing_direction_with_thresholds,
    position_from_thresholds,
    precompute_quantile_thresholds,
    timing_returns_from_positions,
)


class TestTimingAudit(unittest.TestCase):
    def test_position_from_thresholds_pos_and_neg(self) -> None:
        idx = pd.date_range("2024-01-01", periods=5, freq="1h", tz="UTC")
        x = pd.Series([1, 2, 3, 4, 5], index=idx, dtype="float64")
        q_high = pd.Series(4.0, index=idx, dtype="float64")
        q_low = pd.Series(2.0, index=idx, dtype="float64")

        pos = position_from_thresholds(x=x, q_high=q_high, q_low=q_low, direction="pos")
        neg = position_from_thresholds(x=x, q_high=q_high, q_low=q_low, direction="neg")

        self.assertTrue(np.allclose(pos.to_numpy(), np.array([-1.0, -1.0, 0.0, 1.0, 1.0])))
        self.assertTrue(np.allclose(neg.to_numpy(), np.array([1.0, 1.0, 0.0, -1.0, -1.0])))

    def test_timing_returns_from_positions_non_overlapping_and_cost(self) -> None:
        idx = pd.date_range("2024-01-01", periods=8, freq="1h", tz="UTC")
        pos = pd.Series([0, 1, 1, 0, -1, -1, 0, 0], index=idx, dtype="float64")
        fwd = pd.Series(0.01, index=idx, dtype="float64")
        btc = pd.Series(0.005, index=idx, dtype="float64")

        params = TimingAuditParams(
            timeframe="1h",
            horizon=2,
            quantiles=5,
            lookback_days=1,
            fee_rate=0.001,
            slippage_rate=0.0,
            rolling_days=[1],
        )

        out = timing_returns_from_positions(pos=pos, fwd_ret=fwd, btc_ret=btc, params=params)
        self.assertEqual(len(out), 4)  # 0,2,4,6
        self.assertIn("net_ret", out.columns)
        self.assertIn("alpha_btc_net", out.columns)

        expected_net = np.array([0.0, 0.009, -0.012, -0.001], dtype="float64")
        self.assertTrue(np.allclose(out["net_ret"].to_numpy(), expected_net))

        expected_alpha = expected_net - 0.005
        self.assertTrue(np.allclose(out["alpha_btc_net"].to_numpy(), expected_alpha))

    def test_precompute_quantile_thresholds_outputs_shape(self) -> None:
        idx = pd.date_range("2024-01-01", periods=60, freq="1h", tz="UTC")
        X = pd.DataFrame(
            {
                "a": np.arange(len(idx), dtype="float64"),
                "b": np.arange(len(idx), dtype="float64")[::-1],
            },
            index=idx,
        )

        params = TimingAuditParams(
            timeframe="1h",
            horizon=1,
            quantiles=5,
            lookback_days=1,  # 24 bars
            fee_rate=0.0,
            slippage_rate=0.0,
            rolling_days=[1],
        )

        q_high, q_low = precompute_quantile_thresholds(X=X, params=params)
        self.assertEqual(q_high.shape, X.shape)
        self.assertEqual(q_low.shape, X.shape)
        self.assertEqual(list(q_high.columns), ["a", "b"])
        self.assertTrue(q_high.isna().iloc[:23].all(axis=None))
        self.assertTrue(q_low.isna().iloc[:23].all(axis=None))

    def test_choose_timing_direction_with_thresholds_prefers_pos(self) -> None:
        idx = pd.date_range("2024-01-01", periods=120, freq="1h", tz="UTC")
        x = pd.Series((np.arange(len(idx)) % 2).astype("float64"), index=idx)
        # fwd 恒为正，但 x=1 时收益更高：理应选择 direction=pos + 只做多（避免做空端拖累）
        fwd = pd.Series(np.where(x.to_numpy() > 0.0, 0.02, 0.01), index=idx, dtype="float64")

        params = TimingAuditParams(
            timeframe="1h",
            horizon=1,
            quantiles=5,
            lookback_days=1,
            fee_rate=0.0,
            slippage_rate=0.0,
            rolling_days=[1],
        )

        q_high, q_low = precompute_quantile_thresholds(X=pd.DataFrame({"x": x}), params=params)
        direction, side, ic, ret = choose_timing_direction_with_thresholds(
            x=x,
            fwd_ret=fwd,
            btc_ret=None,
            params=params,
            q_high=q_high["x"],
            q_low=q_low["x"],
        )

        self.assertEqual(direction, "pos")
        self.assertEqual(side, "long")  # 恒为正收益下，“只做多”应优于“多空都做”
        self.assertGreater(float(ic.dropna().mean()), 0.9)
        self.assertGreater(float(ret["net_ret"].mean()), 0.0)

    def test_choose_timing_direction_can_flip_negative(self) -> None:
        idx = pd.date_range("2024-01-01", periods=120, freq="1h", tz="UTC")
        x = pd.Series((np.arange(len(idx)) % 2).astype("float64"), index=idx)
        # x=0 时收益为正，x=1 时收益为负：最优应为 direction=neg（x 低偏多、x 高偏空）
        fwd = pd.Series(np.where(x.to_numpy() > 0.0, -0.02, 0.01), index=idx, dtype="float64")

        params = TimingAuditParams(
            timeframe="1h",
            horizon=1,
            quantiles=5,
            lookback_days=1,
            fee_rate=0.0,
            slippage_rate=0.0,
            rolling_days=[1],
        )

        direction, side, ic, ret = choose_timing_direction(x=x, fwd_ret=fwd, btc_ret=None, params=params)
        self.assertEqual(direction, "neg")
        self.assertEqual(side, "both")  # 两端都赚钱时，多空都做应优于只做一边
        self.assertGreater(float(ic.dropna().mean()), 0.9)
        self.assertGreater(float(ret["net_ret"].mean()), 0.0)

    def test_choose_timing_direction_can_select_short_only(self) -> None:
        idx = pd.date_range("2024-01-01", periods=120, freq="1h", tz="UTC")
        x = pd.Series((np.arange(len(idx)) % 2).astype("float64"), index=idx)
        # fwd 恒为负，但 x=1 跌得更狠：理应选择 direction=neg + 只做空（避免做多端亏损）
        fwd = pd.Series(np.where(x.to_numpy() > 0.0, -0.02, -0.01), index=idx, dtype="float64")

        params = TimingAuditParams(
            timeframe="1h",
            horizon=1,
            quantiles=5,
            lookback_days=1,
            fee_rate=0.0,
            slippage_rate=0.0,
            rolling_days=[1],
        )

        direction, side, ic, ret = choose_timing_direction(x=x, fwd_ret=fwd, btc_ret=None, params=params)
        self.assertEqual(direction, "neg")
        self.assertEqual(side, "short")
        self.assertGreater(float(ic.dropna().mean()), 0.9)
        self.assertGreater(float(ret["net_ret"].mean()), 0.0)


if __name__ == "__main__":
    unittest.main()
