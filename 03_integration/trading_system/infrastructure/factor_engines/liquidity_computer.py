"""流动性因子计算器

处理流动性相关的因子（Amihud, price_impact, OBV slope 等）。
"""
from __future__ import annotations

import re
import numpy as np
import pandas as pd
import talib as ta
from .factor_computer import IFactorComputer


class LiquidityFactorComputer(IFactorComputer):
    """流动性因子计算器"""

    # 预编译正则表达式
    _AMIHUD_RE = re.compile(r'^amihud_(\d+)$')
    _PRICE_IMPACT_RE = re.compile(r'^price_impact_(\d+)$')
    _OBV_SLOPE_RE = re.compile(r'^obv_slope_(\d+)$')
    _RET_VOL_RATIO_RE = re.compile(r'^ret_vol_ratio_(\d+)$')

    def can_compute(self, factor_name: str) -> bool:
        """判断是否可以计算该因子"""
        return (self._AMIHUD_RE.match(factor_name) is not None or
                self._PRICE_IMPACT_RE.match(factor_name) is not None or
                self._OBV_SLOPE_RE.match(factor_name) is not None or
                self._RET_VOL_RATIO_RE.match(factor_name) is not None)

    def compute(self, data: pd.DataFrame, factor_name: str) -> pd.Series:
        """计算流动性因子"""
        close = data["close"].astype("float64")
        volume = data["volume"].astype("float64")

        # amihud_<n>
        if match := self._AMIHUD_RE.match(factor_name):
            period = int(match.group(1))
            if period > 0:
                abs_ret = close.pct_change(1).abs()
                vol_safe = volume.replace(0, np.nan)
                amihud = abs_ret / vol_safe
                return amihud.rolling(period).mean()

        # price_impact_<n>
        if match := self._PRICE_IMPACT_RE.match(factor_name):
            period = int(match.group(1))
            if period > 0:
                abs_ret = close.pct_change(1).abs()
                sqrt_vol = np.sqrt(volume.replace(0, np.nan))
                impact = abs_ret / sqrt_vol
                return impact.rolling(period).mean()

        # obv_slope_<n>
        if match := self._OBV_SLOPE_RE.match(factor_name):
            period = int(match.group(1))
            if period > 2:
                obv = ta.OBV(data)
                if not isinstance(obv, pd.Series):
                    obv = pd.Series(obv, index=data.index)

                def _slope(arr: np.ndarray) -> float:
                    if len(arr) < 3 or np.all(np.isnan(arr)):
                        return np.nan
                    valid = arr[~np.isnan(arr)]
                    if len(valid) < 3:
                        return np.nan
                    x = np.arange(len(valid))
                    return np.polyfit(x, valid, 1)[0]

                return obv.rolling(period).apply(_slope, raw=True)

        # ret_vol_ratio_<n>
        if match := self._RET_VOL_RATIO_RE.match(factor_name):
            period = int(match.group(1))
            if period > 0:
                abs_ret = close.pct_change(1).abs().rolling(period).mean()
                vol_mean = volume.rolling(period).mean().replace(0, np.nan)
                return abs_ret / vol_mean

        raise ValueError(f"Cannot compute factor: {factor_name}")
