"""基准测试结果

存储和计算基准测试结果的统计信息。

创建日期: 2026-01-17
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List

logger = logging.getLogger(__name__)


@dataclass
class BenchmarkResult:
    """基准测试结果

    存储单个基准测试的结果和统计信息。
    """

    case_name: str
    execution_times: List[float]
    mean_time: float
    median_time: float
    std_dev: float
    min_time: float
    max_time: float
    throughput: float
    memory_mb: float = 0.0

    @classmethod
    def from_times(
        cls,
        case_name: str,
        execution_times: List[float],
        operations: int = 1,
        memory_mb: float = 0.0
    ) -> BenchmarkResult:
        """从执行时间列表创建结果

        Args:
            case_name: 测试用例名称
            execution_times: 执行时间列表（秒）
            operations: 操作数量
            memory_mb: 内存使用（MB）

        Returns:
            基准测试结果
        """
        if not execution_times:
            raise ValueError("execution_times 不能为空")

        # 计算统计信息
        sorted_times = sorted(execution_times)
        n = len(sorted_times)

        mean_time = sum(execution_times) / n
        median_time = sorted_times[n // 2]

        # 计算标准差
        variance = sum((t - mean_time) ** 2 for t in execution_times) / n
        std_dev = variance ** 0.5

        min_time = min(execution_times)
        max_time = max(execution_times)

        # 计算吞吐量（ops/sec）
        throughput = operations / mean_time if mean_time > 0 else 0.0

        return cls(
            case_name=case_name,
            execution_times=execution_times,
            mean_time=mean_time,
            median_time=median_time,
            std_dev=std_dev,
            min_time=min_time,
            max_time=max_time,
            throughput=throughput,
            memory_mb=memory_mb
        )

    def __str__(self) -> str:
        """格式化输出结果"""
        lines = []
        lines.append(f"测试用例: {self.case_name}")
        lines.append(f"  平均时间: {self.mean_time * 1000:.2f} ms")
        lines.append(f"  中位数: {self.median_time * 1000:.2f} ms")
        lines.append(f"  标准差: {self.std_dev * 1000:.2f} ms")
        lines.append(f"  最小值: {self.min_time * 1000:.2f} ms")
        lines.append(f"  最大值: {self.max_time * 1000:.2f} ms")
        lines.append(f"  吞吐量: {self.throughput:.2f} ops/sec")
        if self.memory_mb > 0:
            lines.append(f"  内存使用: {self.memory_mb:.2f} MB")
        return "\n".join(lines)
