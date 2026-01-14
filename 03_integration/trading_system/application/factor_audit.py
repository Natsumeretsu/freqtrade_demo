from __future__ import annotations

"""
factor_audit.py - 因子体检（研究层通用工具）

本模块提供“横截面因子体检”的可复用函数：
- RankIC（Spearman）
- 分位组合收益（top / bottom / long-short）
- 简化成本后收益（按换手 * round-trip 成本）
- 时间周期解析（15m/1h/4h 等）

设计目标：
- 研究脚本（scripts/qlib/factor_audit.py）与后续策略/模型工具可复用同一套指标口径；
- 保持依赖轻量：仅 pandas/numpy。
"""

import math
from typing import Any

import numpy as np
import pandas as pd
from qlib.contrib.eva.alpha import calc_ic


def parse_timeframe_minutes(timeframe: str) -> int | None:
    tf = str(timeframe or "").strip().lower()
    if not tf:
        return None

    if tf.endswith("m"):
        n = tf[:-1].strip()
        if n.isdigit():
            v = int(n)
            return v if v > 0 else None
        return None
    if tf.endswith("h"):
        n = tf[:-1].strip()
        if n.isdigit():
            v = int(n)
            return v * 60 if v > 0 else None
        return None
    if tf.endswith("d"):
        n = tf[:-1].strip()
        if n.isdigit():
            v = int(n)
            return v * 24 * 60 if v > 0 else None
        return None

    return None


