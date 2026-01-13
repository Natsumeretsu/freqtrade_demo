from __future__ import annotations

"""
signal_ops.py - 序列信号算子（cross / reentry / regime）

目标：
- 将策略中常见的“交叉事件/再入事件/模式判定”抽为纯函数，减少对第三方 helper 的隐式依赖
- 统一跨策略口径，避免“同名信号在不同策略里细节不同”的漂移

说明：
- 返回值均为 pd.Series[bool]，可直接参与 AND/OR 组合
- 遇到 NaN 时，pandas 比较通常会产生 False（符合“缺数据不触发事件”的直觉）
"""

import numpy as np
import pandas as pd


def _const_bool(index: pd.Index, value: bool) -> pd.Series:
    return pd.Series(bool(value), index=index, dtype="bool")


def crossed_above(a: pd.Series, b: pd.Series) -> pd.Series:
    """
    a 上穿 b：
    - 当前 a > b
    - 上一根 a <= b
    """
    idx = getattr(a, "index", None)
    if idx is None:
        return pd.Series(dtype="bool")
    return (a > b) & (a.shift(1) <= b.shift(1))


def crossed_below(a: pd.Series, b: pd.Series) -> pd.Series:
    """
    a 下穿 b：
    - 当前 a < b
    - 上一根 a >= b
    """
    idx = getattr(a, "index", None)
    if idx is None:
        return pd.Series(dtype="bool")
    return (a < b) & (a.shift(1) >= b.shift(1))


def bull_mode(close: pd.Series, ema_long: pd.Series, *, offset: float) -> pd.Series:
    """牛市模式：close > ema_long * (1 + offset)。"""
    idx = getattr(close, "index", None)
    if idx is None:
        return pd.Series(dtype="bool")

    off = float(offset)
    if not np.isfinite(off) or off < 0:
        off = 0.0
    return close > (ema_long * (1.0 + off))


def bear_mode(close: pd.Series, ema_long: pd.Series, *, offset: float) -> pd.Series:
    """熊市模式：close < ema_long * (1 - offset)。"""
    idx = getattr(close, "index", None)
    if idx is None:
        return pd.Series(dtype="bool")

    off = float(offset)
    if not np.isfinite(off) or off < 0:
        off = 0.0
    return close < (ema_long * (1.0 - off))


def reentry_event(
    close: pd.Series,
    ema_short: pd.Series,
    ema_long: pd.Series,
    *,
    side: str,
    min_long_offset: float,
    spread_metric: pd.Series,
    min_spread: float,
) -> pd.Series:
    """
    趋势内回踩再入（事件）：

    - long：
      - close 上穿 ema_short
      - close > ema_long * (1 + min_long_offset)
      - spread_metric > min_spread
    - short：
      - close 下穿 ema_short
      - close < ema_long * (1 - min_long_offset)
      - spread_metric > min_spread

    说明：
    - spread_metric 由策略侧传入：可以是 abs(ema_s/ema_l - 1) 或 (ema_s/ema_l - 1) 等
    """
    idx = getattr(close, "index", None)
    if idx is None:
        return pd.Series(dtype="bool")

    s = str(side or "").strip().lower()
    off = float(min_long_offset)
    if not np.isfinite(off) or off < 0:
        off = 0.0

    ms = float(min_spread)
    if not np.isfinite(ms) or ms < 0:
        ms = 0.0

    spread_ok = spread_metric > ms
    if s == "long":
        raw = crossed_above(close, ema_short)
        trend_ok = close > (ema_long * (1.0 + off))
        return raw & trend_ok & spread_ok
    if s == "short":
        raw = crossed_below(close, ema_short)
        trend_ok = close < (ema_long * (1.0 - off))
        return raw & trend_ok & spread_ok
    return _const_bool(idx, False)

