from __future__ import annotations

"""
timing_audit.py - 择时因子体检（单品种时间序列）

你关心的是“某个币用某个因子做择时，短期能不能赚到超额收益”，这属于时间序列/择时问题，
而不是横截面（同一时刻在多个币之间选强弱）。

本模块提供：
- 日内 RankIC（把每一天当作一段样本，计算当天因子与未来收益的 Spearman 相关）
- 基于滚动分位阈值的简单择时策略：
  - 因子高于历史分位上阈值 -> 做多
  - 因子低于历史分位下阈值 -> 做空
  - 其他 -> 空仓
- 成本模型：按仓位变化 * 单边成本（fee+slippage）
- 30/60 天滚动稳定性摘要（用几何复利的 log1p 累加）

注意：
这是一套“因子筛选/体检”工具，不等价于完整实盘策略。
当筛出少量“过关”的因子后，再组合成统一评分/概率模型，再由 Freqtrade 负责执行与风控。
"""

import math
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from trading_system.application.factor_audit import parse_timeframe_minutes, rolling_return_summary


@dataclass(frozen=True)
class TimingAuditParams:
    timeframe: str
    horizon: int
    quantiles: int
    lookback_days: int
    fee_rate: float
    slippage_rate: float
    rolling_days: list[int]


def _effective_timeframe(*, timeframe: str, horizon: int) -> str:
    """
    将 “每根K线” 的 timeframe 转换成 “每次持仓周期” 的等效 timeframe。

    示例：
    - timeframe=15m, horizon=4 -> 60m
    - timeframe=1h,  horizon=4 -> 4h
    """
    minutes = parse_timeframe_minutes(timeframe)
    h = int(horizon)
    if minutes is None or minutes <= 0 or h <= 0:
        return str(timeframe)
    eff = int(minutes * h)
    if eff % 60 == 0:
        hh = eff // 60
        return f"{hh}h"
    return f"{eff}m"


def _spearman_corr_1d(a: pd.Series, b: pd.Series) -> float:
    """
    1D Spearman 相关（不依赖 scipy）。
    """
    x = a.astype("float64")
    y = b.astype("float64")
    m = x.notna() & y.notna()
    if int(m.sum()) < 3:
        return float("nan")

    xr = x[m].rank(method="average").to_numpy(dtype="float64")
    yr = y[m].rank(method="average").to_numpy(dtype="float64")
    n = float(len(xr))
    if n < 3:
        return float("nan")

    dx = xr - float(xr.mean())
    dy = yr - float(yr.mean())
    den = float(np.sqrt((dx * dx).sum() * (dy * dy).sum()))
    if not math.isfinite(den) or den <= 0:
        return float("nan")
    return float((dx * dy).sum() / den)


def daily_rank_ic(*, x: pd.Series, y: pd.Series, min_points: int = 10) -> pd.Series:
    """
    计算“日内 RankIC”序列：每个自然日计算一次 Spearman 相关。
    """
    if x is None or y is None:
        return pd.Series(dtype="float64")
    if x.empty or y.empty:
        return pd.Series(dtype="float64")

    xx = x.astype("float64")
    yy = y.astype("float64")
    df = pd.DataFrame({"x": xx, "y": yy}).dropna()
    if df.empty:
        return pd.Series(dtype="float64")

    # 按自然日分组（UTC）
    day = df.index.to_series().dt.floor("D")
    out: dict[pd.Timestamp, float] = {}
    for d, g in df.groupby(day):
        if len(g) < int(min_points):
            continue
        out[pd.Timestamp(d)] = _spearman_corr_1d(g["x"], g["y"])

    s = pd.Series(out, dtype="float64").sort_index()
    s.name = "rank_ic"
    return s


