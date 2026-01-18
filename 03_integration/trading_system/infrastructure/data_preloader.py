"""数据预加载与批处理优化模块

提供数据预加载、缓存和批处理能力，减少重复 I/O 操作。
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class PreloadConfig:
    """预加载配置"""
    enabled: bool = True  # 是否启用预加载
    cache_size: int = 100  # 缓存的数据集数量
    preload_window: int = 1000  # 预加载的数据窗口大小（行数）
    batch_size: int = 50  # 批处理大小
    ttl_seconds: int = 3600  # 缓存过期时间（秒）


class DataPreloader:
    """数据预加载器

    功能：
    1. 预加载历史数据到内存
    2. 批量处理多个交易对
    3. 缓存计算结果
    """

    def __init__(self, config: Optional[PreloadConfig] = None):
        self._config = config or PreloadConfig()
        self._cache: dict[str, tuple[pd.DataFrame, datetime]] = {}

    def preload_data(
        self,
        pair: str,
        timeframe: str,
        data_loader,
        start_time: Optional[datetime] = None,
    ) -> pd.DataFrame:
        """预加载数据

        Args:
            pair: 交易对
            timeframe: 时间周期
            data_loader: 数据加载器函数
            start_time: 起始时间

        Returns:
            预加载的数据
        """
        if not self._config.enabled:
            return data_loader(pair, timeframe, start_time)

        cache_key = f"{pair}_{timeframe}"

        # 检查缓存
        if cache_key in self._cache:
            cached_data, cached_time = self._cache[cache_key]
            # 检查缓存是否过期
            if (datetime.now() - cached_time).total_seconds() < self._config.ttl_seconds:
                logger.debug(f"使用缓存数据: {cache_key}")
                return cached_data

        # 加载数据
        logger.debug(f"预加载数据: {cache_key}")
        data = data_loader(pair, timeframe, start_time)

        # 缓存数据
        self._cache[cache_key] = (data, datetime.now())

        # 清理过期缓存
        self._cleanup_cache()

        return data

    def batch_preload(
        self,
        pairs: list[str],
        timeframe: str,
        data_loader,
        start_time: Optional[datetime] = None,
    ) -> dict[str, pd.DataFrame]:
        """批量预加载多个交易对的数据

        Args:
            pairs: 交易对列表
            timeframe: 时间周期
            data_loader: 数据加载器函数
            start_time: 起始时间

        Returns:
            交易对到数据的字典
        """
        results = {}
        for pair in pairs:
            try:
                results[pair] = self.preload_data(pair, timeframe, data_loader, start_time)
            except Exception as e:
                logger.error(f"预加载 {pair} 数据失败: {e}")
                results[pair] = pd.DataFrame()
        return results

    def _cleanup_cache(self) -> None:
        """清理过期缓存"""
        if len(self._cache) <= self._config.cache_size:
            return

        # 按时间排序，删除最旧的缓存
        sorted_items = sorted(
            self._cache.items(),
            key=lambda x: x[1][1],  # 按缓存时间排序
        )

        # 保留最新的 cache_size 个
        to_keep = dict(sorted_items[-self._config.cache_size:])
        self._cache = to_keep

    def clear_cache(self) -> None:
        """清空所有缓存"""
        self._cache.clear()

    def get_cache_stats(self) -> dict:
        """获取缓存统计信息"""
        return {
            "cache_size": len(self._cache),
            "max_cache_size": self._config.cache_size,
            "cached_keys": list(self._cache.keys()),
        }