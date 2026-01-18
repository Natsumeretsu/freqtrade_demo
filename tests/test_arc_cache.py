"""测试 ARC 智能缓存淘汰策略

验证 ARC 算法的正确性和性能提升。

创建日期: 2026-01-17
"""

import sys
import os
import time
import numpy as np
import pandas as pd

# 添加项目路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(project_root, '03_integration'))

from trading_system.infrastructure.factor_engines.arc_cache import ARCCache, CacheEntry
from trading_system.infrastructure.factor_engines.factor_cache import FactorCacheKey


def generate_test_data(rows=100):
    """生成测试数据"""
    np.random.seed(42)
    dates = pd.date_range('2024-01-01', periods=rows, freq='1h')

    data = pd.DataFrame({
        'date': dates,
        'close': 100 + np.random.randn(rows).cumsum(),
    })

    return data.set_index('date')


def test_arc_basic_operations():
    """测试 ARC 缓存基础操作"""
    print("\n=== 测试 ARC 缓存基础操作 ===")

    # 初始化缓存
    cache = ARCCache(capacity=3)

    # 创建测试键
    key1 = FactorCacheKey("BTC/USDT", "1h", "ema_10", 1000)
    key2 = FactorCacheKey("BTC/USDT", "1h", "sma_20", 1000)
    key3 = FactorCacheKey("BTC/USDT", "1h", "rsi_14", 1000)

    # 创建测试值
    value1 = pd.Series([1.0, 2.0, 3.0])
    value2 = pd.Series([4.0, 5.0, 6.0])
    value3 = pd.Series([7.0, 8.0, 9.0])

    # 测试 set 和 get
    cache.set(key1, value1)
    cache.set(key2, value2)
    cache.set(key3, value3)

    assert cache.get(key1) is not None, "key1 应该在缓存中"
    assert cache.get(key2) is not None, "key2 应该在缓存中"
    assert cache.get(key3) is not None, "key3 应该在缓存中"

    print(f"  缓存大小: {len(cache)}")
    print(f"  T1 大小: {len(cache.t1)}")
    print(f"  T2 大小: {len(cache.t2)}")
    print("[PASS] 基础操作测试通过")


def test_arc_eviction():
    """测试 ARC 缓存淘汰策略"""
    print("\n=== 测试 ARC 缓存淘汰策略 ===")

    # 初始化缓存（容量为 3）
    cache = ARCCache(capacity=3)

    # 创建 4 个键
    keys = [
        FactorCacheKey("BTC/USDT", "1h", f"factor_{i}", 1000)
        for i in range(4)
    ]
    values = [pd.Series([float(i)]) for i in range(4)]

    # 添加前 3 个（填满缓存）
    for i in range(3):
        cache.set(keys[i], values[i])

    print(f"  添加 3 个项后，缓存大小: {len(cache)}")

    # 添加第 4 个（触发淘汰）
    cache.set(keys[3], values[3])

    print(f"  添加第 4 个项后，缓存大小: {len(cache)}")
    assert len(cache) == 3, "缓存大小应该保持为 3"

    print("[PASS] 淘汰策略测试通过")


def test_arc_frequent_access():
    """测试 ARC 频繁访问（T1 -> T2 迁移）"""
    print("\n=== 测试 ARC 频繁访问 ===")

    cache = ARCCache(capacity=5)

    # 创建测试键
    key1 = FactorCacheKey("BTC/USDT", "1h", "ema_10", 1000)
    value1 = pd.Series([1.0, 2.0, 3.0])

    # 第一次访问（放入 T1）
    cache.set(key1, value1)
    print(f"  第一次访问后 - T1: {len(cache.t1)}, T2: {len(cache.t2)}")
    assert key1 in cache.t1, "第一次访问应该在 T1 中"

    # 第二次访问（移动到 T2）
    result = cache.get(key1)
    print(f"  第二次访问后 - T1: {len(cache.t1)}, T2: {len(cache.t2)}")
    assert result is not None, "应该命中缓存"
    assert key1 in cache.t2, "第二次访问应该移动到 T2"
    assert key1 not in cache.t1, "应该从 T1 中移除"

    print("[PASS] 频繁访问测试通过")


def test_arc_hit_rate():
    """测试 ARC 缓存命中率"""
    print("\n=== 测试 ARC 缓存命中率 ===")

    cache = ARCCache(capacity=10)

    # 创建 10 个键
    keys = [
        FactorCacheKey("BTC/USDT", "1h", f"factor_{i}", 1000)
        for i in range(10)
    ]
    values = [pd.Series([float(i)]) for i in range(10)]

    # 填充缓存
    for i in range(10):
        cache.set(keys[i], values[i])

    # 访问前 5 个键（应该全部命中）
    for i in range(5):
        result = cache.get(keys[i])
        assert result is not None, f"key {i} 应该命中"

    print(f"  命中次数: {cache._hits}")
    print(f"  未命中次数: {cache._misses}")
    print(f"  命中率: {cache.hit_rate():.2%}")

    assert cache._hits == 5, "应该有 5 次命中"
    assert cache.hit_rate() > 0, "命中率应该大于 0"

    print("[PASS] 命中率测试通过")


if __name__ == "__main__":
    print("="*60)
    print("开始测试 ARC 智能缓存淘汰策略")
    print("="*60)

    try:
        test_arc_basic_operations()
        test_arc_eviction()
        test_arc_frequent_access()
        test_arc_hit_rate()

        print("\n" + "="*60)
        print("[SUCCESS] 所有测试通过！")
        print("="*60)
    except Exception as e:
        print(f"\n[ERROR] 测试失败: {e}")
        import traceback
        traceback.print_exc()
