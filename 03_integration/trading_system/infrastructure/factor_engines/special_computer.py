"""特殊因子计算器

处理特殊因子（hl_range, vol_of_vol 等）。
"""
from __future__ import annotations

import re
import numpy as np
import pandas as pd
from .factor_computer import IFactorComputer


class SpecialFactorComputer(IFactorComputer):
    """特殊因子计算器"""

    # 预编译正则表达式
    _VOL_OF_VOL_RE = re.compile(r'^vol_of_vol_(\d+)$')

    def can_compute(self, factor_name: str) -> bool:
        """判断是否可以计算该因子"""
        return (factor_name == "hl_range" or
                self._VOL_OF_VOL_RE.match(factor_name) is not None)

    def compute(self, data: pd.DataFrame, factor_name: str) -> pd.Series:
        """计算特殊因子"""
        close = data["close"].astype("float64")
        high = data["high"].astype("float64")
        low = data["low"].astype("float64")

        # hl_range
        if factor_name == "hl_range":
            return (high / low.replace(0, np.nan)) - 1.0

        # vol_of_vol_<n>
        if match := self._VOL_OF_VOL_RE.match(factor_name):
            period = int(match.group(1))
            if period > 1:
                ret1 = close.pct_change(1)
                vol_series = ret1.rolling(period).std()
                return vol_series.pct_change(period)

        raise ValueError(f"Cannot compute factor: {factor_name}")
