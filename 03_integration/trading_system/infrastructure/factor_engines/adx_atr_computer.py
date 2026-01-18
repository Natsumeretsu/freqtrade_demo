"""ADX/ATR 因子计算器

处理 ADX（平均趋向指数）和 ATR（平均真实波幅）指标。
"""
from __future__ import annotations

import re
import numpy as np
import pandas as pd
import talib as ta
from .factor_computer import IFactorComputer


class AdxAtrFactorComputer(IFactorComputer):
    """ADX/ATR 因子计算器"""

    # 预编译正则表达式
    _ADX_RE = re.compile(r'^adx_(\d+)$')
    _ATR_RE = re.compile(r'^atr_(\d+)$')
    _ATR_PCT_RE = re.compile(r'^atr_pct_(\d+)$')

    def __init__(self, default_adx_period: int = 14, default_atr_period: int = 14):
        self._default_adx_period = default_adx_period
        self._default_atr_period = default_atr_period

    def can_compute(self, factor_name: str) -> bool:
        """判断是否可以计算该因子"""
        return (factor_name in {"adx", "atr", "atr_pct"} or
                self._ADX_RE.match(factor_name) is not None or
                self._ATR_RE.match(factor_name) is not None or
                self._ATR_PCT_RE.match(factor_name) is not None)

    def compute(self, data: pd.DataFrame, factor_name: str) -> pd.Series:
        """计算 ADX/ATR 因子"""
        close = data["close"].astype("float64")

        # adx (默认周期)
        if factor_name == "adx":
            return ta.ADX(data, timeperiod=self._default_adx_period)

        # adx_<n>
        if match := self._ADX_RE.match(factor_name):
            period = int(match.group(1))
            if period > 0:
                return ta.ADX(data, timeperiod=period)

        # atr (默认周期)
        if factor_name == "atr":
            return ta.ATR(data, timeperiod=self._default_atr_period)

        # atr_<n>
        if match := self._ATR_RE.match(factor_name):
            period = int(match.group(1))
            if period > 0:
                return ta.ATR(data, timeperiod=period)

        # atr_pct (默认周期)
        if factor_name == "atr_pct":
            atr_series = ta.ATR(data, timeperiod=self._default_atr_period)
            return atr_series / close.replace(0, np.nan)

        # atr_pct_<n>
        if match := self._ATR_PCT_RE.match(factor_name):
            period = int(match.group(1))
            if period > 0:
                atr_series = ta.ATR(data, timeperiod=period)
                return atr_series / close.replace(0, np.nan)

        raise ValueError(f"Cannot compute factor: {factor_name}")
