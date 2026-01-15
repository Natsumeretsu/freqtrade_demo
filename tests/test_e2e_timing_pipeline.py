"""
test_e2e_timing_pipeline.py - 端到端集成测试

测试完整的时序预测流程：
1. 数据质量检查
2. 因子计算
3. 信号生成
4. Gate 过滤
5. 风险调整
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "03_integration"))

from trading_system.infrastructure.data_quality import (
    DataQualityChecker,
    QualityConfig,
)
from trading_system.application.factor_usecase import FactorComputationUseCase
from trading_system.infrastructure.factor_engines.talib_engine import TalibFactorEngine
from trading_system.application.gate_pipeline import combine_gates, gate_funnel


def _generate_realistic_ohlcv(n: int = 500, seed: int = 42) -> pd.DataFrame:
    """生成模拟真实市场的 OHLCV 数据"""
    rng = np.random.default_rng(seed)

    # 生成带趋势和波动的价格序列
    returns = rng.normal(0.0002, 0.02, size=n)  # 微正漂移
    close = 100 * np.exp(np.cumsum(returns))

    # 生成 high/low（基于 close 的波动）
    volatility = np.abs(rng.normal(0.01, 0.005, size=n))
    high = close * (1 + volatility)
    low = close * (1 - volatility)
    open_ = close * (1 + rng.normal(0, 0.005, size=n))

    # 确保 OHLC 关系正确
    high = np.maximum(high, np.maximum(open_, close))
    low = np.minimum(low, np.minimum(open_, close))

    # 生成成交量（与波动率正相关）
    base_volume = 1000000
    volume = base_volume * (1 + volatility * 10) * rng.uniform(0.5, 1.5, size=n)

    # 创建时间索引
    idx = pd.date_range("2024-01-01", periods=n, freq="15min", tz="UTC")

    return pd.DataFrame({
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume,
    }, index=idx)


class TestE2EDataQuality(unittest.TestCase):
    """数据质量检查端到端测试"""

    def test_clean_data_passes(self) -> None:
        """干净数据应通过质量检查"""
        df = _generate_realistic_ohlcv(200)
        checker = DataQualityChecker()
        report = checker.check(df)

        self.assertTrue(report.passed)
        error_issues = [i for i in report.issues if i.level == "error"]
        self.assertEqual(len(error_issues), 0)

    def test_data_with_gaps_detected(self) -> None:
        """时间间隔异常应被检测"""
        df = _generate_realistic_ohlcv(200)
        # 删除中间一段数据制造间隔
        df = pd.concat([df.iloc[:50], df.iloc[60:]])

        checker = DataQualityChecker()
        report = checker.check(df)

        gap_issues = [i for i in report.issues if i.category == "gap"]
        self.assertGreater(len(gap_issues), 0)


class TestE2EFactorComputation(unittest.TestCase):
    """因子计算端到端测试"""

    def setUp(self) -> None:
        self.df = _generate_realistic_ohlcv(500)
        self.engine = TalibFactorEngine()
        self.usecase = FactorComputationUseCase(self.engine)

    def test_compute_basic_factors(self) -> None:
        """基础因子计算"""
        factors = ["ema_short_10", "rsi_14", "atr_14"]
        result = self.usecase.execute(self.df, factors)

        for f in factors:
            self.assertIn(f, result.columns)
            # 检查非全 NaN
            self.assertFalse(result[f].isna().all())

    def test_factor_values_reasonable(self) -> None:
        """因子值应在合理范围内"""
        result = self.usecase.execute(self.df, ["rsi_14"])

        rsi = result["rsi_14"].dropna()
        self.assertTrue((rsi >= 0).all())
        self.assertTrue((rsi <= 100).all())

    def test_no_lookahead_bias(self) -> None:
        """验证无前视偏差（因子只依赖历史数据）"""
        factors = ["ema_short_10"]

        # 计算完整数据的因子
        full_result = self.usecase.execute(self.df, factors)

        # 只用前 400 行计算
        partial_result = self.usecase.execute(self.df.iloc[:400], factors)

        # 前 400 行的因子值应该相同
        pd.testing.assert_series_equal(
            full_result["ema_short_10"].iloc[:400],
            partial_result["ema_short_10"],
            check_names=False,
        )


class TestE2EGatePipeline(unittest.TestCase):
    """Gate 过滤端到端测试"""

    def setUp(self) -> None:
        self.df = _generate_realistic_ohlcv(500)
        self.engine = TalibFactorEngine()
        self.usecase = FactorComputationUseCase(self.engine)

    def test_gate_reduces_signals(self) -> None:
        """Gate 应该过滤掉部分信号"""
        # 计算因子
        result = self.usecase.execute(self.df, ["rsi_14", "atr_14"])

        # 创建 Gate 条件
        rsi_gate = (result["rsi_14"] > 30) & (result["rsi_14"] < 70)
        vol_gate = result["atr_14"] > result["atr_14"].rolling(20).mean()

        # 组合 Gate
        final_mask = combine_gates(
            [("rsi_filter", rsi_gate), ("vol_filter", vol_gate)],
            index=result.index,
            fillna=False,
        )

        # 验证过滤效果
        self.assertLess(final_mask.sum(), len(result))
        self.assertGreater(final_mask.sum(), 0)

    def test_gate_funnel_tracks_dropoff(self) -> None:
        """Gate funnel 应正确追踪每层过滤"""
        result = self.usecase.execute(self.df, ["rsi_14"])

        # 多层 Gate
        gate1 = result["rsi_14"] > 20
        gate2 = result["rsi_14"] < 80
        gate3 = result["rsi_14"] > 40

        final_mask, rows = gate_funnel(
            [("rsi>20", gate1), ("rsi<80", gate2), ("rsi>40", gate3)],
            index=result.index,
            fillna=False,
        )

        # 验证漏斗递减
        self.assertEqual(len(rows), 3)
        for i in range(1, len(rows)):
            self.assertLessEqual(rows[i].survivors, rows[i-1].survivors)


class TestE2EFullPipeline(unittest.TestCase):
    """完整流程端到端测试"""

    def test_full_pipeline_integration(self) -> None:
        """测试完整的数据->因子->信号->过滤流程"""
        # 1. 生成数据
        df = _generate_realistic_ohlcv(500)

        # 2. 数据质量检查
        checker = DataQualityChecker()
        quality_report = checker.check(df)
        self.assertTrue(quality_report.passed)

        # 3. 因子计算
        engine = TalibFactorEngine()
        usecase = FactorComputationUseCase(engine)
        factors = ["ema_short_10", "ema_long_20", "rsi_14", "atr_14"]
        result = usecase.execute(df, factors)

        # 4. 生成信号（简单趋势跟踪）
        trend_signal = result["ema_short_10"] > result["ema_long_20"]

        # 5. Gate 过滤
        rsi_gate = (result["rsi_14"] > 30) & (result["rsi_14"] < 70)
        final_signal = trend_signal & rsi_gate

        # 6. 验证输出
        self.assertIsInstance(final_signal, pd.Series)
        self.assertEqual(len(final_signal), len(df))

        # 信号应该有一定比例为 True
        signal_ratio = final_signal.sum() / len(final_signal)
        self.assertGreater(signal_ratio, 0.01)
        self.assertLess(signal_ratio, 0.99)


if __name__ == "__main__":
    unittest.main()
