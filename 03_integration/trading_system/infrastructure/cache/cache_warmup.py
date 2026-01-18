"""缓存预热

提供缓存预热和过期策略。

创建日期: 2026-01-17
"""
from typing import Dict, Any, Callable, Optional
from datetime import datetime, timedelta
import threading


class CacheWarmup:
    """缓存预热管理器"""

    def __init__(self, cache):
        self.cache = cache
        self._warmup_data: Dict[str, Callable] = {}

    def register(self, key: str, loader: Callable) -> None:
        """注册预热数据加载器"""
        self._warmup_data[key] = loader

    def warmup(self) -> None:
        """执行缓存预热"""
        for key, loader in self._warmup_data.items():
            value = loader()
            self.cache.put(key, value)


class CacheExpiration:
    """缓存过期管理器"""

    def __init__(self, cache):
        self.cache = cache
        self._expiration: Dict[str, datetime] = {}
        self._ttl: Dict[str, int] = {}

    def set_ttl(self, key: str, ttl_seconds: int) -> None:
        """设置键的过期时间（秒）"""
        self._ttl[key] = ttl_seconds
        self._expiration[key] = datetime.now() + timedelta(seconds=ttl_seconds)

    def is_expired(self, key: str) -> bool:
        """检查键是否过期"""
        if key not in self._expiration:
            return False
        return datetime.now() > self._expiration[key]

    def cleanup_expired(self) -> int:
        """清理过期的缓存项"""
        expired_keys = [k for k in self._expiration.keys() if self.is_expired(k)]
        for key in expired_keys:
            if key in self.cache._cache:
                del self.cache._cache[key]
            del self._expiration[key]
            if key in self._ttl:
                del self._ttl[key]
        return len(expired_keys)
