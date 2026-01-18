"""价格动量因子计算器

处理价格动量相关的因子（ema_spread, price_to_high, price_to_low 等）。
"""
from __future__ import annotations

import re
import numpy as np
import pandas as pd
import talib as ta
from .factor_computer import IFactorComputer


class PriceMomentumFactorComputer(IFactorComputer):
    """价格动量因子计算器"""

    # 预编译正则表达式
    _EMA_SPREAD_RE = re.compile(r'^ema_spread_(\d+)_(\d+)$')
    _PRICE_TO_HIGH_RE = re.compile(r'^price_to_high_(\d+)$')
    _PRICE_TO_LOW_RE = re.compile(r'^price_to_low_(\d+)$')

    def can_compute(self, factor_name: str) -> bool:
        """判断是否可以计算该因子"""
        return (self._EMA_SPREAD_RE.match(factor_name) is not None or
                self._PRICE_TO_HIGH_RE.match(factor_name) is not None or
                self._PRICE_TO_LOW_RE.match(factor_name) is not None)

    def compute(self, data: pd.DataFrame, factor_name: str) -> pd.Series:
        """计算价格动量因子"""
        close = data["close"].astype("float64")
        high = data["high"].astype("float64")
        low = data["low"].astype("float64")

        # ema_spread_<short>_<long>
        if match := self._EMA_SPREAD_RE.match(factor_name):
            short_period = int(match.group(1))
            long_period = int(match.group(2))
            if short_period > 0 and long_period > 0:
                ema_short = ta.EMA(data, timeperiod=short_period)
                ema_long = ta.EMA(data, timeperiod=long_period)
                if not isinstance(ema_short, pd.Series):
                    ema_short = pd.Series(ema_short, index=data.index)
                if not isinstance(ema_long, pd.Series):
                    ema_long = pd.Series(ema_long, index=data.index)
                return (ema_short / ema_long.replace(0, np.nan)) - 1.0

        # price_to_high_<n>
        if match := self._PRICE_TO_HIGH_RE.match(factor_name):
            period = int(match.group(1))
            if period > 0:
                highest = high.rolling(period).max().replace(0, np.nan)
                return (close / highest) - 1.0

        # price_to_low_<n>
        if match := self._PRICE_TO_LOW_RE.match(factor_name):
            period = int(match.group(1))
            if period > 0:
                lowest = low.rolling(period).min().replace(0, np.nan)
                return (close / lowest) - 1.0

        raise ValueError(f"Cannot compute factor: {factor_name}")
