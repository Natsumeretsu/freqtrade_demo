"""
test_timing_policy_schema.py - 择时策略配置 Schema 单元测试
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "03_integration"))

from trading_system.domain.timing_policy_schema import (
    Direction,
    FactorSpec,
    TimingPolicyConfig,
    TimingPolicyValidationError,
    TradeSide,
    validate_timing_policy,
)


class TestFactorSpec(unittest.TestCase):
    def test_valid_factor(self) -> None:
        f = FactorSpec(name="ema_20", direction=Direction.neg, side=TradeSide.both, weight=1.0)
        self.assertEqual(f.name, "ema_20")
        self.assertEqual(f.direction, Direction.neg)
        self.assertEqual(f.weight, 1.0)

    def test_empty_name_raises(self) -> None:
        with self.assertRaises(Exception):
            FactorSpec(name="", direction=Direction.pos, side=TradeSide.both, weight=1.0)

    def test_zero_weight_raises(self) -> None:
        with self.assertRaises(Exception):
            FactorSpec(name="ema_20", weight=0.0)

    def test_negative_weight_raises(self) -> None:
        with self.assertRaises(Exception):
            FactorSpec(name="ema_20", weight=-1.0)


class TestTimingPolicyConfig(unittest.TestCase):
    def test_minimal_valid_config(self) -> None:
        data = {
            "version": 2,
            "exchange": "okx",
            "defaults": {
                "main": {
                    "factors": [{"name": "ema_20", "direction": "neg"}]
                }
            }
        }
        cfg = validate_timing_policy(data)
        self.assertEqual(cfg.version, 2)
        self.assertEqual(cfg.exchange, "okx")
        self.assertEqual(len(cfg.defaults.main.factors), 1)

    def test_no_factors_raises(self) -> None:
        data = {"version": 2, "exchange": "okx"}
        with self.assertRaises(TimingPolicyValidationError):
            validate_timing_policy(data)

    def test_invalid_timeframe_raises(self) -> None:
        data = {
            "version": 2,
            "main": {"timeframe": "invalid"},
            "defaults": {"main": {"factors": [{"name": "ema_20"}]}}
        }
        with self.assertRaises(TimingPolicyValidationError):
            validate_timing_policy(data)

    def test_quantiles_out_of_range_raises(self) -> None:
        data = {
            "version": 2,
            "main": {"quantiles": 100},
            "defaults": {"main": {"factors": [{"name": "ema_20"}]}}
        }
        with self.assertRaises(TimingPolicyValidationError):
            validate_timing_policy(data)

    def test_pair_level_factors(self) -> None:
        data = {
            "version": 2,
            "pairs": {
                "BTC/USDT:USDT": {
                    "main": {"factors": [{"name": "rsi_14", "direction": "pos"}]}
                }
            }
        }
        cfg = validate_timing_policy(data)
        self.assertIn("BTC/USDT:USDT", cfg.pairs)
        self.assertEqual(cfg.pairs["BTC/USDT:USDT"].main.factors[0].name, "rsi_14")


if __name__ == "__main__":
    unittest.main()
