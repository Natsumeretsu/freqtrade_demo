from __future__ import annotations

"""
export_timing_policy.py - 把择时体检（timing_audit）的结果合成“执行器策略可用”的 policy 文件

你最关心的不是“研究报告”，而是“我接下来到底怎么跑回测/实盘”：
- timing_audit 负责：批量筛因子，输出每个币的最佳因子（含方向/稳健性/成本后收益）
- 本脚本负责：把 15m（主）和 1h（复核）的 summary 合并成一个 YAML，供 Freqtrade 执行器策略读取

重要（与“本征模态/去冗余”目标对齐）：
- 默认启用“相关性去冗余”：在同一 pair 内，用择时序列（pos）之间的 |corr| 判断信号是否重复。
- 这要求 timing_audit 运行时带上 --export-series（输出 timing_<pair>_<factor>_h<h>.csv），否则本脚本会明确报错。

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
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml


_REPO_ROOT = Path(__file__).resolve().parents[2]
_DEDUPE_METHODS = ("corr", "none")


def _repo_rel(path: Path) -> str:
    """
    将路径转为仓库相对路径（posix），避免把本机绝对路径写进可提交文件。

    说明：
    - policy 的 meta 仅用于追溯/复现，不应泄漏用户目录或磁盘路径；
    - 若路径不在仓库内（例如跨盘），为安全起见退化为仅保留 basename。
    """
    try:
        return path.resolve().relative_to(_REPO_ROOT).as_posix()
    except Exception:
        return path.name


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
        "--allow-other-horizons",
        action="store_true",
        help="允许使用非 prefer-horizon 的行（默认只用 prefer-horizon，避免执行/研究尺度错配）。",
    )
    p.add_argument(
        "--roll-key",
        default="roll_30d_median",
        help="排序指标（默认 roll_30d_median）。",
    )

    p.add_argument(
        "--main-entry-threshold",
        type=float,
        default=0.67,
        help="写入 policy.main.entry_threshold（默认 0.67）。",
    )
    p.add_argument(
        "--main-exit-threshold",
        type=float,
        default=None,
        help="写入 policy.main.exit_threshold（默认与 entry_threshold 相同）。",
    )
    p.add_argument(
        "--confirm-entry-threshold",
        type=float,
        default=0.67,
        help="写入 policy.confirm.entry_threshold（默认 0.67）。",
    )
    p.add_argument(
        "--confirm-exit-threshold",
        type=float,
        default=None,
        help="写入 policy.confirm.exit_threshold（默认与 entry_threshold 相同）。",
    )

    p.add_argument(
        "--fusion-main-weight",
        type=float,
        default=0.70,
        help="写入 policy.fusion.main_weight（默认 0.70，随后会在策略侧做归一化）。",
    )
    p.add_argument(
        "--fusion-confirm-weight",
        type=float,
        default=0.30,
        help="写入 policy.fusion.confirm_weight（默认 0.30，随后会在策略侧做归一化）。",
    )
    p.add_argument(
        "--fusion-entry-threshold",
        type=float,
        default=None,
        help="写入 policy.fusion.entry_threshold（默认取 main_entry_threshold）。",
    )
    p.add_argument(
        "--fusion-exit-threshold",
        type=float,
        default=None,
        help="写入 policy.fusion.exit_threshold（默认取 fusion_entry_threshold）。",
    )

    p.add_argument(
        "--weight-mode",
        choices=("equal", "harmonic"),
        default="equal",
        help="TopK 因子权重方案：equal=同权；harmonic=按名次 1/k 衰减后归一化。",
    )

    p.add_argument(
        "--dedupe-method",
        choices=_DEDUPE_METHODS,
        default="corr",
        help="去冗余方法：corr=按择时序列(pos)相关性去重；none=不去重。",
    )
    p.add_argument(
        "--dedupe-threshold",
        type=float,
        default=0.90,
        help="相关性去冗余阈值：|corr| >= threshold 视为“同一模态/重复信号”。",
    )
    p.add_argument(
        "--dedupe-min-common-obs",
        type=int,
        default=200,
        help="计算相关性所需的最小共同观测点数（默认 200）。",
    )
    p.add_argument(
        "--dedupe-family-cap",
        type=int,
        default=0,
        help=(
            "同一 pair 内每个“因子家族”最多保留 N 个（默认 0=不限制）。"
            "用于抑制 ema/vol/adx 等线性相关家族占满 TopK，逼近“少数模态张成”。"
        ),
    )
    p.add_argument(
        "--main-series-dir",
        default="",
        help="15m（主）择时序列 CSV 目录（默认取 main-csv 所在目录）。",
    )
    p.add_argument(
        "--confirm-series-dir",
        default="",
        help="1h（复核）择时序列 CSV 目录（默认取 confirm-csv 所在目录）。",
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


def _safe_name(s: str) -> str:
    """
    生成与 timing_audit.py 一致的文件名片段。
    """
    return str(s).replace("/", "_").replace(":", "_").replace("\\", "_")


def _resolve_series_dir(*, arg: str, csv_path: Path) -> Path:
    raw = str(arg or "").strip()
    if raw:
        return (_REPO_ROOT / Path(raw)).resolve()
    return csv_path.parent.resolve()


def _series_path(*, series_dir: Path, pair: str, factor: str, horizon: int) -> Path:
    safe_pair = _safe_name(pair)
    safe_factor = _safe_name(factor)
    hh = int(horizon)
    return (series_dir / f"timing_{safe_pair}_{safe_factor}_h{hh}.csv").resolve()


def _load_pos_series(*, series_dir: Path, pair: str, factor: str, horizon: int) -> pd.Series:
    path = _series_path(series_dir=series_dir, pair=pair, factor=factor, horizon=horizon)
    if not path.is_file():
        raise FileNotFoundError(
            "未找到择时序列文件："
            f"{path.as_posix()}\n"
            "提示：请在运行 scripts/qlib/timing_audit.py 时加入 --export-series，"
            "确保输出 timing_<pair>_<factor>_h<h>.csv。"
        )
    df = pd.read_csv(path, index_col=0)
    if df is None or df.empty or "pos" not in df.columns:
        raise ValueError(f"择时序列文件格式异常（需要 pos 列）：{path.as_posix()}")
    s = df["pos"].astype("float64").replace([np.inf, -np.inf], np.nan).dropna()
    s.name = f"{pair}|{factor}|h{int(horizon)}"
    return s


def _factor_family(factor: str) -> str:
    """
    将因子名映射为“家族”，用于限制同一类指标在 TopK 中的重复出现。

    设计目标：
    - 把“同一类线性滤波/变换”的多窗口版本归为同一族（ema/vol/adx/atr/...）
    - 把 Koopa-lite 的不同组件拆分为更细家族（koop_pred/koop_fit/koop_spectrum/fft）
    - 未识别的因子：回退到第一个 '_' 之前的前缀，尽量避免全部落到 'other'
    """
    n = str(factor or "").strip().lower()
    if not n:
        return "other"

    # --- 特殊：避免 ema_spread 与 ema_<n> 被强行视为同一族（保留一定互补性） ---
    if n == "ema_spread":
        return "ema_spread"

    # --- Koopman 本征模态因子（PyDMD HODMD） ---
    if n.startswith("koop_pred_ret"):
        return "koop_pred"
    if n == "koop_spectral_radius":
        return "koop_spectrum"
    if n == "koop_reconstruction_error":
        return "koop_error"
    if n.startswith("koop_mode_") and "_amp" in n:
        return "koop_mode_amp"
    if n.startswith("koop_mode_") and "_freq" in n:
        return "koop_mode_freq"
    if n.startswith("koop_mode_") and "_decay" in n:
        return "koop_mode_decay"
    if n.startswith("koop_"):
        return "koop_other"

    # --- 常见技术指标家族 ---
    if n.startswith("ema_"):
        return "ema"
    if n.startswith("adx"):
        return "adx"
    if n.startswith("atr_pct"):
        return "atr_pct"
    if n.startswith("atr"):
        return "atr"
    if n.startswith("vol_"):
        return "vol"
    if n.startswith("ret_"):
        return "ret"
    if n.startswith("roc_"):
        return "roc"
    if n.startswith("rsi_"):
        return "rsi"
    if n.startswith("bb_width_"):
        return "bb_width"
    if n.startswith("bb_percent_b_"):
        return "bb_percent_b"
    if n.startswith("macd"):
        return "macd"
    if n.startswith("stoch_"):
        return "stoch"
    if n.startswith("cci_"):
        return "cci"
    if n.startswith("mfi_"):
        return "mfi"
    if n.startswith("willr_"):
        return "willr"
    if n.startswith("skew_"):
        return "skew"
    if n.startswith("kurt_"):
        return "kurt"
    if n.startswith("volume_z_"):
        return "volume_z"
    if n == "hl_range":
        return "hl_range"

    # 默认回退：用前缀当家族（例如 foo_12 → foo）
    return n.split("_", 1)[0] if "_" in n else n


def _abs_corr_active(a: pd.Series, b: pd.Series, *, min_common_obs: int) -> float:
    """
    计算择时仓位(pos)的 |corr|，优先在“至少一方非 0”的 active 子集上评估：

    - 目的：避免两条信号都“长期空仓(0)”导致虚高的相似性。
    - 若 active 样本不足，则回退到全量交集。
    """
    aa = a.astype("float64")
    bb = b.astype("float64")
    joined = pd.concat([aa, bb], axis=1, join="inner").dropna()
    if joined is None or joined.empty:
        return float("nan")

    if int(len(joined)) < int(min_common_obs):
        return float("nan")

    x = joined.iloc[:, 0].to_numpy(dtype="float64")
    y = joined.iloc[:, 1].to_numpy(dtype="float64")
    active = (x != 0.0) | (y != 0.0)
    if int(active.sum()) >= int(min_common_obs):
        x2 = x[active]
        y2 = y[active]
    else:
        x2 = x
        y2 = y

    # 零方差：说明该信号基本不动/不交易，视作“高度冗余”（避免把 dead signal 选进 TopK）
    if float(np.nanstd(x2)) <= 1e-12 or float(np.nanstd(y2)) <= 1e-12:
        return 1.0

    corr = float(np.corrcoef(x2, y2)[0, 1])
    if not np.isfinite(corr):
        return 1.0
    return abs(corr)


def _diversify_by_corr(
    *,
    rows: list[dict[str, Any]],
    series_dir: Path,
    threshold: float,
    min_common_obs: int,
    family_cap: int,
    topk: int,
) -> list[dict[str, Any]]:
    """
    在同一 pair 内做相关性去冗余（贪心）：
    - 先按输入 rows 的顺序（已排好：pass 优先、roll 降序）遍历
    - 若候选与已选任一项的 |corr| >= threshold，则视为重复信号并跳过
    - 若 family_cap>0，则同一“因子家族”最多选 family_cap 个（家族由 _factor_family() 规则给出）
    - 若某候选缺少择时序列(pos)文件，则跳过其相关性判断（避免因裁剪导出导致硬失败）
    - 不足 TopK 时：先放宽相关性阈值、再放宽 family_cap，最后才用剩余候选“强行补齐”（避免 policy 为空）
    """
    if not rows:
        return []

    thr = float(threshold)
    if not np.isfinite(thr) or thr <= 0:
        thr = 0.90
    if thr > 0.999:
        thr = 0.999

    min_obs = int(min_common_obs)
    if min_obs <= 0:
        min_obs = 200

    fam_cap = int(family_cap)
    if fam_cap < 0:
        fam_cap = 0

    # 1) 惰性加载 + 贪心选择（TopK 很小，避免为低排名候选做大量 IO）
    selected: list[int] = []
    selected_pos: list[pd.Series] = []
    family_counts: dict[str, int] = {}
    missing_idx: set[int] = set()
    missing_order: list[int] = []
    missing_examples: list[str] = []
    pos_cache: dict[int, pd.Series] = {}

    # 阈值逐步放宽：先尽量“去冗余”，不足再逐步放宽以补齐 TopK
    thr_steps: list[float] = [thr]
    for t in [0.90, 0.95, 0.99, 0.999]:
        if float(t) > float(thr_steps[-1]):
            thr_steps.append(float(t))

    n = int(len(rows))

    def _try_pick(*, corr_thr: float, enforce_family_cap: bool) -> None:
        for i in range(n):
            if len(selected) >= int(topk):
                break
            if i in selected:
                continue

            r = rows[i]
            pair = str(r.get("pair", ""))
            factor = str(r.get("factor", ""))
            hz = int(r.get("horizon", 1))

            fam = _factor_family(factor)
            if enforce_family_cap and fam_cap > 0:
                if int(family_counts.get(fam, 0)) >= int(fam_cap):
                    continue

            series_path = _series_path(series_dir=series_dir, pair=pair, factor=factor, horizon=hz)
            if not series_path.is_file():
                if i not in missing_idx:
                    missing_idx.add(i)
                    missing_order.append(i)
                    if len(missing_examples) < 3:
                        missing_examples.append(series_path.as_posix())
                # 缺少 pos 序列时：无法参与相关性去冗余；留给“补齐阶段”处理
                continue

            if i not in pos_cache:
                pos_cache[i] = _load_pos_series(series_dir=series_dir, pair=pair, factor=factor, horizon=hz)
            s = pos_cache[i]

            if not selected_pos:
                selected.append(i)
                selected_pos.append(s)
                if enforce_family_cap and fam_cap > 0:
                    family_counts[fam] = int(family_counts.get(fam, 0)) + 1
                continue

            ok = True
            for sp in selected_pos:
                c = _abs_corr_active(s, sp, min_common_obs=min_obs)
                v = 0.0 if (c is None or (not np.isfinite(float(c)))) else float(c)
                if float(v) >= float(corr_thr):
                    ok = False
                    break
            if ok:
                selected.append(i)
                selected_pos.append(s)
                if enforce_family_cap and fam_cap > 0:
                    family_counts[fam] = int(family_counts.get(fam, 0)) + 1

    # 1-A) 先启用 family_cap（若配置）并用严格阈值开始去冗余
    for t in thr_steps:
        _try_pick(corr_thr=float(t), enforce_family_cap=True)
        if len(selected) >= int(topk):
            break

    # 1-A2) 仍不足 TopK：优先用“缺少 pos 序列”的候选补齐，但仍遵守 family_cap
    # 这样可以避免因为 timing_audit 的导出裁剪导致“不得不放弃 family_cap”。
    if len(selected) < int(topk) and missing_order:
        selected_set = set(selected)
        for i in missing_order:
            if len(selected) >= int(topk):
                break
            if i in selected_set:
                continue
            r = rows[i]
            factor = str(r.get("factor", ""))
            fam = _factor_family(factor)
            if fam_cap > 0 and int(family_counts.get(fam, 0)) >= int(fam_cap):
                continue
            selected.append(i)
            selected_set.add(i)
            if fam_cap > 0:
                family_counts[fam] = int(family_counts.get(fam, 0)) + 1

    # 1-B) 仍不足 TopK：允许同族多选，但仍尽量保持低相关
    if len(selected) < int(topk):
        for t in thr_steps:
            _try_pick(corr_thr=float(t), enforce_family_cap=False)
            if len(selected) >= int(topk):
                break

    # 只有当“缺少 pos 序列”的候选被选中时，才提示 corr 去冗余不完整（避免刷屏）。
    selected_missing = [i for i in selected if i in missing_idx]
    if selected_missing:
        ex = "；示例：" + ", ".join(missing_examples) if missing_examples else ""
        print(
            "[WARN] corr 去冗余："
            f"有 {len(selected_missing)} 个被选中的候选缺少 pos 序列文件，"
            f"已对这些候选跳过相关性判断（候选缺失合计 {len(missing_idx)}）{ex}"
        )

    # 2) 不足 TopK：补齐（不再考虑相关性/同族上限）
    if len(selected) < int(topk):
        selected_set = set(selected)
        for i in range(n):
            if len(selected) >= int(topk):
                break
            if i in selected_set:
                continue
            selected.append(i)
            selected_set.add(i)

    return [rows[idx] for idx in selected[: int(topk)]]


def _select_topk(
    df: pd.DataFrame,
    *,
    topk: int,
    allow_watch: bool,
    roll_key: str,
    prefer_horizon: int,
    allow_other_horizons: bool,
    weight_mode: str,
    dedupe_method: str,
    dedupe_threshold: float,
    dedupe_min_common_obs: int,
    dedupe_family_cap: int,
    series_dir: Path,
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

    method = str(dedupe_method or "").strip().lower()
    if method not in _DEDUPE_METHODS:
        raise ValueError(f"dedupe_method 不支持：{dedupe_method}（支持：{list(_DEDUPE_METHODS)}）")
    if method != "none":
        if series_dir is None or not Path(series_dir).is_dir():
            raise ValueError(f"series_dir 不存在或不是目录：{Path(series_dir).as_posix()}")

    work = df.copy()
    if work is None or work.empty:
        return {}

    # --- 口径对齐：horizon ---
    if "horizon" in work.columns:
        hz = pd.to_numeric(work["horizon"], errors="coerce").astype("float64")
        work["horizon"] = hz
    else:
        work["horizon"] = float("nan")

    prefer = int(prefer_horizon)
    work["_horizon_pref"] = (work["horizon"] == float(prefer)).astype("int64")

    # 默认强约束：只用 prefer_horizon，避免把“不同持仓周期”的研究结果混进同一个执行器策略
    if (not bool(allow_other_horizons)) and "horizon" in df.columns:
        work = work[work["horizon"] == float(prefer)].copy()

    if work is None or work.empty:
        return {}

    # --- 排序分数 ---
    if roll_col:
        work["_roll"] = pd.to_numeric(work[roll_col], errors="coerce").astype("float64")
    else:
        work["_roll"] = float("nan")
    work["_roll"] = work["_roll"].replace([np.inf, -np.inf], np.nan).fillna(float("-inf"))

    # --- verdict 过滤（pass 优先，其次 watch） ---
    verdict_col = "verdict" if "verdict" in work.columns else ""
    if verdict_col:
        v = work[verdict_col].astype(str).str.lower()
        work["_verdict_rank"] = np.where(v == "pass", 0, np.where(v == "watch", 1, 99)).astype("int64")
        if bool(allow_watch):
            work = work[work["_verdict_rank"] <= 1].copy()
        else:
            work = work[work["_verdict_rank"] == 0].copy()
    else:
        work["_verdict_rank"] = 0

    # --- pair 清洗 ---
    work["pair"] = work["pair"].astype(str).str.strip()
    work = work[work["pair"].astype(str).str.len() > 0].copy()
    if work.empty:
        return {}

    out: dict[str, list[dict[str, Any]]] = {}
    for pair, g in work.groupby("pair", sort=False):
        gg = g.sort_values(["_verdict_rank", "_horizon_pref", "_roll"], ascending=[True, False, False]).copy()
        if gg.empty:
            continue

        # 候选列表（同一 pair 内按 factor/direction/side 去重）
        candidates: list[dict[str, Any]] = []
        seen: set[tuple[str, str, str]] = set()
        for _, r in gg.iterrows():
            factor = str(r.get("factor", "")).strip()
            if not factor:
                continue
            direction = str(r.get("direction", "pos")).strip().lower()
            side = str(r.get("side", "both")).strip().lower()
            if direction not in {"pos", "neg"}:
                direction = "pos"
            if side not in {"both", "long", "short"}:
                side = "both"
            key = (factor, direction, side)
            if key in seen:
                continue
            seen.add(key)

            hz2 = _to_float(r.get("horizon"))
            hz_i = int(hz2) if math.isfinite(hz2) and int(hz2) > 0 else int(prefer)
            candidates.append(
                {
                    "pair": str(pair),
                    "factor": factor,
                    "direction": direction,
                    "side": side,
                    "horizon": int(hz_i),
                    "_roll": float(_to_float(r.get("_roll"))),
                }
            )

        if not candidates:
            continue

        picked_rows: list[dict[str, Any]]
        if method == "corr":
            picked_rows = _diversify_by_corr(
                rows=candidates,
                series_dir=Path(series_dir),
                threshold=float(dedupe_threshold),
                min_common_obs=int(dedupe_min_common_obs),
                family_cap=int(dedupe_family_cap),
                topk=int(max(1, topk)),
            )
        else:
            picked_rows = candidates[: int(max(1, topk))]

        wm = str(weight_mode or "").strip().lower()
        if wm == "harmonic":
            raw_w = [1.0 / float(i + 1) for i in range(len(picked_rows))]
            s_w = float(sum(raw_w))
            weights = [(w / s_w) for w in raw_w] if s_w > 0 else [1.0 for _ in raw_w]
        else:
            weights = [1.0 for _ in picked_rows]

        specs: list[dict[str, Any]] = []
        for rr, w in zip(picked_rows, weights, strict=False):
            specs.append(
                {
                    "name": str(rr.get("factor", "")).strip(),
                    "direction": str(rr.get("direction", "pos")).strip().lower(),
                    "side": str(rr.get("side", "both")).strip().lower(),
                    "weight": float(w),
                }
            )
        specs = [s for s in specs if str(s.get("name", "")).strip()]
        if specs:
            out[str(pair)] = _normalize_weight_list(specs)

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
    main_entry_threshold = float(args.main_entry_threshold)
    confirm_entry_threshold = float(args.confirm_entry_threshold)
    main_exit_threshold = (
        float(args.main_exit_threshold) if args.main_exit_threshold is not None else float(main_entry_threshold)
    )
    confirm_exit_threshold = (
        float(args.confirm_exit_threshold) if args.confirm_exit_threshold is not None else float(confirm_entry_threshold)
    )
    fusion_main_weight = float(args.fusion_main_weight)
    fusion_confirm_weight = float(args.fusion_confirm_weight)
    fusion_entry_threshold = (
        float(args.fusion_entry_threshold) if args.fusion_entry_threshold is not None else float(main_entry_threshold)
    )
    fusion_exit_threshold = (
        float(args.fusion_exit_threshold) if args.fusion_exit_threshold is not None else float(fusion_entry_threshold)
    )

    main_series_dir = _resolve_series_dir(arg=str(args.main_series_dir), csv_path=main_csv)
    confirm_series_dir = _resolve_series_dir(arg=str(args.confirm_series_dir), csv_path=confirm_csv)

    main_map = _select_topk(
        df_main,
        topk=topk,
        allow_watch=bool(args.allow_watch),
        roll_key=roll_key,
        prefer_horizon=int(args.prefer_horizon),
        allow_other_horizons=bool(args.allow_other_horizons),
        weight_mode=str(args.weight_mode),
        dedupe_method=str(args.dedupe_method),
        dedupe_threshold=float(args.dedupe_threshold),
        dedupe_min_common_obs=int(args.dedupe_min_common_obs),
        dedupe_family_cap=int(args.dedupe_family_cap),
        series_dir=main_series_dir,
    )
    confirm_map = _select_topk(
        df_confirm,
        topk=topk,
        allow_watch=bool(args.allow_watch),
        roll_key=roll_key,
        prefer_horizon=int(args.prefer_horizon),
        allow_other_horizons=bool(args.allow_other_horizons),
        weight_mode=str(args.weight_mode),
        dedupe_method=str(args.dedupe_method),
        dedupe_threshold=float(args.dedupe_threshold),
        dedupe_min_common_obs=int(args.dedupe_min_common_obs),
        dedupe_family_cap=int(args.dedupe_family_cap),
        series_dir=confirm_series_dir,
    )

    pairs = sorted(set(main_map.keys()) | set(confirm_map.keys()))

    policy: dict[str, Any] = {
        "version": 2,
        "exchange": "okx",
        "trading_mode": "futures",
        "meta": {
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "generator": "scripts/qlib/export_timing_policy.py",
            "main_csv": _repo_rel(main_csv),
            "confirm_csv": _repo_rel(confirm_csv),
            "main_series_dir": _repo_rel(main_series_dir),
            "confirm_series_dir": _repo_rel(confirm_series_dir),
            "topk": int(topk),
            "allow_watch": bool(args.allow_watch),
            "roll_key": str(roll_key),
            "weight_mode": str(args.weight_mode),
            "prefer_horizon": int(args.prefer_horizon),
            "allow_other_horizons": bool(args.allow_other_horizons),
            "dedupe": {
                "method": str(args.dedupe_method),
                "threshold": float(args.dedupe_threshold),
                "min_common_obs": int(args.dedupe_min_common_obs),
                "family_cap": int(args.dedupe_family_cap),
                "note": (
                    "去冗余基于择时序列 pos 的 |corr|（active 优先）+ 同族上限（family_cap），"
                    "用于逼近“少数模态张成”的信号集合。"
                ),
            },
        },
        "main": {
            "timeframe": str(main_tf),
            "quantiles": 5,
            "lookback_days": 14,
            "entry_threshold": float(main_entry_threshold),
            "exit_threshold": float(main_exit_threshold),
        },
        "confirm": {
            "timeframe": str(confirm_tf),
            "quantiles": 5,
            "lookback_days": 30,
            "entry_threshold": float(confirm_entry_threshold),
            "exit_threshold": float(confirm_exit_threshold),
        },
        "fusion": {
            "main_weight": float(fusion_main_weight),
            "confirm_weight": float(fusion_confirm_weight),
            "entry_threshold": float(fusion_entry_threshold),
            "exit_threshold": float(fusion_exit_threshold),
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
    print(f"- main_series_dir   : {main_series_dir.as_posix()}")
    print(f"- confirm_series_dir: {confirm_series_dir.as_posix()}")
    print(f"- out        : {out_path.as_posix()}")
    print(f"- pairs      : {len(pairs)}")
    print(f"- topk       : {topk}")
    print(f"- allow_watch: {bool(args.allow_watch)}")
    print(f"- roll_key   : {roll_key}")
    print(f"- weight_mode: {str(args.weight_mode)}")
    print(f"- main_entry_threshold   : {float(main_entry_threshold)}")
    print(f"- confirm_entry_threshold: {float(confirm_entry_threshold)}")
    print(f"- main_exit_threshold    : {float(main_exit_threshold)}")
    print(f"- confirm_exit_threshold : {float(confirm_exit_threshold)}")
    print(f"- fusion_main_weight     : {float(fusion_main_weight)}")
    print(f"- fusion_confirm_weight  : {float(fusion_confirm_weight)}")
    print(f"- fusion_entry_threshold : {float(fusion_entry_threshold)}")
    print(f"- fusion_exit_threshold  : {float(fusion_exit_threshold)}")
    print(f"- prefer_horizon: {int(args.prefer_horizon)}")
    print(f"- allow_other_horizons: {bool(args.allow_other_horizons)}")
    print(f"- dedupe_method   : {str(args.dedupe_method)}")
    print(f"- dedupe_threshold: {float(args.dedupe_threshold)}")
    print(f"- dedupe_min_obs  : {int(args.dedupe_min_common_obs)}")
    print(f"- dedupe_family_cap: {int(args.dedupe_family_cap)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
