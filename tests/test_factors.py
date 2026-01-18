"""
因子计算单元测试
"""

import pandas as pd
from simple_factors.basic_factors import (
    calculate_all_factors,
    calculate_momentum,
    calculate_volatility,
    calculate_volume_surge,
)


class TestMomentumFactor:
    """动量因子测试"""

    def test_momentum_basic(self, sample_ohlcv_data):
        """测试基本动量计算"""
        result = calculate_momentum(sample_ohlcv_data, window=32)

        # 验证返回类型
        assert isinstance(result, pd.Series)

        # 验证长度
        assert len(result) == len(sample_ohlcv_data)

        # 验证前 window 个值为 NaN
        assert result.iloc[:32].isna().all()

        # 验证后续值不为 NaN（至少大部分）
        assert result.iloc[32:].notna().sum() > 0

    def test_momentum_with_trend(self, sample_ohlcv_with_trend):
        """测试上升趋势中的动量因子"""
        result = calculate_momentum(sample_ohlcv_with_trend, window=32)

        # 上升趋势中，动量因子应该大部分为正
        valid_momentum = result.dropna()
        positive_ratio = (valid_momentum > 0).sum() / len(valid_momentum)

        assert positive_ratio > 0.6, f"上升趋势中正动量比例应 > 60%，实际 {positive_ratio:.2%}"

    def test_momentum_window_parameter(self, sample_ohlcv_data):
        """测试不同窗口参数"""
        result_short = calculate_momentum(sample_ohlcv_data, window=10)
        result_long = calculate_momentum(sample_ohlcv_data, window=50)

        # 短窗口应该有更多有效值
        assert result_short.notna().sum() > result_long.notna().sum()


class TestVolatilityFactor:
    """波动率因子测试"""

    def test_volatility_basic(self, sample_ohlcv_data):
        """测试基本波动率计算"""
        result = calculate_volatility(sample_ohlcv_data, window=96)

        # 验证返回类型
        assert isinstance(result, pd.Series)

        # 验证长度
        assert len(result) == len(sample_ohlcv_data)

        # 验证前 window 个值为 NaN
        assert result.iloc[:96].isna().all()

    def test_volatility_positive(self, sample_ohlcv_data):
        """测试波动率为非负值"""
        result = calculate_volatility(sample_ohlcv_data, window=96)
        valid_values = result.dropna()

        # 波动率（标准差）应该全部 >= 0
        assert (valid_values >= 0).all()

    def test_volatility_range(self, sample_ohlcv_data):
        """测试波动率合理范围"""
        result = calculate_volatility(sample_ohlcv_data, window=96)
        valid_values = result.dropna()

        # 对于加密市场，日内波动率通常在 0.001 ~ 0.1 之间
        assert valid_values.min() >= 0
        assert valid_values.max() < 1.0, "波动率异常过高"


class TestVolumeSurgeFactor:
    """成交量激增因子测试"""

    def test_volume_surge_basic(self, sample_ohlcv_data):
        """测试基本成交量激增计算"""
        result = calculate_volume_surge(sample_ohlcv_data, window=96)

        # 验证返回类型
        assert isinstance(result, pd.Series)

        # 验证长度
        assert len(result) == len(sample_ohlcv_data)

    def test_volume_surge_positive(self, sample_ohlcv_data):
        """测试成交量激增为正值"""
        result = calculate_volume_surge(sample_ohlcv_data, window=96)
        valid_values = result.dropna()

        # 成交量比率应该全部 > 0
        assert (valid_values > 0).all()

    def test_volume_surge_mean_around_one(self, sample_ohlcv_data):
        """测试成交量激增均值接近 1"""
        result = calculate_volume_surge(sample_ohlcv_data, window=96)
        valid_values = result.dropna()

        # 如果成交量是随机分布，均值应该接近 1
        mean_surge = valid_values.mean()
        assert 0.8 < mean_surge < 1.2, f"成交量激增均值应接近 1，实际 {mean_surge:.2f}"


class TestCalculateAllFactors:
    """综合因子计算测试"""

    def test_all_factors_columns(self, sample_ohlcv_data):
        """测试返回的 DataFrame 包含所有因子列"""
        result = calculate_all_factors(sample_ohlcv_data)

        # 验证返回类型
        assert isinstance(result, pd.DataFrame)

        # 验证包含原始列
        for col in ['open', 'high', 'low', 'close', 'volume']:
            assert col in result.columns

        # 验证包含因子列
        assert 'momentum_8h' in result.columns
        assert 'volatility_24h' in result.columns
        assert 'volume_surge' in result.columns

    def test_all_factors_no_mutation(self, sample_ohlcv_data):
        """测试不修改原始 DataFrame"""
        original_columns = sample_ohlcv_data.columns.tolist()
        _ = calculate_all_factors(sample_ohlcv_data)

        # 原始 DataFrame 不应该被修改
        assert sample_ohlcv_data.columns.tolist() == original_columns

    def test_all_factors_length(self, sample_ohlcv_data):
        """测试返回 DataFrame 长度一致"""
        result = calculate_all_factors(sample_ohlcv_data)

        assert len(result) == len(sample_ohlcv_data)
