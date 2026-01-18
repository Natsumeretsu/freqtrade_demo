"""测试性能监控系统

验证性能监控的正确性和功能完整性。

创建日期: 2026-01-17
"""

import sys
import os
import time
from datetime import datetime, timedelta

# 添加项目路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(project_root, '03_integration'))

from trading_system.infrastructure.monitoring import PerformanceMonitor


def test_timing_decorator():
    """测试时间监控装饰器"""
    print("\n=== 测试时间监控装饰器 ===")

    monitor = PerformanceMonitor()
    monitor.start()

    @monitor.timing("test_operation", "test_factor")
    def slow_function():
        time.sleep(0.01)  # 模拟耗时操作
        return "result"

    # 执行多次
    for _ in range(10):
        result = slow_function()
        assert result == "result"

    # 获取报告
    report = monitor.get_report()
    print(report)

    # 验证
    assert "总操作数: 10" in report
    assert "成功操作数: 10" in report
    assert "平均响应时间" in report

    print("[PASS] 时间监控装饰器测试通过")


def test_cache_stats():
    """测试缓存统计记录"""
    print("\n=== 测试缓存统计记录 ===")

    monitor = PerformanceMonitor()
    monitor.start()

    # 模拟缓存统计
    monitor.record_cache_stats(
        cache_type="factor_cache",
        hits=850,
        misses=150,
        evictions=20,
        size=950,
        max_size=1000
    )

    # 获取报告
    report = monitor.get_report()
    print(report)

    # 验证
    assert "缓存命中率: 85.00%" in report
    assert "总命中数: 850" in report
    assert "总未命中数: 150" in report

    print("[PASS] 缓存统计记录测试通过")


def test_memory_usage():
    """测试内存使用记录"""
    print("\n=== 测试内存使用记录 ===")

    monitor = PerformanceMonitor()
    monitor.start()

    # 模拟内存使用
    monitor.record_memory_usage(
        component="data_buffer",
        memory_mb=125.3,
        max_memory_mb=500.0
    )

    monitor.record_memory_usage(
        component="factor_cache",
        memory_mb=45.7,
        max_memory_mb=100.0
    )

    # 获取报告
    report = monitor.get_report()
    print(report)

    # 验证
    assert "data_buffer" in report
    assert "125.3" in report or "125.30" in report
    assert "factor_cache" in report

    print("[PASS] 内存使用记录测试通过")


def test_comprehensive_monitoring():
    """测试综合监控"""
    print("\n=== 测试综合监控 ===")

    monitor = PerformanceMonitor()
    monitor.start()

    # 时间监控
    @monitor.timing("compute_factor")
    def compute_factor(factor_name):
        time.sleep(0.005)
        return f"result_{factor_name}"

    # 执行多个因子计算
    for i in range(20):
        compute_factor(f"factor_{i}")

    # 缓存统计
    monitor.record_cache_stats(
        cache_type="arc_cache",
        hits=170,
        misses=30,
        evictions=5,
        size=195,
        max_size=200
    )

    # 内存使用
    monitor.record_memory_usage(
        component="data_prefetcher",
        memory_mb=250.0,
        max_memory_mb=500.0
    )

    # 获取报告
    report = monitor.get_report()
    print(report)

    # 验证
    assert "总操作数: 20" in report
    assert "缓存命中率: 85.00%" in report
    assert "data_prefetcher" in report

    print("[PASS] 综合监控测试通过")


if __name__ == "__main__":
    print("="*60)
    print("开始测试性能监控系统")
    print("="*60)

    try:
        test_timing_decorator()
        test_cache_stats()
        test_memory_usage()
        test_comprehensive_monitoring()

        print("\n" + "="*60)
        print("[SUCCESS] 所有测试通过！")
        print("="*60)
    except Exception as e:
        print(f"\n[ERROR] 测试失败: {e}")
        import traceback
        traceback.print_exc()
