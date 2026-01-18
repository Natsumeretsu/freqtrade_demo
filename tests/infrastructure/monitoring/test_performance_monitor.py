"""性能监控测试

测试性能监控的各项功能。

创建日期: 2026-01-17
"""
import unittest
import time
import sys
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root / '03_integration'))

from trading_system.infrastructure.monitoring import PerformanceMonitor


class TestPerformanceMonitor(unittest.TestCase):
    """性能监控测试类"""

    def setUp(self):
        """测试前准备"""
        self.monitor = PerformanceMonitor(interval=0.5)

    def tearDown(self):
        """测试后清理"""
        if self.monitor._running:
            self.monitor.stop()

    def test_start_and_stop(self):
        """测试启动和停止"""
        self.monitor.start()
        self.assertTrue(self.monitor._running)
        
        time.sleep(1)
        
        self.monitor.stop()
        self.assertFalse(self.monitor._running)

    def test_collect_snapshot(self):
        """测试收集性能快照"""
        self.monitor.start()
        time.sleep(1)

        snapshot = self.monitor.get_current_metrics()
        self.assertIsNotNone(snapshot)
        self.assertGreaterEqual(snapshot.cpu_percent, 0)
        self.assertGreaterEqual(snapshot.memory_percent, 0)

        self.monitor.stop()

    def test_get_report(self):
        """测试获取报告"""
        self.monitor.start()
        time.sleep(1)
        
        report = self.monitor.get_report()
        self.assertIsInstance(report, str)
        self.assertIn('CPU', report)
        self.assertIn('内存', report)
        
        self.monitor.stop()


if __name__ == '__main__':
    unittest.main()
