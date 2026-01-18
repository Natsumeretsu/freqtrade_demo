"""熵因子计算器

处理熵相关的因子（dir_entropy, vol_state_entropy, bucket_entropy 等）。
"""
from __future__ import annotations

import re
import numpy as np
import pandas as pd
from .factor_computer import IFactorComputer


def _calc_entropy(arr: np.ndarray) -> float:
    """计算熵"""
    if len(arr) < 2 or np.all(np.isnan(arr)):
        return np.nan
    valid = arr[~np.isnan(arr)]
    if len(valid) < 2:
        return np.nan
    _, counts = np.unique(valid, return_counts=True)
    probs = counts / len(valid)
    return -np.sum(probs * np.log2(probs + 1e-10))


def _discretize_to_state(arr: np.ndarray) -> float:
    """将数组离散化为状态（低/中/高）"""
    if len(arr) < 3 or np.all(np.isnan(arr)):
        return np.nan
    valid = arr[~np.isnan(arr)]
    if len(valid) < 3:
        return np.nan
    q33 = np.percentile(valid, 33)
    q66 = np.percentile(valid, 66)
    last_val = valid[-1]
    if last_val <= q33:
        return 0  # 低
    elif last_val <= q66:
        return 1  # 中
    else:
        return 2  # 高


class EntropyFactorComputer(IFactorComputer):
    """熵因子计算器"""

    # 预编译正则表达式
    _DIR_ENTROPY_RE = re.compile(r'^dir_entropy_(\d+)$')
    _VOL_STATE_ENTROPY_RE = re.compile(r'^vol_state_entropy_(\d+)$')
    _BUCKET_ENTROPY_RE = re.compile(r'^bucket_entropy_(\d+)$')

    def can_compute(self, factor_name: str) -> bool:
        """判断是否可以计算该因子"""
        return (self._DIR_ENTROPY_RE.match(factor_name) is not None or
                self._VOL_STATE_ENTROPY_RE.match(factor_name) is not None or
                self._BUCKET_ENTROPY_RE.match(factor_name) is not None)

    def compute(self, data: pd.DataFrame, factor_name: str) -> pd.Series:
        """计算熵因子"""
        close = data["close"].astype("float64")
        ret1 = close.pct_change(1)

        # dir_entropy_<n>
        if match := self._DIR_ENTROPY_RE.match(factor_name):
            period = int(match.group(1))
            if period > 2:
                ret_sign = np.sign(ret1)
                return ret_sign.rolling(period).apply(_calc_entropy, raw=True)

        # vol_state_entropy_<n>
        if match := self._VOL_STATE_ENTROPY_RE.match(factor_name):
            period = int(match.group(1))
            if period > 2:
                vol_series = ret1.rolling(period).std()
                vol_state = vol_series.rolling(period).apply(_discretize_to_state, raw=True)
                return vol_state.rolling(period).apply(_calc_entropy, raw=True)

        # bucket_entropy_<n>
        if match := self._BUCKET_ENTROPY_RE.match(factor_name):
            period = int(match.group(1))
            if period > 4:
                def _bucket_entropy(arr: np.ndarray) -> float:
                    if len(arr) < 5 or np.all(np.isnan(arr)):
                        return np.nan
                    valid = arr[~np.isnan(arr)]
                    if len(valid) < 5:
                        return np.nan
                    try:
                        buckets = pd.qcut(valid, q=5, labels=False, duplicates="drop")
                        return _calc_entropy(buckets)
                    except ValueError:
                        return np.nan
                return ret1.rolling(period).apply(_bucket_entropy, raw=True)

        raise ValueError(f"Cannot compute factor: {factor_name}")
