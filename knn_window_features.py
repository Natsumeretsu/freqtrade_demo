from __future__ import annotations

from typing import Final

import numpy as np
import pandas as pd
import talib.abstract as ta
from pandas import DataFrame


_BASE_FEATURE_NAMES: Final[list[str]] = [
    # 动量：相对上一根收盘的变化（更接近平稳序列）
    "ret",
    # 形态：实体/影线/收盘位置（都做了范围归一化）
    "body_pct",
    "range_pct",
    "upper_wick_pct",
    "lower_wick_pct",
    "close_pos",
    # 成交量变化：相对上一根的变化
    "vol_chg",
]

_TREND_FEATURE_NAMES: Final[list[str]] = [
    # 趋势上下文：用“相对偏离”表达，避免把绝对价格水平当成特征
    "close_ema_fast_diff",
    "close_ema_long_diff",
    "ema_fast_slow_diff",
    "ema_slow_long_diff",
    # 强度：ADX 本身已是无量纲（由 build_trend_indicators 提供）
    "adx",
]


def get_knn_window_feature_columns(window: int) -> list[str]:
    """
    生成多 K 线窗口特征列名（稳定顺序，便于训练/推理对齐）。

    命名规则：{base_name}_lag_{k}
    - lag_0：当前 K 线（最近一根）
    - lag_1：上一根
    - ...
    """
    if window <= 0:
        raise ValueError("window 必须为正整数")

    columns: list[str] = []
    for lag in range(window):
        for base_name in _BASE_FEATURE_NAMES:
            columns.append(f"{base_name}_lag_{lag}")
    return columns


def get_knn_trend_feature_columns() -> list[str]:
    """
    趋势上下文特征列名（与 build_trend_indicators 输出的 ema/adx 对齐）。

    说明：
    - 这里的特征设计目标是“让模型知道当前处在什么趋势结构里”。
    - 用 ratio-1 的形式表达偏离，能更好适配不同价格区间（并且更接近 0 均值）。
    """
    return list(_TREND_FEATURE_NAMES)


def build_knn_window_features(dataframe: DataFrame, window: int) -> DataFrame:
    """
    将“最近 window 根 K 线”的形态/动量/波动/成交量变化展开成固定长度向量特征。

    说明：
    - 所有特征只使用当前及历史数据（不使用 shift(-1) 之类的未来信息），避免数据泄露。
    - 对高低范围为 0 的极端情况做了保护，防止除零。
    """
    if window <= 0:
        raise ValueError("window 必须为正整数")

    high = dataframe["high"]
    low = dataframe["low"]
    open_ = dataframe["open"]
    close = dataframe["close"]
    volume = dataframe["volume"]

    hl_range = high - low
    hl_safe = hl_range.replace(0, np.nan)
    close_safe = close.replace(0, np.nan)

    # K 线形态：实体 + 上下影线
    body = close - open_
    oc_max = pd.concat([open_, close], axis=1).max(axis=1)
    oc_min = pd.concat([open_, close], axis=1).min(axis=1)
    upper_wick = high - oc_max
    lower_wick = oc_min - low

    base = pd.DataFrame(
        {
            "ret": close.pct_change(),
            "body_pct": body / hl_safe,
            "range_pct": hl_range / close_safe,
            "upper_wick_pct": upper_wick / hl_safe,
            "lower_wick_pct": lower_wick / hl_safe,
            "close_pos": (close - low) / hl_safe,
            "vol_chg": volume.pct_change(),
        },
        index=dataframe.index,
    ).replace([np.inf, -np.inf], np.nan)

    cols: dict[str, pd.Series] = {}
    for lag in range(window):
        for base_name in _BASE_FEATURE_NAMES:
            cols[f"{base_name}_lag_{lag}"] = base[base_name].shift(lag)

    return pd.DataFrame(cols, index=dataframe.index)


def build_knn_trend_features(dataframe: DataFrame, trend: DataFrame) -> DataFrame:
    """
    将趋势指标转换为更适合做距离度量的上下文特征（给 KNN 使用）。

    要求：trend 至少包含列：ema_fast / ema_slow / ema_long / adx
    """
    close = dataframe["close"].replace(0, np.nan)
    ema_fast = trend["ema_fast"].replace(0, np.nan)
    ema_slow = trend["ema_slow"].replace(0, np.nan)
    ema_long = trend["ema_long"].replace(0, np.nan)

    trend_features = pd.DataFrame(
        {
            "close_ema_fast_diff": close / ema_fast - 1.0,
            "close_ema_long_diff": close / ema_long - 1.0,
            "ema_fast_slow_diff": ema_fast / ema_slow - 1.0,
            "ema_slow_long_diff": ema_slow / ema_long - 1.0,
        },
        index=dataframe.index,
    )
    return trend_features.replace([np.inf, -np.inf], np.nan)


def build_trend_indicators(
    dataframe: DataFrame,
    ema_fast: int = 20,
    ema_slow: int = 50,
    ema_long: int = 200,
    adx_period: int = 14,
) -> DataFrame:
    """
    计算趋势判断常用指标（用于“先判趋势”过滤，不直接决定 KNN 输入特征）。
    """
    if ema_fast <= 0 or ema_slow <= 0 or ema_long <= 0 or adx_period <= 0:
        raise ValueError("指标周期必须为正整数")

    trend_df = pd.DataFrame(
        {
            "ema_fast": ta.EMA(dataframe, timeperiod=ema_fast),
            "ema_slow": ta.EMA(dataframe, timeperiod=ema_slow),
            "ema_long": ta.EMA(dataframe, timeperiod=ema_long),
            "adx": ta.ADX(dataframe, timeperiod=adx_period),
        },
        index=dataframe.index,
    )
    return trend_df.replace([np.inf, -np.inf], np.nan)
