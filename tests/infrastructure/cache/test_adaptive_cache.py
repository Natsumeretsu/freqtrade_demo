"""自适应缓存测试

测试自适应缓存的各项功能。

创建日期: 2026-01-17
"""
import unittest
import time
import sys
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root / '03_integration'))

from trading_system.infrastructure.cache import AdaptiveCache


class TestAdaptiveCache(unittest.TestCase):
    """自适应缓存测试类"""

    def setUp(self):
        """测试前准备"""
        self.cache = AdaptiveCache(initial_size=3)

    def tearDown(self):
        """测试后清理"""
        self.cache.clear()

    def test_put_and_get(self):
        """测试基本的存取功能"""
        self.cache.put('key1', 'value1')
        self.assertEqual(self.cache.get('key1'), 'value1')
        
    def test_get_nonexistent_key(self):
        """测试获取不存在的键"""
        self.assertIsNone(self.cache.get('nonexistent'))

    def test_eviction_when_full(self):
        """测试缓存满时的驱逐机制"""
        # 填满缓存
        self.cache.put('key1', 'value1')
        self.cache.put('key2', 'value2')
        self.cache.put('key3', 'value3')
        
        # 添加第4个元素，应该驱逐一个
        self.cache.put('key4', 'value4')
        self.assertEqual(self.cache.size(), 3)

    def test_access_frequency_tracking(self):
        """测试访问频率追踪"""
        self.cache.put('key1', 'value1')

        # 多次访问
        for _ in range(5):
            self.cache.get('key1')

        stats = self.cache.get_stats()
        self.assertEqual(stats['total_access'], 6)  # 1次put + 5次get

    def test_time_decay_eviction(self):
        """测试时间衰减驱逐策略"""
        # 添加三个键
        self.cache.put('key1', 'value1')
        time.sleep(0.1)
        self.cache.put('key2', 'value2')
        time.sleep(0.1)
        self.cache.put('key3', 'value3')
        
        # key1 是最旧的，应该被优先驱逐
        self.cache.put('key4', 'value4')
        self.assertIsNone(self.cache.get('key1'))

    def test_clear(self):
        """测试清空缓存"""
        self.cache.put('key1', 'value1')
        self.cache.put('key2', 'value2')
        
        self.cache.clear()
        self.assertEqual(self.cache.size(), 0)
        self.assertIsNone(self.cache.get('key1'))

    def test_size(self):
        """测试获取缓存大小"""
        self.assertEqual(self.cache.size(), 0)
        
        self.cache.put('key1', 'value1')
        self.assertEqual(self.cache.size(), 1)
        
        self.cache.put('key2', 'value2')
        self.assertEqual(self.cache.size(), 2)

    def test_get_stats(self):
        """测试获取统计信息"""
        self.cache.put('key1', 'value1')
        self.cache.put('key2', 'value2')
        
        # 访问 key1 多次
        for _ in range(3):
            self.cache.get('key1')
        
        stats = self.cache.get_stats()
        self.assertEqual(stats['size'], 2)
        self.assertEqual(stats['max_size'], 3)
        self.assertGreater(stats['total_access'], 0)

    def test_update_existing_key(self):
        """测试更新已存在的键"""
        self.cache.put('key1', 'value1')
        self.cache.put('key1', 'value2')
        
        self.assertEqual(self.cache.get('key1'), 'value2')
        self.assertEqual(self.cache.size(), 1)


if __name__ == '__main__':
    unittest.main()
