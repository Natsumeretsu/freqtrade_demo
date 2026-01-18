"""随机指标因子计算器

处理 STOCH 随机指标（slowk/slowd）。
"""
from __future__ import annotations

import re
import pandas as pd
import talib as ta
from .factor_computer import IFactorComputer


class StochasticFactorComputer(IFactorComputer):
    """随机指标因子计算器"""

    # 预编译正则表达式
    _STOCH_K_RE = re.compile(r'^stoch_k_(\d+)_(\d+)_(\d+)$')
    _STOCH_D_RE = re.compile(r'^stoch_d_(\d+)_(\d+)_(\d+)$')

    def can_compute(self, factor_name: str) -> bool:
        """判断是否可以计算该因子"""
        return (self._STOCH_K_RE.match(factor_name) is not None or
                self._STOCH_D_RE.match(factor_name) is not None)

    def compute(self, data: pd.DataFrame, factor_name: str) -> pd.Series:
        """计算随机指标因子"""
        # stoch_k_<k_period>_<d_period>_<smooth_k>
        if match := self._STOCH_K_RE.match(factor_name):
            k_period = int(match.group(1))
            d_period = int(match.group(2))
            smooth_k = int(match.group(3))
            if k_period > 1 and d_period > 0 and smooth_k > 0:
                st = ta.STOCH(
                    data,
                    fastk_period=k_period,
                    slowk_period=smooth_k,
                    slowk_matype=0,
                    slowd_period=d_period,
                    slowd_matype=0,
                )
                return st["slowk"].astype("float64")

        # stoch_d_<k_period>_<d_period>_<smooth_k>
        if match := self._STOCH_D_RE.match(factor_name):
            k_period = int(match.group(1))
            d_period = int(match.group(2))
            smooth_k = int(match.group(3))
            if k_period > 1 and d_period > 0 and smooth_k > 0:
                st = ta.STOCH(
                    data,
                    fastk_period=k_period,
                    slowk_period=smooth_k,
                    slowk_matype=0,
                    slowd_period=d_period,
                    slowd_matype=0,
                )
                return st["slowd"].astype("float64")

        raise ValueError(f"Cannot compute factor: {factor_name}")
