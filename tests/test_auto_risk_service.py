from __future__ import annotations

import os
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd


_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "03_integration"))


import trading_system.infrastructure.auto_risk as auto_risk_mod  # noqa: E402
from trading_system.infrastructure.auto_risk import AutoRiskService  # noqa: E402
from trading_system.infrastructure.config_loader import ConfigManager  # noqa: E402
from trading_system.infrastructure.ml.drift import build_feature_baseline  # noqa: E402


class _StubLoader:
    def __init__(self, *, features: list[str], model_info: dict) -> None:
        self.features = features
        self.model_info = model_info


class _StubModelCache:
    def __init__(self, loader: _StubLoader) -> None:
        self._loader = loader

    def get(self, model_dir: str | Path) -> _StubLoader:
        return self._loader


class _StubDP:
    def __init__(self, *, market_pair: str, market_df: pd.DataFrame | None) -> None:
        self._market_pair = str(market_pair)
        self._market_df = market_df

    def get_pair_dataframe(self, *, pair: str, timeframe: str, candle_type: str | None = None) -> pd.DataFrame:
        if str(pair) != self._market_pair or self._market_df is None:
            raise KeyError(f"pair_not_found: {pair}")
        return self._market_df


class TestAutoRiskService(unittest.TestCase):
    def test_drift_crit_blocks_entry_then_recovers_after_ok_streak(self) -> None:
        # 开启 auto risk
        os.environ["AUTO_RISK_ENABLED"] = "true"

        # 将模型目录指向 artifacts（避免污染研究层目录）
        qlib_model_dir = (_REPO_ROOT / "artifacts" / "test_models").resolve()
        os.environ["QLIB_MODEL_DIR"] = qlib_model_dir.as_posix()

        cfg = ConfigManager(repo_root=_REPO_ROOT)

        # 准备 stub 模型信息（包含 regime 阈值与 baseline 文件名）
        features = ["ret_12", "vol_12", "ema_spread"]
        model_info = {
            "feature_baseline_file": "feature_baseline.json",
            "regime_evaluation": {
                "definition": {
                    "thresholds": {
                        "vol_12_q90": 0.03,
                        "ema_spread_abs_q70": 0.01,
                        "trend_strength_q70": 3.0,
                    }
                }
            },
        }
        loader = _StubLoader(features=features, model_info=model_info)

        service = AutoRiskService(cfg=cfg, model_cache=_StubModelCache(loader))

        # 写入 baseline（内容不重要，主要用于通过“文件存在”校验）
        model_dir = service.model_dir(pair="BTC/USDT:USDT", timeframe="4h")
        model_dir.mkdir(parents=True, exist_ok=True)
        baseline = build_feature_baseline(pd.DataFrame({c: np.linspace(0, 1, 200) for c in features}), quantile_bins=10)
        (model_dir / "feature_baseline.json").write_text(
            auto_risk_mod.json.dumps(baseline, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        # patch：让 drift 状态按序返回（crit -> ok -> ok -> ok）
        statuses = ["crit", "ok", "ok", "ok"]
        orig_eval = auto_risk_mod.evaluate_feature_drift
        orig_feat = auto_risk_mod.compute_features

        def _fake_compute_features(df: pd.DataFrame, *, feature_cols=None) -> pd.DataFrame:
            cols = list(feature_cols or [])
            out = pd.DataFrame(index=df.index)
            for c in cols:
                out[c] = 0.0
            return out

        def _fake_evaluate_feature_drift(*args, **kwargs) -> dict:
            s = statuses.pop(0)
            return {"status": s, "features": {}}

        auto_risk_mod.compute_features = _fake_compute_features  # type: ignore[assignment]
        auto_risk_mod.evaluate_feature_drift = _fake_evaluate_feature_drift  # type: ignore[assignment]

        try:
            # 构造 4 根“新K线”，触发 4 次评估
            for i in range(4):
                df = pd.DataFrame(
                    {
                        "date": pd.date_range("2026-01-01", periods=10 + i, freq="4h", tz="UTC"),
                        "ret_12": 0.05,
                        "vol_12": 0.01,
                        "ema_spread": 0.02,
                    }
                )
                decision = service.decision_with_df(
                    df=df,
                    pair="BTC/USDT:USDT",
                    timeframe="4h",
                    current_time=datetime(2026, 1, 2, tzinfo=timezone.utc),
                    side="long",
                )

                if i == 0:
                    self.assertFalse(decision.allow_entry)
                if i in {1, 2}:
                    # 默认 recover_ok_checks=3：恢复期内仍禁止新开仓
                    self.assertFalse(decision.allow_entry)
                if i == 3:
                    self.assertTrue(decision.allow_entry)
        finally:
            auto_risk_mod.compute_features = orig_feat  # type: ignore[assignment]
            auto_risk_mod.evaluate_feature_drift = orig_eval  # type: ignore[assignment]
            os.environ.pop("AUTO_RISK_ENABLED", None)
            os.environ.pop("QLIB_MODEL_DIR", None)

    def test_market_context_scales_down_on_corr_beta_breakdown(self) -> None:
        os.environ["AUTO_RISK_ENABLED"] = "true"
        try:
            cfg = ConfigManager(repo_root=_REPO_ROOT)
            cfg.configs.setdefault("trading_system", {}).setdefault("auto_risk", {})
            cfg.configs["trading_system"]["auto_risk"]["drift"] = {"enabled": False}
            cfg.configs["trading_system"]["auto_risk"]["regime"] = {"enabled": False}
            cfg.configs["trading_system"]["auto_risk"]["market_context"] = {
                "enabled": True,
                "market_pair": "BTC/USDT",
                "window": 72,
                "reference_window": 500,
                "min_periods": 50,
                "min_scale": 0.80,
                "corr_delta_warn": 0.25,
                "corr_delta_crit": 0.50,
                "beta_delta_warn": 0.50,
                "beta_delta_crit": 1.00,
            }

            loader = _StubLoader(features=[], model_info={})
            service = AutoRiskService(cfg=cfg, model_cache=_StubModelCache(loader))

            n = 600
            dates = pd.date_range("2026-01-01", periods=n, freq="4h", tz="UTC")
            rng = np.random.default_rng(7)
            mkt_ret = rng.normal(0.0, 0.002, size=n).astype("float64")
            asset_ret = mkt_ret.copy()
            asset_ret[-72:] = -mkt_ret[-72:]  # 强制“断裂”：最近窗口与历史方向相反

            mkt_close = 100.0 * np.cumprod(1.0 + mkt_ret)
            asset_close = 50.0 * np.cumprod(1.0 + asset_ret)

            market_df = pd.DataFrame({"date": dates, "close": mkt_close})
            asset_df = pd.DataFrame({"date": dates, "close": asset_close})

            # 覆盖合约后缀：pair="ETH/USDT:USDT" 将自动把 market_pair 归一化为 "BTC/USDT:USDT"
            dp = _StubDP(market_pair="BTC/USDT:USDT", market_df=market_df)
            decision = service.decision_with_df(
                df=asset_df,
                dp=dp,
                pair="ETH/USDT:USDT",
                timeframe="4h",
                current_time=dates[-1].to_pydatetime(),
                side="long",
            )

            self.assertEqual(decision.market_context_status, "crit")
            self.assertTrue(np.isfinite(float(decision.market_context_scale)))
            self.assertLess(float(decision.market_context_scale), 1.0)
            self.assertAlmostEqual(float(decision.market_context_scale), 0.80, places=6)
            self.assertAlmostEqual(float(decision.stake_scale), float(decision.market_context_scale), places=6)
            self.assertIn("market_context_crit", decision.reasons)
        finally:
            os.environ.pop("AUTO_RISK_ENABLED", None)

    def test_market_context_fail_open_when_market_df_missing(self) -> None:
        os.environ["AUTO_RISK_ENABLED"] = "true"
        try:
            cfg = ConfigManager(repo_root=_REPO_ROOT)
            cfg.configs.setdefault("trading_system", {}).setdefault("auto_risk", {})
            cfg.configs["trading_system"]["auto_risk"]["drift"] = {"enabled": False}
            cfg.configs["trading_system"]["auto_risk"]["regime"] = {"enabled": False}
            cfg.configs["trading_system"]["auto_risk"]["market_context"] = {"enabled": True, "market_pair": "BTC/USDT"}

            loader = _StubLoader(features=[], model_info={})
            service = AutoRiskService(cfg=cfg, model_cache=_StubModelCache(loader))

            dates = pd.date_range("2026-01-01", periods=100, freq="4h", tz="UTC")
            asset_df = pd.DataFrame({"date": dates, "close": 100.0 + np.arange(len(dates), dtype="float64") * 0.1})

            # market_df 缺失：应 fail-open（scale=1，不阻断交易）
            dp = _StubDP(market_pair="BTC/USDT:USDT", market_df=None)
            decision = service.decision_with_df(
                df=asset_df,
                dp=dp,
                pair="ETH/USDT:USDT",
                timeframe="4h",
                current_time=dates[-1].to_pydatetime(),
                side="long",
            )

            self.assertIn(decision.market_context_status, {"unknown", "disabled"})
            self.assertAlmostEqual(float(decision.market_context_scale), 1.0, places=6)
            self.assertAlmostEqual(float(decision.stake_scale), 1.0, places=6)
            self.assertIn("market_context_market_df_missing", decision.reasons)
        finally:
            os.environ.pop("AUTO_RISK_ENABLED", None)


if __name__ == "__main__":
    unittest.main()
