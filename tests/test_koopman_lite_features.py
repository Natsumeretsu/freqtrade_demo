from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "03_integration"))

from trading_system.infrastructure.koopman_lite import compute_koopman_lite_features  # noqa: E402
from trading_system.infrastructure.factor_engines.talib_engine import TalibEngineParams, TalibFactorEngine  # noqa: E402


def _sample_ohlcv(n: int = 400) -> pd.DataFrame:
    rng = np.random.default_rng(7)
    close = 100 + np.cumsum(rng.normal(0, 0.6, size=n))
    high = close * (1.0 + np.abs(rng.normal(0.001, 0.001, size=n)))
    low = close * (1.0 - np.abs(rng.normal(0.001, 0.001, size=n)))
    vol = rng.uniform(100, 1000, size=n)
    return pd.DataFrame({"close": close, "high": high, "low": low, "volume": vol})


class TestKoopmanLiteFeatures(unittest.TestCase):
    def test_compute_koopman_lite_features_basic(self) -> None:
        """测试基于 PyDMD HODMD 的本征模态提取"""
        df = _sample_ohlcv(500)
        feats = compute_koopman_lite_features(
            close=df["close"],
            window=96,
            embed_dim=8,
            stride=5,
            ridge=1e-3,
            pred_horizons=[1, 4],
            fft_window=0,  # 不再使用独立 FFT
            fft_topk=0,
            n_modes=3,
        )

        # 验证新的本征模态因子
        expected_cols = [
            "koop_spectral_radius",
            "koop_reconstruction_error",
            "koop_mode_0_amp",
            "koop_mode_0_freq",
            "koop_mode_0_decay",
            "koop_mode_1_amp",
            "koop_mode_1_freq",
            "koop_mode_1_decay",
            "koop_mode_2_amp",
            "koop_mode_2_freq",
            "koop_mode_2_decay",
            "koop_pred_ret_h1",
            "koop_pred_ret_h4",
        ]
        for col in expected_cols:
            self.assertIn(col, feats.columns, f"缺少列: {col}")

        arr = feats.astype("float64").to_numpy()
        self.assertFalse(np.isinf(arr).any(), "存在无穷值")

        # 过了窗口后应出现可用值
        tail = feats.iloc[200:].astype("float64")
        self.assertTrue(np.isfinite(tail.to_numpy()).any(), "尾部无有效值")

    def test_eigenmode_interpretation(self) -> None:
        """测试本征模态的物理意义"""
        df = _sample_ohlcv(500)
        feats = compute_koopman_lite_features(
            close=df["close"],
            window=96,
            embed_dim=8,
            stride=5,
            ridge=1e-3,
            pred_horizons=[1],
            fft_window=0,
            fft_topk=0,
            n_modes=3,
        )

        # 谱半径应在合理范围内（接近 1 表示稳定系统）
        sr = feats["koop_spectral_radius"].dropna()
        if len(sr) > 0:
            self.assertTrue((sr > 0).all(), "谱半径应为正")
            self.assertTrue((sr < 10).all(), "谱半径异常大")

        # 模态振幅应为非负
        amp0 = feats["koop_mode_0_amp"].dropna()
        if len(amp0) > 0:
            self.assertTrue((amp0 >= 0).all(), "振幅应非负")

    def test_talib_engine_supports_and_compute_koopman_lite(self) -> None:
        """测试 TalibFactorEngine 对新因子的支持"""
        df = _sample_ohlcv(500)
        engine = TalibFactorEngine(
            params=TalibEngineParams(
                koop_window=96,
                koop_embed_dim=8,
                koop_stride=5,
                koop_ridge=1e-3,
            )
        )

        # 测试新的因子名
        names = [
            "koop_spectral_radius",
            "koop_reconstruction_error",
            "koop_mode_0_amp",
            "koop_mode_0_freq",
            "koop_mode_0_decay",
            "koop_pred_ret_h4",
        ]
        for n in names:
            self.assertTrue(engine.supports(n), f"不支持因子: {n}")

        out = engine.compute(df, names)
        for n in names:
            self.assertIn(n, out.columns, f"输出缺少列: {n}")
        self.assertEqual(len(out), len(df))


if __name__ == "__main__":
    unittest.main()