def timing_strategy_series(
    *,
    x: pd.Series,
    fwd_ret: pd.Series,
    btc_ret: pd.Series | None,
    params: TimingAuditParams,
    direction: str,
    side: str = "both",
) -> pd.DataFrame:
    """
    生成择时策略收益序列（非重叠持仓：每 horizon 根 K 线评估/换仓一次）。

    说明：
    - 该函数会在内部计算滚动分位阈值（rolling quantile）。
    - 如果你要批量评估大量因子（几十个/上百个），建议先用
      `precompute_quantile_thresholds()` 预计算阈值，再调用
      `choose_timing_direction_with_thresholds()`，性能会好很多。
    """
    if x is None or fwd_ret is None:
        return pd.DataFrame()
    if x.empty or fwd_ret.empty:
        return pd.DataFrame()

    q = int(params.quantiles)
    if q < 2:
        raise ValueError("quantiles 至少为 2")

    horizon = int(params.horizon)
    if horizon <= 0:
        raise ValueError("horizon 必须为正整数")

    tf_minutes = parse_timeframe_minutes(params.timeframe)
    if tf_minutes is None or tf_minutes <= 0:
        raise ValueError("timeframe 无法解析为分钟：仅支持 15m/1h/4h 等格式")

    lookback_days = int(params.lookback_days)
    if lookback_days <= 0:
        raise ValueError("lookback_days 必须为正整数")

    bars_per_day = int(1440 // int(tf_minutes)) if (1440 % int(tf_minutes) == 0) else None
    if bars_per_day is None or bars_per_day <= 0:
        raise ValueError("timeframe 无法整除 1440：无法换算天内 bars")

    lookback_bars = int(lookback_days * bars_per_day)
    if lookback_bars <= 10:
        raise ValueError("lookback_bars 过小：请增大 lookback_days 或使用更高频 timeframe")

    xx = x.astype("float64").copy()
    yy = fwd_ret.astype("float64")

    # 滚动分位阈值（只需要 top/bottom 两条阈值）
    # 注意：shift(1) 避免前向偏差（t 时刻的阈值只能用 t-1 及之前的数据）
    high_q = 1.0 - (1.0 / float(q))
    low_q = 1.0 / float(q)
    q_high = xx.rolling(lookback_bars).quantile(high_q).shift(1)
    q_low = xx.rolling(lookback_bars).quantile(low_q).shift(1)

    pos = position_from_thresholds(x=xx, q_high=q_high, q_low=q_low, direction=str(direction))
    pos = apply_trade_side(pos=pos, side=str(side))
    return timing_returns_from_positions(pos=pos, fwd_ret=yy, btc_ret=btc_ret, params=params)


def timing_returns_from_positions(
    *,
    pos: pd.Series,
    fwd_ret: pd.Series,
    btc_ret: pd.Series | None,
    params: TimingAuditParams,
) -> pd.DataFrame:
    """
    从“目标仓位序列”生成择时策略收益序列。

    - 非重叠持仓：每 horizon 根 K 线评估/换仓一次
    - 成本模型：按仓位变化 * 单边成本（fee + slippage）
    """
    if pos is None or fwd_ret is None:
        return pd.DataFrame()
    if pos.empty or fwd_ret.empty:
        return pd.DataFrame()

    horizon = int(params.horizon)
    if horizon <= 0:
        raise ValueError("horizon 必须为正整数")

    df = pd.DataFrame({"pos": pos.astype("float64"), "fwd_ret": fwd_ret.astype("float64")}).sort_index()
    if btc_ret is not None and not btc_ret.empty:
        df["btc_ret"] = btc_ret.astype("float64").reindex(df.index)

    # 丢弃没有 forward return 的行
    work = df.dropna(subset=["fwd_ret"])
    work = work.dropna(subset=["pos", "fwd_ret"], how="any")
    if work.empty:
        return pd.DataFrame()

    # 非重叠抽样：每 horizon 根 K 线做一次“开仓/持有/换仓”决策
    work = work.iloc[::horizon].copy()
    if work.empty:
        return pd.DataFrame()

    # 成本模型：按仓位变化 * 单边成本（fee + slippage）
    per_side = float(params.fee_rate) + float(params.slippage_rate)
    prev_pos = work["pos"].shift(1).fillna(0.0)
    trade_size = (work["pos"] - prev_pos).abs()
    cost = trade_size * float(per_side)

    gross = work["pos"] * work["fwd_ret"]
    net = gross - cost

    out = pd.DataFrame(
        {
            "pos": work["pos"].astype("float64"),
            "fwd_ret": work["fwd_ret"].astype("float64"),
            "trade_size": trade_size.astype("float64"),
            "cost": cost.astype("float64"),
            "gross_ret": gross.astype("float64"),
            "net_ret": net.astype("float64"),
        },
        index=work.index,
    ).sort_index()

    if "btc_ret" in work.columns:
        out["btc_ret"] = work["btc_ret"].astype("float64")
        out["alpha_btc_net"] = (out["net_ret"] - out["btc_ret"]).astype("float64")

    return out.replace([np.inf, -np.inf], np.nan)


def position_from_thresholds(*, x: pd.Series, q_high: pd.Series, q_low: pd.Series, direction: str) -> pd.Series:
    """
    由滚动分位阈值生成目标仓位：多/空/空仓。

    - direction=pos：因子越大越偏多（x 高 -> 多）
    - direction=neg：因子越小越偏多（x 低 -> 多）

    注意：
    - direction=neg 并不会重新对 -x 计算分位阈值，而是利用“分位对称”关系：
      用同一套 (q_high, q_low) 推导出相反方向的阈值决策。
    """
    if x is None or x.empty:
        return pd.Series(dtype="float64")
    if q_high is None or q_low is None:
        return pd.Series(0.0, index=x.index, dtype="float64")

    xx = x.astype("float64")
    hi = q_high.astype("float64").reindex(xx.index)
    lo = q_low.astype("float64").reindex(xx.index)

    pos = pd.Series(0.0, index=xx.index, dtype="float64")
    d = str(direction or "").strip().lower()
    if d == "neg":
        # 等价于对 -x 做分位阈值：x 越小越偏多
        pos[xx <= lo] = 1.0
        pos[xx >= hi] = -1.0
    else:
        pos[xx >= hi] = 1.0
        pos[xx <= lo] = -1.0
    return pos


def continuous_score_from_thresholds(
    *,
    x: pd.Series,
    q_high: pd.Series,
    q_low: pd.Series,
    direction: str,
    clip: float = 1.0,
    eps: float = 1e-12,
) -> pd.Series:
    """
    使用滚动分位阈值把因子值映射为 [-clip, clip] 的连续得分（更像“投影/加权和”，而非二值投票）。

    约定（direction=pos）：
    - x == q_low  -> score == -1
    - x == q_high -> score == +1
    - x 在 (q_low, q_high) 内线性插值

    direction=neg：符号翻转（因子越小越偏多）。

    注意：
    - q_high/q_low 可能因为 lookback 不足而为 NaN，此时返回 0（不贡献信号）。
    - 当 q_high≈q_low（序列近似常数）时，用 eps 做数值稳定。
    """
    if x is None or x.empty:
        return pd.Series(dtype="float64")
    if q_high is None or q_low is None:
        return pd.Series(0.0, index=x.index, dtype="float64")

    xx = x.astype("float64")
    hi = q_high.astype("float64").reindex(xx.index)
    lo = q_low.astype("float64").reindex(xx.index)

    mid = (hi + lo) / 2.0
    half_span = (hi - lo).abs() / 2.0

    c = float(clip)
    if not np.isfinite(c) or c <= 0:
        c = 1.0

    e = float(eps)
    if not np.isfinite(e) or e <= 0:
        e = 1e-12

    denom = half_span + e
    raw = (xx - mid) / denom
    raw = raw.replace([np.inf, -np.inf], np.nan).clip(lower=-c, upper=c).fillna(0.0)

    d = str(direction or "").strip().lower()
    if d == "neg":
        raw = -raw
    return raw.astype("float64")


def apply_trade_side(*, pos: pd.Series, side: str) -> pd.Series:
    """
    将目标仓位裁剪为“只做多 / 只做空 / 多空都做”。

    - side=both：保持原样（-1/0/1）
    - side=long：只做多（负仓位裁剪为 0）
    - side=short：只做空（正仓位裁剪为 0）
    """
    if pos is None or pos.empty:
        return pd.Series(dtype="float64")

    s = str(side or "").strip().lower()
    p = pos.astype("float64")
    if s == "long":
        return p.clip(lower=0.0)
    if s == "short":
        return p.clip(upper=0.0)
    return p


def _prepare_non_overlapping_inputs(
    *,
    pos: pd.Series,
    fwd_ret: pd.Series,
    btc_ret: pd.Series | None,
    horizon: int,
) -> pd.DataFrame:
    """
    对齐输入并做“非重叠抽样”（每 horizon 根 K 线评估/换仓一次）。

    说明：
    - 该步骤是择时体检最频繁的预处理环节；把它提取出来可以避免在
      “方向选择/长短腿选择”时重复做对齐+丢弃 NaN + 抽样，显著提速。
    """
    if pos is None or fwd_ret is None:
        return pd.DataFrame()
    if pos.empty or fwd_ret.empty:
        return pd.DataFrame()

    h = int(horizon)
    if h <= 0:
        raise ValueError("horizon 必须为正整数")

    df = pd.DataFrame({"pos": pos.astype("float64"), "fwd_ret": fwd_ret.astype("float64")}).sort_index()
    if btc_ret is not None and not btc_ret.empty:
        df["btc_ret"] = btc_ret.astype("float64").reindex(df.index)

    work = df.dropna(subset=["fwd_ret"])
    work = work.dropna(subset=["pos", "fwd_ret"], how="any")
    if work.empty:
        return pd.DataFrame()

    work = work.iloc[::h].copy()
    return work.replace([np.inf, -np.inf], np.nan)


def _returns_from_prepared(
    *,
    work: pd.DataFrame,
    pos_sampled: pd.Series,
    params: TimingAuditParams,
) -> pd.DataFrame:
    """
    基于 _prepare_non_overlapping_inputs() 的输出，计算 gross/net/cost 等序列。
    """
    if work is None or work.empty:
        return pd.DataFrame()
    if pos_sampled is None or pos_sampled.empty:
        return pd.DataFrame()

    p = pos_sampled.astype("float64").reindex(work.index).fillna(0.0)
    fwd = work["fwd_ret"].astype("float64")

    per_side = float(params.fee_rate) + float(params.slippage_rate)
    prev_pos = p.shift(1).fillna(0.0)
    trade_size = (p - prev_pos).abs()
    cost = trade_size * float(per_side)

    gross = p * fwd
    net = gross - cost

    out = pd.DataFrame(
        {
            "pos": p.astype("float64"),
            "fwd_ret": fwd.astype("float64"),
            "trade_size": trade_size.astype("float64"),
            "cost": cost.astype("float64"),
            "gross_ret": gross.astype("float64"),
            "net_ret": net.astype("float64"),
        },
        index=work.index,
    ).sort_index()

    if "btc_ret" in work.columns:
        out["btc_ret"] = work["btc_ret"].astype("float64")
        out["alpha_btc_net"] = (out["net_ret"] - out["btc_ret"]).astype("float64")

    return out.replace([np.inf, -np.inf], np.nan)


def _score_net_ret(net_ret: pd.Series, *, eff_tf: str, rolling_days: list[int]) -> tuple[float, float, float]:
    """
    评分用于“自动选择方向/长短腿”：
    - 优先看滚动中位数（更像“常态表现”）
    - 其次看滚动 P10（更像“坏的时候会有多惨”）
    - 再看均值（作为次要参考）
    """
    if net_ret is None or net_ret.empty:
        return (float("-inf"), float("-inf"), float("-inf"))

    s = net_ret.astype("float64").dropna()
    if s.empty:
        return (float("-inf"), float("-inf"), float("-inf"))

    roll = rolling_return_summary(s, timeframe=str(eff_tf), days=list(rolling_days or []))

    if 30 in set(int(d) for d in (rolling_days or [])):
        base = "roll_30d"
    else:
        base = f"roll_{int(rolling_days[0])}d" if rolling_days else ""

    med = float(roll.get(f"{base}_median", float("-inf"))) if base else float("-inf")
    p10 = float(roll.get(f"{base}_p10", float("-inf"))) if base else float("-inf")
    mean = float(s.mean())

    if not math.isfinite(med):
        med = float("-inf")
    if not math.isfinite(p10):
        p10 = float("-inf")
    if not math.isfinite(mean):
        mean = float("-inf")

    return (med, p10, mean)


def precompute_quantile_thresholds(*, X: pd.DataFrame, params: TimingAuditParams) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    批量预计算滚动分位阈值（用于加速“多因子批量体检”）。

    返回：
    - q_high：每列的上分位阈值（top 20% 之类）
    - q_low ：每列的下分位阈值（bottom 20% 之类）

    备注：
    - 只依赖 params.timeframe/quantiles/lookback_days；params.horizon/fee 等不影响阈值计算。
    """
    if X is None or X.empty:
        return pd.DataFrame(), pd.DataFrame()

    q = int(params.quantiles)
    if q < 2:
        raise ValueError("quantiles 至少为 2")

    tf_minutes = parse_timeframe_minutes(params.timeframe)
    if tf_minutes is None or tf_minutes <= 0:
        raise ValueError("timeframe 无法解析为分钟：仅支持 15m/1h/4h 等格式")

    lookback_days = int(params.lookback_days)
    if lookback_days <= 0:
        raise ValueError("lookback_days 必须为正整数")

    bars_per_day = int(1440 // int(tf_minutes)) if (1440 % int(tf_minutes) == 0) else None
    if bars_per_day is None or bars_per_day <= 0:
        raise ValueError("timeframe 无法整除 1440：无法换算天内 bars")

    lookback_bars = int(lookback_days * bars_per_day)
    if lookback_bars <= 10:
        raise ValueError("lookback_bars 过小：请增大 lookback_days 或使用更高频 timeframe")

    work = X.astype("float64").sort_index()

    high_q = 1.0 - (1.0 / float(q))
    low_q = 1.0 / float(q)

    # shift(1) 避免前向偏差（t 时刻的阈值只能用 t-1 及之前的数据）
    q_high = work.rolling(lookback_bars).quantile(high_q).shift(1)
    q_low = work.rolling(lookback_bars).quantile(low_q).shift(1)
    return q_high.replace([np.inf, -np.inf], np.nan), q_low.replace([np.inf, -np.inf], np.nan)


def choose_timing_direction_with_thresholds(
    *,
    x: pd.Series,
    fwd_ret: pd.Series,
    btc_ret: pd.Series | None,
    params: TimingAuditParams,
    q_high: pd.Series,
    q_low: pd.Series,
) -> tuple[str, str, pd.Series, pd.DataFrame]:
    """
    正向/反向自动选择（使用预计算的滚动分位阈值）。

    适用场景：同一个币要批量评估大量因子时，先一次性算出阈值，再复用。
    """
    eff_tf = _effective_timeframe(timeframe=params.timeframe, horizon=params.horizon)

    def _best_for_direction(direction: str) -> tuple[tuple[float, float, float], str, pd.DataFrame]:
        base_pos = position_from_thresholds(x=x, q_high=q_high, q_low=q_low, direction=str(direction))
        work = _prepare_non_overlapping_inputs(pos=base_pos, fwd_ret=fwd_ret, btc_ret=btc_ret, horizon=int(params.horizon))
        if work is None or work.empty:
            return (float("-inf"), float("-inf"), float("-inf")), "both", pd.DataFrame()

        base_pos_sampled = work["pos"].astype("float64")

        best_score = (float("-inf"), float("-inf"), float("-inf"))
        best_side = "both"
        best_ret = pd.DataFrame()

        for side in ("both", "long", "short"):
            pos2 = apply_trade_side(pos=base_pos_sampled, side=str(side))
            ret_df = _returns_from_prepared(work=work, pos_sampled=pos2, params=params)
            score = _score_net_ret(ret_df.get("net_ret", pd.Series(dtype="float64")), eff_tf=eff_tf, rolling_days=list(params.rolling_days or []))
            if score > best_score:
                best_score = score
                best_side = str(side)
                best_ret = ret_df

        return best_score, best_side, best_ret

    score_pos, side_pos, ret_pos = _best_for_direction("pos")
    score_neg, side_neg, ret_neg = _best_for_direction("neg")

    if score_neg > score_pos:
        direction = "neg"
        side = str(side_neg)
        ret_df = ret_neg
    else:
        direction = "pos"
        side = str(side_pos)
        ret_df = ret_pos

    ic = daily_rank_ic(x=(-x if direction == "neg" else x), y=fwd_ret, min_points=10)
    return direction, side, ic, ret_df


def choose_timing_direction(
    *,
    x: pd.Series,
    fwd_ret: pd.Series,
    btc_ret: pd.Series | None,
    params: TimingAuditParams,
) -> tuple[str, str, pd.Series, pd.DataFrame]:
    """
    正向/反向自动选择：优先看 30d（或 rolling_days[0]）滚动中位数，其次看 net_ret 均值。
    """
    q = int(params.quantiles)
    if q < 2:
        raise ValueError("quantiles 至少为 2")

    tf_minutes = parse_timeframe_minutes(params.timeframe)
    if tf_minutes is None or tf_minutes <= 0:
        raise ValueError("timeframe 无法解析为分钟：仅支持 15m/1h/4h 等格式")

    lookback_days = int(params.lookback_days)
    if lookback_days <= 0:
        raise ValueError("lookback_days 必须为正整数")

    bars_per_day = int(1440 // int(tf_minutes)) if (1440 % int(tf_minutes) == 0) else None
    if bars_per_day is None or bars_per_day <= 0:
        raise ValueError("timeframe 无法整除 1440：无法换算天内 bars")

    lookback_bars = int(lookback_days * bars_per_day)
    if lookback_bars <= 10:
        raise ValueError("lookback_bars 过小：请增大 lookback_days 或使用更高频 timeframe")

    xx = x.astype("float64").copy()
    high_q = 1.0 - (1.0 / float(q))
    low_q = 1.0 / float(q)
    # shift(1) 避免前向偏差（t 时刻的阈值只能用 t-1 及之前的数据）
    q_high = xx.rolling(lookback_bars).quantile(high_q).shift(1)
    q_low = xx.rolling(lookback_bars).quantile(low_q).shift(1)

    return choose_timing_direction_with_thresholds(
        x=xx,
        fwd_ret=fwd_ret.astype("float64"),
        btc_ret=btc_ret,
        params=params,
        q_high=q_high,
        q_low=q_low,
    )
