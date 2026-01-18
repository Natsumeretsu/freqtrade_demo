"""并行化因子计算性能基准测试

对比串行与并行计算的性能差异。
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "03_integration"))

from trading_system.infrastructure.factor_engines.parallel_computer import (
    ParallelConfig,
    ParallelFactorComputer,
)


def mock_compute_func(data: pd.DataFrame, factor_name: str) -> pd.Series:
    """模拟因子计算（带延迟）"""
    time.sleep(0.05)  # 模拟计算延迟

    if "ema" in factor_name:
        period = int(factor_name.split("_")[-1])
        return data["close"].ewm(span=period, adjust=False).mean()
    elif "ret" in factor_name:
        period = int(factor_name.split("_")[-1])
        return data["close"].pct_change(period)
    else:
        return pd.Series(index=data.index, dtype=float)


def run_benchmark():
    """运行性能基准测试"""
    print("=" * 60)
    print("并行化因子计算性能基准测试")
    print("=" * 60)

    # 准备测试数据
    np.random.seed(42)
    dates = pd.date_range("2024-01-01", periods=500, freq="1h")
    data = pd.DataFrame({
        "close": 100 + np.cumsum(np.random.randn(500) * 0.5),
        "high": 101 + np.cumsum(np.random.randn(500) * 0.5),
        "low": 99 + np.cumsum(np.random.randn(500) * 0.5),
        "volume": np.random.randint(1000, 10000, 500),
    }, index=dates)

    # 因子列表（10 个因子）
    factor_names = [
        "ema_10", "ema_20", "ema_30", "ema_50", "ema_100",
        "ret_1", "ret_5", "ret_10", "ret_20", "ret_30",
    ]

    print(f"\n数据规模: {len(data)} 行")
    print(f"因子数量: {len(factor_names)} 个")
    print(f"因子列表: {', '.join(factor_names)}")

    # 测试 1: 串行计算
    print("\n" + "-" * 60)
    print("测试 1: 串行计算")
    print("-" * 60)
    config_serial = ParallelConfig(enabled=False)
    computer_serial = ParallelFactorComputer(config_serial)

    start_time = time.time()
    results_serial = computer_serial.compute_parallel(data, factor_names, mock_compute_func)
    serial_time = time.time() - start_time

    print(f"串行计算耗时: {serial_time:.2f} 秒")
    print(f"计算结果数量: {len(results_serial)} 个因子")

    # 测试 2: 多进程并行计算
    print("\n" + "-" * 60)
    print("测试 2: 多进程并行计算")
    print("-" * 60)
    config_parallel = ParallelConfig(
        enabled=True,
        use_processes=True,
        max_workers=4,
        min_factors_for_parallel=3,
    )
    computer_parallel = ParallelFactorComputer(config_parallel)

    start_time = time.time()
    results_parallel = computer_parallel.compute_parallel(data, factor_names, mock_compute_func)
    parallel_time = time.time() - start_time

    print(f"并行计算耗时: {parallel_time:.2f} 秒")
    print(f"计算结果数量: {len(results_parallel)} 个因子")

    # 性能对比
    print("\n" + "=" * 60)
    print("性能对比")
    print("=" * 60)
    speedup = serial_time / parallel_time if parallel_time > 0 else 0
    print(f"串行耗时: {serial_time:.2f} 秒")
    print(f"并行耗时: {parallel_time:.2f} 秒")
    print(f"加速比: {speedup:.2f}x")
    print(f"性能提升: {(speedup - 1) * 100:.1f}%")

    # 验证结果一致性
    print("\n" + "-" * 60)
    print("结果一致性验证")
    print("-" * 60)
    all_match = True
    for factor_name in factor_names:
        if factor_name in results_serial and factor_name in results_parallel:
            serial_val = results_serial[factor_name]
            parallel_val = results_parallel[factor_name]
            if not serial_val.equals(parallel_val):
                all_match = False
                print(f"⚠️ 因子 {factor_name} 结果不一致")

    if all_match:
        print("✅ 所有因子结果一致")
    else:
        print("❌ 部分因子结果不一致")

    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)


if __name__ == "__main__":
    run_benchmark()
