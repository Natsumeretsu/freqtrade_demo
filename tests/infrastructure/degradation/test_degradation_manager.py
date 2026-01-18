"""降级管理器测试

测试降级管理器的各项功能。

创建日期: 2026-01-17
"""
import unittest
import sys
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root / '03_integration'))

from trading_system.infrastructure.degradation import DegradationManager


class TestDegradationManager(unittest.TestCase):
    """降级管理器测试类"""

    def setUp(self):
        """测试前准备"""
        self.manager = DegradationManager()

    def test_register_strategy(self):
        """测试注册降级策略"""
        def primary():
            return "primary"
        
        def fallback():
            return "fallback"
        
        self.manager.register_strategy(
            'test_service',
            primary,
            fallback
        )
        
        status = self.manager.get_service_status('test_service')
        self.assertEqual(status['status'], 'closed')

    def test_execute_primary_success(self):
        """测试主服务执行成功"""
        def primary():
            return "primary_result"
        
        def fallback():
            return "fallback_result"
        
        self.manager.register_strategy('test_service', primary, fallback)
        result = self.manager.execute('test_service')
        
        self.assertEqual(result, "primary_result")

    def test_execute_fallback_on_failure(self):
        """测试主服务失败时降级"""
        def primary():
            raise Exception("primary failed")
        
        def fallback():
            return "fallback_result"
        
        self.manager.register_strategy('test_service', primary, fallback)
        result = self.manager.execute('test_service')
        
        self.assertEqual(result, "fallback_result")

    def test_unregistered_service(self):
        """测试未注册的服务"""
        with self.assertRaises(ValueError):
            self.manager.execute('unknown_service')

    def test_reset_service(self):
        """测试重置服务"""
        def primary():
            raise Exception("error")
        
        def fallback():
            return "fallback"
        
        self.manager.register_strategy('test_service', primary, fallback, failure_threshold=2)
        
        # 触发失败
        for _ in range(2):
            self.manager.execute('test_service')
        
        # 重置
        self.manager.reset_service('test_service')
        status = self.manager.get_service_status('test_service')
        self.assertEqual(status['failure_count'], 0)


if __name__ == '__main__':
    unittest.main()
