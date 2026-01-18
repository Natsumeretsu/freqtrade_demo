"""成交量因子计算器

处理成交量相关的因子（volume_ratio, volume_z, rel_vol 等）。
"""
from __future__ import annotations

import re
import numpy as np
import pandas as pd
from .factor_computer import IFactorComputer


class VolumeFactorComputer(IFactorComputer):
    """成交量因子计算器"""

    # 预编译正则表达式
    _VOLUME_Z_RE = re.compile(r'^volume_z_(\d+)$')
    _VOL_RATIO_RE = re.compile(r'^volume_ratio_(\d+)$')
    _REL_VOL_RE = re.compile(r'^rel_vol_(\d+)$')

    def __init__(self, default_volume_ratio_lookback: int = 20):
        self._default_volume_ratio_lookback = default_volume_ratio_lookback

    def can_compute(self, factor_name: str) -> bool:
        """判断是否可以计算该因子"""
        return (factor_name == "volume_ratio" or
                self._VOLUME_Z_RE.match(factor_name) is not None or
                self._VOL_RATIO_RE.match(factor_name) is not None or
                self._REL_VOL_RE.match(factor_name) is not None)

    def compute(self, data: pd.DataFrame, factor_name: str) -> pd.Series:
        """计算成交量因子"""
        volume = data["volume"].astype("float64")

        # volume_ratio (默认 lookback)
        if factor_name == "volume_ratio":
            mean = volume.rolling(self._default_volume_ratio_lookback).mean().replace(0, np.nan)
            return volume / mean

        # volume_ratio_<n>
        if match := self._VOL_RATIO_RE.match(factor_name):
            lookback = int(match.group(1))
            if lookback > 0:
                mean = volume.rolling(lookback).mean().replace(0, np.nan)
                return volume / mean

        # volume_z_<n>
        if match := self._VOLUME_Z_RE.match(factor_name):
            period = int(match.group(1))
            if period > 1:
                mean = volume.rolling(period).mean()
                std = volume.rolling(period).std()
                return (volume - mean) / std.replace(0, np.nan)

        # rel_vol_<n>
        if match := self._REL_VOL_RE.match(factor_name):
            period = int(match.group(1))
            if period > 0:
                mean = volume.rolling(period).mean().replace(0, np.nan)
                return volume / mean

        raise ValueError(f"Cannot compute factor: {factor_name}")
