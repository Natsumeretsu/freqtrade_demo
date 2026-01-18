"""因子计算器性能分析脚本

使用 cProfile 分析所有因子计算器的性能，识别瓶颈。

创建日期: 2026-01-17
"""

import sys
import os
import cProfile
import pstats
import io
from pstats import SortKey
import time
import numpy as np
import pandas as pd

# 添加项目路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(project_root, '03_integration'))

from trading_system.infrastructure.factor_engines.talib_engine import TalibFactorEngine


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


def profile_factor_group(engine, data, factor_names, group_name):
    """分析一组因子的性能"""
    print(f"\n{'='*60}")
    print(f"分析因子组: {group_name}")
    print(f"因子数量: {len(factor_names)}")
    print(f"{'='*60}")

    # 创建 profiler
    profiler = cProfile.Profile()

    # 开始性能分析
    profiler.enable()
    start_time = time.time()

    result = engine.compute(data, factor_names)

    elapsed = time.time() - start_time
    profiler.disable()

    # 输出统计信息
    print(f"\n总耗时: {elapsed:.4f}s")
    print(f"平均每因子: {elapsed/len(factor_names):.4f}s")
    print(f"计算结果: {len(result)} 行 x {len(result.columns)} 列")

    # 输出性能分析报告
    s = io.StringIO()
    ps = pstats.Stats(profiler, stream=s).sort_stats(SortKey.CUMULATIVE)
    ps.print_stats(20)  # 只显示前 20 个最耗时的函数

    print("\n性能分析报告 (前 20 个最耗时函数):")
    print(s.getvalue())

    return elapsed, result


def main():
    """主函数"""
    print("="*60)
    print("因子计算器性能分析")
    print("="*60)

    # 生成测试数据
    print("\n生成测试数据...")
    data = generate_test_data(5000)
    print(f"数据规模: {len(data)} 行")

    # 初始化引擎（禁用缓存和并行计算，以便准确测量）
    from trading_system.infrastructure.factor_engines.factor_cache import FactorCache
    from trading_system.infrastructure.factor_engines.parallel_computer import ParallelConfig

    cache = FactorCache(max_size=0)  # 禁用缓存
    parallel_config = ParallelConfig(enabled=False)  # 禁用并行计算
    engine = TalibFactorEngine(cache=cache, parallel_config=parallel_config)

    print("引擎配置: 缓存=禁用, 并行计算=禁用")

    # 定义因子分组
    factor_groups = {
        "EMA因子": ['ema_short_10', 'ema_long_50', 'ema_short_20'],
        "动量因子": ['rsi_14', 'cci_14', 'roc_10', 'willr_14'],
        "波动率因子": ['atr_14', 'bb_width_20_2', 'vol_20'],
        "趋势因子": ['adx_14', 'macd', 'macdsignal', 'macdhist'],
        "成交量因子": ['volume_ratio_72', 'volume_z_20', 'mfi_14'],
        "统计因子": ['ret_5', 'skew_20', 'kurt_20'],
        "布林带因子": ['bb_width_20_2', 'bb_percent_b_20_2'],
        "随机指标": ['stoch_k_14_3_3', 'stoch_d_14_3_3'],
    }

    # 性能结果汇总
    results = {}

    # 逐组分析
    for group_name, factor_names in factor_groups.items():
        elapsed, result = profile_factor_group(engine, data, factor_names, group_name)
        results[group_name] = {
            'elapsed': elapsed,
            'count': len(factor_names),
            'avg_time': elapsed / len(factor_names)
        }

    # 输出性能汇总
    print("\n" + "="*60)
    print("性能汇总报告")
    print("="*60)

    # 按平均耗时排序
    sorted_results = sorted(results.items(), key=lambda x: x[1]['avg_time'], reverse=True)

    print(f"\n{'因子组':<15} {'因子数':<8} {'总耗时(s)':<12} {'平均耗时(s)':<12}")
    print("-" * 60)
    for group_name, stats in sorted_results:
        print(f"{group_name:<15} {stats['count']:<8} {stats['elapsed']:<12.4f} {stats['avg_time']:<12.4f}")

    # 识别最慢的因子组
    slowest_group = sorted_results[0]
    print(f"\n[WARNING] 最慢的因子组: {slowest_group[0]}")
    print(f"   平均耗时: {slowest_group[1]['avg_time']:.4f}s")
    print(f"   优化建议: 考虑向量化优化或使用更高效的算法")

    print("\n" + "="*60)
    print("分析完成")
    print("="*60)


if __name__ == "__main__":
    main()
