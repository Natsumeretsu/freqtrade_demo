"""EMA 因子计算器

处理 EMA 相关的因子计算。
"""
from __future__ import annotations

import re
import pandas as pd
from .factor_computer import IFactorComputer


class EMAFactorComputer(IFactorComputer):
    """EMA 因子计算器"""

    # 预编译正则表达式
    _EMA_SHORT_RE = re.compile(r'^ema_short_(\d+)$')
    _EMA_LONG_RE = re.compile(r'^ema_long_(\d+)$')
    _EMA_RE = re.compile(r'^ema_(\d+)$')

    def can_compute(self, factor_name: str) -> bool:
        """判断是否可以计算该因子"""
        return (self._EMA_SHORT_RE.match(factor_name) is not None or
                self._EMA_LONG_RE.match(factor_name) is not None or
                self._EMA_RE.match(factor_name) is not None or
                factor_name == "ema_spread")

    def compute(self, data: pd.DataFrame, factor_name: str) -> pd.Series:
        """计算 EMA 因子"""
        close = data["close"].astype("float64")

        # ema_short_<n>
        if match := self._EMA_SHORT_RE.match(factor_name):
            period = int(match.group(1))
            return close.ewm(span=period, adjust=False).mean()

        # ema_long_<n>
        if match := self._EMA_LONG_RE.match(factor_name):
            period = int(match.group(1))
            return close.ewm(span=period, adjust=False).mean()

        # ema_<n>
        if match := self._EMA_RE.match(factor_name):
            period = int(match.group(1))
            return close.ewm(span=period, adjust=False).mean()

        # ema_spread
        if factor_name == "ema_spread":
            ema10 = close.ewm(span=10, adjust=False).mean()
            ema50 = close.ewm(span=50, adjust=False).mean()
            return ema10 / ema50 - 1.0

        raise ValueError(f"Cannot compute factor: {factor_name}")
