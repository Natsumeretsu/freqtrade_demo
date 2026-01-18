"""布林带因子计算器

处理布林带宽度和百分比 B 指标。
"""
from __future__ import annotations

import re
import numpy as np
import pandas as pd
import talib as ta
from .factor_computer import IFactorComputer


class BollingerFactorComputer(IFactorComputer):
    """布林带因子计算器"""

    # 预编译正则表达式
    _BB_WIDTH_RE = re.compile(r'^bb_width_(\d+)_(\d+)$')
    _BB_PCTB_RE = re.compile(r'^bb_percent_b_(\d+)_(\d+)$')

    def can_compute(self, factor_name: str) -> bool:
        """判断是否可以计算该因子"""
        return (self._BB_WIDTH_RE.match(factor_name) is not None or
                self._BB_PCTB_RE.match(factor_name) is not None)

    def compute(self, data: pd.DataFrame, factor_name: str) -> pd.Series:
        """计算布林带因子"""
        close = data["close"].astype("float64")

        # bb_width_<period>_<dev>
        if match := self._BB_WIDTH_RE.match(factor_name):
            period = int(match.group(1))
            dev = int(match.group(2))
            if period > 1 and dev > 0:
                upper, middle, lower = ta.BBANDS(close, timeperiod=period, nbdevup=float(dev), nbdevdn=float(dev), matype=0)
                if not isinstance(upper, pd.Series):
                    upper = pd.Series(upper, index=data.index)
                if not isinstance(lower, pd.Series):
                    lower = pd.Series(lower, index=data.index)
                return (upper / lower.replace(0, np.nan)) - 1.0

        # bb_percent_b_<period>_<dev>
        if match := self._BB_PCTB_RE.match(factor_name):
            period = int(match.group(1))
            dev = int(match.group(2))
            if period > 1 and dev > 0:
                upper, middle, lower = ta.BBANDS(close, timeperiod=period, nbdevup=float(dev), nbdevdn=float(dev), matype=0)
                if not isinstance(upper, pd.Series):
                    upper = pd.Series(upper, index=data.index)
                if not isinstance(lower, pd.Series):
                    lower = pd.Series(lower, index=data.index)
                denom = (upper - lower).replace(0, np.nan)
                return (close - lower) / denom

        raise ValueError(f"Cannot compute factor: {factor_name}")
