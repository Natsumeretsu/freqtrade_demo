"""因子缓存层

提供因子计算结果的缓存功能，避免重复计算。
"""
from __future__ import annotations

import logging
import pickle
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Callable

import pandas as pd

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class FactorCacheKey:
    """因子缓存键

    使用 (pair, timeframe, factor_name, end_timestamp) 作为唯一标识。
    """
    pair: str              # 交易对，如 "BTC/USDT"
    timeframe: str         # 时间周期，如 "1h"
    factor_name: str       # 因子名称，如 "ema_20"
    end_timestamp: int     # 数据截止时间戳

    def __hash__(self) -> int:
        return hash((self.pair, self.timeframe, self.factor_name, self.end_timestamp))


class FactorCache:
    """因子缓存层

    支持 LRU 和 ARC 两种缓存策略。
    """

    def __init__(self, max_size: int = 1000, strategy: str = "lru"):
        """初始化缓存

        Args:
            max_size: 最大缓存条目数
            strategy: 缓存策略，"lru" 或 "arc"
        """
        self._max_size = max_size
        self._strategy = strategy.lower()

        if self._strategy == "arc":
            # 使用 ARC 缓存
            from .arc_cache import ARCCache
            self._arc_cache = ARCCache(capacity=max_size)
            self._cache = None
            self._access_order = None
        else:
            # 使用 LRU 缓存
            self._cache: Dict[FactorCacheKey, pd.Series] = {}
            self._access_order: list[FactorCacheKey] = []
            self._arc_cache = None

        self._hits = 0
        self._misses = 0

    def get(self, key: FactorCacheKey) -> Optional[pd.Series]:
        """获取缓存的因子值

        Args:
            key: 缓存键

        Returns:
            缓存的因子值，如果未命中则返回 None
        """
        if self._strategy == "arc":
            # 使用 ARC 缓存
            result = self._arc_cache.get(key)
            if result is not None:
                self._hits += 1
                return result.copy()
            else:
                self._misses += 1
                return None
        else:
            # 使用 LRU 缓存
            if key in self._cache:
                self._hits += 1
                # 更新访问顺序（LRU）
                if key in self._access_order:
                    self._access_order.remove(key)
                self._access_order.append(key)
                return self._cache[key].copy()

            self._misses += 1
            return None

    def set(self, key: FactorCacheKey, value: pd.Series) -> None:
        """设置缓存的因子值

        Args:
            key: 缓存键
            value: 因子值
        """
        if self._strategy == "arc":
            # 使用 ARC 缓存
            self._arc_cache.set(key, value.copy())
        else:
            # 使用 LRU 缓存
            # 如果缓存已满，移除最久未使用的条目
            if len(self._cache) >= self._max_size and key not in self._cache:
                if self._access_order:
                    oldest_key = self._access_order.pop(0)
                    del self._cache[oldest_key]

            self._cache[key] = value.copy()

            # 更新访问顺序
            if key in self._access_order:
                self._access_order.remove(key)
            self._access_order.append(key)

    def get_hit_rate(self) -> float:
        """获取缓存命中率

        Returns:
            命中率（0.0-1.0）
        """
        if self._strategy == "arc":
            return self._arc_cache.hit_rate()
        else:
            total = self._hits + self._misses
            return self._hits / total if total > 0 else 0.0

    def get_stats(self) -> dict:
        """获取缓存统计信息

        Returns:
            包含命中数、未命中数、命中率、缓存大小的字典
        """
        if self._strategy == "arc":
            return {
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": self.get_hit_rate(),
                "cache_size": len(self._arc_cache),
                "max_size": self._max_size,
                "strategy": "arc",
                "t1_size": len(self._arc_cache.t1),
                "t2_size": len(self._arc_cache.t2),
                "p": self._arc_cache.p
            }
        else:
            return {
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": self.get_hit_rate(),
                "cache_size": len(self._cache),
                "max_size": self._max_size,
                "strategy": "lru"
            }

    def clear(self) -> None:
        """清空缓存"""
        if self._strategy == "arc":
            self._arc_cache.clear()
        else:
            self._cache.clear()
            self._access_order.clear()
        self._hits = 0
        self._misses = 0

    def __len__(self) -> int:
        """返回当前缓存条目数"""
        if self._strategy == "arc":
            return len(self._arc_cache)
        else:
            return len(self._cache)

    def warmup(
        self,
        data: pd.DataFrame,
        factor_names: list[str],
        compute_func: Callable[[pd.DataFrame, str], pd.Series],
        pair: str = "UNKNOWN",
        timeframe: str = "1h"
    ) -> None:
        """缓存预热：预计算常用因子并存入缓存

        Args:
            data: OHLCV 数据
            factor_names: 需要预热的因子列表
            compute_func: 因子计算函数
            pair: 交易对名称
            timeframe: 时间周期
        """
        logger.info(f"开始缓存预热: {len(factor_names)} 个因子")

        end_timestamp = int(data.index[-1].timestamp()) if hasattr(data.index[-1], 'timestamp') else 0

        for factor_name in factor_names:
            cache_key = FactorCacheKey(
                pair=pair,
                timeframe=timeframe,
                factor_name=factor_name,
                end_timestamp=end_timestamp
            )

            # 如果已在缓存中，跳过
            if cache_key in self._cache:
                continue

            try:
                factor_value = compute_func(data, factor_name)
                self.set(cache_key, factor_value)
                logger.debug(f"预热因子: {factor_name}")
            except Exception as e:
                logger.warning(f"预热因子 {factor_name} 失败: {e}")

        logger.info(f"缓存预热完成: {len(self._cache)}/{self._max_size}")

    def save_to_disk(self, filepath: str | Path) -> None:
        """将缓存保存到磁盘

        Args:
            filepath: 保存路径
        """
        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)

        with open(filepath, 'wb') as f:
            pickle.dump({
                'cache': self._cache,
                'access_order': self._access_order,
                'hits': self._hits,
                'misses': self._misses
            }, f)

        logger.info(f"缓存已保存到: {filepath}")

    def load_from_disk(self, filepath: str | Path) -> bool:
        """从磁盘加载缓存

        Args:
            filepath: 加载路径

        Returns:
            是否加载成功
        """
        filepath = Path(filepath)

        if not filepath.exists():
            logger.warning(f"缓存文件不存在: {filepath}")
            return False

        try:
            with open(filepath, 'rb') as f:
                data = pickle.load(f)

            self._cache = data['cache']
            self._access_order = data['access_order']
            self._hits = data['hits']
            self._misses = data['misses']

            logger.info(f"缓存已从磁盘加载: {len(self._cache)} 个条目")
            return True
        except Exception as e:
            logger.error(f"加载缓存失败: {e}")
            return False
