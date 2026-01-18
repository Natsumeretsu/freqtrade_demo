"""因子缓存层单元测试"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "03_integration"))

from trading_system.infrastructure.factor_engines.factor_cache import (
    FactorCache,
    FactorCacheKey,
)


class TestFactorCache(unittest.TestCase):
    def test_cache_key_equality(self) -> None:
        """测试缓存键的相等性"""
        key1 = FactorCacheKey("BTC/USDT", "1h", "ema_20", 1000)
        key2 = FactorCacheKey("BTC/USDT", "1h", "ema_20", 1000)
        key3 = FactorCacheKey("BTC/USDT", "1h", "ema_20", 2000)

        self.assertEqual(key1, key2)
        self.assertNotEqual(key1, key3)

    def test_cache_set_and_get(self) -> None:
        """测试缓存的设置和获取"""
        cache = FactorCache(max_size=10)
        key = FactorCacheKey("BTC/USDT", "1h", "ema_20", 1000)
        value = pd.Series([1.0, 2.0, 3.0])

        # 设置缓存
        cache.set(key, value)

        # 获取缓存
        cached_value = cache.get(key)
        self.assertIsNotNone(cached_value)
        pd.testing.assert_series_equal(cached_value, value)

    def test_cache_miss(self) -> None:
        """测试缓存未命中"""
        cache = FactorCache(max_size=10)
        key = FactorCacheKey("BTC/USDT", "1h", "ema_20", 1000)

        # 缓存未命中
        cached_value = cache.get(key)
        self.assertIsNone(cached_value)

    def test_cache_hit_rate(self) -> None:
        """测试缓存命中率"""
        cache = FactorCache(max_size=10)
        key = FactorCacheKey("BTC/USDT", "1h", "ema_20", 1000)
        value = pd.Series([1.0, 2.0, 3.0])

        # 初始命中率为 0
        self.assertEqual(cache.get_hit_rate(), 0.0)

        # 设置缓存
        cache.set(key, value)

        # 命中一次
        cache.get(key)
        self.assertEqual(cache.get_hit_rate(), 1.0)

        # 未命中一次
        cache.get(FactorCacheKey("ETH/USDT", "1h", "ema_20", 1000))
        self.assertEqual(cache.get_hit_rate(), 0.5)


if __name__ == "__main__":
    unittest.main()
