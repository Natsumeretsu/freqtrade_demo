"""基准测试用例集

包含各种优化项的基准测试用例。

创建日期: 2026-01-17
"""

import sys
import os
import time
from datetime import datetime

# 添加项目路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(project_root, '03_integration'))

from trading_system.infrastructure.benchmarking import BenchmarkRunner


def generate_test_data(rows=1000):
    """生成测试数据（简化版）"""
    import random
    random.seed(42)

    # 生成简单的数值列表
    data = [100 + random.random() * 10 for _ in range(rows)]
    return data


def benchmark_simple_calculation():
    """基准测试：简单计算"""
    data = generate_test_data(1000)

    # 计算简单移动平均（手动实现）
    window = 10
    result = []
    for i in range(len(data)):
        if i < window - 1:
            result.append(None)
        else:
            avg = sum(data[i-window+1:i+1]) / window
            result.append(avg)
    return result


def benchmark_batch_calculation():
    """基准测试：批量计算"""
    data = generate_test_data(1000)

    # 批量计算多个指标（手动实现）
    results = {}
    for window in [5, 10, 20, 50]:
        result = []
        for i in range(len(data)):
            if i < window - 1:
                result.append(None)
            else:
                avg = sum(data[i-window+1:i+1]) / window
                result.append(avg)
        results[f'sma_{window}'] = result

    return results


def run_all_benchmarks():
    """运行所有基准测试"""
    print("="*60)
    print("开始运行基准测试套件")
    print("="*60)

    runner = BenchmarkRunner()

    # 测试1：简单计算
    print("\n[1/2] 运行简单计算基准测试...")
    result1 = runner.run_benchmark(
        name="simple_calculation",
        func=benchmark_simple_calculation,
        repeat=5,
        warmup=2,
        operations=1000
    )
    print(result1)

    # 测试2：批量计算
    print("\n[2/2] 运行批量计算基准测试...")
    result2 = runner.run_benchmark(
        name="batch_calculation",
        func=benchmark_batch_calculation,
        repeat=5,
        warmup=2,
        operations=4000
    )
    print(result2)

    print("\n" + "="*60)
    print("[SUCCESS] 所有基准测试完成！")
    print("="*60)


if __name__ == "__main__":
    try:
        run_all_benchmarks()
    except Exception as e:
        print(f"\n[ERROR] 基准测试失败: {e}")
        import traceback
        traceback.print_exc()
