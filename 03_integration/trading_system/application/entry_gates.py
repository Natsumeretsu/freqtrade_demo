from __future__ import annotations

"""
entry_gates.py - 入场门控（Gate）组件（纯函数）

业界常见做法是把“策略装配层”与“门控公式”分离：
- 策略负责：选择哪些门控、参数如何取值、enter_tag 如何归因
- 组件负责：稳定的计算口径（避免不同策略里同名逻辑悄悄漂移）

本模块提供一些高复用的 Gate：
- 宏观体制：macro_close vs macro_sma（可选 slope 约束）
- EMA 长期趋势：EMA 在 lookback 窗口内的有效上/下行
- ATR% 范围：最小波动率 + 可选最大波动率
- 成交量/流动性：volume_ratio 下限
- 追高抑制、动量方向等基础门控

注意：
- 所有函数返回 pd.Series[bool]（即使未启用也返回全 True/False 的 Series），便于策略统一 `.fillna(False)`。
"""

import numpy as np
import pandas as pd


def _const_bool(index: pd.Index, value: bool) -> pd.Series:
    return pd.Series(bool(value), index=index, dtype="bool")


def ema_trend_ok(
    ema: pd.Series,
    *,
    lookback: int,
    min_slope: float,
    direction: str,
) -> pd.Series:
    """
    EMA 有效趋势门控：
    - direction="up"  ：ema_now > ema_then * (1 + min_slope)
    - direction="down"：ema_now < ema_then * (1 - min_slope)
    """
    idx = getattr(ema, "index", None)
    if idx is None:
        return pd.Series(dtype="bool")

    lb = int(lookback)
    if lb <= 0:
        return _const_bool(idx, True)

    ms = float(min_slope)
    if not np.isfinite(ms) or ms < 0:
        ms = 0.0

    d = str(direction or "").strip().lower()
    if d == "up":
        return ema > (ema.shift(lb) * (1.0 + ms))
    if d == "down":
        return ema < (ema.shift(lb) * (1.0 - ms))
    return _const_bool(idx, True)


def ema_spread_ok(
    ema_short: pd.Series,
    ema_long: pd.Series,
    *,
    min_spread: float,
    abs_value: bool,
) -> pd.Series:
    """短长 EMA 乖离门控：|(ema_s/ema_l)-1| 或 (ema_s/ema_l)-1 是否超过阈值。"""
    idx = getattr(ema_short, "index", None)
    if idx is None:
        return pd.Series(dtype="bool")

    ms = float(min_spread)
    if not np.isfinite(ms) or ms < 0:
        ms = 0.0

    spread = (ema_short / ema_long) - 1.0
    if bool(abs_value):
        spread = spread.abs()
    return spread > ms


def atr_pct_range_ok(
    df: pd.DataFrame,
    *,
    min_pct: float,
    use_max_filter: bool,
    max_pct: float,
) -> pd.Series:
    """ATR% 范围门控：atr_pct > min_pct 且（可选）atr_pct < max_pct。"""
    if df is None or df.empty:
        return pd.Series(dtype="bool")
    if "atr_pct" not in df.columns:
        return _const_bool(df.index, False)

    mn = float(min_pct)
    if not np.isfinite(mn) or mn < 0:
        mn = 0.0

    ok = df["atr_pct"] > mn
    if bool(use_max_filter):
        mx = float(max_pct)
        if np.isfinite(mx) and mx > 0:
            ok = ok & (df["atr_pct"] < mx)
    return ok


def volume_ratio_min_ok(
    df: pd.DataFrame,
    *,
    enabled: bool,
    min_ratio: float,
    require_column: bool,
    fail_open: bool,
) -> pd.Series:
    """
    流动性门控：volume_ratio >= min_ratio。

    - enabled=False：返回全 True
    - enabled=True 且缺列：
      - require_column=True：按 fail_open 决定 True/False
      - require_column=False：返回全 True
    """
    if df is None or df.empty:
        return pd.Series(dtype="bool")

    if not bool(enabled):
        return _const_bool(df.index, True)

    if "volume_ratio" not in df.columns:
        if not bool(require_column):
            return _const_bool(df.index, True)
        return _const_bool(df.index, bool(fail_open))

    mr = float(min_ratio)
    if not np.isfinite(mr) or mr <= 0:
        return _const_bool(df.index, True)

    return df["volume_ratio"] >= mr


def macro_sma_regime_ok(
    df: pd.DataFrame,
    *,
    enabled: bool,
    macro_close_col: str,
    macro_sma_col: str,
    is_long: bool,
    require_columns: bool,
    slope_lookback: int,
    min_slope: float,
    fail_open: bool,
) -> pd.Series:
    """
    宏观体制硬门控（可选 slope 约束）：
    - long ：macro_close > macro_sma
    - short：macro_close < macro_sma
    - 若 slope_lookback>0 且 min_slope>0：
      - long ：macro_sma > macro_sma.shift(lb) * (1+min_slope)
      - short：macro_sma < macro_sma.shift(lb) * (1-min_slope)
    """
    if df is None or df.empty:
        return pd.Series(dtype="bool")

    if not bool(enabled):
        return _const_bool(df.index, True)

    close_col = str(macro_close_col or "").strip()
    sma_col = str(macro_sma_col or "").strip()
    if not close_col or not sma_col:
        return _const_bool(df.index, True)

    if close_col not in df.columns or sma_col not in df.columns:
        if not bool(require_columns):
            return _const_bool(df.index, True)
        return _const_bool(df.index, bool(fail_open))

    if bool(is_long):
        ok = df[close_col] > df[sma_col]
    else:
        ok = df[close_col] < df[sma_col]

    lb = int(slope_lookback)
    ms = float(min_slope)
    if lb > 0 and np.isfinite(ms) and ms > 0:
        if bool(is_long):
            ok = ok & (df[sma_col] > (df[sma_col].shift(lb) * (1.0 + ms)))
        else:
            ok = ok & (df[sma_col] < (df[sma_col].shift(lb) * (1.0 - ms)))

    return ok


def price_not_too_far_from_ema(
    close: pd.Series,
    ema_short: pd.Series,
    *,
    max_offset: float,
    side: str,
) -> pd.Series:
    """抑制追高/追空：价格距离短 EMA 过远时拒绝。"""
    idx = getattr(close, "index", None)
    if idx is None:
        return pd.Series(dtype="bool")

    off = float(max_offset)
    if not np.isfinite(off) or off < 0:
        off = 0.0

    s = str(side or "").strip().lower()
    if s == "long":
        return close <= (ema_short * (1.0 + off))
    if s == "short":
        return close >= (ema_short * (1.0 - off))
    return _const_bool(idx, True)


def momentum_ok(close: pd.Series, *, side: str) -> pd.Series:
    """动量方向门控：long 需要收盘价上行，short 需要收盘价下行。"""
    idx = getattr(close, "index", None)
    if idx is None:
        return pd.Series(dtype="bool")

    s = str(side or "").strip().lower()
    if s == "long":
        return close > close.shift(1)
    if s == "short":
        return close < close.shift(1)
    return _const_bool(idx, True)

