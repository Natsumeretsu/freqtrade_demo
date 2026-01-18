"""增量回测

支持增量回测，避免重复计算历史数据。

创建日期: 2026-01-17
"""
from typing import Dict, List, Optional, Any
from pathlib import Path
import json
import hashlib
from datetime import datetime
import pandas as pd


class BacktestCheckpoint:
    """回测检查点"""

    def __init__(self, checkpoint_dir: str = "checkpoints"):
        self.checkpoint_dir = Path(checkpoint_dir)
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

    def save(
        self,
        strategy_name: str,
        end_date: datetime,
        results: Dict[str, Any],
        config_hash: str
    ) -> None:
        """保存检查点"""
        checkpoint_file = self._get_checkpoint_path(strategy_name, config_hash)
        
        checkpoint_data = {
            'strategy_name': strategy_name,
            'end_date': end_date.isoformat(),
            'config_hash': config_hash,
            'results': results,
            'saved_at': datetime.now().isoformat()
        }
        
        with open(checkpoint_file, 'w', encoding='utf-8') as f:
            json.dump(checkpoint_data, f, indent=2, ensure_ascii=False)

    def load(
        self,
        strategy_name: str,
        config_hash: str
    ) -> Optional[Dict[str, Any]]:
        """加载检查点"""
        checkpoint_file = self._get_checkpoint_path(strategy_name, config_hash)
        
        if not checkpoint_file.exists():
            return None
        
        with open(checkpoint_file, 'r', encoding='utf-8') as f:
            return json.load(f)

    def _get_checkpoint_path(self, strategy_name: str, config_hash: str) -> Path:
        """获取检查点文件路径"""
        filename = f"{strategy_name}_{config_hash}.json"
        return self.checkpoint_dir / filename

    def exists(self, strategy_name: str, config_hash: str) -> bool:
        """检查检查点是否存在"""
        return self._get_checkpoint_path(strategy_name, config_hash).exists()


class IncrementalBacktest:
    """增量回测管理器"""

    def __init__(self, checkpoint_dir: str = "checkpoints"):
        self.checkpoint = BacktestCheckpoint(checkpoint_dir)

    @staticmethod
    def compute_config_hash(config: Dict[str, Any]) -> str:
        """计算配置哈希值"""
        config_str = json.dumps(config, sort_keys=True)
        return hashlib.md5(config_str.encode()).hexdigest()

    def run(
        self,
        strategy_name: str,
        data: pd.DataFrame,
        config: Dict[str, Any],
        backtest_func: callable
    ) -> Dict[str, Any]:
        """运行增量回测"""
        config_hash = self.compute_config_hash(config)
        
        # 尝试加载检查点
        checkpoint_data = self.checkpoint.load(strategy_name, config_hash)
        
        if checkpoint_data:
            # 存在检查点，只回测新数据
            last_date = datetime.fromisoformat(checkpoint_data['end_date'])
            new_data = data[data.index > last_date]
            
            if len(new_data) == 0:
                # 没有新数据
                return checkpoint_data['results']
            
            # 回测新数据
            new_results = backtest_func(new_data, config)
            
            # 合并结果
            merged_results = self._merge_results(
                checkpoint_data['results'],
                new_results
            )
        else:
            # 不存在检查点，全量回测
            merged_results = backtest_func(data, config)
        
        # 保存新检查点
        end_date = data.index[-1] if isinstance(data.index[-1], datetime) else datetime.now()
        self.checkpoint.save(strategy_name, end_date, merged_results, config_hash)
        
        return merged_results

    def _merge_results(
        self,
        old_results: Dict[str, Any],
        new_results: Dict[str, Any]
    ) -> Dict[str, Any]:
        """合并回测结果"""
        merged = old_results.copy()
        
        # 合并交易记录
        if 'trades' in old_results and 'trades' in new_results:
            merged['trades'] = old_results['trades'] + new_results['trades']
        
        # 更新统计指标
        if 'total_trades' in old_results and 'total_trades' in new_results:
            merged['total_trades'] = old_results['total_trades'] + new_results['total_trades']
        
        return merged

    def clear_checkpoint(self, strategy_name: str, config_hash: str) -> None:
        """清除检查点"""
        checkpoint_file = self.checkpoint._get_checkpoint_path(strategy_name, config_hash)
        if checkpoint_file.exists():
            checkpoint_file.unlink()
