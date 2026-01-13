from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pandas as pd


_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "03_integration"))


from trading_system.application.gate_pipeline import (  # noqa: E402
    combine_gates,
    gate_funnel,
    render_gate_funnel_summary,
    top_bottlenecks,
)


class TestGatePipeline(unittest.TestCase):
    def test_combine_gates(self) -> None:
        idx = pd.RangeIndex(4)
        g1 = pd.Series([True, True, False, False], index=idx)
        g2 = pd.Series([True, False, True, False], index=idx)

        out = combine_gates([("g1", g1), ("g2", g2)], index=idx, fillna=True)
        self.assertEqual(out.tolist(), [True, False, False, False])

    def test_gate_funnel_stats(self) -> None:
        idx = pd.RangeIndex(4)
        g1 = pd.Series([True, True, False, False], index=idx)
        g2 = pd.Series([True, False, True, False], index=idx)

        final_mask, rows = gate_funnel([("g1", g1), ("g2", g2)], index=idx, fillna=True)
        self.assertEqual(final_mask.tolist(), [True, False, False, False])
        self.assertEqual(len(rows), 2)

        r1 = rows[0]
        self.assertEqual(r1.name, "g1")
        self.assertEqual(r1.survivors, 2)
        self.assertEqual(r1.marginal_drop, 2)

        r2 = rows[1]
        self.assertEqual(r2.name, "g2")
        self.assertEqual(r2.survivors, 1)
        self.assertEqual(r2.marginal_drop, 1)

        top = top_bottlenecks(rows, top_k=1)
        self.assertEqual(len(top), 1)
        self.assertEqual(top[0].name, "g1")

        summary = render_gate_funnel_summary(rows, top_k=2)
        self.assertIn("final=", summary)
        self.assertIn("bottlenecks=[", summary)


if __name__ == "__main__":
    unittest.main()
