"""
数据预处理模块 - MVP版本

提供数据清洗、特征工程、样本分割等核心功能。
"""

from __future__ import annotations

import pandas as pd
import numpy as np
from typing import Tuple, Optional


def clean_ohlcv_data(
    df: pd.DataFrame,
    max_price_change: float = 0.2,
    remove_duplicates: bool = True
) -> pd.DataFrame:
    """
    清洗 OHLCV 数据

    Args:
        df: 原始 OHLCV DataFrame
        max_price_change: 单根K线最大涨跌幅（默认 20%）
        remove_duplicates: 是否移除重复时间戳

    Returns:
        清洗后的 DataFrame
    """
    result = df.copy()

    # 移除重复时间戳
    if remove_duplicates and 'date' in result.columns:
        result = result.drop_duplicates(subset=['date'], keep='first')

    # 移除缺失值
    result = result.dropna(subset=['open', 'high', 'low', 'close', 'volume'])

    # 移除异常涨跌幅
    returns = result['close'].pct_change().abs()
    valid_mask = returns <= max_price_change
    result = result[valid_mask]

    # 验证 OHLC 关系
    valid_ohlc = (
        (result['high'] >= result['low']) &
        (result['high'] >= result['open']) &
        (result['high'] >= result['close']) &
        (result['low'] <= result['open']) &
        (result['low'] <= result['close'])
    )
    result = result[valid_ohlc]

    return result.reset_index(drop=True)


def calculate_forward_returns(
    df: pd.DataFrame,
    price_col: str = 'close',
    periods: list[int] = [1, 4, 8]
) -> pd.DataFrame:
    """
    计算未来收益

    Args:
        df: OHLCV DataFrame
        price_col: 价格列名
        periods: 未来周期列表（单位：K线数）

    Returns:
        添加了未来收益列的 DataFrame
    """
    result = df.copy()

    for period in periods:
        col_name = f'forward_return_{period}p'
        result[col_name] = result[price_col].pct_change(period).shift(-period)

    return result


def split_train_val_test(
    df: pd.DataFrame,
    train_ratio: float = 0.6,
    val_ratio: float = 0.2,
    test_ratio: float = 0.2
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    分割训练集、验证集、测试集

    Args:
        df: 完整 DataFrame
        train_ratio: 训练集比例
        val_ratio: 验证集比例
        test_ratio: 测试集比例

    Returns:
        (训练集, 验证集, 测试集)
    """
    assert abs(train_ratio + val_ratio + test_ratio - 1.0) < 1e-6, \
        "比例之和必须为 1"

    n = len(df)
    train_end = int(n * train_ratio)
    val_end = int(n * (train_ratio + val_ratio))

    train_df = df.iloc[:train_end].copy()
    val_df = df.iloc[train_end:val_end].copy()
    test_df = df.iloc[val_end:].copy()

    return train_df, val_df, test_df


def normalize_features(
    df: pd.DataFrame,
    feature_cols: list[str],
    method: str = 'zscore'
) -> pd.DataFrame:
    """
    特征标准化

    Args:
        df: DataFrame
        feature_cols: 需要标准化的列
        method: 标准化方法 ('zscore' 或 'minmax')

    Returns:
        标准化后的 DataFrame
    """
    result = df.copy()

    for col in feature_cols:
        if col not in result.columns:
            continue

        if method == 'zscore':
            mean = result[col].mean()
            std = result[col].std()
            if std > 0:
                result[col] = (result[col] - mean) / std
        elif method == 'minmax':
            min_val = result[col].min()
            max_val = result[col].max()
            if max_val > min_val:
                result[col] = (result[col] - min_val) / (max_val - min_val)
        else:
            raise ValueError(f"不支持的标准化方法: {method}")

    return result
