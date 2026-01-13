from __future__ import annotations

"""
risk_scaling.py - 风险缩放/门控的可复用工具

设计目标（偏“业界成熟范式”）：
- 策略里经常出现“硬过滤 + 软缩放”组合：
  - 硬过滤：不满足条件就不交易（或直接打到最低风险）
  - 软缩放：把连续指标映射到 0~1 的风险折扣（仓位/杠杆/阈值）
- 将映射逻辑抽成纯函数，便于复用与单测，避免不同策略里口径漂移。

注意：
- 本模块不依赖 Freqtrade，仅使用 pandas/numpy 的基础数据结构。
"""

from typing import Final

import numpy as np
import pandas as pd


_EPS: Final[float] = 1e-12


def clamp01(x: float, *, default: float = 1.0) -> float:
    """把数值夹到 [0,1]，无效输入则返回 default。"""
    try:
        v = float(x)
    except Exception:
        return float(default)
    if not np.isfinite(v):
        return float(default)
    return float(max(0.0, min(1.0, v)))


def step_min(*, value: float, min_value: float, floor: float) -> float:
    """
    阶跃缩放（下限门槛）：
    - value < min_value → floor
    - 否则 → 1.0
    """
    try:
        v = float(value)
        m = float(min_value)
        if not np.isfinite(v) or not np.isfinite(m):
            return 1.0
        if m <= 0:
            return 1.0
        return clamp01(float(floor)) if v < m else 1.0
    except Exception:
        return 1.0


def step_max(*, value: float, max_value: float, floor: float) -> float:
    """
    阶跃缩放（上限门槛）：
    - value > max_value → floor
    - 否则 → 1.0
    """
    try:
        v = float(value)
        m = float(max_value)
        if not np.isfinite(v) or not np.isfinite(m):
            return 1.0
        if m <= 0:
            return 1.0
        return clamp01(float(floor)) if v > m else 1.0
    except Exception:
        return 1.0


def linear_scale_up(*, value: float, min_value: float, target_value: float, floor: float) -> float:
    """
    线性缩放（越大越好）：
    - value <= min_value → floor
    - value >= target_value → 1.0
    - 其余区间线性插值

    常见用途：流动性/成交量比率（volume_ratio）。
    """
    try:
        v = float(value)
        v_min = float(min_value)
        v_t = float(target_value)
        if not (np.isfinite(v) and np.isfinite(v_min) and np.isfinite(v_t)):
            return 1.0
        floor_v = clamp01(float(floor))

        if v_t <= v_min + _EPS:
            # 退化为“阈值阶跃”：达到 target 就满额，否则 floor
            return 1.0 if v >= v_t else floor_v

        if v <= v_min:
            return floor_v
        if v >= v_t:
            return 1.0
        ratio = (v - v_min) / (v_t - v_min)
        return float(floor_v + (1.0 - floor_v) * ratio)
    except Exception:
        return 1.0


def linear_scale_down(*, value: float, start_value: float, end_value: float, floor: float) -> float:
    """
    线性缩放（越大越差）：
    - value <= start_value → 1.0
    - value >= end_value → floor
    - 其余区间线性下降

    常见用途：波动率上限（例如 atr_pct）。

    兼容策略口径：
    - 若 end_value <= start_value：视为“未启用线性缩放”，直接返回 1.0
    """
    try:
        v = float(value)
        s = float(start_value)
        e = float(end_value)
        if not (np.isfinite(v) and np.isfinite(s) and np.isfinite(e)):
            return 1.0

        s = float(max(0.0, s))
        e = float(max(0.0, e))
        if e <= s + _EPS:
            return 1.0

        floor_v = clamp01(float(floor))
        if v <= s:
            return 1.0
        if v >= e:
            return floor_v
        ratio = (v - s) / (e - s)
        return float(1.0 - (1.0 - floor_v) * ratio)
    except Exception:
        return 1.0


def macro_sma_soft_scale(
    df: pd.DataFrame,
    *,
    macro_close_col: str,
    macro_sma_col: str,
    is_long: bool,
    floor: float,
    slope_lookback: int,
    min_slope: float,
) -> float:
    """
    宏观体制软缩放（SMA 体制 + SMA 斜率强度）。

    逻辑：
    - 体制不符合（long: close<=sma；short: close>=sma）→ floor
    - 体制符合但“趋势强度”不足 → 在 floor~1 之间插值
    - 体制符合且强度足够 → 1

    说明：
    - slope 的口径为 (sma_now / sma_then) - 1
    - short 方向用 -slope 的强度（下行越陡越强）
    - 当 lookback/min_slope 不可用或历史不足时：仅做体制判断，不再做斜率插值（保持 1）
    """
    if df is None or df.empty:
        return 1.0

    floor_v = clamp01(float(floor))

    try:
        last = df.iloc[-1]
        macro_close = float(last.get(macro_close_col, np.nan))
        macro_sma = float(last.get(macro_sma_col, np.nan))
    except Exception:
        return 1.0

    if not (np.isfinite(macro_close) and np.isfinite(macro_sma)) or macro_sma <= 0:
        return 1.0

    regime_ok = (macro_close > macro_sma) if bool(is_long) else (macro_close < macro_sma)
    if not regime_ok:
        return floor_v

    lb = int(slope_lookback)
    min_s = float(min_slope)
    if lb <= 0 or not np.isfinite(min_s) or min_s <= 0:
        return 1.0
    if len(df) <= lb or macro_sma_col not in df.columns:
        return 1.0

    try:
        sma_then = float(df[macro_sma_col].iloc[-1 - lb])
    except Exception:
        return 1.0
    if not np.isfinite(sma_then) or sma_then <= 0:
        return 1.0

    slope = (macro_sma / sma_then) - 1.0
    strength = float(max(0.0, slope)) if bool(is_long) else float(max(0.0, -slope))

    if strength <= 0:
        return floor_v
    if strength >= min_s:
        return 1.0
    return float(floor_v + (1.0 - floor_v) * (strength / min_s))

