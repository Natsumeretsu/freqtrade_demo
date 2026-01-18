"""
基础因子计算 - MVP版本

只包含经过验证的核心因子，避免过度抽象。
每个因子都应该有明确的盈利假设和验证结果。
"""

from __future__ import annotations

import pandas as pd


def calculate_momentum(df: pd.DataFrame, window: int = 32) -> pd.Series:
    """
    动量因子（改进版，考虑加密市场特性）

    假设：短期价格动量在加密市场中有效期约8小时（32个15分钟K线）

    Args:
        df: OHLCV DataFrame
        window: 回看窗口（默认32 = 8小时）

    Returns:
        动量因子值
    """
    return df['close'].pct_change(window)


def calculate_volatility(df: pd.DataFrame, window: int = 96) -> pd.Series:
    """
    波动率因子

    假设：高波动率预示价格不稳定，可能出现反转

    Args:
        df: OHLCV DataFrame
        window: 回看窗口（默认96 = 24小时）

    Returns:
        波动率（标准差）
    """
    returns = df['close'].pct_change()
    return returns.rolling(window=window).std()


def calculate_volume_surge(df: pd.DataFrame, window: int = 96) -> pd.Series:
    """
    成交量激增因子

    假设：成交量突然放大预示趋势启动或反转

    Args:
        df: OHLCV DataFrame
        window: 回看窗口（默认96 = 24小时）

    Returns:
        成交量相对均值的倍数
    """
    volume_ma = df['volume'].rolling(window=window).mean()
    return df['volume'] / volume_ma


def calculate_all_factors(df: pd.DataFrame) -> pd.DataFrame:
    """
    计算所有因子

    Args:
        df: OHLCV DataFrame

    Returns:
        包含所有因子的DataFrame
    """
    result = df.copy()

    result['momentum_8h'] = calculate_momentum(df, window=32)
    result['volatility_24h'] = calculate_volatility(df, window=96)
    result['volume_surge'] = calculate_volume_surge(df, window=96)

    return result