def bars_per_day(timeframe: str) -> int | None:
    minutes = parse_timeframe_minutes(timeframe)
    if minutes is None or minutes <= 0:
        return None
    if 1440 % minutes != 0:
        return None
    return int(1440 // minutes)


def normalize_weights(*, pairs: list[str], weights: dict[str, float]) -> dict[str, float]:
    """
    归一化权重（只保留 pairs 内的项，且 w>0）。
    """
    if not weights:
        return {}

    out: dict[str, float] = {}
    for p in pairs:
        w = weights.get(p)
        if w is None:
            continue
        try:
            ww = float(w)
        except Exception:
            continue
        if not math.isfinite(ww) or ww <= 0:
            continue
        out[str(p)] = ww

    total = float(sum(out.values()))
    if total <= 0:
        return {}
    return {k: float(v / total) for k, v in out.items()}


def market_return_series(y_wide: pd.DataFrame, weights: dict[str, float]) -> pd.Series:
    """
    market_ret：用所有可用资产的 forward return 做等权/权重均值。

    - weights 为空：等权（忽略 NaN）
    - weights 非空：按列权重加权，并对缺失列/缺失值做动态归一化
    """
    y = y_wide.astype("float64")
    if y.empty:
        return pd.Series(dtype="float64")

    if not weights:
        return y.mean(axis=1, skipna=True)

    w = pd.Series(weights, dtype="float64").reindex(y.columns).fillna(0.0)
    if float(w.sum()) <= 0:
        return y.mean(axis=1, skipna=True)

    mask = y.notna()
    w_eff = mask.mul(w, axis=1).astype("float64")
    denom = w_eff.sum(axis=1).replace(0.0, np.nan)
    num = y.fillna(0.0).mul(w, axis=1).sum(axis=1)
    return (num / denom).astype("float64")


def cross_section_audit(
    *,
    x_wide: pd.DataFrame,
    y_wide: pd.DataFrame,
    quantiles: int,
    weights: dict[str, float],
    fee_rate: float,
    slippage_rate: float,
) -> tuple[pd.Series, pd.DataFrame]:
    """
    横截面因子体检（单因子）。

    输入：
    - x_wide：因子值矩阵，index=date，columns=pair
    - y_wide：forward return 矩阵，index=date，columns=pair

    输出：
    - ic_series：每个日期的 RankIC（Spearman）
    - ret_df：包含 top/bottom/long-short、market、alpha、换手、成本后收益等序列
    """
    if x_wide is None or y_wide is None or x_wide.empty or y_wide.empty:
        return pd.Series(dtype="float64"), pd.DataFrame()

    # 对齐 index/columns
    x = x_wide.reindex(index=y_wide.index, columns=y_wide.columns).astype("float64")
    y = y_wide.astype("float64")

    q = int(quantiles)
    if q < 2:
        raise ValueError("quantiles 至少为 2")

    market_ret = market_return_series(y, weights)

    # --- RankIC（Spearman） ---
    # 使用 Qlib 的现成实现：按 datetime 分组计算 spearman 相关（减少自研“造轮子”维护成本）
    xx = x.copy()
    yy = y.copy()
    xx.index = xx.index.rename("datetime")
    yy.index = yy.index.rename("datetime")
    xx.columns = xx.columns.astype("string")
    yy.columns = yy.columns.astype("string")
    xx.columns.name = "instrument"
    yy.columns.name = "instrument"

    stacked = pd.DataFrame(
        {"pred": xx.stack(future_stack=True), "label": yy.stack(future_stack=True)}
    ).dropna()
    if stacked.empty:
        ic = pd.Series(index=y.index, dtype="float64", name="rank_ic")
    else:
        _, ric = calc_ic(stacked["pred"], stacked["label"], date_col="datetime", dropna=False)
        ic = ric.reindex(y.index).astype("float64")
        # 与旧口径一致：每期至少 3 个点才计算相关（避免小样本把 ic “锁死”在 ±1）
        n_by_date = stacked.groupby(level="datetime").size().reindex(y.index).fillna(0.0).astype("float64")
        ic[(n_by_date < 3.0) | (~np.isfinite(ic))] = np.nan
        ic.name = "rank_ic"

    # --- 分位收益（top/bottom/long-short） ---
    x_rank = x.rank(axis=1, method="average")
    x_count = x_rank.notna().sum(axis=1).astype("float64")
    denom_x = x_count.replace(0.0, np.nan)
    bins = np.floor(((x_rank - 1.0).div(denom_x, axis=0)) * float(q))
    bins = bins.clip(lower=0, upper=q - 1)

    top_mask = bins == (q - 1)
    bottom_mask = bins == 0

    top_ret = y.where(top_mask).mean(axis=1, skipna=True)
    bottom_ret = y.where(bottom_mask).mean(axis=1, skipna=True)
    ls_ret = top_ret - bottom_ret
    top_alpha = top_ret - market_ret

    # turnover（1 - overlap/size）
    top_cnt = top_mask.sum(axis=1).astype("float64")
    bottom_cnt = bottom_mask.sum(axis=1).astype("float64")
    top_overlap = (top_mask & top_mask.shift(1)).sum(axis=1).astype("float64")
    bottom_overlap = (bottom_mask & bottom_mask.shift(1)).sum(axis=1).astype("float64")

    turnover_top = 1.0 - (top_overlap / top_cnt.replace(0.0, np.nan))
    turnover_bottom = 1.0 - (bottom_overlap / bottom_cnt.replace(0.0, np.nan))

    # 首期没有“上一期持仓”，turnover 置空，避免把“首次建仓”混进平均换手
    if len(turnover_top) > 0:
        turnover_top.iloc[0] = np.nan
    if len(turnover_bottom) > 0:
        turnover_bottom.iloc[0] = np.nan

    # 成本模型（简化）：换仓部分发生一次“平旧 + 开新”的 round-trip
    per_side = float(fee_rate) + float(slippage_rate)
    round_trip = 2.0 * per_side
    cost_top = turnover_top * float(round_trip)
    cost_bottom = turnover_bottom * float(round_trip)

    top_ret_net = top_ret - cost_top
    bottom_ret_net = bottom_ret - cost_bottom
    short_bottom_net = (-bottom_ret) - cost_bottom
    ls_ret_net = top_ret_net + short_bottom_net

    ret_df = pd.DataFrame(
        {
            "top_ret": top_ret,
            "bottom_ret": bottom_ret,
            "ls_ret": ls_ret,
            "market_ret": market_ret,
            "top_alpha": top_alpha,
            "turnover_top": turnover_top,
            "turnover_bottom": turnover_bottom,
            "cost_top": cost_top,
            "cost_bottom": cost_bottom,
            "top_ret_net": top_ret_net,
            "bottom_ret_net": bottom_ret_net,
            "short_bottom_net": short_bottom_net,
            "ls_ret_net": ls_ret_net,
        }
    ).sort_index()

    return ic, ret_df


def rolling_return_summary(series: pd.Series, *, timeframe: str, days: list[int]) -> dict[str, Any]:
    """
    计算滚动窗口收益摘要（用 log1p 累加实现几何复利）。
    """
    out: dict[str, Any] = {}
    bpd = bars_per_day(timeframe)
    if bpd is None:
        return out

    s = series.astype("float64").replace([np.inf, -np.inf], np.nan).dropna()
    if s.empty:
        return out

    # 对于 short 或极端波动场景，单期收益可能出现 <= -100%（例如价格暴涨导致 short 亏损超过本金）。
    # 这类“爆仓/归零”事件不能被 log1p 直接变成 NaN 再丢弃，否则会把最坏情景从滚动窗口里“抹掉”。
    # 处理方式：把收益下限裁剪到 (-1, +inf)，保留极端事件对滚动收益的惩罚效应。
    lower = float(np.nextafter(-1.0, 0.0))  # 比 -1 稍大一点的可表示浮点数
    s = s.clip(lower=lower)

    logret = np.log1p(s)

    for d in days:
        dd = int(d)
        if dd <= 0:
            continue
        w = int(dd * bpd)
        if w <= 1:
            continue
        roll = logret.rolling(w).sum()
        rr = np.expm1(roll).dropna()
        if rr.empty:
            continue

        out[f"roll_{dd}d_median"] = float(rr.median())
        out[f"roll_{dd}d_p10"] = float(rr.quantile(0.10))
        out[f"roll_{dd}d_p90"] = float(rr.quantile(0.90))
        out[f"roll_{dd}d_worst"] = float(rr.min())
        out[f"roll_{dd}d_best"] = float(rr.max())
    return out


def _direction_score(
    ret_df: pd.DataFrame, *, timeframe: str, rolling_days: list[int]
) -> tuple[float, float]:
    """
    方向选择打分：优先看 30d（或首个 rolling_days）的滚动中位数，其次看 ls_ret_net 的均值。
    """
    if ret_df is None or ret_df.empty or "ls_ret_net" not in ret_df.columns:
        return (float("-inf"), float("-inf"))

    ls = ret_df["ls_ret_net"].astype("float64").dropna()
    mean = float(ls.mean()) if not ls.empty else float("-inf")
    if not math.isfinite(mean):
        mean = float("-inf")

    roll = rolling_return_summary(ls, timeframe=timeframe, days=rolling_days)
    key: str | None = None
    if 30 in set(int(d) for d in (rolling_days or [])):
        key = "roll_30d_median"
    elif rolling_days:
        key = f"roll_{int(rolling_days[0])}d_median"

    roll_median = roll.get(key) if key else None
    roll_score = float(roll_median) if roll_median is not None else float("-inf")
    if not math.isfinite(roll_score):
        roll_score = float("-inf")

    return (roll_score, mean)


def choose_factor_direction(
    *,
    x_wide: pd.DataFrame,
    y_wide: pd.DataFrame,
    quantiles: int,
    weights: dict[str, float],
    fee_rate: float,
    slippage_rate: float,
    timeframe: str,
    rolling_days: list[int],
) -> tuple[str, pd.Series, pd.DataFrame]:
    """
    自动选择因子方向（正向/反向）。

    - pos：因子值越大越看多（top 分位做多）；
    - neg：因子值越小越看多（等价于对因子取负后再做 top 分位做多）。

    选择准则：
    1) 优先比较 30d（或首个 rolling_days）的滚动收益中位数（基于 ls_ret_net）；
    2) 其次比较 ls_ret_net 的均值。
    """
    ic_pos, ret_pos = cross_section_audit(
        x_wide=x_wide,
        y_wide=y_wide,
        quantiles=quantiles,
        weights=weights,
        fee_rate=fee_rate,
        slippage_rate=slippage_rate,
    )
    ic_neg, ret_neg = cross_section_audit(
        x_wide=-x_wide,
        y_wide=y_wide,
        quantiles=quantiles,
        weights=weights,
        fee_rate=fee_rate,
        slippage_rate=slippage_rate,
    )

    score_pos = _direction_score(ret_pos, timeframe=timeframe, rolling_days=rolling_days)
    score_neg = _direction_score(ret_neg, timeframe=timeframe, rolling_days=rolling_days)

    if score_neg > score_pos:
        return "neg", ic_neg, ret_neg
    return "pos", ic_pos, ret_pos
