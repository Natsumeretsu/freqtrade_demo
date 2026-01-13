from __future__ import annotations

import sys
import unittest
from pathlib import Path


_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "03_integration"))


from trading_system.infrastructure.ml.qlib_signal import QlibSignalService  # noqa: E402


class TestQlibSignalMapping(unittest.TestCase):
    def test_side_proba_long_short(self) -> None:
        self.assertAlmostEqual(QlibSignalService.side_proba(proba_up=0.7, side="long") or 0.0, 0.7, places=6)
        self.assertAlmostEqual(QlibSignalService.side_proba(proba_up=0.7, side="short") or 0.0, 0.3, places=6)

    def test_soft_scale_piecewise(self) -> None:
        # p <= 0.5：返回 floor
        self.assertAlmostEqual(QlibSignalService.soft_scale(side_proba=0.5, floor=0.3, threshold=0.55), 0.3, places=6)
        # p >= threshold：返回 1
        self.assertAlmostEqual(QlibSignalService.soft_scale(side_proba=0.9, floor=0.3, threshold=0.55), 1.0, places=6)
        # 中间线性插值：p=0.525（在 0.5~0.55 中点）-> 0.3 + 0.5*(1-0.3)=0.65
        self.assertAlmostEqual(QlibSignalService.soft_scale(side_proba=0.525, floor=0.3, threshold=0.55), 0.65, places=6)

    def test_hard_fuse_block(self) -> None:
        self.assertFalse(QlibSignalService.hard_fuse_block(side_proba=0.4, enabled=False, min_proba=0.45))
        self.assertTrue(QlibSignalService.hard_fuse_block(side_proba=0.4, enabled=True, min_proba=0.45))
        self.assertFalse(QlibSignalService.hard_fuse_block(side_proba=0.46, enabled=True, min_proba=0.45))


if __name__ == "__main__":
    unittest.main()

