"""熔断器测试

测试熔断器的各项功能。

创建日期: 2026-01-17
"""
import unittest
import time
import sys
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root / '03_integration'))

from trading_system.infrastructure.degradation import CircuitBreaker, CircuitState


class TestCircuitBreaker(unittest.TestCase):
    """熔断器测试类"""

    def setUp(self):
        """测试前准备"""
        self.breaker = CircuitBreaker(
            failure_threshold=3,
            timeout=1,
            expected_exception=ValueError
        )

    def test_initial_state(self):
        """测试初始状态"""
        self.assertEqual(self.breaker.state, CircuitState.CLOSED)
        self.assertEqual(self.breaker.failure_count, 0)

    def test_successful_call(self):
        """测试成功调用"""
        def success_func():
            return "success"
        
        result = self.breaker.call(success_func)
        self.assertEqual(result, "success")
        self.assertEqual(self.breaker.state, CircuitState.CLOSED)

    def test_failure_count_increment(self):
        """测试失败计数递增"""
        def fail_func():
            raise ValueError("error")
        
        for i in range(2):
            try:
                self.breaker.call(fail_func)
            except ValueError:
                pass
        
        self.assertEqual(self.breaker.failure_count, 2)
        self.assertEqual(self.breaker.state, CircuitState.CLOSED)

    def test_circuit_opens_after_threshold(self):
        """测试达到阈值后熔断器开启"""
        def fail_func():
            raise ValueError("error")
        
        # 触发3次失败
        for i in range(3):
            try:
                self.breaker.call(fail_func)
            except ValueError:
                pass
        
        self.assertEqual(self.breaker.state, CircuitState.OPEN)

    def test_open_circuit_rejects_calls(self):
        """测试开启状态的熔断器拒绝调用"""
        def fail_func():
            raise ValueError("error")
        
        # 触发熔断
        for i in range(3):
            try:
                self.breaker.call(fail_func)
            except ValueError:
                pass
        
        # 尝试调用应该被拒绝
        with self.assertRaises(Exception) as context:
            self.breaker.call(lambda: "test")
        
        self.assertIn("熔断器开启", str(context.exception))

    def test_half_open_state_after_timeout(self):
        """测试超时后进入半开状态"""
        def fail_func():
            raise ValueError("error")
        
        # 触发熔断
        for i in range(3):
            try:
                self.breaker.call(fail_func)
            except ValueError:
                pass
        
        # 等待超时
        time.sleep(1.1)
        
        # 下次调用应该进入半开状态
        def success_func():
            return "success"
        
        result = self.breaker.call(success_func)
        self.assertEqual(result, "success")
        self.assertEqual(self.breaker.state, CircuitState.CLOSED)

    def test_reset(self):
        """测试手动重置"""
        def fail_func():
            raise ValueError("error")
        
        # 触发熔断
        for i in range(3):
            try:
                self.breaker.call(fail_func)
            except ValueError:
                pass
        
        # 重置
        self.breaker.reset()
        self.assertEqual(self.breaker.state, CircuitState.CLOSED)
        self.assertEqual(self.breaker.failure_count, 0)


if __name__ == '__main__':
    unittest.main()
