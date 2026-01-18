"""技术指标因子计算器

处理 RSI、CCI、MFI、ROC、WILLR 等技术指标。
"""
from __future__ import annotations

import re
import pandas as pd
import talib as ta
from .factor_computer import IFactorComputer


class TechnicalFactorComputer(IFactorComputer):
    """技术指标因子计算器"""

    # 预编译正则表达式
    _RSI_RE = re.compile(r'^rsi_(\d+)$')
    _CCI_RE = re.compile(r'^cci_(\d+)$')
    _MFI_RE = re.compile(r'^mfi_(\d+)$')
    _WILLR_RE = re.compile(r'^willr_(\d+)$')

    def can_compute(self, factor_name: str) -> bool:
        """判断是否可以计算该因子"""
        return (self._RSI_RE.match(factor_name) is not None or
                self._CCI_RE.match(factor_name) is not None or
                self._MFI_RE.match(factor_name) is not None or
                self._WILLR_RE.match(factor_name) is not None)

    def compute(self, data: pd.DataFrame, factor_name: str) -> pd.Series:
        """计算技术指标因子"""
        close = data["close"].astype("float64")

        # rsi_<n>
        if match := self._RSI_RE.match(factor_name):
            period = int(match.group(1))
            if period > 0:
                result = ta.RSI(close, timeperiod=period)
                return pd.Series(result, index=data.index) if not isinstance(result, pd.Series) else result

        # cci_<n>
        if match := self._CCI_RE.match(factor_name):
            period = int(match.group(1))
            if period > 0:
                result = ta.CCI(data["high"], data["low"], close, timeperiod=period)
                return pd.Series(result, index=data.index) if not isinstance(result, pd.Series) else result

        # mfi_<n>
        if match := self._MFI_RE.match(factor_name):
            period = int(match.group(1))
            if period > 0:
                result = ta.MFI(data["high"], data["low"], close, data["volume"], timeperiod=period)
                return pd.Series(result, index=data.index) if not isinstance(result, pd.Series) else result

        # willr_<n>
        if match := self._WILLR_RE.match(factor_name):
            period = int(match.group(1))
            if period > 0:
                result = ta.WILLR(data["high"], data["low"], close, timeperiod=period)
                return pd.Series(result, index=data.index) if not isinstance(result, pd.Series) else result

        raise ValueError(f"Cannot compute factor: {factor_name}")
