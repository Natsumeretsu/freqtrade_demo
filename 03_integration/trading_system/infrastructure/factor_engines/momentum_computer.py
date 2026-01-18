"""动量因子计算器

处理动量相关的因子计算（ret, roc 等）。
"""
from __future__ import annotations

import re
import pandas as pd
from .factor_computer import IFactorComputer


class MomentumFactorComputer(IFactorComputer):
    """动量因子计算器"""

    # 预编译正则表达式
    _RET_RE = re.compile(r'^ret_(\d+)$')
    _ROC_RE = re.compile(r'^roc_(\d+)$')

    def can_compute(self, factor_name: str) -> bool:
        """判断是否可以计算该因子"""
        return (self._RET_RE.match(factor_name) is not None or
                self._ROC_RE.match(factor_name) is not None)

    def compute(self, data: pd.DataFrame, factor_name: str) -> pd.Series:
        """计算动量因子"""
        close = data["close"].astype("float64")

        # ret_<n>
        if match := self._RET_RE.match(factor_name):
            period = int(match.group(1))
            return close.pct_change(period)

        # roc_<n>
        if match := self._ROC_RE.match(factor_name):
            period = int(match.group(1))
            return (close - close.shift(period)) / close.shift(period) * 100

        raise ValueError(f"Cannot compute factor: {factor_name}")
