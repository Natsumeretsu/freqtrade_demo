"""内存池基类

提供内存池的基础功能。

创建日期: 2026-01-17
"""
from __future__ import annotations

import logging
import threading
from typing import Any, Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class MemoryPool:
    """内存池基类

    管理固定大小的内存块，支持获取和归还操作。
    """

    def __init__(
        self,
        block_size: int,
        initial_blocks: int = 10,
        max_blocks: int = 100,
        auto_expand: bool = True
    ):
        """初始化内存池

        Args:
            block_size: 内存块大小（字节）
            initial_blocks: 初始内存块数量
            max_blocks: 最大内存块数量
            auto_expand: 是否自动扩容
        """
        self.block_size = block_size
        self.initial_blocks = initial_blocks
        self.max_blocks = max_blocks
        self.auto_expand = auto_expand

        self._pool: List[bytearray] = []
        self._in_use: set = set()
        self._lock = threading.Lock()
        self._stats = {
            'total_allocated': 0,
            'total_released': 0,
            'current_in_use': 0,
            'peak_usage': 0,
            'expand_count': 0
        }

        # 预分配初始内存块
        self._allocate_blocks(initial_blocks)
        logger.info(f"内存池初始化: block_size={block_size}, initial_blocks={initial_blocks}")

    def _allocate_blocks(self, count: int) -> None:
        """分配内存块

        Args:
            count: 要分配的内存块数量
        """
        for _ in range(count):
            if len(self._pool) + len(self._in_use) >= self.max_blocks:
                logger.warning(f"达到最大内存块数量: {self.max_blocks}")
                break
            block = bytearray(self.block_size)
            self._pool.append(block)
        logger.debug(f"分配了 {count} 个内存块")

    def acquire(self) -> Optional[bytearray]:
        """获取内存块

        Returns:
            内存块，如果池为空且无法扩容则返回None
        """
        with self._lock:
            # 如果池为空且允许自动扩容
            if not self._pool and self.auto_expand:
                expand_size = min(self.initial_blocks, 
                                self.max_blocks - len(self._in_use))
                if expand_size > 0:
                    self._allocate_blocks(expand_size)
                    self._stats['expand_count'] += 1
                    logger.debug(f"自动扩容: 新增 {expand_size} 个内存块")

            # 从池中获取内存块
            if self._pool:
                block = self._pool.pop()
                self._in_use.add(id(block))
                self._stats['total_allocated'] += 1
                self._stats['current_in_use'] = len(self._in_use)
                self._stats['peak_usage'] = max(
                    self._stats['peak_usage'],
                    self._stats['current_in_use']
                )
                logger.debug(f"获取内存块: 当前使用 {len(self._in_use)}")
                return block

            logger.warning("内存池已空且无法扩容")
            return None

    def release(self, block: bytearray) -> None:
        """归还内存块

        Args:
            block: 要归还的内存块
        """
        with self._lock:
            block_id = id(block)
            if block_id not in self._in_use:
                logger.warning("尝试归还未分配的内存块")
                return

            # 清空内存块内容
            block[:] = b'\x00' * len(block)

            # 归还到池中
            self._in_use.remove(block_id)
            self._pool.append(block)
            self._stats['total_released'] += 1
            self._stats['current_in_use'] = len(self._in_use)
            logger.debug(f"归还内存块: 当前使用 {len(self._in_use)}")

    def clear(self) -> None:
        """清空内存池"""
        with self._lock:
            self._pool.clear()
            self._in_use.clear()
            self._stats['current_in_use'] = 0
            logger.info("内存池已清空")

    def get_stats(self) -> Dict[str, int]:
        """获取内存池统计信息

        Returns:
            统计信息字典
        """
        with self._lock:
            stats = self._stats.copy()
            stats['pool_size'] = len(self._pool)
            stats['in_use'] = len(self._in_use)
            stats['total_capacity'] = len(self._pool) + len(self._in_use)
            return stats

    def get_usage_rate(self) -> float:
        """获取内存池使用率

        Returns:
            使用率（0.0-1.0）
        """
        with self._lock:
            total = len(self._pool) + len(self._in_use)
            if total == 0:
                return 0.0
            return len(self._in_use) / total
