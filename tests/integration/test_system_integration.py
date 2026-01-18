"""系统集成测试

测试所有组件的集成功能。

创建日期: 2026-01-17
"""
import unittest
import sys
from pathlib import Path
import time

# 添加项目路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / '03_integration'))

from trading_system import SystemManager, SystemConfig


class TestSystemIntegration(unittest.TestCase):
    """系统集成测试类"""

    def setUp(self):
        """测试前准备"""
        self.config = SystemConfig()
        self.system = SystemManager(self.config)

    def tearDown(self):
        """测试后清理"""
        self.system.stop()

    def test_system_initialization(self):
        """测试系统初始化"""
        self.assertIsNotNone(self.system.cache)
        self.assertIsNotNone(self.system.degradation)
        self.assertIsNotNone(self.system.monitor)
        self.assertIsNotNone(self.system.backtest)

    def test_system_start_stop(self):
        """测试系统启动和停止"""
        self.system.start()
        time.sleep(0.5)
        
        status = self.system.get_status()
        self.assertTrue(status['monitor_running'])
        
        self.system.stop()
        status = self.system.get_status()
        self.assertFalse(status['monitor_running'])

    def test_cache_integration(self):
        """测试缓存集成"""
        self.system.cache.put('test_key', 'test_value')
        value = self.system.cache.get('test_key')
        self.assertEqual(value, 'test_value')

    def test_config_integration(self):
        """测试配置集成"""
        self.config.set('test.key', 'test_value')
        value = self.config.get('test.key')
        self.assertEqual(value, 'test_value')


if __name__ == '__main__':
    unittest.main()
