"""Koopman 性能对比测试"""
from __future__ import annotations

import sys
import time
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "03_integration"))

from trading_system.infrastructure.koopman_lite import compute_koopman_lite_features
from trading_system.infrastructure.koopman_optimized import compute_koopman_optimized


def _sample_close(n: int = 1000) -> pd.Series:
    """生成测试用收盘价序列"""
    rng = np.random.default_rng(42)
    close = 100 + np.cumsum(rng.normal(0, 0.5, size=n))
    return pd.Series(close, index=pd.date_range("2020-01-01", periods=n, freq="1h"))


class TestKoopmanPerformance(unittest.TestCase):
    def test_optimized_vs_original(self) -> None:
        """对比优化版本与原始版本的性能"""
        close = _sample_close(1000)

        # 测试参数（使用较小的参数以加快测试）
        params = {
            "close": close,
            "window": 128,
            "embed_dim": 8,
            "stride": 10,
            "ridge": 0.01,
            "pred_horizons": [1, 3],
            "n_modes": 3,
        }

        # 原始版本
        start = time.time()
        result_original = compute_koopman_lite_features(
            **params,
            fft_window=0,
            fft_topk=0,
        )
        time_original = time.time() - start

        # 优化版本
        start = time.time()
        result_optimized = compute_koopman_optimized(**params)
        time_optimized = time.time() - start

        # 验证结果形状一致
        self.assertEqual(result_original.shape, result_optimized.shape)

        # 验证列名一致
        self.assertEqual(set(result_original.columns), set(result_optimized.columns))

        # 打印性能对比
        speedup = time_original / time_optimized if time_optimized > 0 else float('inf')
        print(f"\n性能对比:")
        print(f"  原始版本: {time_original:.3f}s")
        print(f"  优化版本: {time_optimized:.3f}s")
        print(f"  加速比: {speedup:.2f}x")

        # 验证优化版本更快
        self.assertLess(time_optimized, time_original * 1.1)  # 允许 10% 误差


if __name__ == "__main__":
    unittest.main()
