"""内存池管理测试用例

测试内存池、对象池和缓冲区管理器功能。

创建日期: 2026-01-17
"""

import sys
import os
import numpy as np

# 添加项目路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(project_root, '03_integration'))

from trading_system.infrastructure.memory_pool import (
    MemoryPool,
    ObjectPool,
    BufferManager
)


def test_memory_pool():
    """测试内存池"""
    print("\n[测试1] 内存池")

    pool = MemoryPool(block_size=1024, initial_blocks=5, max_blocks=10)

    # 测试获取内存块
    block1 = pool.acquire()
    assert block1 is not None
    assert len(block1) == 1024
    print("  [OK] 获取内存块成功")

    # 测试统计信息
    stats = pool.get_stats()
    assert stats['current_in_use'] == 1
    assert stats['pool_size'] == 4
    print(f"  [OK] 统计信息: 使用中={stats['current_in_use']}, 池大小={stats['pool_size']}")

    # 测试归还内存块
    pool.release(block1)
    stats = pool.get_stats()
    assert stats['current_in_use'] == 0
    assert stats['pool_size'] == 5
    print("  [OK] 归还内存块成功")

    print("  [SUCCESS] 内存池测试通过")


def test_object_pool():
    """测试对象池"""
    print("\n[测试2] 对象池")

    # 创建列表对象池
    def list_factory():
        return []

    def list_reset(lst):
        lst.clear()

    pool = ObjectPool(
        factory=list_factory,
        reset_func=list_reset,
        max_size=10,
        initial_size=3
    )

    # 测试获取对象
    obj1 = pool.acquire()
    assert obj1 is not None
    assert isinstance(obj1, list)
    obj1.append(1)
    obj1.append(2)
    print("  [OK] 获取对象成功")

    # 测试统计信息
    stats = pool.get_stats()
    assert stats['current_in_use'] == 1
    print(f"  [OK] 统计信息: 使用中={stats['current_in_use']}")

    # 测试归还对象
    pool.release(obj1)
    assert len(obj1) == 0  # 应该被重置
    stats = pool.get_stats()
    assert stats['current_in_use'] == 0
    print("  [OK] 归还对象成功，对象已重置")

    print("  [SUCCESS] 对象池测试通过")


def test_buffer_manager():
    """测试缓冲区管理器"""
    print("\n[测试3] 缓冲区管理器")

    manager = BufferManager(max_buffers=20)

    # 测试获取缓冲区
    buffer1 = manager.get_buffer(size=100, dtype='float64')
    assert buffer1 is not None
    assert buffer1.size == 100
    assert buffer1.dtype == np.float64
    print("  [OK] 获取缓冲区成功")

    # 测试使用缓冲区
    buffer1[:] = np.random.randn(100)
    print("  [OK] 使用缓冲区成功")

    # 测试统计信息
    stats = manager.get_stats()
    assert stats['in_use'] == 1
    print(f"  [OK] 统计信息: 使用中={stats['in_use']}")

    # 测试释放缓冲区
    manager.release_buffer(buffer1)
    assert np.all(buffer1 == 0)  # 应该被清空
    stats = manager.get_stats()
    assert stats['in_use'] == 0
    print("  [OK] 释放缓冲区成功，缓冲区已清空")

    print("  [SUCCESS] 缓冲区管理器测试通过")


def run_all_tests():
    """运行所有测试"""
    print("=" * 60)
    print("内存池管理测试套件")
    print("=" * 60)
    
    try:
        test_memory_pool()
        test_object_pool()
        test_buffer_manager()
        
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
    success = run_all_tests()
    sys.exit(0 if success else 1)
