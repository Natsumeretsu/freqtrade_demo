"""性能分析工具

提供代码性能分析和瓶颈检测功能。

创建日期: 2026-01-17
"""
import cProfile
import pstats
import io
import time
import functools
from pathlib import Path
from typing import Callable, Any, Dict, Optional
from dataclasses import dataclass
from datetime import datetime


@dataclass
class PerformanceMetrics:
    """性能指标

    Attributes:
        function_name: 函数名称
        execution_time: 执行时间（秒）
        call_count: 调用次数
        memory_usage: 内存使用（字节）
        timestamp: 时间戳
    """
    function_name: str
    execution_time: float
    call_count: int
    memory_usage: Optional[int] = None
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


class PerformanceProfiler:
    """性能分析器"""

    def __init__(self):
        self.metrics: Dict[str, PerformanceMetrics] = {}

    def profile(self, func: Callable) -> Callable:
        """性能分析装饰器"""
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            result = func(*args, **kwargs)
            execution_time = time.time() - start_time

            func_name = func.__name__
            if func_name not in self.metrics:
                self.metrics[func_name] = PerformanceMetrics(
                    function_name=func_name,
                    execution_time=execution_time,
                    call_count=1
                )
            else:
                metric = self.metrics[func_name]
                metric.execution_time += execution_time
                metric.call_count += 1

            return result
        return wrapper

    def get_report(self) -> str:
        """生成性能报告"""
        if not self.metrics:
            return "没有性能数据"

        report = ["=" * 60, "性能分析报告", "=" * 60, ""]

        sorted_metrics = sorted(
            self.metrics.values(),
            key=lambda x: x.execution_time,
            reverse=True
        )

        for metric in sorted_metrics:
            avg_time = metric.execution_time / metric.call_count
            report.append(f"函数: {metric.function_name}")
            report.append(f"  总执行时间: {metric.execution_time:.4f}秒")
            report.append(f"  调用次数: {metric.call_count}")
            report.append(f"  平均时间: {avg_time:.4f}秒")
            report.append("")

        return "\n".join(report)

    def clear(self) -> None:
        """清空性能数据"""
        self.metrics.clear()


def profile_function(func: Callable, *args, **kwargs) -> Dict[str, Any]:
    """使用cProfile分析函数性能"""
    profiler = cProfile.Profile()
    profiler.enable()
    
    result = func(*args, **kwargs)
    
    profiler.disable()
    
    # 生成统计信息
    stream = io.StringIO()
    stats = pstats.Stats(profiler, stream=stream)
    stats.sort_stats('cumulative')
    stats.print_stats(20)
    
    return {
        'result': result,
        'profile_output': stream.getvalue()
    }


def save_profile_report(output: str, filename: str) -> None:
    """保存性能分析报告到文件"""
    report_path = Path(filename)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(output)
    
    print(f"性能报告已保存到: {report_path}")


# 使用示例
if __name__ == "__main__":
    # 示例1: 使用装饰器
    profiler = PerformanceProfiler()
    
    @profiler.profile
    def example_function():
        time.sleep(0.1)
        return "完成"
    
    # 调用函数
    for _ in range(5):
        example_function()
    
    # 打印报告
    print(profiler.get_report())
