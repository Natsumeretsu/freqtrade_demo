"""
Pytest 配置和共享 fixtures
"""

import numpy as np
import pandas as pd
import pytest


@pytest.fixture
def sample_ohlcv_data():
    """
    生成模拟的 OHLCV 数据用于测试

    Returns:
        pd.DataFrame: 包含 200 行的 OHLCV 数据
    """
    np.random.seed(42)
    n = 200

    # 生成模拟价格数据（随机游走）
    close_prices = 100 * np.exp(np.cumsum(np.random.randn(n) * 0.02))

    df = pd.DataFrame({
        'date': pd.date_range('2024-01-01', periods=n, freq='15min'),
        'open': close_prices * (1 + np.random.randn(n) * 0.001),
        'high': close_prices * (1 + np.abs(np.random.randn(n)) * 0.005),
        'low': close_prices * (1 - np.abs(np.random.randn(n)) * 0.005),
        'close': close_prices,
        'volume': np.random.uniform(1000, 10000, n)
    })

    return df


@pytest.fixture
def sample_ohlcv_with_trend():
    """
    生成带明显趋势的 OHLCV 数据

    Returns:
        pd.DataFrame: 包含上升趋势的 OHLCV 数据
    """
    np.random.seed(42)
    n = 200

    # 生成上升趋势
    trend = np.linspace(100, 120, n)
    noise = np.random.randn(n) * 0.5
    close_prices = trend + noise

    df = pd.DataFrame({
        'date': pd.date_range('2024-01-01', periods=n, freq='15min'),
        'open': close_prices * (1 + np.random.randn(n) * 0.001),
        'high': close_prices * (1 + np.abs(np.random.randn(n)) * 0.005),
        'low': close_prices * (1 - np.abs(np.random.randn(n)) * 0.005),
        'close': close_prices,
        'volume': np.random.uniform(1000, 10000, n)
    })

    return df
