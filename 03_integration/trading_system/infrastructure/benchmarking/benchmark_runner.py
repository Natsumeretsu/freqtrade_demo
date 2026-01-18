"""基准测试运行器

运行基准测试并收集结果。

创建日期: 2026-01-17
"""
from __future__ import annotations

import gc
import time
import logging
from typing import Callable, Any, Optional
from .benchmark_result import BenchmarkResult

logger = logging.getLogger(__name__)


class BenchmarkRunner:
    """基准测试运行器

    运行基准测试并收集统计信息。
    """

    def __init__(self):
        """初始化基准测试运行器"""
        pass

    def run_benchmark(
        self,
        name: str,
        func: Callable,
        repeat: int = 5,
        warmup: int = 2,
        operations: int = 1,
        *args,
        **kwargs
    ) -> BenchmarkResult:
        """运行基准测试

        Args:
            name: 测试名称
            func: 测试函数
            repeat: 重复次数
            warmup: 预热次数
            operations: 操作数量
            *args: 函数参数
            **kwargs: 函数关键字参数

        Returns:
            基准测试结果
        """
        logger.info(f"开始基准测试: {name}")

        # 预热
        if warmup > 0:
            logger.debug(f"预热 {warmup} 次")
            for _ in range(warmup):
                func(*args, **kwargs)

        # 收集执行时间
        execution_times = []

        for i in range(repeat):
            # 禁用垃圾回收
            gc_was_enabled = gc.isenabled()
            if gc_was_enabled:
                gc.disable()

            try:
                # 使用高精度计时器
                start_time = time.perf_counter()
                func(*args, **kwargs)
                end_time = time.perf_counter()

                elapsed = end_time - start_time
                execution_times.append(elapsed)

                logger.debug(f"第 {i+1}/{repeat} 次: {elapsed * 1000:.2f} ms")

            finally:
                # 恢复垃圾回收
                if gc_was_enabled:
                    gc.enable()

        # 创建结果
        result = BenchmarkResult.from_times(
            case_name=name,
            execution_times=execution_times,
            operations=operations
        )

        logger.info(f"完成基准测试: {name}")
        return result
