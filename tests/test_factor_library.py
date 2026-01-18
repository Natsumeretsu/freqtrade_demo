"""因子库单元测试

测试因子注册、加载和计算功能。
"""

from __future__ import annotations

import pandas as pd
import pytest

from integration.factor_library import (
    BaseFactor,
    FactorLibrary,
    get_factor_class,
    list_all_factors,
    register_factor,
)


def test_list_all_factors():
    """测试列出所有已注册的因子"""
    factors = list_all_factors()
    assert isinstance(factors, list)
    assert len(factors) >= 3  # 至少有3个因子（momentum, volatility, volume_surge）
    assert "momentum_8h" in factors
    assert "volatility_24h" in factors
    assert "volume_surge" in factors


def test_get_factor_class():
    """测试获取因子类"""
    momentum_class = get_factor_class("momentum_8h")
    assert momentum_class is not None
    assert issubclass(momentum_class, BaseFactor)

    # 测试不存在的因子
    invalid_class = get_factor_class("non_existent_factor")
    assert invalid_class is None


def test_momentum_factor_calculation():
    """测试动量因子计算"""
    # 创建测试数据
    df = pd.DataFrame({
        "open": [100, 101, 102, 103, 104],
        "high": [101, 102, 103, 104, 105],
        "low": [99, 100, 101, 102, 103],
        "close": [100, 101, 102, 103, 104],
        "volume": [1000, 1100, 1200, 1300, 1400],
    })

    # 获取因子并计算
    factor_class = get_factor_class("momentum_8h")
    factor = factor_class(window=2)  # 使用小窗口便于测试
    result = factor.calculate(df)

    # 验证结果
    assert isinstance(result, pd.Series)
    assert len(result) == len(df)
    # 前2个值应该是 NaN（窗口不足）
    assert pd.isna(result.iloc[0])
    assert pd.isna(result.iloc[1])
    # 第3个值应该是 (102-100)/100 = 0.02
    assert abs(result.iloc[2] - 0.02) < 1e-6


def test_factor_library_calculate_factors():
    """测试 FactorLibrary 批量计算因子"""
    # 创建测试数据
    df = pd.DataFrame({
        "open": [100, 101, 102, 103, 104],
        "high": [101, 102, 103, 104, 105],
        "low": [99, 100, 101, 102, 103],
        "close": [100, 101, 102, 103, 104],
        "volume": [1000, 1100, 1200, 1300, 1400],
    })

    # 创建因子库并计算因子
    factor_lib = FactorLibrary()
    result = factor_lib.calculate_factors(df, ["momentum_8h", "volume_surge"])

    # 验证结果
    assert isinstance(result, pd.DataFrame)
    assert "momentum_8h" in result.columns
    assert "volume_surge" in result.columns
    assert len(result) == len(df)

