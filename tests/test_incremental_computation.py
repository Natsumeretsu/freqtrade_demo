"""测试增量计算引擎

验证增量计算的正确性和性能提升。

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

from trading_system.infrastructure.factor_engines.incremental_engine import (
    StateManager,
    IncrementalComputer,
    FactorState
)


def generate_test_data(rows=1000):
    """生成测试数据"""
    np.random.seed(42)
    dates = pd.date_range('2024-01-01', periods=rows, freq='1h')

    data = pd.DataFrame({
        'date': dates,
        'close': 100 + np.random.randn(rows).cumsum(),
    })

    return data.set_index('date')


def test_ema_incremental():
    """测试 EMA 增量计算"""
    print("\n=== 测试 EMA 增量计算 ===")

    # 生成测试数据
    data = generate_test_data(100)
    close_prices = data['close'].values

    # 初始化增量计算器
    state_manager = StateManager()
    computer = IncrementalComputer(state_manager)

    # 增量计算 EMA
    period = 10
    ema_incremental = []

    for price in close_prices:
        ema_value = computer.update_ema('ema_10', price, period)
        ema_incremental.append(ema_value)

    # 使用 Pandas 计算标准 EMA
    ema_standard = data['close'].ewm(span=period, adjust=False).mean().values

    # 验证结果
    diff = np.abs(np.array(ema_incremental) - ema_standard).max()
    print(f"最大差异: {diff:.10f}")

    assert diff < 1e-6, f"EMA 增量计算误差过大: {diff}"
    print("[PASS] EMA 增量计算测试通过")


def test_sma_incremental():
    """测试 SMA 增量计算"""
    print("\n=== 测试 SMA 增量计算 ===")

    # 生成测试数据
    data = generate_test_data(100)
    close_prices = data['close'].values

    # 初始化增量计算器
    state_manager = StateManager()
    computer = IncrementalComputer(state_manager)

    # 增量计算 SMA
    period = 20
    sma_incremental = []

    for price in close_prices:
        sma_value = computer.update_sma('sma_20', price, period)
        sma_incremental.append(sma_value)

    # 使用 Pandas 计算标准 SMA
    sma_standard = data['close'].rolling(period).mean().values

    # 验证结果（跳过前 period-1 个 NaN 值）
    diff = np.abs(np.array(sma_incremental[period-1:]) - sma_standard[period-1:]).max()
    print(f"最大差异: {diff:.10f}")

    assert diff < 1e-6, f"SMA 增量计算误差过大: {diff}"
    print("[PASS] SMA 增量计算测试通过")


def test_performance():
    """测试增量计算性能"""
    print("\n=== 测试增量计算性能 ===")

    # 生成大规模测试数据
    data = generate_test_data(5000)
    close_prices = data['close'].values

    period = 20

    # 测试 1: 增量计算
    print("\n[1] 增量计算:")
    state_manager = StateManager()
    computer = IncrementalComputer(state_manager)

    start = time.time()
    for price in close_prices:
        computer.update_ema('ema_20', price, period)
    time_incremental = time.time() - start
    print(f"  耗时: {time_incremental:.6f}s")

    # 测试 2: 全量计算（模拟传统方式）
    print("\n[2] 全量计算:")
    start = time.time()
    for i in range(len(close_prices)):
        data['close'][:i+1].ewm(span=period, adjust=False).mean()
    time_full = time.time() - start
    print(f"  耗时: {time_full:.6f}s")

    # 性能对比
    speedup = time_full / time_incremental if time_incremental > 0 else float('inf')
    print(f"\n[结果] 性能提升: {speedup:.2f}x")
    print(f"  增量计算: {time_incremental:.6f}s")
    print(f"  全量计算: {time_full:.6f}s")

    assert speedup > 10, f"增量计算性能提升不足: {speedup:.2f}x"
    print("[PASS] 性能测试通过")


if __name__ == "__main__":
    print("="*60)
    print("开始测试增量计算引擎")
    print("="*60)

    try:
        test_ema_incremental()
        test_sma_incremental()
        test_performance()

        print("\n" + "="*60)
        print("[SUCCESS] 所有测试通过！")
        print("="*60)
    except Exception as e:
        print(f"\n[ERROR] 测试失败: {e}")
        import traceback
        traceback.print_exc()
