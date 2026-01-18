"""集成测试 - 测试完整数据流

测试从数据清洗到因子计算再到验证的完整流程。
"""
import pytest
import pandas as pd
import numpy as np

from data_pipeline import clean_ohlcv_data, calculate_forward_returns
from simple_factors.basic_factors import calculate_all_factors
from factor_validator import validate_factor


@pytest.fixture
def sample_ohlcv_data():
    """生成样本 OHLCV 数据"""
    np.random.seed(42)
    n = 100

    dates = pd.date_range('2024-01-01', periods=n, freq='1h')
    base_price = 100.0

    # 生成带趋势的价格数据
    trend = np.linspace(0, 10, n)
    noise = np.random.randn(n) * 2
    close = base_price + trend + noise

    df = pd.DataFrame({
        'date': dates,
        'open': close * (1 + np.random.randn(n) * 0.01),
        'high': close * (1 + np.abs(np.random.randn(n)) * 0.02),
        'low': close * (1 - np.abs(np.random.randn(n)) * 0.02),
        'close': close,
        'volume': np.random.randint(1000, 10000, n)
    })

    return df


class TestFullFactorPipeline:
    """测试完整的因子计算和验证流程"""

    def test_full_pipeline(self, sample_ohlcv_data):
        """测试完整数据流: 清洗 → 未来收益 → 因子 → 验证"""
        # 1. 数据清洗
        df = clean_ohlcv_data(sample_ohlcv_data)
        assert len(df) > 0
        assert 'close' in df.columns

        # 2. 计算未来收益
        df = calculate_forward_returns(df, periods=[1, 4, 8])
        assert 'forward_return_1p' in df.columns
        assert 'forward_return_4p' in df.columns
        assert 'forward_return_8p' in df.columns

        # 3. 计算因子
        df = calculate_all_factors(df)
        assert 'momentum_8h' in df.columns
        assert 'volatility_24h' in df.columns
        assert 'volume_surge' in df.columns

        # 4. 验证因子（使用宽松阈值）
        passed, stats = validate_factor(
            df,
            'momentum_8h',
            'forward_return_1p',
            ic_threshold=0.0,  # 宽松阈值
            t_threshold=0.0
        )

        assert 'ic' in stats
        assert 't_stat' in stats
        assert not pd.isna(stats['ic'])
        assert not pd.isna(stats['t_stat'])
