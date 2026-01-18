"""MACD 因子计算器

处理 MACD（移动平均收敛散度）指标。
"""
from __future__ import annotations

import pandas as pd
import talib as ta
from .factor_computer import IFactorComputer


class MacdFactorComputer(IFactorComputer):
    """MACD 因子计算器"""

    def __init__(self, fast_period: int = 12, slow_period: int = 26, signal_period: int = 9):
        self._fast_period = fast_period
        self._slow_period = slow_period
        self._signal_period = signal_period

    def can_compute(self, factor_name: str) -> bool:
        """判断是否可以计算该因子"""
        return factor_name in {"macd", "macdsignal", "macdhist"}

    def compute(self, data: pd.DataFrame, factor_name: str) -> pd.Series:
        """计算 MACD 因子

        注意：MACD 三个指标需要一起计算，因此这里会计算所有三个
        """
        macd = ta.MACD(
            data,
            fastperiod=self._fast_period,
            slowperiod=self._slow_period,
            signalperiod=self._signal_period,
        )

        if factor_name == "macd":
            return macd["macd"]
        elif factor_name == "macdsignal":
            return macd["macdsignal"]
        elif factor_name == "macdhist":
            return macd["macdhist"]

        raise ValueError(f"Cannot compute factor: {factor_name}")
