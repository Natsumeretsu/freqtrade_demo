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
from integration.factor_library.registry import FactorRegistry


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


# ==================== FactorRegistry 测试 ====================


def test_factor_registry_duplicate_registration():
    """测试重复注册因子应该抛出 ValueError"""
    registry = FactorRegistry()

    # 创建测试因子类
    @register_factor
    class TestFactor1(BaseFactor):
        @property
        def name(self) -> str:
            return "test_duplicate"

        @property
        def description(self) -> str:
            return "测试因子"

        def calculate(self, df: pd.DataFrame) -> pd.Series:
            return df["close"]

    # 尝试注册同名因子应该抛出错误
    with pytest.raises(ValueError, match="因子 'test_duplicate' 已注册"):
        @register_factor
        class TestFactor2(BaseFactor):
            @property
            def name(self) -> str:
                return "test_duplicate"

            @property
            def description(self) -> str:
                return "重复因子"

            def calculate(self, df: pd.DataFrame) -> pd.Series:
                return df["close"]


def test_factor_registry_clear():
    """测试清空注册表功能"""
    from integration.factor_library.registry import _registry

    # 记录清空前的因子数量
    factors_before = len(list_all_factors())
    assert factors_before > 0

    # 清空注册表
    _registry.clear()

    # 验证注册表已清空
    assert len(list_all_factors()) == 0

    # 重新导入以恢复注册的因子
    import importlib
    import integration.factor_library.technical
    importlib.reload(integration.factor_library.technical)


# ==================== 边界条件测试 ====================


def test_factor_with_empty_dataframe():
    """测试空数据框"""
    df = pd.DataFrame(columns=["open", "high", "low", "close", "volume"])

    factor_class = get_factor_class("momentum_8h")
    factor = factor_class(window=2)
    result = factor.calculate(df)

    assert isinstance(result, pd.Series)
    assert len(result) == 0


def test_factor_with_missing_columns():
    """测试缺失必需列的数据框"""
    # 缺少 volume 列
    df = pd.DataFrame({
        "open": [100, 101, 102],
        "high": [101, 102, 103],
        "low": [99, 100, 101],
        "close": [100, 101, 102],
    })

    factor_class = get_factor_class("volume_surge")
    factor = factor_class(window=2)

    # 应该抛出 KeyError
    with pytest.raises(KeyError):
        factor.calculate(df)


def test_factor_with_invalid_window_parameter():
    """测试无效的窗口参数"""
    factor_class = get_factor_class("momentum_8h")

    # 测试负数窗口
    with pytest.raises(ValueError, match="window 必须大于0"):
        factor_class(window=-1)

    # 测试零窗口
    with pytest.raises(ValueError, match="window 必须大于0"):
        factor_class(window=0)


def test_volatility_factor_invalid_window():
    """测试波动率因子的窗口参数验证"""
    factor_class = get_factor_class("volatility_24h")

    # 波动率因子要求 window > 1
    with pytest.raises(ValueError, match="window 必须大于1"):
        factor_class(window=1)

    with pytest.raises(ValueError, match="window 必须大于1"):
        factor_class(window=0)


def test_volume_surge_factor_invalid_parameters():
    """测试成交量激增因子的参数验证"""
    factor_class = get_factor_class("volume_surge")

    # 测试无效的 threshold
    with pytest.raises(ValueError, match="threshold 必须大于0"):
        factor_class(window=10, threshold=-1.0)

    with pytest.raises(ValueError, match="threshold 必须大于0"):
        factor_class(window=10, threshold=0.0)


# ==================== FactorLibrary 错误处理测试 ====================


def test_factor_library_get_nonexistent_factor():
    """测试获取不存在的因子"""
    factor_lib = FactorLibrary()

    with pytest.raises(ValueError, match="因子 'nonexistent_factor' 未注册"):
        factor_lib.get_factor("nonexistent_factor")


def test_factor_library_calculate_with_invalid_factor():
    """测试计算不存在的因子时的错误处理"""
    df = pd.DataFrame({
        "open": [100, 101, 102],
        "high": [101, 102, 103],
        "low": [99, 100, 101],
        "close": [100, 101, 102],
        "volume": [1000, 1100, 1200],
    })

    factor_lib = FactorLibrary()
    # calculate_factors 会捕获异常并将结果设为 None
    result = factor_lib.calculate_factors(df, ["nonexistent_factor"])

    assert isinstance(result, pd.DataFrame)
    assert "nonexistent_factor" in result.columns
    assert result["nonexistent_factor"].isna().all()


# ==================== 具体因子测试 ====================


@pytest.mark.parametrize("factor_name,expected_category", [
    ("sma_20", "technical"),
    ("ema_20", "technical"),
    ("rsi_14", "technical"),
    ("macd_12_26_9", "technical"),
    ("atr_14", "technical"),
    ("bb_width_20", "technical"),
    ("obv", "volume"),
    ("cmf_20", "volume"),
    ("vwap_20", "volume"),
])
def test_factor_categories(factor_name, expected_category):
    """测试因子类别分类"""
    factor_class = get_factor_class(factor_name)
    assert factor_class is not None
    factor = factor_class()
    assert factor.category == expected_category


@pytest.mark.parametrize("factor_name", [
    "sma_20",
    "ema_20",
    "rsi_14",
    "macd_12_26_9",
    "atr_14",
    "bb_width_20",
    "obv",
    "cmf_20",
    "vwap_20",
    "roc_12",
    "williams_r_14",
])
def test_factor_calculation_returns_series(factor_name):
    """测试因子计算返回正确的 Series 类型"""
    # 创建足够长的测试数据
    df = pd.DataFrame({
        "open": list(range(100, 150)),
        "high": list(range(101, 151)),
        "low": list(range(99, 149)),
        "close": list(range(100, 150)),
        "volume": list(range(1000, 1050)),
    })

    factor_class = get_factor_class(factor_name)
    factor = factor_class()
    result = factor.calculate(df)

    assert isinstance(result, pd.Series)
    assert len(result) == len(df)


def test_ma_crossover_factor_validation():
    """测试均线交叉因子的参数验证"""
    factor_class = get_factor_class("ma_cross_5_20")

    # fast_window 必须小于 slow_window
    with pytest.raises(ValueError, match="fast_window 必须小于 slow_window"):
        factor_class(fast_window=20, slow_window=5)

    with pytest.raises(ValueError, match="fast_window 必须小于 slow_window"):
        factor_class(fast_window=10, slow_window=10)


def test_bollinger_band_factors():
    """测试布林带相关因子"""
    df = pd.DataFrame({
        "open": list(range(100, 150)),
        "high": list(range(101, 151)),
        "low": list(range(99, 149)),
        "close": list(range(100, 150)),
        "volume": list(range(1000, 1050)),
    })

    # 测试布林带宽度
    bb_width_class = get_factor_class("bb_width_20")
    bb_width = bb_width_class()
    result_width = bb_width.calculate(df)
    assert isinstance(result_width, pd.Series)
    assert len(result_width) == len(df)

    # 测试布林带位置
    bb_pos_class = get_factor_class("bb_position_20")
    bb_pos = bb_pos_class()
    result_pos = bb_pos.calculate(df)
    assert isinstance(result_pos, pd.Series)
    assert len(result_pos) == len(df)


def test_factor_repr():
    """测试因子的字符串表示"""
    factor_class = get_factor_class("momentum_8h")
    factor = factor_class(window=96)
    repr_str = repr(factor)
    assert "MomentumFactor" in repr_str
    assert "window=96" in repr_str

