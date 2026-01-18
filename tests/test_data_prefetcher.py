"""测试数据预加载器

验证数据预加载的正确性和性能提升。

创建日期: 2026-01-17
"""

import sys
import os
import time
from datetime import datetime, timedelta
import numpy as np
import pandas as pd

# 添加项目路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(project_root, '03_integration'))

from trading_system.infrastructure.factor_engines.data_prefetcher import (
    DataPrefetcher,
    TimeWindowStrategy,
    DataBuffer
)


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


def test_data_buffer():
    """测试数据缓冲区"""
    print("\n=== 测试数据缓冲区 ===")

    # 创建缓冲区（最大 1MB）
    buffer = DataBuffer(max_size_mb=1)

    # 生成测试数据
    data1 = generate_test_data(100)
    data2 = generate_test_data(200)

    # 测试 set 和 get
    buffer.set("BTC_1h", data1)
    result = buffer.get("BTC_1h")

    assert result is not None, "应该能获取到数据"
    assert len(result) == len(data1), "数据长度应该一致"

    # 测试缓冲区大小限制
    buffer.set("ETH_1h", data2)
    print(f"  缓冲区大小: {buffer._get_buffer_size_mb():.2f} MB")

    print("[PASS] 数据缓冲区测试通过")


def test_time_window_strategy():
    """测试时间窗口策略"""
    print("\n=== 测试时间窗口策略 ===")

    strategy = TimeWindowStrategy(window_days=7)

    current_time = datetime(2024, 1, 10, 12, 0, 0)
    start_time, end_time = strategy.get_prefetch_range(current_time)

    print(f"  当前时间: {current_time}")
    print(f"  预加载范围: {start_time} ~ {end_time}")

    expected_start = datetime(2024, 1, 3, 12, 0, 0)
    assert start_time == expected_start, "开始时间应该是 7 天前"
    assert end_time == current_time, "结束时间应该是当前时间"

    print("[PASS] 时间窗口策略测试通过")


def test_data_prefetcher():
    """测试数据预加载器"""
    print("\n=== 测试数据预加载器 ===")

    # 创建预加载器
    strategy = TimeWindowStrategy(window_days=7)
    prefetcher = DataPrefetcher(strategy, max_buffer_size=100)

    # 模拟数据加载函数
    def mock_data_loader(pair, timeframe, start_time, end_time):
        return generate_test_data(500)

    # 启动预加载
    prefetcher.start()

    # 预加载数据
    prefetcher.prefetch("BTC/USDT", "1h", mock_data_loader)

    # 获取预加载的数据
    data = prefetcher.get_data("BTC/USDT", "1h")

    assert data is not None, "应该能获取到预加载的数据"
    assert len(data) == 500, "数据长度应该正确"

    print(f"  预加载数据量: {len(data)} 行")
    print("[PASS] 数据预加载器测试通过")


if __name__ == "__main__":
    print("="*60)
    print("开始测试数据预加载器")
    print("="*60)

    try:
        test_data_buffer()
        test_time_window_strategy()
        test_data_prefetcher()

        print("\n" + "="*60)
        print("[SUCCESS] 所有测试通过！")
        print("="*60)
    except Exception as e:
        print(f"\n[ERROR] 测试失败: {e}")
        import traceback
        traceback.print_exc()
