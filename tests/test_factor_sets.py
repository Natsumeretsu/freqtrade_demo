from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch


# 让测试可直接导入 03_integration/trading_system（不依赖额外环境变量）
_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "03_integration"))


from trading_system.application.factor_sets import get_factor_templates, render_factor_names  # noqa: E402


class TestFactorSets(unittest.TestCase):
    def test_render_factor_names_basic(self) -> None:
        templates = ["ema_short_{ema_short_len}", "ema_long_{ema_long_len}", "adx"]
        out = render_factor_names(templates, {"ema_short_len": 20, "ema_long_len": 160})
        self.assertEqual(out, ["ema_short_20", "ema_long_160", "adx"])

    def test_render_factor_names_skip_missing_placeholder(self) -> None:
        templates = ["ema_short_{ema_short_len}", "adx"]
        out = render_factor_names(templates, {})
        self.assertEqual(out, ["adx"])

    def test_render_factor_names_skip_non_positive(self) -> None:
        templates = ["ema_short_{ema_short_len}", "adx"]
        out = render_factor_names(templates, {"ema_short_len": 0})
        self.assertEqual(out, ["adx"])

    def test_render_factor_names_dedupe_preserve_order(self) -> None:
        templates = ["adx", "adx", "ema_{n}", "ema_{n}"]
        out = render_factor_names(templates, {"n": 10})
        self.assertEqual(out, ["adx", "ema_10"])

    def test_get_factor_templates_from_repo_config(self) -> None:
        templates = get_factor_templates("SmallAccountFuturesTrendV1")
        self.assertTrue(isinstance(templates, list))
        self.assertTrue(len(templates) >= 5)

    def test_get_factor_templates_expands_includes_and_preserves_order(self) -> None:
        templates = get_factor_templates("SmallAccountFuturesTrendV1")
        self.assertTrue(all(not str(x).startswith("@") for x in templates))

        # 验证 cta_core 展开后的前缀（cta_alpha + cta_risk）
        # cta_alpha: ret_1, ret_3, ret_7, ret_14, ret_28
        # cta_risk: vol_14, skew_30, kurt_30, volume_z_30, hl_range (vol_28 removed: failed validation)
        expected_prefix = [
            "ret_1",
            "ret_3",
            "ret_7",
            "ret_14",
            "ret_28",
            "vol_14",
            "skew_30",
        ]
        self.assertEqual(templates[: len(expected_prefix)], expected_prefix)
        self.assertIn("ema_short_{ema_short_len}", templates)

    def test_get_factor_templates_cycle_is_guarded(self) -> None:
        class DummyCfg:
            def __init__(self, mapping: dict) -> None:
                self._m = dict(mapping)

            def get(self, key: str, default=None):
                return self._m.get(key, default)

        dummy = DummyCfg(
            {
                "factors.factor_sets.a": ["ret_1", "@b", "adx"],
                "factors.factor_sets.b": ["@c"],
                "factors.factor_sets.c": ["@b", "atr"],
            }
        )

        with patch("trading_system.application.factor_sets.get_config", return_value=dummy):
            templates = get_factor_templates("a")
        self.assertEqual(templates, ["ret_1", "atr", "adx"])


if __name__ == "__main__":
    unittest.main()
