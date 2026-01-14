from __future__ import annotations

"""
export_timing_policy.py - 把择时体检（timing_audit）的结果合成“执行器策略可用”的 policy 文件

你最关心的不是“研究报告”，而是“我接下来到底怎么跑回测/实盘”：
- timing_audit 负责：批量筛因子，输出每个币的最佳因子（含方向/稳健性/成本后收益）
- 本脚本负责：把 15m（主）和 1h（复核）的 summary 合并成一个 YAML，供 Freqtrade 执行器策略读取

示例：
  uv run python -X utf8 scripts/qlib/export_timing_policy.py ^
    --main-csv artifacts/timing_audit/.../timing_summary.csv ^
    --confirm-csv artifacts/timing_audit/.../timing_summary.csv ^
    --out 04_shared/config/timing_policy_okx_futures_15m_1h.yaml ^
    --topk 3 ^
    --allow-watch
"""

import argparse
import math
from pathlib import Path
from typing import Any

import pandas as pd
import yaml


_REPO_ROOT = Path(__file__).resolve().parents[2]


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="合成择时执行器策略的 timing_policy YAML。")
    p.add_argument("--main-csv", required=True, help="15m（主信号）timing_summary.csv 路径。")
    p.add_argument("--confirm-csv", required=True, help="1h（复核）timing_summary.csv 路径。")
    p.add_argument("--out", default="04_shared/config/timing_policy_okx_futures_15m_1h.yaml", help="输出 YAML 路径。")

    p.add_argument("--topk", type=int, default=3, help="每个币保留 TopK 因子（默认 3）。")
    p.add_argument(
        "--allow-watch",
        action="store_true",
        help="允许使用 verdict=watch 的因子（默认只用 pass）。",
    )
    p.add_argument(
        "--prefer-horizon",
        type=int,
        default=1,
        help="同分时优先选择的 horizon（默认 1）。",
    )
    p.add_argument(
        "--roll-key",
        default="roll_30d_median",
        help="排序指标（默认 roll_30d_median）。",
    )
    return p.parse_args()


def _read_summary(path: Path) -> pd.DataFrame:
    if not path.is_file():
        raise FileNotFoundError(f"未找到 CSV：{path.as_posix()}")
    df = pd.read_csv(path)
    if df is None or df.empty:
        raise ValueError(f"CSV 为空：{path.as_posix()}")
    return df


def _to_float(v: Any) -> float:
    try:
        x = float(v)
    except Exception:
        return float("nan")
    return x if math.isfinite(x) else float("nan")


