"""指标存储器

使用内存存储性能指标，支持查询和导出。

创建日期: 2026-01-17
"""
from __future__ import annotations

import logging
from collections import deque
from datetime import datetime
from typing import Optional, List
from .metrics_collector import TimingMetric, CacheMetric, MemoryMetric

logger = logging.getLogger(__name__)


class MetricsStorage:
    """指标存储器

    使用 deque 存储最近的指标数据。
    """

    def __init__(self, max_records: int = 10000):
        """初始化指标存储器

        Args:
            max_records: 最大记录数
        """
        self.max_records = max_records
        self._timing_records: deque[TimingMetric] = deque(maxlen=max_records)
        self._cache_records: deque[CacheMetric] = deque(maxlen=max_records)
        self._memory_records: deque[MemoryMetric] = deque(maxlen=max_records)
        self._start_time: Optional[datetime] = None

    def store_timing(self, metric: TimingMetric) -> None:
        """存储时间指标

        Args:
            metric: 时间指标
        """
        if self._start_time is None:
            self._start_time = metric.start_time
        self._timing_records.append(metric)

    def store_cache(self, metric: CacheMetric) -> None:
        """存储缓存指标

        Args:
            metric: 缓存指标
        """
        if self._start_time is None:
            self._start_time = metric.timestamp
        self._cache_records.append(metric)

    def store_memory(self, metric: MemoryMetric) -> None:
        """存储内存指标

        Args:
            metric: 内存指标
        """
        if self._start_time is None:
            self._start_time = metric.timestamp
        self._memory_records.append(metric)

    def get_timing_records(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> List[TimingMetric]:
        """获取时间记录

        Args:
            start_time: 开始时间
            end_time: 结束时间

        Returns:
            时间记录列表
        """
        records = list(self._timing_records)

        if start_time:
            records = [r for r in records if r.start_time >= start_time]
        if end_time:
            records = [r for r in records if r.end_time <= end_time]

        return records

    def get_cache_records(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> List[CacheMetric]:
        """获取缓存记录

        Args:
            start_time: 开始时间
            end_time: 结束时间

        Returns:
            缓存记录列表
        """
        records = list(self._cache_records)

        if start_time:
            records = [r for r in records if r.timestamp >= start_time]
        if end_time:
            records = [r for r in records if r.timestamp <= end_time]

        return records

    def get_memory_records(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> List[MemoryMetric]:
        """获取内存记录

        Args:
            start_time: 开始时间
            end_time: 结束时间

        Returns:
            内存记录列表
        """
        records = list(self._memory_records)

        if start_time:
            records = [r for r in records if r.timestamp >= start_time]
        if end_time:
            records = [r for r in records if r.timestamp <= end_time]

        return records

    def get_start_time(self) -> Optional[datetime]:
        """获取监控开始时间"""
        return self._start_time

    def get_record_count(self) -> dict:
        """获取记录数量统计

        Returns:
            记录数量字典
        """
        return {
            "timing": len(self._timing_records),
            "cache": len(self._cache_records),
            "memory": len(self._memory_records),
            "total": len(self._timing_records) + len(self._cache_records) + len(self._memory_records)
        }

    def clear(self) -> None:
        """清空所有记录"""
        self._timing_records.clear()
        self._cache_records.clear()
        self._memory_records.clear()
        self._start_time = None
        logger.info("已清空所有监控记录")
