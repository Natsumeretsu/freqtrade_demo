"""数据预加载器

在因子计算前提前加载所需的历史数据，避免计算时的 I/O 等待。

核心组件：
1. DataPrefetcher - 数据预加载器
2. TimeWindowStrategy - 时间窗口策略
3. DataBuffer - 数据缓冲区

创建日期: 2026-01-17
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple
import pandas as pd

logger = logging.getLogger(__name__)


class TimeWindowStrategy:
    """时间窗口预加载策略

    预加载最近 N 天的数据。
    """

    def __init__(self, window_days: int = 7):
        """初始化时间窗口策略

        Args:
            window_days: 预加载窗口天数
        """
        self.window_days = window_days

    def get_prefetch_range(self, current_time: datetime) -> Tuple[datetime, datetime]:
        """获取预加载时间范围

        Args:
            current_time: 当前时间

        Returns:
            (开始时间, 结束时间)
        """
        end_time = current_time
        start_time = current_time - timedelta(days=self.window_days)
        return start_time, end_time


class DataBuffer:
    """数据缓冲区

    管理预加载的数据。
    """

    def __init__(self, max_size_mb: int = 500):
        """初始化数据缓冲区

        Args:
            max_size_mb: 最大缓冲区大小（MB）
        """
        self.max_size_mb = max_size_mb
        self._buffer: Dict[str, pd.DataFrame] = {}
        self._access_time: Dict[str, datetime] = {}

    def get(self, key: str) -> Optional[pd.DataFrame]:
        """获取缓冲数据

        Args:
            key: 缓冲键

        Returns:
            数据，如果不存在则返回 None
        """
        if key in self._buffer:
            self._access_time[key] = datetime.now()
            return self._buffer[key].copy()
        return None

    def set(self, key: str, data: pd.DataFrame) -> None:
        """设置缓冲数据

        Args:
            key: 缓冲键
            data: 数据
        """
        # 检查缓冲区大小
        current_size = self._get_buffer_size_mb()
        data_size = data.memory_usage(deep=True).sum() / (1024 * 1024)

        # 如果超过限制，清理最久未访问的数据
        while current_size + data_size > self.max_size_mb and self._buffer:
            oldest_key = min(self._access_time, key=self._access_time.get)
            del self._buffer[oldest_key]
            del self._access_time[oldest_key]
            current_size = self._get_buffer_size_mb()

        self._buffer[key] = data.copy()
        self._access_time[key] = datetime.now()

    def _get_buffer_size_mb(self) -> float:
        """获取当前缓冲区大小（MB）"""
        total_size = 0
        for data in self._buffer.values():
            total_size += data.memory_usage(deep=True).sum()
        return total_size / (1024 * 1024)

    def clear(self) -> None:
        """清空缓冲区"""
        self._buffer.clear()
        self._access_time.clear()


class DataPrefetcher:
    """数据预加载器

    在因子计算前提前加载所需的历史数据。
    """

    def __init__(
        self,
        strategy: TimeWindowStrategy,
        max_buffer_size: int = 500
    ):
        """初始化数据预加载器

        Args:
            strategy: 预加载策略
            max_buffer_size: 最大缓冲区大小（MB）
        """
        self.strategy = strategy
        self.buffer = DataBuffer(max_size_mb=max_buffer_size)
        self._enabled = False

    def prefetch(self, pair: str, timeframe: str, data_loader) -> None:
        """预加载数据

        Args:
            pair: 交易对
            timeframe: 时间周期
            data_loader: 数据加载函数
        """
        if not self._enabled:
            return

        # 获取预加载时间范围
        current_time = datetime.now()
        start_time, end_time = self.strategy.get_prefetch_range(current_time)

        # 生成缓冲键
        key = f"{pair}_{timeframe}"

        # 加载数据
        try:
            data = data_loader(pair, timeframe, start_time, end_time)
            self.buffer.set(key, data)
            logger.info(f"预加载数据成功: {key}, 数据量: {len(data)} 行")
        except Exception as e:
            logger.warning(f"预加载数据失败: {key}, 错误: {e}")

    def get_data(self, pair: str, timeframe: str) -> Optional[pd.DataFrame]:
        """获取预加载的数据

        Args:
            pair: 交易对
            timeframe: 时间周期

        Returns:
            预加载的数据，如果不存在则返回 None
        """
        key = f"{pair}_{timeframe}"
        return self.buffer.get(key)

    def start(self) -> None:
        """启动预加载"""
        self._enabled = True
        logger.info("数据预加载器已启动")

    def stop(self) -> None:
        """停止预加载"""
        self._enabled = False
        logger.info("数据预加载器已停止")

    def clear(self) -> None:
        """清空缓冲区"""
        self.buffer.clear()
        logger.info("数据预加载缓冲区已清空")
