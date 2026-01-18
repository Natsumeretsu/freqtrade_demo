"""性能基准测试

测试各个组件的性能指标。

创建日期: 2026-01-17
"""
import time
import sys
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / '03_integration'))

from trading_system.infrastructure.cache import AdaptiveCache
from trading_system.infrastructure.degradation import CircuitBreaker


def benchmark_cache():
    """基准测试：缓存性能"""
    cache = AdaptiveCache(initial_size=1000)
    
    # 写入测试
    start = time.time()
    for i in range(1000):
        cache.put(f'key_{i}', f'value_{i}')
    write_time = time.time() - start
    
    print(f"缓存写入 1000 项: {write_time:.4f}秒")
    
    # 读取测试
    start = time.time()
    for i in range(1000):
        cache.get(f'key_{i}')
    read_time = time.time() - start
    
    print(f"缓存读取 1000 项: {read_time:.4f}秒")


def benchmark_circuit_breaker():
    """基准测试：熔断器性能"""
    breaker = CircuitBreaker(failure_threshold=5, timeout=1)
    
    def test_func():
        return "success"
    
    start = time.time()
    for _ in range(1000):
        breaker.call(test_func)
    elapsed = time.time() - start
    
    print(f"熔断器调用 1000 次: {elapsed:.4f}秒")


if __name__ == '__main__':
    print("=" * 60)
    print("性能基准测试")
    print("=" * 60)
    
    print("\n[1/2] 缓存性能测试")
    benchmark_cache()
    
    print("\n[2/2] 熔断器性能测试")
    benchmark_circuit_breaker()
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)
