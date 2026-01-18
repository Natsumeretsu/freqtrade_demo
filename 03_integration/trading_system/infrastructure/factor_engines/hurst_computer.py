"""Hurst 指数因子计算器

处理 Hurst 指数和市场制度相关的因子。
"""
from __future__ import annotations

import re
import numpy as np
import pandas as pd
from .factor_computer import IFactorComputer


class HurstFactorComputer(IFactorComputer):
    """Hurst 指数因子计算器"""

    # 预编译正则表达式
    _HURST_RE = re.compile(r'^hurst_(\d+)$')

    def can_compute(self, factor_name: str) -> bool:
        """判断是否可以计算该因子"""
        return self._HURST_RE.match(factor_name) is not None

    def compute(self, data: pd.DataFrame, factor_name: str) -> pd.Series:
        """计算 Hurst 指数因子"""
        close = data["close"].astype("float64")

        # hurst_<n>
        if match := self._HURST_RE.match(factor_name):
            period = int(match.group(1))
            if period >= 20:
                def _hurst(arr: np.ndarray) -> float:
                    if len(arr) < 20 or np.all(np.isnan(arr)):
                        return np.nan
                    valid = arr[~np.isnan(arr)]
                    if len(valid) < 20:
                        return np.nan
                    # R/S 分析法估计 Hurst 指数
                    mean = np.mean(valid)
                    deviations = valid - mean
                    cumsum = np.cumsum(deviations)
                    R = np.max(cumsum) - np.min(cumsum)
                    S = np.std(valid, ddof=1)
                    if S == 0:
                        return np.nan
                    RS = R / S
                    if RS <= 0:
                        return np.nan
                    # H = log(R/S) / log(n)
                    return np.log(RS) / np.log(len(valid))
                return close.rolling(period).apply(_hurst, raw=True)

        raise ValueError(f"Cannot compute factor: {factor_name}")
