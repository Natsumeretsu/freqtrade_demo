from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

import pandas as pd


def _load_export_timing_policy_module():
    repo_root = Path(__file__).resolve().parents[1]
    mod_path = repo_root / "scripts" / "qlib" / "export_timing_policy.py"
    spec = importlib.util.spec_from_file_location("export_timing_policy", mod_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[attr-defined]
    return module


class TestExportTimingPolicyFamilyCap(unittest.TestCase):
    def test_family_cap_limits_same_family_in_topk(self) -> None:
        mod = _load_export_timing_policy_module()

        pair = "AAA/USDT:USDT"
        df = pd.DataFrame(
            [
                # 两个 ema_* 都很强：不加 family_cap 会被同时选进 TopK
                {
                    "pair": pair,
                    "horizon": 1,
                    "factor": "ema_20",
                    "direction": "pos",
                    "side": "both",
                    "roll_30d_median": 0.30,
                    "verdict": "pass",
                },
                {
                    "pair": pair,
                    "horizon": 1,
                    "factor": "ema_50",
                    "direction": "pos",
                    "side": "both",
                    "roll_30d_median": 0.29,
                    "verdict": "pass",
                },
                {
                    "pair": pair,
                    "horizon": 1,
                    "factor": "adx_30",
                    "direction": "pos",
                    "side": "both",
                    "roll_30d_median": 0.28,
                    "verdict": "pass",
                },
                {
                    "pair": pair,
                    "horizon": 1,
                    "factor": "vol_24",
                    "direction": "pos",
                    "side": "both",
                    "roll_30d_median": 0.27,
                    "verdict": "pass",
                },
            ]
        )

        def _write_pos_series(series_dir: Path, *, factor: str, pos: list[int]) -> None:
            safe_pair = mod._safe_name(pair)
            safe_factor = mod._safe_name(factor)
            path = series_dir / f"timing_{safe_pair}_{safe_factor}_h1.csv"
            pd.DataFrame({"pos": pos}).to_csv(path)

        # 让两条 ema 序列不完全相关（避免 corr 去冗余把它们先过滤掉，影响 family_cap 的测试意义）
        ema_20_pos = [1, 0] * 10
        ema_50_pos = [1, 1, 0, 0] * 5
        adx_30_pos = [1, 0, 0, 0, 0] * 4
        vol_24_pos = [0, 1, 0] * 6 + [0, 1]

        with tempfile.TemporaryDirectory() as td:
            series_dir = Path(td)
            _write_pos_series(series_dir, factor="ema_20", pos=ema_20_pos)
            _write_pos_series(series_dir, factor="ema_50", pos=ema_50_pos)
            _write_pos_series(series_dir, factor="adx_30", pos=adx_30_pos)
            _write_pos_series(series_dir, factor="vol_24", pos=vol_24_pos)

            # 1) family_cap=0：允许同族多选
            out0 = mod._select_topk(
                df,
                topk=3,
                allow_watch=True,
                roll_key="roll_30d_median",
                prefer_horizon=1,
                allow_other_horizons=False,
                weight_mode="equal",
                dedupe_method="corr",
                dedupe_threshold=0.999,
                dedupe_min_common_obs=5,
                dedupe_family_cap=0,
                series_dir=series_dir,
            )
            names0 = [x["name"] for x in out0[pair]]
            self.assertEqual(names0, ["ema_20", "ema_50", "adx_30"])

            # 2) family_cap=1：同族最多 1 个 → ema_50 被跳过，vol_24 递补
            out1 = mod._select_topk(
                df,
                topk=3,
                allow_watch=True,
                roll_key="roll_30d_median",
                prefer_horizon=1,
                allow_other_horizons=False,
                weight_mode="equal",
                dedupe_method="corr",
                dedupe_threshold=0.999,
                dedupe_min_common_obs=5,
                dedupe_family_cap=1,
                series_dir=series_dir,
            )
            names1 = [x["name"] for x in out1[pair]]
            self.assertEqual(names1, ["ema_20", "adx_30", "vol_24"])


if __name__ == "__main__":
    unittest.main()
