"""测试缓存预热功能"""
import sys
import os
import time
import tempfile
import numpy as np
import pandas as pd

# 添加项目路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(project_root, '03_integration'))

from trading_system.infrastructure.factor_engines.factor_cache import FactorCache
from trading_system.infrastructure.factor_engines.talib_engine import TalibFactorEngine


def generate_test_data(rows=1000):
    """生成测试数据"""
    np.random.seed(42)
    dates = pd.date_range('2024-01-01', periods=rows, freq='1h')

    data = pd.DataFrame({
        'date': dates,
        'open': 100 + np.random.randn(rows).cumsum(),
        'high': 102 + np.random.randn(rows).cumsum(),
        'low': 98 + np.random.randn(rows).cumsum(),
        'close': 100 + np.random.randn(rows).cumsum(),
        'volume': np.random.randint(1000, 10000, rows),
    })

    data['high'] = data[['open', 'high', 'close']].max(axis=1)
    data['low'] = data[['open', 'low', 'close']].min(axis=1)

    return data.set_index('date')


def test_cache_warmup():
    """测试缓存预热功能"""
    print("\n=== 测试缓存预热功能 ===")

    # 创建测试数据
    data = generate_test_data(1000)

    # 初始化引擎和缓存
    cache = FactorCache(max_size=1000)
    engine = TalibFactorEngine(cache=cache)
    engine.set_context(pair='BTC/USDT', timeframe='1h')

    factor_names = ['ema_short_10', 'rsi_14', 'bb_width_20_2']

    # 测试预热前的性能
    print("\n[1] 预热前测试:")
    start = time.time()
    result1 = engine.compute(data, factor_names)
    time_before = time.time() - start
    print(f"  计算时间: {time_before:.4f}s")
    print(f"  缓存大小: {len(cache)}")

    # 清空缓存
    cache.clear()

    # 执行缓存预热
    print("\n[2] 执行缓存预热:")
    start = time.time()
    cache.warmup(data, factor_names, engine._compute_single_factor, 'BTC/USDT', '1h')
    warmup_time = time.time() - start
    print(f"  预热时间: {warmup_time:.4f}s")
    print(f"  缓存大小: {len(cache)}")

    # 测试预热后的性能
    print("\n[3] 预热后测试:")
    start = time.time()
    result2 = engine.compute(data, factor_names)
    time_after = time.time() - start
    print(f"  计算时间: {time_after:.4f}s")

    speedup = time_before / time_after if time_after > 0 else float('inf')
    print(f"\n[结果] 加速比: {speedup:.2f}x")

    assert len(cache) > 0, "缓存预热失败"
    print("[PASS] 缓存预热测试通过")


def test_cache_persistence():
    """测试缓存持久化"""
    print("\n=== 测试缓存持久化 ===")

    data = generate_test_data(500)

    # 创建临时文件
    with tempfile.NamedTemporaryFile(delete=False, suffix='.pkl') as f:
        cache_file = f.name

    try:
        # 创建并预热缓存
        cache1 = FactorCache(max_size=1000)
        engine = TalibFactorEngine(cache=cache1)
        engine.set_context(pair='BTC/USDT', timeframe='1h')

        factor_names = ['ema_short_10', 'rsi_14']
        cache1.warmup(data, factor_names, engine._compute_single_factor, 'BTC/USDT', '1h')

        print(f"[1] 原始缓存大小: {len(cache1)}")

        # 保存到磁盘
        cache1.save_to_disk(cache_file)
        print(f"[2] 缓存已保存到: {cache_file}")

        # 从磁盘加载
        cache2 = FactorCache(max_size=1000)
        success = cache2.load_from_disk(cache_file)
        print(f"[3] 加载成功: {success}")
        print(f"[4] 加载后缓存大小: {len(cache2)}")

        assert success, "缓存加载失败"
        assert len(cache2) == len(cache1), "缓存大小不匹配"
        print("[PASS] 缓存持久化测试通过")

    finally:
        # 清理临时文件
        if os.path.exists(cache_file):
            os.remove(cache_file)


if __name__ == "__main__":
    print("=" * 60)
    print("开始测试缓存预热功能")
    print("=" * 60)

    try:
        test_cache_warmup()
        test_cache_persistence()

        print("\n" + "=" * 60)
        print("[SUCCESS] 所有测试通过！")
        print("=" * 60)
    except Exception as e:
        print(f"\n[ERROR] 测试失败: {e}")
        import traceback
        traceback.print_exc()
