"""
测试 Alphalens 适配器
"""

import pandas as pd
import pytest
from datetime import datetime, timedelta

from trading_system.infrastructure.analysis.alphalens_adapter import (
    convert_to_alphalens_format,
    validate_factor_data,
    validate_pricing_data,
)


@pytest.fixture
def sample_factor_data():
    """生成测试用的因子数据"""
    dates = pd.date_range('2024-01-01', periods=10, freq='1h')
    pairs = ['BTC/USDT:USDT', 'ETH/USDT:USDT']

    data = []
    for date in dates:
        for pair in pairs:
            data.append({
                'date': date,
                'pair': pair,
                'factor_value': 0.5 + 0.1 * len(data)
            })

    return pd.DataFrame(data)


@pytest.fixture
def sample_pricing_data():
    """生成测试用的价格数据"""
    dates = pd.date_range('2024-01-01', periods=20, freq='1h')

    pricing_data = {
        'BTC/USDT:USDT': pd.DataFrame({
            'date': dates,
            'close': 40000 + 100 * range(len(dates))
        }),
        'ETH/USDT:USDT': pd.DataFrame({
            'date': dates,
            'close': 2000 + 10 * range(len(dates))
        })
    }

    return pricing_data


def test_convert_to_alphalens_format(sample_factor_data, sample_pricing_data):
    """测试数据格式转换"""
    result = convert_to_alphalens_format(
        factor_data=sample_factor_data,
        pricing_data=sample_pricing_data,
        periods=[1, 5],
        quantiles=5,
    )

    # 验证结果格式
    assert isinstance(result, pd.DataFrame)
    assert isinstance(result.index, pd.MultiIndex)
    assert result.index.names == ['date', 'asset']
    assert 'factor' in result.columns


def test_validate_factor_data_empty():
    """测试空因子数据验证"""
    with pytest.raises(ValueError, match="因子数据为空"):
        validate_factor_data(pd.DataFrame())


def test_validate_pricing_data_empty():
    """测试空价格数据验证"""
    with pytest.raises(ValueError, match="价格数据为空"):
        validate_pricing_data({})
