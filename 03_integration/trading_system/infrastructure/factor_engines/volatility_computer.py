"""波动率因子计算器

处理波动率相关的因子计算（vol, skew, kurt 等）。
"""
from __future__ import annotations

import re
import pandas as pd
from .factor_computer import IFactorComputer


class VolatilityFactorComputer(IFactorComputer):
    """波动率因子计算器"""

    # 预编译正则表达式
    _VOL_RE = re.compile(r'^vol_(\d+)$')
    _SKEW_RE = re.compile(r'^skew_(\d+)$')
    _KURT_RE = re.compile(r'^kurt_(\d+)$')

    def can_compute(self, factor_name: str) -> bool:
        """判断是否可以计算该因子"""
        return (self._VOL_RE.match(factor_name) is not None or
                self._SKEW_RE.match(factor_name) is not None or
                self._KURT_RE.match(factor_name) is not None)

    def compute(self, data: pd.DataFrame, factor_name: str) -> pd.Series:
        """计算波动率因子"""
        close = data["close"].astype("float64")
        ret1 = close.pct_change(1)

        # vol_<n>
        if match := self._VOL_RE.match(factor_name):
            period = int(match.group(1))
            return ret1.rolling(period).std()

        # skew_<n>
        if match := self._SKEW_RE.match(factor_name):
            period = int(match.group(1))
            return ret1.rolling(period).skew()

        # kurt_<n>
        if match := self._KURT_RE.match(factor_name):
            period = int(match.group(1))
            return ret1.rolling(period).kurt()

        raise ValueError(f"Cannot compute factor: {factor_name}")
