"""ARC 智能缓存淘汰策略

实现 ARC (Adaptive Replacement Cache) 算法，结合访问频率和计算成本。

核心组件：
1. CacheEntry - 缓存项
2. ARCCache - ARC 缓存实现

创建日期: 2026-01-17
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from collections import OrderedDict
from typing import Dict, Optional, Any
import pandas as pd
from .factor_cache import FactorCacheKey


@dataclass
class CacheEntry:
    """缓存项

    存储缓存值及其访问统计信息。
    """
    key: FactorCacheKey
    value: pd.Series
    access_count: int = 0
    last_access_time: float = field(default_factory=time.time)
    compute_cost: float = 1.0  # 计算成本权重
    priority: float = 0.0      # 保留优先级


# 因子计算成本映射表
FACTOR_COMPUTE_COST = {
    # 低成本因子（1x）
    'ema_short_10': 1.0,
    'ema_short_20': 1.0,
    'ema_long_50': 1.0,
    'ema_long_200': 1.0,

    # 中成本因子（5x）
    'sma_10': 5.0,
    'sma_20': 5.0,
    'vol_20': 5.0,
    'rsi_14': 5.0,
    'atr_14': 5.0,

    # 高成本因子（10x）
    'skew_20': 10.0,
    'kurt_20': 10.0,
    'adx_14': 10.0,
}


def get_compute_cost(factor_name: str) -> float:
    """获取因子的计算成本

    Args:
        factor_name: 因子名称

    Returns:
        计算成本权重
    """
    return FACTOR_COMPUTE_COST.get(factor_name, 1.0)


class ARCCache:
    """ARC 自适应缓存

    实现 ARC (Adaptive Replacement Cache) 算法。
    维护 4 个列表：T1、T2、B1、B2。
    """

    def __init__(self, capacity: int):
        """初始化 ARC 缓存

        Args:
            capacity: 缓存容量
        """
        self.capacity = capacity
        self.p = 0  # 自适应参数

        self.t1: OrderedDict[FactorCacheKey, CacheEntry] = OrderedDict()  # 最近访问一次
        self.t2: OrderedDict[FactorCacheKey, CacheEntry] = OrderedDict()  # 最近访问多次
        self.b1: OrderedDict[FactorCacheKey, None] = OrderedDict()  # T1 幽灵列表
        self.b2: OrderedDict[FactorCacheKey, None] = OrderedDict()  # T2 幽灵列表

        # 统计信息
        self._hits = 0
        self._misses = 0

    def get(self, key: FactorCacheKey) -> Optional[pd.Series]:
        """获取缓存项

        Args:
            key: 缓存键

        Returns:
            缓存值，如果不存在则返回 None
        """
        # 情况 1: 在 T1 中命中
        if key in self.t1:
            entry = self.t1.pop(key)
            entry.access_count += 1
            entry.last_access_time = time.time()
            self.t2[key] = entry  # 移动到 T2（频繁访问）
            self._hits += 1
            return entry.value

        # 情况 2: 在 T2 中命中
        if key in self.t2:
            entry = self.t2.pop(key)
            entry.access_count += 1
            entry.last_access_time = time.time()
            self.t2[key] = entry  # 移动到 T2 末尾（LRU 更新）
            self._hits += 1
            return entry.value

        # 缓存未命中
        self._misses += 1
        return None

    def set(self, key: FactorCacheKey, value: pd.Series) -> None:
        """设置缓存项

        Args:
            key: 缓存键
            value: 缓存值
        """
        compute_cost = get_compute_cost(key.factor_name)

        # 情况 1: 在 B1 中（曾经在 T1 中被淘汰）
        if key in self.b1:
            # 增加 p，偏向 LRU（T1）
            delta = max(len(self.b2) // len(self.b1), 1) if len(self.b1) > 0 else 1
            self.p = min(self.p + delta, self.capacity)
            self._replace(key, in_b1=True)
            self.b1.pop(key)
            entry = CacheEntry(key, value, access_count=1, compute_cost=compute_cost)
            entry.last_access_time = time.time()
            self.t2[key] = entry  # 直接放入 T2
            return

        # 情况 2: 在 B2 中（曾经在 T2 中被淘汰）
        if key in self.b2:
            # 减少 p，偏向 LFU（T2）
            delta = max(len(self.b1) // len(self.b2), 1) if len(self.b2) > 0 else 1
            self.p = max(self.p - delta, 0)
            self._replace(key, in_b1=False)
            self.b2.pop(key)
            entry = CacheEntry(key, value, access_count=1, compute_cost=compute_cost)
            entry.last_access_time = time.time()
            self.t2[key] = entry  # 直接放入 T2
            return

        # 情况 3: 全新的键
        if len(self.t1) + len(self.b1) == self.capacity:
            if len(self.t1) < self.capacity:
                self.b1.popitem(last=False)  # 删除 B1 中最旧的
                self._replace(key, in_b1=True)
            else:
                self.t1.popitem(last=False)  # 删除 T1 中最旧的
        elif len(self.t1) + len(self.b1) < self.capacity:
            total = len(self.t1) + len(self.t2) + len(self.b1) + len(self.b2)
            if total >= self.capacity:
                if total == 2 * self.capacity:
                    self.b2.popitem(last=False)  # 删除 B2 中最旧的
                self._replace(key, in_b1=True)

        entry = CacheEntry(key, value, access_count=1, compute_cost=compute_cost)
        entry.last_access_time = time.time()
        self.t1[key] = entry  # 新键放入 T1

    def _replace(self, key: FactorCacheKey, in_b1: bool) -> None:
        """执行缓存替换

        Args:
            key: 缓存键
            in_b1: 是否在 B1 中
        """
        # 情况 1: T1 不为空且满足条件
        if len(self.t1) > 0 and (
            (in_b1 and len(self.t1) == self.p) or
            (len(self.t1) > self.p)
        ):
            # 从 T1 中淘汰
            old_key, old_entry = self.t1.popitem(last=False)
            self.b1[old_key] = None  # 移动到 B1 幽灵列表
        else:
            # 从 T2 中淘汰
            if len(self.t2) > 0:
                old_key, old_entry = self.t2.popitem(last=False)
                self.b2[old_key] = None  # 移动到 B2 幽灵列表

    def hit_rate(self) -> float:
        """计算缓存命中率

        Returns:
            命中率（0-1 之间）
        """
        total = self._hits + self._misses
        if total == 0:
            return 0.0
        return self._hits / total

    def clear(self) -> None:
        """清空缓存"""
        self.t1.clear()
        self.t2.clear()
        self.b1.clear()
        self.b2.clear()
        self.p = 0
        self._hits = 0
        self._misses = 0

    def __len__(self) -> int:
        """返回缓存中的项数"""
        return len(self.t1) + len(self.t2)

    def __contains__(self, key: FactorCacheKey) -> bool:
        """检查键是否在缓存中"""
        return key in self.t1 or key in self.t2
