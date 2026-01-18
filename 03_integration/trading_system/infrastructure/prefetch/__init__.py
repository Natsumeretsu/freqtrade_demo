"""智能预取模块

提供智能数据预取功能。

核心组件：
1. AccessTracker - 访问跟踪器
2. PatternDetector - 模式检测器
3. PrefetchScheduler - 预取调度器

创建日期: 2026-01-17
"""
from .tracker import AccessTracker, AccessRecord
from .detector import PatternDetector, AccessPattern
from .scheduler import PrefetchScheduler

__all__ = [
    'AccessTracker',
    'AccessRecord',
    'PatternDetector',
    'AccessPattern',
    'PrefetchScheduler',
]