def _normalize_weight_list(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    # 仅做基础清洗：保证 weight 为正数；不强制归一化（执行器会按 abs(weight) 归一）
    out: list[dict[str, Any]] = []
    for it in items:
        name = str(it.get("name", "")).strip()
        if not name:
            continue
        direction = str(it.get("direction", "pos")).strip().lower()
        if direction not in {"pos", "neg"}:
            direction = "pos"
        side = str(it.get("side", "both")).strip().lower()
        if side not in {"both", "long", "short"}:
            side = "both"
        w = _to_float(it.get("weight", 1.0))
        if not math.isfinite(w) or w <= 0:
            w = 1.0
        out.append({"name": name, "direction": direction, "side": side, "weight": float(w)})
    return out


def _select_topk(
    df: pd.DataFrame,
    *,
    topk: int,
    allow_watch: bool,
    roll_key: str,
    prefer_horizon: int,
) -> dict[str, list[dict[str, Any]]]:
    if df is None or df.empty:
        return {}

    must_cols = {"pair", "factor", "direction", "side"}
    missing = [c for c in must_cols if c not in df.columns]
    if missing:
        raise ValueError(f"CSV 缺少必要列：{missing}")

    roll_col = str(roll_key).strip()
    if roll_col and roll_col not in df.columns:
        raise ValueError(f"CSV 缺少排序列：{roll_col}")

    def _prep(frame: pd.DataFrame) -> pd.DataFrame:
        if frame is None or frame.empty:
            return pd.DataFrame()

        work2 = frame.copy()

        # 同分时优先 horizon
        if "horizon" in work2.columns:
            prefer = int(prefer_horizon)
            work2["_horizon_pref"] = (work2["horizon"].astype("float64") == float(prefer)).astype("int64")
        else:
            work2["_horizon_pref"] = 0

        if roll_col:
            work2["_roll"] = pd.to_numeric(work2[roll_col], errors="coerce").astype("float64")
        else:
            work2["_roll"] = float("nan")

        # 先按 horizon_pref 再按 roll 排序（pair 内部有序）
        return work2.sort_values(["pair", "_horizon_pref", "_roll"], ascending=[True, False, False])

    work = df.copy()
    if work is None or work.empty:
        return {}

    # 选择逻辑（风险优先）：
    # - 默认只用 pass；
    # - allow_watch=true 时：先取 pass 的 TopK，不足再用 watch 补齐（避免 watch 覆盖 pass）。
    verdict_col = "verdict" if "verdict" in work.columns else ""
    if verdict_col:
        v = work[verdict_col].astype(str).str.lower()
        pass_df = work[v == "pass"].copy()
        watch_df = work[v == "watch"].copy()
    else:
        pass_df = work.copy()
        watch_df = pd.DataFrame()

    pass_df = _prep(pass_df)
    watch_df = _prep(watch_df) if bool(allow_watch) else pd.DataFrame()

    if pass_df.empty and watch_df.empty:
        return {}

    out: dict[str, list[dict[str, Any]]] = {}
    pairs = []
    if not pass_df.empty:
        pairs += pass_df["pair"].astype(str).tolist()
    if not watch_df.empty:
        pairs += watch_df["pair"].astype(str).tolist()
    pairs = list(dict.fromkeys([p for p in pairs if p]))  # 去重保序

    for pair in pairs:
        selected: list[dict[str, Any]] = []
        seen: set[tuple[str, str, str]] = set()

        if not pass_df.empty:
            g = pass_df[pass_df["pair"].astype(str) == str(pair)]
            for _, r in g.iterrows():
                if len(selected) >= int(max(1, topk)):
                    break
                name = str(r.get("factor", "")).strip()
                direction = str(r.get("direction", "pos")).strip().lower()
                side = str(r.get("side", "both")).strip().lower()
                if direction not in {"pos", "neg"}:
                    direction = "pos"
                if side not in {"both", "long", "short"}:
                    side = "both"
                key = (name, direction, side)
                if not name or key in seen:
                    continue
                seen.add(key)
                selected.append(
                    {
                        "name": name,
                        "direction": direction,
                        "side": side,
                        "weight": 1.0,
                    }
                )

        if bool(allow_watch) and len(selected) < int(max(1, topk)) and not watch_df.empty:
            g = watch_df[watch_df["pair"].astype(str) == str(pair)]
            for _, r in g.iterrows():
                if len(selected) >= int(max(1, topk)):
                    break
                name = str(r.get("factor", "")).strip()
                direction = str(r.get("direction", "pos")).strip().lower()
                side = str(r.get("side", "both")).strip().lower()
                if direction not in {"pos", "neg"}:
                    direction = "pos"
                if side not in {"both", "long", "short"}:
                    side = "both"
                key = (name, direction, side)
                if not name or key in seen:
                    continue
                seen.add(key)
                selected.append(
                    {
                        "name": name,
                        "direction": direction,
                        "side": side,
                        "weight": 1.0,
                    }
                )

        if selected:
            out[str(pair)] = _normalize_weight_list(selected)

    return out


def _infer_timeframe(df: pd.DataFrame) -> str:
    if df is None or df.empty or "timeframe" not in df.columns:
        return ""
    vals = [str(x).strip() for x in df["timeframe"].dropna().unique().tolist()]
    vals = [v for v in vals if v]
    return vals[0] if len(vals) == 1 else (vals[0] if vals else "")


def main() -> int:
    args = _parse_args()
    main_csv = (_REPO_ROOT / Path(str(args.main_csv))).resolve()
    confirm_csv = (_REPO_ROOT / Path(str(args.confirm_csv))).resolve()
    out_path = (_REPO_ROOT / Path(str(args.out))).resolve()

    df_main = _read_summary(main_csv)
    df_confirm = _read_summary(confirm_csv)

    main_tf = _infer_timeframe(df_main) or "15m"
    confirm_tf = _infer_timeframe(df_confirm) or "1h"

    topk = int(args.topk)
    if topk <= 0:
        topk = 1

    roll_key = str(args.roll_key).strip() or "roll_30d_median"

    main_map = _select_topk(
        df_main,
        topk=topk,
        allow_watch=bool(args.allow_watch),
        roll_key=roll_key,
        prefer_horizon=int(args.prefer_horizon),
    )
    confirm_map = _select_topk(
        df_confirm,
        topk=topk,
        allow_watch=bool(args.allow_watch),
        roll_key=roll_key,
        prefer_horizon=int(args.prefer_horizon),
    )

    pairs = sorted(set(main_map.keys()) | set(confirm_map.keys()))

    policy: dict[str, Any] = {
        "version": 2,
        "exchange": "okx",
        "trading_mode": "futures",
        "main": {
            "timeframe": str(main_tf),
            "quantiles": 5,
            "lookback_days": 14,
            "entry_threshold": 0.67,
        },
        "confirm": {
            "timeframe": str(confirm_tf),
            "quantiles": 5,
            "lookback_days": 30,
            "entry_threshold": 0.67,
        },
        "defaults": {
            "main": {"factors": [{"name": "ema_20", "direction": "neg", "side": "both", "weight": 1.0}]},
            "confirm": {"factors": [{"name": "ema_20", "direction": "neg", "side": "both", "weight": 1.0}]},
        },
        "pairs": {},
    }

    for pair in pairs:
        policy["pairs"][pair] = {
            "main": {"factors": main_map.get(pair, policy["defaults"]["main"]["factors"])},
            "confirm": {"factors": confirm_map.get(pair, policy["defaults"]["confirm"]["factors"])},
        }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(yaml.safe_dump(policy, allow_unicode=True, sort_keys=False), encoding="utf-8")

    print("")
    print("=== timing_policy 生成完成 ===")
    print(f"- main_csv   : {main_csv.as_posix()}")
    print(f"- confirm_csv: {confirm_csv.as_posix()}")
    print(f"- out        : {out_path.as_posix()}")
    print(f"- pairs      : {len(pairs)}")
    print(f"- topk       : {topk}")
    print(f"- allow_watch: {bool(args.allow_watch)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
