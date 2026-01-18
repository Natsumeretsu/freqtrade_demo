"""反转因子计算器

处理反转相关的因子（reversal, zscore_close 等）。
"""
from __future__ import annotations

import re
import numpy as np
import pandas as pd
from .factor_computer import IFactorComputer


class ReversalFactorComputer(IFactorComputer):
    """反转因子计算器"""

    # 预编译正则表达式
    _REVERSAL_RE = re.compile(r'^reversal_(\d+)$')
    _ZSCORE_CLOSE_RE = re.compile(r'^zscore_close_(\d+)$')

    def can_compute(self, factor_name: str) -> bool:
        """判断是否可以计算该因子"""
        return (self._REVERSAL_RE.match(factor_name) is not None or
                self._ZSCORE_CLOSE_RE.match(factor_name) is not None)

    def compute(self, data: pd.DataFrame, factor_name: str) -> pd.Series:
        """计算反转因子"""
        close = data["close"].astype("float64")

        # reversal_<n>
        if match := self._REVERSAL_RE.match(factor_name):
            period = int(match.group(1))
            if period > 0:
                return -close.pct_change(period)

        # zscore_close_<n>
        if match := self._ZSCORE_CLOSE_RE.match(factor_name):
            period = int(match.group(1))
            if period > 1:
                mean = close.rolling(period).mean()
                std = close.rolling(period).std().replace(0, np.nan)
                return (close - mean) / std

        raise ValueError(f"Cannot compute factor: {factor_name}")
