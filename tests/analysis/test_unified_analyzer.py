"""
测试统一分析器
"""

import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "03_integration"))

import pandas as pd
import pytest
from pathlib import Path

from trading_system.infrastructure.analysis.unified_analyzer import FactorAnalyzer


@pytest.fixture
def sample_data():
    """生成测试数据"""
    dates = pd.date_range('2024-01-01', periods=10, freq='1h')
    pairs = ['BTC/USDT:USDT', 'ETH/USDT:USDT']

    # 因子数据
    factor_data = []
    for date in dates:
        for pair in pairs:
            factor_data.append({
                'date': date,
                'pair': pair,
                'factor_value': 0.5 + 0.1 * len(factor_data)
            })
    factor_df = pd.DataFrame(factor_data)

    # 价格数据
    pricing_data = {
        'BTC/USDT:USDT': pd.DataFrame({
            'date': pd.date_range('2024-01-01', periods=20, freq='1h'),
            'close': [40000 + 100 * i for i in range(20)]
        }),
        'ETH/USDT:USDT': pd.DataFrame({
            'date': pd.date_range('2024-01-01', periods=20, freq='1h'),
            'close': [2000 + 10 * i for i in range(20)]
        })
    }

    return factor_df, pricing_data


def test_factor_analyzer_init(sample_data):
    """测试分析器初始化"""
    factor_df, pricing_data = sample_data

    analyzer = FactorAnalyzer(
        factor_data=factor_df,
        pricing_data=pricing_data,
        periods=[1, 5],
        quantiles=5,
        freq='h',  # 明确指定小时频率
    )

    assert analyzer is not None
    assert analyzer.periods == [1, 5]
    assert analyzer.quantiles == 5


def test_get_summary(sample_data):
    """测试获取摘要"""
    factor_df, pricing_data = sample_data

    analyzer = FactorAnalyzer(
        factor_data=factor_df,
        pricing_data=pricing_data,
        periods=[1, 5],
        quantiles=5,
        freq='h',  # 明确指定小时频率
    )

    summary = analyzer.get_summary()

    assert 'ic_mean' in summary
    assert 'ic_std' in summary
    assert 'long_short_return' in summary
