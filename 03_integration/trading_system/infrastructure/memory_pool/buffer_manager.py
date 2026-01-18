"""缓冲区管理器

管理NumPy数组缓冲区，支持不同大小和类型的缓冲区复用。

创建日期: 2026-01-17
"""
from __future__ import annotations

import logging
import threading
from typing import Dict, List, Tuple
from datetime import datetime
import numpy as np

logger = logging.getLogger(__name__)


class BufferManager:
    """缓冲区管理器

    管理NumPy数组缓冲区，支持按大小和类型分类管理。
    """

    def __init__(self, max_buffers: int = 100):
        """初始化缓冲区管理器

        Args:
            max_buffers: 最大缓冲区数量
        """
        self.max_buffers = max_buffers

        # 按 (size, dtype) 分类存储缓冲区
        self._buffers: Dict[Tuple[int, str], List[np.ndarray]] = {}
        self._in_use: set = set()
        self._timestamps: Dict[int, datetime] = {}
        self._lock = threading.Lock()
        self._stats = {
            'total_allocated': 0,
            'total_released': 0,
            'total_cleared': 0,
            'current_in_use': 0
        }

        logger.info(f"缓冲区管理器初始化: max_buffers={max_buffers}")

    def get_buffer(self, size: int, dtype: str = 'float64') -> np.ndarray:
        """获取缓冲区

        Args:
            size: 缓冲区大小（元素数量）
            dtype: 数据类型

        Returns:
            NumPy数组缓冲区
        """
        key = (size, dtype)

        with self._lock:
            # 尝试从池中获取
            if key in self._buffers and self._buffers[key]:
                buffer = self._buffers[key].pop()
                self._in_use.add(id(buffer))
                self._timestamps[id(buffer)] = datetime.now()
                self._stats['total_allocated'] += 1
                self._stats['current_in_use'] = len(self._in_use)
                logger.debug(f"获取缓冲区: size={size}, dtype={dtype}")
                return buffer

            # 创建新缓冲区
            if len(self._in_use) < self.max_buffers:
                buffer = np.zeros(size, dtype=dtype)
                self._in_use.add(id(buffer))
                self._timestamps[id(buffer)] = datetime.now()
                self._stats['total_allocated'] += 1
                self._stats['current_in_use'] = len(self._in_use)
                logger.debug(f"创建新缓冲区: size={size}, dtype={dtype}")
                return buffer

            logger.warning("缓冲区已满，无法分配")
            # 返回临时缓冲区（不纳入管理）
            return np.zeros(size, dtype=dtype)

    def release_buffer(self, buffer: np.ndarray) -> None:
        """释放缓冲区

        Args:
            buffer: 要释放的缓冲区
        """
        with self._lock:
            buffer_id = id(buffer)
            if buffer_id not in self._in_use:
                logger.warning("尝试释放未分配的缓冲区")
                return

            # 清空缓冲区内容
            buffer[:] = 0

            # 归还到池中
            key = (buffer.size, str(buffer.dtype))
            if key not in self._buffers:
                self._buffers[key] = []
            self._buffers[key].append(buffer)

            self._in_use.remove(buffer_id)
            self._timestamps.pop(buffer_id, None)
            self._stats['total_released'] += 1
            self._stats['current_in_use'] = len(self._in_use)
            logger.debug(f"释放缓冲区: size={buffer.size}, dtype={buffer.dtype}")

    def clear_unused(self, max_age: float = 60.0) -> int:
        """清理未使用的缓冲区

        Args:
            max_age: 最大闲置时间（秒）

        Returns:
            清理的缓冲区数量
        """
        with self._lock:
            now = datetime.now()
            cleared = 0

            # 清理每个类型的缓冲区池
            for key in list(self._buffers.keys()):
                buffers = self._buffers[key]
                # 保留最近使用的缓冲区
                self._buffers[key] = [
                    buf for buf in buffers
                    if (now - self._timestamps.get(id(buf), now)).total_seconds() < max_age
                ]
                cleared += len(buffers) - len(self._buffers[key])

            self._stats['total_cleared'] += cleared
            logger.info(f"清理了 {cleared} 个未使用的缓冲区")
            return cleared

    def clear_all(self) -> None:
        """清空所有缓冲区"""
        with self._lock:
            self._buffers.clear()
            self._in_use.clear()
            self._timestamps.clear()
            self._stats['current_in_use'] = 0
            logger.info("所有缓冲区已清空")

    def get_stats(self) -> dict:
        """获取缓冲区统计信息

        Returns:
            统计信息字典
        """
        with self._lock:
            stats = self._stats.copy()
            stats['total_buffers'] = sum(len(buffers) for buffers in self._buffers.values())
            stats['in_use'] = len(self._in_use)
            stats['buffer_types'] = len(self._buffers)
            return stats
