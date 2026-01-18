"""并行回测

支持多进程并行回测。

创建日期: 2026-01-17
"""
from typing import List, Dict, Any, Callable
from multiprocessing import Pool, cpu_count
import pandas as pd


class ParallelBacktest:
    """并行回测管理器"""

    def __init__(self, n_workers: int = None):
        self.n_workers = n_workers or cpu_count()

    def run_parallel(
        self,
        strategies: List[str],
        data: pd.DataFrame,
        config: Dict[str, Any],
        backtest_func: Callable
    ) -> Dict[str, Any]:
        """并行运行多个策略的回测"""
        tasks = [(strategy, data, config, backtest_func) for strategy in strategies]
        
        with Pool(self.n_workers) as pool:
            results = pool.starmap(self._run_single, tasks)
        
        return dict(zip(strategies, results))

    @staticmethod
    def _run_single(strategy: str, data: pd.DataFrame, config: Dict[str, Any], backtest_func: Callable) -> Any:
        """运行单个策略回测"""
        return backtest_func(data, config)
