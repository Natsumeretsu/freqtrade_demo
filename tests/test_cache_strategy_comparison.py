"""测试 LRU vs ARC 缓存策略对比

对比 LRU 和 ARC 两种缓存策略的命中率和性能。

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

from trading_system.infrastructure.factor_engines.factor_cache import FactorCache, FactorCacheKey


def generate_test_data(rows=1000):
    """生成测试数据"""
    np.random.seed(42)
    dates = pd.date_range('2024-01-01', periods=rows, freq='1h')

    data = pd.DataFrame({
        'date': dates,
        'close': 100 + np.random.randn(rows).cumsum(),
    })

    return data.set_index('date')


def test_uniform_access_pattern():
    """测试均匀访问模式下的缓存命中率"""
    print("\n=== 测试均匀访问模式 ===")

    # 创建 LRU 和 ARC 缓存
    lru_cache = FactorCache(max_size=50, strategy="lru")
    arc_cache = FactorCache(max_size=50, strategy="arc")

    # 创建 100 个不同的键（缓存容量为 50）
    keys = [
        FactorCacheKey("BTC/USDT", "1h", f"factor_{i}", 1000)
        for i in range(100)
    ]
    values = [pd.Series([float(i)]) for i in range(100)]

    # 均匀访问模式：随机访问所有键
    np.random.seed(42)
    access_sequence = np.random.choice(100, size=500, replace=True)

    # 测试 LRU
    for idx in access_sequence:
        result = lru_cache.get(keys[idx])
        if result is None:
            lru_cache.set(keys[idx], values[idx])

    # 测试 ARC
    for idx in access_sequence:
        result = arc_cache.get(keys[idx])
        if result is None:
            arc_cache.set(keys[idx], values[idx])

    # 输出结果
    lru_stats = lru_cache.get_stats()
    arc_stats = arc_cache.get_stats()

    print(f"\n[LRU] 命中率: {lru_stats['hit_rate']:.2%}")
    print(f"  命中: {lru_stats['hits']}, 未命中: {lru_stats['misses']}")
    print(f"  缓存大小: {lru_stats['cache_size']}/{lru_stats['max_size']}")

    print(f"\n[ARC] 命中率: {arc_stats['hit_rate']:.2%}")
    print(f"  命中: {arc_stats['hits']}, 未命中: {arc_stats['misses']}")
    print(f"  缓存大小: {arc_stats['cache_size']}/{arc_stats['max_size']}")
    print(f"  T1: {arc_stats['t1_size']}, T2: {arc_stats['t2_size']}, p: {arc_stats['p']}")

    improvement = (arc_stats['hit_rate'] - lru_stats['hit_rate']) / lru_stats['hit_rate'] * 100
    print(f"\n[结果] ARC 提升: {improvement:+.1f}%")

    print("[PASS] 均匀访问模式测试完成")


def test_skewed_access_pattern():
    """测试偏斜访问模式下的缓存命中率（80/20 规则）"""
    print("\n=== 测试偏斜访问模式 ===")

    # 创建 LRU 和 ARC 缓存
    lru_cache = FactorCache(max_size=50, strategy="lru")
    arc_cache = FactorCache(max_size=50, strategy="arc")

    # 创建 100 个不同的键
    keys = [
        FactorCacheKey("BTC/USDT", "1h", f"factor_{i}", 1000)
        for i in range(100)
    ]
    values = [pd.Series([float(i)]) for i in range(100)]

    # 偏斜访问模式：80% 的访问集中在 20% 的键上
    np.random.seed(42)
    hot_keys = 20  # 热点键数量
    access_sequence = []
    for _ in range(500):
        if np.random.random() < 0.8:
            # 80% 的访问集中在前 20 个键
            access_sequence.append(np.random.randint(0, hot_keys))
        else:
            # 20% 的访问分散在其他键
            access_sequence.append(np.random.randint(hot_keys, 100))

    # 测试 LRU
    for idx in access_sequence:
        result = lru_cache.get(keys[idx])
        if result is None:
            lru_cache.set(keys[idx], values[idx])

    # 测试 ARC
    for idx in access_sequence:
        result = arc_cache.get(keys[idx])
        if result is None:
            arc_cache.set(keys[idx], values[idx])

    # 输出结果
    lru_stats = lru_cache.get_stats()
    arc_stats = arc_cache.get_stats()

    print(f"\n[LRU] 命中率: {lru_stats['hit_rate']:.2%}")
    print(f"  命中: {lru_stats['hits']}, 未命中: {lru_stats['misses']}")

    print(f"\n[ARC] 命中率: {arc_stats['hit_rate']:.2%}")
    print(f"  命中: {arc_stats['hits']}, 未命中: {arc_stats['misses']}")
    print(f"  T1: {arc_stats['t1_size']}, T2: {arc_stats['t2_size']}, p: {arc_stats['p']}")

    improvement = (arc_stats['hit_rate'] - lru_stats['hit_rate']) / lru_stats['hit_rate'] * 100
    print(f"\n[结果] ARC 提升: {improvement:+.1f}%")

    print("[PASS] 偏斜访问模式测试完成")


if __name__ == "__main__":
    print("="*60)
    print("开始测试 LRU vs ARC 缓存策略对比")
    print("="*60)

    try:
        test_uniform_access_pattern()
        test_skewed_access_pattern()

        print("\n" + "="*60)
        print("[SUCCESS] 所有测试完成！")
        print("="*60)
    except Exception as e:
        print(f"\n[ERROR] 测试失败: {e}")
        import traceback
        traceback.print_exc()
