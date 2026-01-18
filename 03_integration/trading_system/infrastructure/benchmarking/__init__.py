"""自动化性能基准测试模块

提供自动化性能基准测试功能。

核心组件：
1. BenchmarkRunner - 基准测试运行器
2. BenchmarkResult - 测试结果
3. ResultComparator - 结果对比器

创建日期: 2026-01-17
"""
from .benchmark_runner import BenchmarkRunner
from .benchmark_result import BenchmarkResult

__all__ = [
    'BenchmarkRunner',
    'BenchmarkResult',
]
