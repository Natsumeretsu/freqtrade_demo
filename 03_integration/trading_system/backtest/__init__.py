"""回测模块

提供增量回测功能。

创建日期: 2026-01-17
"""
from .incremental_backtest import IncrementalBacktest, BacktestCheckpoint

__all__ = ['IncrementalBacktest', 'BacktestCheckpoint']
