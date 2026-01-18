"""自适应缓存

根据访问模式动态调整缓存策略。

创建日期: 2026-01-17
"""
from typing import Any, Dict, Optional
from collections import OrderedDict
import time


class AdaptiveCache:
    """自适应缓存"""

    def __init__(self, initial_size: int = 100):
        self._cache: OrderedDict = OrderedDict()
        self._max_size = initial_size
        self._access_count: Dict[str, int] = {}
        self._last_access: Dict[str, float] = {}

    def get(self, key: str) -> Optional[Any]:
        """获取缓存值"""
        if key in self._cache:
            self._access_count[key] = self._access_count.get(key, 0) + 1
            self._last_access[key] = time.time()
            self._cache.move_to_end(key)
            return self._cache[key]
        return None

    def put(self, key: str, value: Any) -> None:
        """存入缓存"""
        if key in self._cache:
            self._cache.move_to_end(key)
        self._cache[key] = value
        self._access_count[key] = 1
        self._last_access[key] = time.time()
        
        if len(self._cache) > self._max_size:
            self._evict()

    def _evict(self) -> None:
        """驱逐缓存项"""
        # 计算每个键的得分（访问频率 + 时间衰减）
        now = time.time()
        scores = {}
        for key in self._cache:
            freq = self._access_count.get(key, 1)
            age = now - self._last_access.get(key, now)
            scores[key] = freq / (1 + age / 3600)  # 时间衰减
        
        # 移除得分最低的项
        min_key = min(scores, key=scores.get)
        del self._cache[min_key]
        del self._access_count[min_key]
        del self._last_access[min_key]
    def clear(self) -> None:
        """清空缓存"""
        self._cache.clear()
        self._access_count.clear()
        self._last_access.clear()

    def size(self) -> int:
        """获取当前缓存大小"""
        return len(self._cache)

    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        if not self._cache:
            return {
                'size': 0,
                'max_size': self._max_size,
                'hit_rate': 0.0
            }
        
        total_access = sum(self._access_count.values())
        avg_access = total_access / len(self._cache) if self._cache else 0
        
        return {
            'size': len(self._cache),
            'max_size': self._max_size,
            'total_access': total_access,
            'avg_access_per_key': avg_access,
            'most_accessed': max(self._access_count, key=self._access_count.get) if self._access_count else None
        }
