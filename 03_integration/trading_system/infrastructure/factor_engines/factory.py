from __future__ import annotations

"""
factory.py - 因子引擎工厂（配置驱动）

目标：
- 统一“根据配置创建 IFactorEngine”的逻辑，避免在容器/脚本/模块里重复拼装参数
- 便于后续扩展更多引擎（例如：qlib 表达式引擎、pandas 引擎等）
"""

from trading_system.domain.factor_engine import IFactorEngine
from trading_system.infrastructure.config_loader import ConfigManager, get_config
from trading_system.infrastructure.factor_engines.talib_engine import TalibEngineParams, TalibFactorEngine


def create_factor_engine(cfg: ConfigManager | None = None) -> IFactorEngine:
    cfg = cfg or get_config()

    engine_type = str(cfg.get("trading_system.factor_engine.type", "talib")).strip().lower() or "talib"
    if engine_type == "talib":
        p = cfg.get("trading_system.factor_engine.talib", {}) or {}
        p = p if isinstance(p, dict) else {}
        params = TalibEngineParams(
            adx_period=int(p.get("adx_period", 14)),
            atr_period=int(p.get("atr_period", 14)),
            macd_fast=int(p.get("macd_fast", 12)),
            macd_slow=int(p.get("macd_slow", 26)),
            macd_signal=int(p.get("macd_signal", 9)),
            volume_ratio_lookback=int(p.get("volume_ratio_lookback", 72)),
        )
        return TalibFactorEngine(params=params)

    raise ValueError(f"未知 factor_engine.type：{engine_type}")

