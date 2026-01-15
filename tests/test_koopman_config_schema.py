"""
test_koopman_config_schema.py - Koopman 配置 Schema 单元测试
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "03_integration"))

from trading_system.domain.koopman_config_schema import (
    KoopmanConfig,
    load_koopman_config,
)


class TestKoopmanConfigSchema(unittest.TestCase):
    def test_default_values(self) -> None:
        cfg = KoopmanConfig()
        self.assertEqual(cfg.window, 512)
        self.assertEqual(cfg.embed_dim, 16)
        self.assertEqual(cfg.stride, 10)
        self.assertAlmostEqual(cfg.ridge, 0.001)
        self.assertEqual(cfg.pred_horizons, [1, 4])

    def test_custom_values(self) -> None:
        cfg = KoopmanConfig(
            window=256,
            embed_dim=8,
            stride=5,
            ridge=0.01,
            pred_horizons=[1, 2, 4],
        )
        self.assertEqual(cfg.window, 256)
        self.assertEqual(cfg.embed_dim, 8)

    def test_load_from_dict(self) -> None:
        raw = {"window": 1024, "fft_topk": 16}
        cfg = load_koopman_config(raw)
        self.assertEqual(cfg.window, 1024)
        self.assertEqual(cfg.fft_topk, 16)
        # 未指定的使用默认值
        self.assertEqual(cfg.embed_dim, 16)

    def test_load_none_returns_default(self) -> None:
        cfg = load_koopman_config(None)
        self.assertEqual(cfg.window, 512)

    def test_horizons_sorted_and_deduped(self) -> None:
        cfg = KoopmanConfig(pred_horizons=[4, 1, 4, 2])
        self.assertEqual(cfg.pred_horizons, [1, 2, 4])

    def test_invalid_window_raises(self) -> None:
        with self.assertRaises(ValueError):
            KoopmanConfig(window=10)  # < 32

    def test_invalid_embed_dim_raises(self) -> None:
        with self.assertRaises(ValueError):
            KoopmanConfig(embed_dim=1)  # < 2


if __name__ == "__main__":
    unittest.main()
