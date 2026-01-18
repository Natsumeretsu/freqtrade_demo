"""测试批量因子计算优化

对比批量计算和逐个计算的性能差异。

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

from trading_system.infrastructure.factor_engines.talib_engine import TalibFactorEngine
from trading_system.infrastructure.factor_engines.factor_cache import FactorCache
from trading_system.infrastructure.factor_engines.parallel_computer import ParallelConfig


def generate_test_data(rows=5000):
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


def test_batch_optimization():
    """测试批量计算优化效果"""
    print("\n=== 测试批量因子计算优化 ===")

    # 生成测试数据
    data = generate_test_data(5000)
    print(f"数据规模: {len(data)} 行")

    # 定义测试因子（包含可批量优化的因子）
    factor_names = [
        # EMA 因子（可批量优化）
        'ema_short_10', 'ema_short_20', 'ema_long_50',
        # 统计因子（可批量优化，共享 ret_1）
        'vol_20', 'skew_20', 'kurt_20',
        # 其他因子
        'rsi_14', 'atr_14', 'adx_14'
    ]

    # 测试 1: 不使用批量优化（禁用缓存和并行）
    print("\n[1] 不使用批量优化:")
    cache1 = FactorCache(max_size=0)
    parallel_config1 = ParallelConfig(enabled=False)
    engine1 = TalibFactorEngine(cache=cache1, parallel_config=parallel_config1)

    start = time.time()
    result1 = engine1.compute(data, factor_names)
    time1 = time.time() - start
    print(f"  计算时间: {time1:.4f}s")
    print(f"  结果: {len(result1)} 行 x {len(result1.columns)} 列")

    # 测试 2: 使用批量优化（通过批量计算器）
    print("\n[2] 使用批量优化:")
    from trading_system.infrastructure.factor_engines.batch_optimizer import BatchFactorComputer

    batch_computer = BatchFactorComputer()

    start = time.time()
    result2_dict = batch_computer.compute_batch(data, factor_names, engine1._compute_single_factor)
    result2 = pd.DataFrame(result2_dict, index=data.index)
    time2 = time.time() - start
    print(f"  计算时间: {time2:.4f}s")
    print(f"  结果: {len(result2)} 行 x {len(result2.columns)} 列")

    # 性能对比
    speedup = time1 / time2 if time2 > 0 else float('inf')
    print(f"\n[结果] 性能提升: {speedup:.2f}x")
    print(f"  优化前: {time1:.4f}s")
    print(f"  优化后: {time2:.4f}s")
    print(f"  节省时间: {(time1 - time2):.4f}s ({(1 - time2/time1)*100:.1f}%)")

    # 验证结果一致性
    print("\n[验证] 结果一致性检查:")
    for col in result1.columns:
        if col in result2.columns:
            diff = (result1[col] - result2[col]).abs().max()
            print(f"  {col}: 最大差异 = {diff:.6f}")

    assert speedup > 1.0, f"批量优化未提升性能: {speedup:.2f}x"
    print("\n[PASS] 批量计算优化测试通过")


if __name__ == "__main__":
    print("="*60)
    print("开始测试批量因子计算优化")
    print("="*60)

    try:
        test_batch_optimization()

        print("\n" + "="*60)
        print("[SUCCESS] 所有测试通过！")
        print("="*60)
    except Exception as e:
        print(f"\n[ERROR] 测试失败: {e}")
        import traceback
        traceback.print_exc()

