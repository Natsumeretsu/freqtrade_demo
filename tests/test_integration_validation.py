"""
集成验证测试脚本

测试所有优化功能的集成效果：
- P0.1: 因子缓存
- P2.1: 并行计算
- P2.2: 数据预加载
- P2.3: 内存优化

创建日期: 2026-01-17
"""

import sys
import os
import time
import numpy as np
import pandas as pd

# 添加项目路径到 sys.path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(project_root, '03_integration'))

from trading_system.infrastructure.factor_engines.talib_engine import (
    TalibFactorEngine,
    TalibEngineParams,
)
from trading_system.infrastructure.factor_engines.factor_cache import FactorCache
from trading_system.infrastructure.factor_engines.parallel_computer import ParallelConfig
from trading_system.infrastructure.data_preloader import PreloadConfig, DataPreloader
from trading_system.infrastructure.memory_optimizer import MemoryConfig, MemoryOptimizer


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

    # 确保 high >= close >= low
    data['high'] = data[['open', 'high', 'close']].max(axis=1)
    data['low'] = data[['open', 'low', 'close']].min(axis=1)

    return data.set_index('date')


class TestIntegrationValidation:
    """集成验证测试类"""

    def test_factor_cache_integration(self):
        """测试因子缓存集成"""
        print("\n=== 测试 P0.1: 因子缓存集成 ===")

        # 创建测试数据
        data = generate_test_data(1000)

        # 初始化带缓存的引擎
        cache = FactorCache(max_size=1000)
        engine = TalibFactorEngine(cache=cache)

        # 设置上下文（用于缓存键生成）
        engine.set_context(pair='BTC/USDT', timeframe='1h')

        factor_names = ['ema_short_10', 'rsi_14', 'bb_width_20_2']

        # 第一次计算（应该缓存未命中）
        start = time.time()
        result1 = engine.compute(data, factor_names)
        time1 = time.time() - start

        # 第二次计算（应该缓存命中）
        start = time.time()
        result2 = engine.compute(data, factor_names)
        time2 = time.time() - start

        # 验证结果
        cache_stats = cache.get_stats()
        print(f"[OK] 缓存命中率: {cache_stats['hit_rate']:.2%}")
        print(f"[OK] 缓存大小: {cache_stats['cache_size']}/{cache_stats['max_size']}")
        print(f"[OK] 第一次计算: {time1:.3f}s")

        # 避免除零错误
        speedup = time1 / time2 if time2 > 0.0001 else float('inf')
        print(f"[OK] 第二次计算: {time2:.3f}s (加速 {speedup:.2f}x)")

        assert cache_stats['hit_rate'] > 0.3, "缓存命中率过低"
        assert cache_stats['cache_size'] > 0, "缓存未生效"
        assert not result1.empty, "计算结果为空"

        print("[PASS] 因子缓存集成测试通过")

    def test_parallel_computing_integration(self):
        """测试并行计算集成"""
        print("\n=== 测试 P2.1: 并行计算集成 ===")

        # 创建测试数据
        data = generate_test_data(1000)

        factor_names = [
            'ema_short_10', 'ema_long_50', 'rsi_14', 'cci_14',
            'bb_width_20_2', 'adx_14', 'atr_14', 'volume_ratio_72'
        ]

        # 串行计算
        config_serial = ParallelConfig(enabled=False)
        engine_serial = TalibFactorEngine(parallel_config=config_serial)

        start = time.time()
        result_serial = engine_serial.compute(data, factor_names)
        time_serial = time.time() - start

        # 并行计算
        config_parallel = ParallelConfig(enabled=True, max_workers=4)
        engine_parallel = TalibFactorEngine(parallel_config=config_parallel)

        start = time.time()
        result_parallel = engine_parallel.compute(data, factor_names)
        time_parallel = time.time() - start

        # 验证结果
        speedup = time_serial / time_parallel if time_parallel > 0 else 1.0
        print(f"[OK] 串行计算: {time_serial:.3f}s")
        print(f"[OK] 并行计算: {time_parallel:.3f}s")
        print(f"[OK] 加速比: {speedup:.2f}x")

        assert not result_parallel.empty, "并行计算结果为空"
        assert len(result_parallel.columns) == len(factor_names), "因子数量不匹配"

        print("[PASS] 并行计算集成测试通过")

    def test_memory_optimization_integration(self):
        """测试内存优化集成"""
        print("\n=== 测试 P2.3: 内存优化集成 ===")

        # 创建测试数据
        data = generate_test_data(5000)

        # 优化前
        memory_before = data.memory_usage(deep=True).sum() / 1024**2

        # 应用内存优化
        memory_config = MemoryConfig(
            enabled=True,
            downcast_numeric=True,
            use_categorical=True,
        )
        optimizer = MemoryOptimizer(memory_config)
        data_optimized = optimizer.optimize_dataframe(data.copy())

        # 优化后
        memory_after = data_optimized.memory_usage(deep=True).sum() / 1024**2

        # 验证结果
        reduction = (1 - memory_after / memory_before) * 100
        print(f"[OK] 优化前内存: {memory_before:.2f}MB")
        print(f"[OK] 优化后内存: {memory_after:.2f}MB")
        print(f"[OK] 内存减少: {reduction:.1f}%")

        assert memory_after < memory_before, "内存优化未生效"
        assert reduction > 10, "内存优化效果不明显"

        print("[PASS] 内存优化集成测试通过")

    def test_full_integration(self):
        """测试完整集成（所有优化功能）"""
        print("\n=== 测试完整集成（P0.1 + P2.1 + P2.3）===")

        # 创建测试数据
        data = generate_test_data(2000)

        # 1. 初始化所有优化组件
        cache = FactorCache(max_size=1000)
        parallel_config = ParallelConfig(enabled=True, max_workers=4)
        engine = TalibFactorEngine(cache=cache, parallel_config=parallel_config)

        # 设置上下文（用于缓存键生成）
        engine.set_context(pair='BTC/USDT', timeframe='1h')

        memory_config = MemoryConfig(enabled=True, downcast_numeric=True)
        optimizer = MemoryOptimizer(memory_config)

        # 2. 应用内存优化
        data = optimizer.optimize_dataframe(data)

        # 3. 计算因子
        factor_names = ['ema_short_10', 'rsi_14', 'bb_width_20_2', 'adx_14']

        start = time.time()
        result = engine.compute(data, factor_names)
        elapsed = time.time() - start

        # 4. 验证结果
        cache_stats = cache.get_stats()

        print(f"[OK] 因子计算完成: {len(factor_names)} 个因子")
        print(f"[OK] 计算耗时: {elapsed:.3f}s")
        print(f"[OK] 缓存命中率: {cache_stats['hit_rate']:.2%}")
        print(f"[OK] 内存使用: {data.memory_usage(deep=True).sum() / 1024**2:.2f}MB")

        assert not result.empty, "计算结果为空"
        assert len(result.columns) == len(factor_names), "因子数量不匹配"

        print("[PASS] 完整集成测试通过")


if __name__ == "__main__":
    """运行所有集成测试"""
    print("=" * 60)
    print("开始运行集成验证测试")
    print("=" * 60)

    test_suite = TestIntegrationValidation()

    try:
        # 运行各项测试
        test_suite.test_factor_cache_integration()
        test_suite.test_parallel_computing_integration()
        test_suite.test_memory_optimization_integration()
        test_suite.test_full_integration()

        print("\n" + "=" * 60)
        print("[SUCCESS] 所有集成测试通过！")
        print("=" * 60)

    except AssertionError as e:
        print(f"\n[FAIL] 测试失败: {e}")
    except Exception as e:
        print(f"\n[ERROR] 测试异常: {e}")
        import traceback
        traceback.print_exc()
