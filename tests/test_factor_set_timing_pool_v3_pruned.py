from __future__ import annotations

import sys
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "03_integration"))

from trading_system.application.factor_sets import get_factor_templates, render_factor_names  # noqa: E402
from trading_system.infrastructure.factor_engines.talib_engine import TalibFactorEngine  # noqa: E402


class TestTimingPoolV3Pruned(unittest.TestCase):
    def test_timing_pool_v3_pruned_size_and_support(self) -> None:
        names = render_factor_names(get_factor_templates("timing_pool_v3_pruned"), {})
        self.assertEqual(len(names), 121)

        # 设计约束：volume_ratio_<n> 不允许在同一特征集里出现多个窗口别名
        self.assertFalse(any(str(n).startswith("volume_ratio_") for n in names))

        engine = TalibFactorEngine()
        unsupported = [n for n in names if not engine.supports(n)]
        self.assertEqual(unsupported, [])

    def test_timing_pool_koop_v3_pruned_size_and_contains_koopman_v2(self) -> None:
        names = render_factor_names(get_factor_templates("timing_pool_koop_v3_pruned"), {})
        # 121（传统） + 10（Koopa-lite v2） = 131
        self.assertEqual(len(names), 131)

        for n in [
            "koop_pred_ret_h1",
            "koop_pred_ret_h2",
            "koop_pred_ret_h4",
            "koop_pred_ret_h8",
            "koop_pred_ret_h16",
        ]:
            self.assertIn(n, names)


if __name__ == "__main__":
    unittest.main()

