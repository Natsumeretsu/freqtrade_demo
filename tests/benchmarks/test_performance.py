"""性能基准测试

用于建立性能基线，对比优化前后的性能差异。
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "03_integration"))

from trading_system.infrastructure.factor_engines.talib_engine import TalibFactorEngine


def _sample_ohlcv(n: int = 1000) -> pd.DataFrame:
    """生成样本 OHLCV 数据"""
    rng = np.random.default_rng(42)
    close = 100 + np.cumsum(rng.normal(0, 0.5, size=n))
    high = close * (1.0 + np.abs(rng.normal(0.001, 0.001, size=n)))
    low = close * (1.0 - np.abs(rng.normal(0.001, 0.001, size=n)))
    vol = rng.uniform(100, 1000, size=n)
    return pd.DataFrame({"close": close, "high": high, "low": low, "volume": vol})


def benchmark_factor_computation():
    """基准测试：因子计算性能"""
    print("\n=== 因子计算性能基准测试 ===")

    df = _sample_ohlcv(1000)
    engine = TalibFactorEngine()

    # 测试不同数量的因子
    factor_sets = {
        "10个因子": [
            "ema_short_10", "ema_long_20", "adx", "atr", "rsi_14",
            "ret_1", "ret_5", "vol_12", "bb_width_20_2", "stoch_k_14_3_3"
        ],
        "50个因子": [
            f"ema_short_{i}" for i in range(10, 20)
        ] + [
            f"ret_{i}" for i in range(1, 20)
        ] + [
            f"vol_{i}" for i in [12, 24, 48, 72]
        ] + [
            "adx", "atr", "rsi_14", "cci_20", "mfi_14",
            "bb_width_20_2", "stoch_k_14_3_3", "macdhist"
        ],
        "100个因子": [
            f"ema_short_{i}" for i in range(10, 30)
        ] + [
            f"ema_long_{i}" for i in range(30, 50)
        ] + [
            f"ret_{i}" for i in range(1, 30)
        ] + [
            f"vol_{i}" for i in [12, 24, 48, 72, 96]
        ] + [
            f"roc_{i}" for i in [5, 10, 20]
        ] + [
            "adx", "atr", "rsi_14", "cci_20", "mfi_14",
            "bb_width_20_2", "stoch_k_14_3_3", "macdhist"
        ]
    }

    results = {}
    for name, factors in factor_sets.items():
        start_time = time.perf_counter()
        _ = engine.compute(df, factors)
        elapsed = time.perf_counter() - start_time
        results[name] = elapsed
        print(f"{name}: {elapsed:.4f} 秒")

    return results


def benchmark_koopman_computation():
    """基准测试：Koopman 计算性能"""
    print("\n=== Koopman 计算性能基准测试 ===")

    engine = TalibFactorEngine()

    # 测试不同窗口大小
    window_sizes = [500, 800, 1000, 1400]
    results = {}

    for window in window_sizes:
        df = _sample_ohlcv(window + 100)  # 额外100行用于计算

        start_time = time.perf_counter()
        try:
            _ = engine.compute(df, ["koop_pred_ret_1400_10"])
            elapsed = time.perf_counter() - start_time
            results[f"window_{window}"] = elapsed
            print(f"窗口大小 {window}: {elapsed:.4f} 秒")
        except Exception as e:
            print(f"窗口大小 {window}: 失败 ({e})")
            results[f"window_{window}"] = None

    return results


if __name__ == "__main__":
    print("开始性能基准测试...")
    print(f"测试环境：Python {sys.version}")

    # 运行基准测试
    factor_results = benchmark_factor_computation()
    koopman_results = benchmark_koopman_computation()

    # 输出总结
    print("\n=== 性能基准测试总结 ===")
    print("\n因子计算性能：")
    for name, elapsed in factor_results.items():
        print(f"  {name}: {elapsed:.4f} 秒")

    print("\nKoopman 计算性能：")
    for name, elapsed in koopman_results.items():
        if elapsed is not None:
            print(f"  {name}: {elapsed:.4f} 秒")
        else:
            print(f"  {name}: 失败")

    print("\n基准测试完成！")
