"""
数据预处理模块集成测试
"""

import pandas as pd
from data_pipeline import calculate_forward_returns, clean_ohlcv_data, split_train_val_test


class TestCleanOHLCVData:
    """OHLCV 数据清洗测试"""

    def test_clean_basic(self, sample_ohlcv_data):
        """测试基本清洗功能"""
        result = clean_ohlcv_data(sample_ohlcv_data)

        assert len(result) > 0
        assert result['close'].notna().all()
        assert result['volume'].notna().all()

    def test_remove_extreme_changes(self):
        """测试移除极端涨跌幅"""
        df = pd.DataFrame({
            'date': pd.date_range('2024-01-01', periods=10, freq='15min'),
            'open': [100, 101, 102, 103, 200, 105, 106, 107, 108, 109],
            'high': [101, 102, 103, 104, 201, 106, 107, 108, 109, 110],
            'low': [99, 100, 101, 102, 199, 104, 105, 106, 107, 108],
            'close': [100, 101, 102, 103, 200, 105, 106, 107, 108, 109],
            'volume': [1000] * 10
        })

        result = clean_ohlcv_data(df, max_price_change=0.2)

        # 应该移除涨幅 ~94% 的异常数据
        assert len(result) < len(df)

    def test_validate_ohlc_relationship(self):
        """测试 OHLC 关系验证"""
        df = pd.DataFrame({
            'date': pd.date_range('2024-01-01', periods=5, freq='15min'),
            'open': [100, 101, 102, 103, 104],
            'high': [101, 102, 103, 104, 105],
            'low': [99, 100, 101, 102, 103],
            'close': [100, 101, 102, 103, 104],
            'volume': [1000] * 5
        })

        # 添加一条违反 OHLC 关系的数据
        df.loc[2, 'high'] = 95  # high < low

        result = clean_ohlcv_data(df)

        # 应该移除违反关系的行
        assert len(result) < len(df)


class TestCalculateForwardReturns:
    """未来收益计算测试"""

    def test_forward_returns_basic(self, sample_ohlcv_data):
        """测试基本未来收益计算"""
        result = calculate_forward_returns(sample_ohlcv_data, periods=[1, 4])

        assert 'forward_return_1p' in result.columns
        assert 'forward_return_4p' in result.columns

    def test_forward_returns_values(self):
        """测试未来收益计算正确性"""
        df = pd.DataFrame({
            'close': [100, 102, 104, 106, 108]
        })

        result = calculate_forward_returns(df, periods=[1])

        # 第一个值的未来收益应该是 (102-100)/100 = 0.02
        assert abs(result['forward_return_1p'].iloc[0] - 0.02) < 1e-6


class TestSplitTrainValTest:
    """数据集分割测试"""

    def test_split_ratios(self, sample_ohlcv_data):
        """测试分割比例"""
        train, val, test = split_train_val_test(
            sample_ohlcv_data,
            train_ratio=0.6,
            val_ratio=0.2,
            test_ratio=0.2
        )

        total_len = len(sample_ohlcv_data)
        assert len(train) == int(total_len * 0.6)
        assert len(val) == int(total_len * 0.2)
        assert len(test) > 0

    def test_split_no_overlap(self, sample_ohlcv_data):
        """测试分割无重叠"""
        train, val, test = split_train_val_test(sample_ohlcv_data)

        # 检查索引无重叠
        train_idx = set(train.index)
        val_idx = set(val.index)
        test_idx = set(test.index)

        assert len(train_idx & val_idx) == 0
        assert len(train_idx & test_idx) == 0
        assert len(val_idx & test_idx) == 0
