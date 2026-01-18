"""
因子验证模块集成测试
"""

import pandas as pd
import numpy as np
import pytest

from factor_validator import (
    calculate_ic,
    calculate_ic_stats,
    quantile_analysis,
    validate_factor
)


class TestCalculateIC:
    """IC 计算测试"""

    def test_ic_positive_correlation(self):
        """测试正相关因子的 IC"""
        np.random.seed(42)
        n = 100
        factor = np.random.randn(n)
        forward_return = factor * 0.5 + np.random.randn(n) * 0.3

        ic = calculate_ic(pd.Series(factor), pd.Series(forward_return))

        assert ic > 0.3, f"正相关因子 IC 应 > 0.3，实际 {ic:.3f}"

    def test_ic_negative_correlation(self):
        """测试负相关因子的 IC"""
        np.random.seed(42)
        n = 100
        factor = np.random.randn(n)
        forward_return = -factor * 0.5 + np.random.randn(n) * 0.3

        ic = calculate_ic(pd.Series(factor), pd.Series(forward_return))

        assert ic < -0.3, f"负相关因子 IC 应 < -0.3，实际 {ic:.3f}"

    def test_ic_no_correlation(self):
        """测试无相关因子的 IC"""
        np.random.seed(42)
        n = 100
        factor = np.random.randn(n)
        forward_return = np.random.randn(n)

        ic = calculate_ic(pd.Series(factor), pd.Series(forward_return))

        assert abs(ic) < 0.3, f"无相关因子 IC 应接近 0，实际 {ic:.3f}"


class TestICStats:
    """IC 统计测试"""

    def test_ic_stats_structure(self):
        """测试 IC 统计返回结构"""
        np.random.seed(42)
        n = 100
        factor = pd.Series(np.random.randn(n))
        forward_return = pd.Series(np.random.randn(n))

        stats = calculate_ic_stats(factor, forward_return)

        assert 'ic' in stats
        assert 't_stat' in stats

    def test_t_stat_calculation(self):
        """测试 t 值计算"""
        np.random.seed(42)
        n = 100
        factor = np.random.randn(n)
        forward_return = factor * 0.8 + np.random.randn(n) * 0.2

        stats = calculate_ic_stats(pd.Series(factor), pd.Series(forward_return))

        # 强相关应该有高 t 值
        assert abs(stats['t_stat']) > 5, f"强相关 t 值应 > 5，实际 {stats['t_stat']:.2f}"


class TestQuantileAnalysis:
    """分位数分析测试"""

    def test_quantile_analysis_basic(self):
        """测试基本分位数分析"""
        np.random.seed(42)
        n = 200
        factor = np.random.randn(n)
        forward_return = factor * 0.5 + np.random.randn(n) * 0.3

        df = pd.DataFrame({
            'factor': factor,
            'return': forward_return
        })

        result = quantile_analysis(df, 'factor', 'return', n_quantiles=5)

        assert len(result) == 5
        assert 'mean_return' in result.columns
        assert 'std_return' in result.columns
        assert 'count' in result.columns

    def test_quantile_monotonicity(self):
        """测试分位数单调性"""
        np.random.seed(42)
        n = 500
        factor = np.random.randn(n)
        forward_return = factor * 0.8 + np.random.randn(n) * 0.2

        df = pd.DataFrame({
            'factor': factor,
            'return': forward_return
        })

        result = quantile_analysis(df, 'factor', 'return', n_quantiles=5)

        # 检查收益单调性（允许少量违反）
        returns = result['mean_return'].values
        monotonic_pairs = sum(returns[i] < returns[i+1] for i in range(len(returns)-1))

        assert monotonic_pairs >= 3, "分位数收益应基本单调递增"


class TestValidateFactor:
    """因子验证测试"""

    def test_validate_strong_factor(self):
        """测试强因子验证通过"""
        np.random.seed(42)
        n = 200
        factor = np.random.randn(n)
        forward_return = factor * 0.8 + np.random.randn(n) * 0.2

        df = pd.DataFrame({
            'factor': factor,
            'return': forward_return
        })

        passed, stats = validate_factor(df, 'factor', 'return')

        assert passed, "强因子应通过验证"
        assert abs(stats['ic']) > 0.05
        assert abs(stats['t_stat']) > 2.0

    def test_validate_weak_factor(self):
        """测试弱因子验证失败"""
        np.random.seed(42)
        n = 100
        factor = np.random.randn(n)
        forward_return = np.random.randn(n)

        df = pd.DataFrame({
            'factor': factor,
            'return': forward_return
        })

        passed, stats = validate_factor(df, 'factor', 'return')

        assert not passed, "弱因子应验证失败"
