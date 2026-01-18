"""内存使用优化模块

提供内存监控、优化和管理功能，减少内存占用。
"""
from __future__ import annotations

import gc
import logging
from dataclasses import dataclass
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class MemoryConfig:
    """内存优化配置"""
    enabled: bool = True  # 是否启用内存优化
    auto_gc: bool = True  # 自动垃圾回收
    downcast_numeric: bool = True  # 降低数值类型精度
    use_categorical: bool = True  # 使用分类类型
    chunk_size: int = 10000  # 分块处理大小


class MemoryOptimizer:
    """内存优化器

    功能：
    1. 自动降低数值类型精度
    2. 使用分类类型优化字符串
    3. 自动垃圾回收
    4. 分块处理大数据集
    """

    def __init__(self, config: Optional[MemoryConfig] = None):
        self._config = config or MemoryConfig()

    def optimize_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """优化 DataFrame 内存占用

        Args:
            df: 原始 DataFrame

        Returns:
            优化后的 DataFrame
        """
        if not self._config.enabled or df.empty:
            return df

        original_memory = df.memory_usage(deep=True).sum() / 1024 / 1024
        logger.debug(f"原始内存占用: {original_memory:.2f} MB")

        # 降低数值类型精度
        if self._config.downcast_numeric:
            df = self._downcast_numeric(df)

        # 使用分类类型
        if self._config.use_categorical:
            df = self._use_categorical(df)

        optimized_memory = df.memory_usage(deep=True).sum() / 1024 / 1024
        reduction = (1 - optimized_memory / original_memory) * 100

        logger.debug(f"优化后内存占用: {optimized_memory:.2f} MB")
        logger.debug(f"内存减少: {reduction:.1f}%")

        return df

    def trigger_gc(self) -> None:
        """触发垃圾回收"""
        if self._config.auto_gc:
            gc.collect()
            logger.debug("已触发垃圾回收")

    def get_memory_usage(self) -> dict:
        """获取当前内存使用情况"""
        import psutil
        import os

        process = psutil.Process(os.getpid())
        memory_info = process.memory_info()

        return {
            "rss_mb": memory_info.rss / 1024 / 1024,  # 物理内存
            "vms_mb": memory_info.vms / 1024 / 1024,  # 虚拟内存
        }

    def _downcast_numeric(self, df: pd.DataFrame) -> pd.DataFrame:
        """降低数值类型精度"""
        for col in df.select_dtypes(include=['float']).columns:
            df[col] = pd.to_numeric(df[col], downcast='float')

        for col in df.select_dtypes(include=['int']).columns:
            df[col] = pd.to_numeric(df[col], downcast='integer')

        return df

    def _use_categorical(self, df: pd.DataFrame) -> pd.DataFrame:
        """使用分类类型优化字符串列"""
        for col in df.select_dtypes(include=['object']).columns:
            num_unique = df[col].nunique()
            num_total = len(df[col])
            # 如果唯一值比例 < 50%，转换为分类类型
            if num_unique / num_total < 0.5:
                df[col] = df[col].astype('category')

        return df
