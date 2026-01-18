"""风险因子计算器

处理风险相关的因子（VaR, ES, downside_vol, tail_ratio, gap 等）。
"""
from __future__ import annotations

import re
import numpy as np
import pandas as pd
from .factor_computer import IFactorComputer


class RiskFactorComputer(IFactorComputer):
    """风险因子计算器"""

    # 预编译正则表达式
    _VAR_RE = re.compile(r'^var_(\d+)_(\d+)$')
    _ES_RE = re.compile(r'^es_(\d+)_(\d+)$')
    _DOWNSIDE_VOL_RE = re.compile(r'^downside_vol_(\d+)$')
    _TAIL_RATIO_RE = re.compile(r'^tail_ratio_(\d+)$')
    _GAP_RE = re.compile(r'^gap_(\d+)$')

    def can_compute(self, factor_name: str) -> bool:
        """判断是否可以计算该因子"""
        return (self._VAR_RE.match(factor_name) is not None or
                self._ES_RE.match(factor_name) is not None or
                self._DOWNSIDE_VOL_RE.match(factor_name) is not None or
                self._TAIL_RATIO_RE.match(factor_name) is not None or
                self._GAP_RE.match(factor_name) is not None)

    def compute(self, data: pd.DataFrame, factor_name: str) -> pd.Series:
        """计算风险因子"""
        close = data["close"].astype("float64")
        ret_series = close.pct_change(1)

        # var_<pct>_<n>
        if match := self._VAR_RE.match(factor_name):
            pct = int(match.group(1))
            period = int(match.group(2))
            if 0 < pct < 100 and period > 1:
                return ret_series.rolling(period).quantile(pct / 100.0)

        # es_<pct>_<n>
        if match := self._ES_RE.match(factor_name):
            pct = int(match.group(1))
            period = int(match.group(2))
            if 0 < pct < 100 and period > 1:
                def _es(arr: np.ndarray) -> float:
                    if len(arr) < 5 or np.all(np.isnan(arr)):
                        return np.nan
                    valid = arr[~np.isnan(arr)]
                    if len(valid) < 5:
                        return np.nan
                    threshold = np.percentile(valid, pct)
                    tail = valid[valid <= threshold]
                    return np.mean(tail) if len(tail) > 0 else np.nan
                return ret_series.rolling(period).apply(_es, raw=True)

        # downside_vol_<n>
        if match := self._DOWNSIDE_VOL_RE.match(factor_name):
            period = int(match.group(1))
            if period > 1:
                def _downside_vol(arr: np.ndarray) -> float:
                    if len(arr) < 3 or np.all(np.isnan(arr)):
                        return np.nan
                    valid = arr[~np.isnan(arr)]
                    negative = valid[valid < 0]
                    return np.std(negative, ddof=1) if len(negative) > 1 else np.nan
                return ret_series.rolling(period).apply(_downside_vol, raw=True)

        # tail_ratio_<n>
        if match := self._TAIL_RATIO_RE.match(factor_name):
            period = int(match.group(1))
            if period >= 10:
                def _tail_ratio(arr: np.ndarray) -> float:
                    if len(arr) < 10 or np.all(np.isnan(arr)):
                        return np.nan
                    valid = arr[~np.isnan(arr)]
                    if len(valid) < 10:
                        return np.nan
                    q95 = np.percentile(valid, 95)
                    q05 = np.percentile(valid, 5)
                    return abs(q95 / q05) if q05 != 0 else np.nan
                return ret_series.rolling(period).apply(_tail_ratio, raw=True)

        # gap_<n>
        if match := self._GAP_RE.match(factor_name):
            period = int(match.group(1))
            if period > 0 and "open" in data.columns:
                open_price = data["open"].astype("float64")
                gap = (open_price - close.shift(1)) / close.shift(1).replace(0, np.nan)
                return gap.rolling(period).mean()

        raise ValueError(f"Cannot compute factor: {factor_name}")
