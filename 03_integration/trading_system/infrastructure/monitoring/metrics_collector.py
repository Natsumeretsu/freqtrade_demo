"""指标收集器

收集和聚合系统运行指标。

创建日期: 2026-01-17
"""
from typing import Dict, List
from collections import defaultdict
from datetime import datetime
import threading


class MetricsCollector:
    """指标收集器"""

    def __init__(self):
        self._metrics: Dict[str, List[float]] = defaultdict(list)
        self._lock = threading.Lock()

    def record(self, metric_name: str, value: float) -> None:
        """记录指标值"""
        with self._lock:
            self._metrics[metric_name].append(value)

    def get_average(self, metric_name: str) -> float:
        """获取指标平均值"""
        with self._lock:
            values = self._metrics.get(metric_name, [])
            return sum(values) / len(values) if values else 0.0

    def get_summary(self, metric_name: str) -> Dict[str, float]:
        """获取指标摘要统计"""
        with self._lock:
            values = self._metrics.get(metric_name, [])
            if not values:
                return {}
            
            return {
                'count': len(values),
                'min': min(values),
                'max': max(values),
                'avg': sum(values) / len(values)
            }
