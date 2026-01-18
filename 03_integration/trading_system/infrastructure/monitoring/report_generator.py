"""报告生成器

生成性能监控报告。

创建日期: 2026-01-17
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import List, Optional
from .metrics_collector import TimingMetric, CacheMetric, MemoryMetric

logger = logging.getLogger(__name__)


class ReportGenerator:
    """报告生成器

    生成性能监控摘要报告。
    """

    def __init__(self):
        """初始化报告生成器"""
        pass

    def generate_summary(
        self,
        timing_metrics: List[TimingMetric],
        cache_metrics: List[CacheMetric],
        memory_metrics: List[MemoryMetric],
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> str:
        """生成摘要报告

        Args:
            timing_metrics: 时间指标列表
            cache_metrics: 缓存指标列表
            memory_metrics: 内存指标列表
            start_time: 开始时间
            end_time: 结束时间

        Returns:
            报告文本
        """
        lines = []
        lines.append("=" * 60)
        lines.append("性能监控报告")
        lines.append("=" * 60)

        # 监控时间范围
        if start_time and end_time:
            lines.append(f"监控时间: {start_time.strftime('%Y-%m-%d %H:%M:%S')} ~ {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("")

        # 时间指标
        if timing_metrics:
            lines.append("[时间指标]")
            lines.extend(self._format_timing_metrics(timing_metrics))
            lines.append("")

        # 缓存指标
        if cache_metrics:
            lines.append("[缓存指标]")
            lines.extend(self._format_cache_metrics(cache_metrics))
            lines.append("")

        # 内存指标
        if memory_metrics:
            lines.append("[内存指标]")
            lines.extend(self._format_memory_metrics(memory_metrics))
            lines.append("")

        return "\n".join(lines)

    def _format_timing_metrics(self, metrics: List[TimingMetric]) -> List[str]:
        """格式化时间指标

        Args:
            metrics: 时间指标列表

        Returns:
            格式化后的文本行
        """
        lines = []

        # 计算统计信息
        durations = [m.duration_ms for m in metrics]
        success_count = sum(1 for m in metrics if m.success)

        lines.append(f"- 总操作数: {len(metrics)}")
        lines.append(f"- 成功操作数: {success_count}")
        lines.append(f"- 失败操作数: {len(metrics) - success_count}")

        if durations:
            # 使用 Python 标准库计算统计信息
            sorted_durations = sorted(durations)
            n = len(sorted_durations)

            mean_duration = sum(durations) / len(durations)
            p50 = sorted_durations[int(n * 0.50)]
            p95 = sorted_durations[int(n * 0.95)]
            p99 = sorted_durations[int(n * 0.99)]
            min_duration = min(durations)
            max_duration = max(durations)

            lines.append(f"- 平均响应时间: {mean_duration:.2f} ms")
            lines.append(f"- P50: {p50:.2f} ms")
            lines.append(f"- P95: {p95:.2f} ms")
            lines.append(f"- P99: {p99:.2f} ms")
            lines.append(f"- 最小值: {min_duration:.2f} ms")
            lines.append(f"- 最大值: {max_duration:.2f} ms")

        return lines

    def _format_cache_metrics(self, metrics: List[CacheMetric]) -> List[str]:
        """格式化缓存指标

        Args:
            metrics: 缓存指标列表

        Returns:
            格式化后的文本行
        """
        lines = []

        if not metrics:
            return lines

        # 使用最新的缓存指标
        latest = metrics[-1]

        lines.append(f"- 缓存类型: {latest.cache_type}")
        lines.append(f"- 缓存命中率: {latest.hit_rate:.2%}")
        lines.append(f"- 总命中数: {latest.hits}")
        lines.append(f"- 总未命中数: {latest.misses}")
        lines.append(f"- 淘汰次数: {latest.evictions}")
        lines.append(f"- 当前缓存大小: {latest.size}/{latest.max_size}")

        return lines

    def _format_memory_metrics(self, metrics: List[MemoryMetric]) -> List[str]:
        """格式化内存指标

        Args:
            metrics: 内存指标列表

        Returns:
            格式化后的文本行
        """
        lines = []

        if not metrics:
            return lines

        # 按组件分组
        components = {}
        for metric in metrics:
            if metric.component not in components:
                components[metric.component] = []
            components[metric.component].append(metric)

        # 输出每个组件的最新指标
        for component, comp_metrics in components.items():
            latest = comp_metrics[-1]
            lines.append(f"- {component}: {latest.memory_mb:.2f} MB / {latest.max_memory_mb:.2f} MB ({latest.usage_percent:.1f}%)")

        return lines
