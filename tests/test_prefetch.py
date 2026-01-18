"""智能预取策略测试用例

测试访问跟踪、模式检测和预取调度功能。

创建日期: 2026-01-17
"""

import sys
import os
import time

# 添加项目路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(project_root, '03_integration'))

from trading_system.infrastructure.prefetch import (
    AccessTracker,
    PatternDetector,
    PrefetchScheduler
)


def test_access_tracker():
    """测试访问跟踪器"""
    print("\n[测试1] 访问跟踪器")

    tracker = AccessTracker(max_history=100)

    # 记录访问
    tracker.record_access("data_1", hit=False)
    tracker.record_access("data_2", hit=True)
    tracker.record_access("data_1", hit=True)

    # 验证历史记录
    history = tracker.get_history()
    assert len(history) == 3
    print(f"  [OK] 记录了 {len(history)} 次访问")

    # 验证频率统计
    freq_1 = tracker.get_frequency("data_1")
    freq_2 = tracker.get_frequency("data_2")
    assert freq_1 == 2
    assert freq_2 == 1
    print(f"  [OK] 频率统计正确: data_1={freq_1}, data_2={freq_2}")

    # 验证 top keys
    top_keys = tracker.get_top_keys(n=2)
    assert top_keys[0][0] == "data_1"
    print(f"  [OK] Top keys: {top_keys}")

    print("  [SUCCESS] 访问跟踪器测试通过")


def test_pattern_detector():
    """测试模式检测器"""
    print("\n[测试2] 模式检测器")

    tracker = AccessTracker()
    detector = PatternDetector(tracker, min_confidence=0.5)

    # 模拟顺序访问
    for i in range(1, 6):
        tracker.record_access(f"data_{i}")

    # 检测顺序模式
    pattern = detector.detect_sequential()
    assert pattern is not None
    assert pattern.pattern_type == "sequential"
    assert "data_6" in pattern.next_keys
    print(f"  [OK] 检测到顺序模式，预测: {pattern.next_keys}, 置信度: {pattern.confidence:.2f}")

    print("  [SUCCESS] 模式检测器测试通过")


def test_prefetch_scheduler():
    """测试预取调度器"""
    print("\n[测试3] 预取调度器")

    # 模拟数据加载函数
    def mock_loader(key):
        return f"data_for_{key}"

    scheduler = PrefetchScheduler(loader=mock_loader)

    # 调度预取
    scheduler.schedule_prefetch(["key1", "key2", "key3"])
    assert scheduler.get_queue_size() == 3
    print(f"  [OK] 调度了 {scheduler.get_queue_size()} 个预取任务")

    # 执行预取
    count = scheduler.execute_prefetch(max_items=2)
    assert count == 2
    print(f"  [OK] 执行了 {count} 个预取任务")

    # 获取预取的数据
    data = scheduler.get_prefetched("key1")
    assert data == "data_for_key1"
    print(f"  [OK] 获取预取数据: {data}")

    print("  [SUCCESS] 预取调度器测试通过")


def run_all_tests():
    """运行所有测试"""
    print("=" * 60)
    print("智能预取策略测试套件")
    print("=" * 60)
    
    try:
        test_access_tracker()
        test_pattern_detector()
        test_prefetch_scheduler()
        
        print("\n" + "=" * 60)
        print("[ALL TESTS PASSED] 所有测试通过!")
        print("=" * 60)
        return True
    except AssertionError as e:
        print(f"\n[FAILED] 测试失败: {e}")
        return False
    except Exception as e:
        print(f"\n[ERROR] 测试错误: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    import sys
    success = run_all_tests()
    sys.exit(0 if success else 1)
