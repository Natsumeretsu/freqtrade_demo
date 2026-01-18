"""增量回测测试

测试增量回测的各项功能。

创建日期: 2026-01-17
"""
import unittest
import sys
from pathlib import Path
import pandas as pd
from datetime import datetime, timedelta
import tempfile
import shutil

# 添加项目路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / '03_integration'))

from trading_system.backtest import IncrementalBacktest, BacktestCheckpoint


class TestIncrementalBacktest(unittest.TestCase):
    """增量回测测试类"""

    def setUp(self):
        """测试前准备"""
        self.temp_dir = tempfile.mkdtemp()
        self.backtest = IncrementalBacktest(checkpoint_dir=self.temp_dir)

    def tearDown(self):
        """测试后清理"""
        shutil.rmtree(self.temp_dir)

    def _create_test_data(self, days=10):
        """创建测试数据"""
        dates = pd.date_range(start='2024-01-01', periods=days, freq='D')
        data = pd.DataFrame({
            'close': range(100, 100 + days)
        }, index=dates)
        return data

    def test_compute_config_hash(self):
        """测试配置哈希计算"""
        config1 = {'param1': 'value1', 'param2': 'value2'}
        config2 = {'param1': 'value1', 'param2': 'value2'}
        config3 = {'param1': 'value1', 'param2': 'value3'}
        
        hash1 = IncrementalBacktest.compute_config_hash(config1)
        hash2 = IncrementalBacktest.compute_config_hash(config2)
        hash3 = IncrementalBacktest.compute_config_hash(config3)
        
        self.assertEqual(hash1, hash2)
        self.assertNotEqual(hash1, hash3)

    def test_full_backtest(self):
        """测试全量回测"""
        data = self._create_test_data(10)
        config = {'strategy': 'test'}
        
        def backtest_func(df, cfg):
            return {'total_trades': len(df), 'trades': []}
        
        result = self.backtest.run('test_strategy', data, config, backtest_func)
        self.assertEqual(result['total_trades'], 10)

    def test_incremental_backtest(self):
        """测试增量回测"""
        # 第一次回测
        data1 = self._create_test_data(5)
        config = {'strategy': 'test'}
        
        def backtest_func(df, cfg):
            return {'total_trades': len(df), 'trades': []}
        
        result1 = self.backtest.run('test_strategy', data1, config, backtest_func)
        self.assertEqual(result1['total_trades'], 5)
        
        # 第二次回测（增量）
        data2 = self._create_test_data(10)
        result2 = self.backtest.run('test_strategy', data2, config, backtest_func)
        self.assertEqual(result2['total_trades'], 10)

    def test_clear_checkpoint(self):
        """测试清除检查点"""
        data = self._create_test_data(5)
        config = {'strategy': 'test'}
        
        def backtest_func(df, cfg):
            return {'total_trades': len(df)}
        
        self.backtest.run('test_strategy', data, config, backtest_func)
        
        config_hash = IncrementalBacktest.compute_config_hash(config)
        self.backtest.clear_checkpoint('test_strategy', config_hash)
        
        self.assertFalse(self.backtest.checkpoint.exists('test_strategy', config_hash))


if __name__ == '__main__':
    unittest.main()
