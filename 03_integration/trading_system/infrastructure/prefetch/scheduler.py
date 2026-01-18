"""预取调度器

管理数据预取任务的调度和执行。

创建日期: 2026-01-17
"""
from __future__ import annotations

import logging
from typing import Callable, List, Optional, Any

logger = logging.getLogger(__name__)


class PrefetchScheduler:
    """预取调度器

    调度和执行数据预取任务。
    """

    def __init__(self, loader: Optional[Callable] = None):
        """初始化调度器

        Args:
            loader: 数据加载函数
        """
        self.loader = loader
        self._prefetch_queue: List[str] = []
        self._prefetched_data: dict = {}

    def schedule_prefetch(self, keys: List[str]) -> None:
        """调度预取任务

        Args:
            keys: 需要预取的键列表
        """
        for key in keys:
            if key not in self._prefetch_queue and key not in self._prefetched_data:
                self._prefetch_queue.append(key)
                logger.debug(f"调度预取: {key}")

    def execute_prefetch(self, max_items: int = 5) -> int:
        """执行预取任务

        Args:
            max_items: 最大预取数量

        Returns:
            实际预取的数量
        """
        if not self.loader:
            logger.warning("未设置数据加载函数，跳过预取")
            return 0

        count = 0
        while self._prefetch_queue and count < max_items:
            key = self._prefetch_queue.pop(0)
            try:
                data = self.loader(key)
                self._prefetched_data[key] = data
                count += 1
                logger.debug(f"预取完成: {key}")
            except Exception as e:
                logger.error(f"预取失败: {key}, 错误: {e}")

        return count

    def get_prefetched(self, key: str) -> Optional[Any]:
        """获取预取的数据

        Args:
            key: 键

        Returns:
            预取的数据（如果存在）
        """
        return self._prefetched_data.pop(key, None)

    def clear(self) -> None:
        """清空预取队列和缓存"""
        self._prefetch_queue.clear()
        self._prefetched_data.clear()
        logger.debug("清空预取队列")

    def get_queue_size(self) -> int:
        """获取预取队列大小

        Returns:
            队列中的任务数量
        """
        return len(self._prefetch_queue)
