"""访问跟踪器

记录和分析数据访问模式。

创建日期: 2026-01-17
"""
from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class AccessRecord:
    """访问记录

    Attributes:
        key: 访问的键
        timestamp: 访问时间
        hit: 是否命中缓存
    """
    key: str
    timestamp: datetime
    hit: bool


class AccessTracker:
    """访问跟踪器

    记录数据访问历史并分析访问模式。
    """

    def __init__(self, max_history: int = 1000):
        """初始化跟踪器

        Args:
            max_history: 最大历史记录数
        """
        self.max_history = max_history
        self._history: deque = deque(maxlen=max_history)
        self._frequency: Dict[str, int] = {}

    def record_access(self, key: str, hit: bool = False) -> None:
        """记录访问

        Args:
            key: 访问的键
            hit: 是否命中缓存
        """
        record = AccessRecord(
            key=key,
            timestamp=datetime.now(),
            hit=hit
        )
        self._history.append(record)
        
        # 更新频率统计
        self._frequency[key] = self._frequency.get(key, 0) + 1
        
        logger.debug(f"记录访问: {key}, 命中: {hit}")

    def get_history(self, limit: Optional[int] = None) -> List[AccessRecord]:
        """获取访问历史

        Args:
            limit: 返回的最大记录数

        Returns:
            访问记录列表
        """
        if limit is None:
            return list(self._history)
        return list(self._history)[-limit:]

    def get_frequency(self, key: str) -> int:
        """获取访问频率

        Args:
            key: 键

        Returns:
            访问次数
        """
        return self._frequency.get(key, 0)

    def get_top_keys(self, n: int = 10) -> List[tuple]:
        """获取访问频率最高的键

        Args:
            n: 返回的数量

        Returns:
            (键, 频率) 元组列表
        """
        sorted_items = sorted(self._frequency.items(), key=lambda x: x[1], reverse=True)
        return sorted_items[:n]

    def clear(self) -> None:
        """清空历史记录"""
        self._history.clear()
        self._frequency.clear()
        logger.debug("清空访问历史")
