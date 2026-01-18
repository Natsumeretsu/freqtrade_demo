"""测试 TalibFactorEngine 的缓存功能"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "03_integration"))

from trading_system.infrastructure.factor_engines.talib_engine import TalibFactorEngine
from trading_system.infrastructure.factor_engines.factor_cache import FactorCache


def _sample_ohlcv(n: int = 200) -> pd.DataFrame:
    rng = np.random.default_rng(7)
    close = 100 + np.cumsum(rng.normal(0, 0.5, size=n))
    high = close * (1.0 + np.abs(rng.normal(0.001, 0.001, size=n)))
    low = close * (1.0 - np.abs(rng.normal(0.001, 0.001, size=n)))
    vol = rng.uniform(100, 1000, size=n)
    return pd.DataFrame({"close": close, "high": high, "low": low, "volume": vol})


class TestTalibFactorEngineWithCache(unittest.TestCase):
    def test_engine_accepts_cache_parameter(self) -> None:
        """测试引擎接受缓存参数"""
        cache = FactorCache(max_size=100)
        engine = TalibFactorEngine(cache=cache)

        self.assertIsNotNone(engine._cache)
        self.assertEqual(engine._cache, cache)

    def test_engine_works_without_cache(self) -> None:
        """测试引擎在没有缓存时正常工作"""
        engine = TalibFactorEngine()
        df = _sample_ohlcv(200)

        factors = engine.compute(df, ["ema_short_10", "ret_1"])
        self.assertIn("ema_short_10", factors.columns)
        self.assertIn("ret_1", factors.columns)


if __name__ == "__main__":
    unittest.main()
