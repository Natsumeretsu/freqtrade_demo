"""对象池实现

提供通用对象池功能，支持对象复用。

创建日期: 2026-01-17
"""
from __future__ import annotations

import logging
import threading
from typing import Any, Callable, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class ObjectPool:
    """对象池

    管理可复用对象，减少对象创建和销毁开销。
    """

    def __init__(
        self,
        factory: Callable[[], Any],
        reset_func: Optional[Callable[[Any], None]] = None,
        max_size: int = 50,
        initial_size: int = 5
    ):
        """初始化对象池

        Args:
            factory: 对象工厂函数
            reset_func: 对象重置函数
            max_size: 最大池大小
            initial_size: 初始池大小
        """
        self.factory = factory
        self.reset_func = reset_func
        self.max_size = max_size
        self.initial_size = initial_size

        self._pool: List[Any] = []
        self._in_use: set = set()
        self._lock = threading.Lock()
        self._stats = {
            'total_created': 0,
            'total_acquired': 0,
            'total_released': 0,
            'current_in_use': 0
        }

        # 预创建初始对象
        self._create_objects(initial_size)
        logger.info(f"对象池初始化: initial_size={initial_size}, max_size={max_size}")

    def _create_objects(self, count: int) -> None:
        """创建对象

        Args:
            count: 要创建的对象数量
        """
        for _ in range(count):
            if len(self._pool) + len(self._in_use) >= self.max_size:
                logger.warning(f"达到最大对象数量: {self.max_size}")
                break
            try:
                obj = self.factory()
                self._pool.append(obj)
                self._stats['total_created'] += 1
            except Exception as e:
                logger.error(f"创建对象失败: {e}")
        logger.debug(f"创建了 {count} 个对象")

    def acquire(self) -> Optional[Any]:
        """获取对象

        Returns:
            对象实例，如果池为空且无法创建则返回None
        """
        with self._lock:
            # 如果池为空，尝试创建新对象
            if not self._pool:
                if len(self._in_use) < self.max_size:
                    self._create_objects(1)
                else:
                    logger.warning("对象池已满且无可用对象")
                    return None

            # 从池中获取对象
            if self._pool:
                obj = self._pool.pop()
                self._in_use.add(id(obj))
                self._stats['total_acquired'] += 1
                self._stats['current_in_use'] = len(self._in_use)
                logger.debug(f"获取对象: 当前使用 {len(self._in_use)}")
                return obj

            return None

    def release(self, obj: Any) -> None:
        """归还对象

        Args:
            obj: 要归还的对象
        """
        with self._lock:
            obj_id = id(obj)
            if obj_id not in self._in_use:
                logger.warning("尝试归还未分配的对象")
                return

            # 重置对象状态
            if self.reset_func:
                try:
                    self.reset_func(obj)
                except Exception as e:
                    logger.error(f"重置对象失败: {e}")

            # 归还到池中
            self._in_use.remove(obj_id)
            self._pool.append(obj)
            self._stats['total_released'] += 1
            self._stats['current_in_use'] = len(self._in_use)
            logger.debug(f"归还对象: 当前使用 {len(self._in_use)}")

    def clear(self) -> None:
        """清空对象池"""
        with self._lock:
            self._pool.clear()
            self._in_use.clear()
            self._stats['current_in_use'] = 0
            logger.info("对象池已清空")

    def get_pool_size(self) -> int:
        """获取池中可用对象数量

        Returns:
            可用对象数量
        """
        with self._lock:
            return len(self._pool)

    def get_stats(self) -> dict:
        """获取对象池统计信息

        Returns:
            统计信息字典
        """
        with self._lock:
            stats = self._stats.copy()
            stats['pool_size'] = len(self._pool)
            stats['in_use'] = len(self._in_use)
            return stats
