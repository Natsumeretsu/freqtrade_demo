"""
timing_policy_schema.py - 择时策略配置的 Pydantic Schema

用于验证 timing_policy YAML 配置文件，确保配置错误时直接报错而非默默降级。
"""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator


class Direction(str, Enum):
    """因子方向：pos=因子越大越偏多，neg=因子越小越偏多"""
    pos = "pos"
    neg = "neg"


class TradeSide(str, Enum):
    """交易方向：both=多空都做，long=只做多，short=只做空"""
    both = "both"
    long = "long"
    short = "short"


class TradingMode(str, Enum):
    """交易模式"""
    futures = "futures"
    spot = "spot"


class FactorSpec(BaseModel):
    """单个因子配置"""
    name: str = Field(..., min_length=1, description="因子名称")
    direction: Direction = Field(default=Direction.pos, description="因子方向")
    side: TradeSide = Field(default=TradeSide.both, description="交易方向")
    weight: float = Field(default=1.0, gt=0, description="因子权重（必须>0）")

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        v = str(v).strip()
        if not v:
            raise ValueError("因子名称不能为空")
        return v


class TimeframeBlock(BaseModel):
    """单个时间框架的配置块（main/confirm）"""
    factors: list[FactorSpec] = Field(default_factory=list, description="因子列表")


class TimeframeSettings(BaseModel):
    """时间框架全局设置"""
    timeframe: str = Field(default="15m", description="时间周期")
    quantiles: int = Field(default=5, ge=2, le=20, description="分位数（2-20）")
    lookback_days: int = Field(default=14, ge=1, le=365, description="回看天数（1-365）")
    entry_threshold: float = Field(default=0.67, ge=0.0, le=1.0, description="入场阈值（0-1）")

    @field_validator("timeframe")
    @classmethod
    def validate_timeframe(cls, v: str) -> str:
        v = str(v).strip().lower()
        valid = {"1m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "8h", "12h", "1d"}
        if v not in valid:
            raise ValueError(f"无效的 timeframe: {v}，支持: {valid}")
        return v


class PairConfig(BaseModel):
    """单个交易对的配置"""
    main: TimeframeBlock | None = None
    confirm: TimeframeBlock | None = None


class DefaultsConfig(BaseModel):
    """默认配置（当 pair 未指定时使用）"""
    main: TimeframeBlock | None = None
    confirm: TimeframeBlock | None = None


class TimingPolicyConfig(BaseModel):
    """
    完整的 timing_policy 配置 Schema

    示例 YAML:
    ```yaml
    version: 2
    exchange: okx
    trading_mode: futures
    main:
      timeframe: 15m
      quantiles: 5
      lookback_days: 14
      entry_threshold: 0.67
    confirm:
      timeframe: 1h
      quantiles: 5
      lookback_days: 30
      entry_threshold: 0.67
    defaults:
      main:
        factors:
        - name: ema_20
          direction: neg
          side: both
          weight: 1.0
    pairs:
      BTC/USDT:USDT:
        main:
          factors:
          - name: ema_50
            direction: neg
    ```
    """
    version: int = Field(default=2, ge=1, le=10, description="配置版本")
    exchange: str = Field(default="okx", min_length=1, description="交易所")
    trading_mode: TradingMode = Field(default=TradingMode.futures, description="交易模式")

    main: TimeframeSettings = Field(default_factory=TimeframeSettings, description="主信号设置")
    confirm: TimeframeSettings = Field(default_factory=TimeframeSettings, description="复核信号设置")

    defaults: DefaultsConfig = Field(default_factory=DefaultsConfig, description="默认因子配置")
    pairs: dict[str, PairConfig] = Field(default_factory=dict, description="交易对级别配置")

    @model_validator(mode="after")
    def validate_has_factors(self) -> "TimingPolicyConfig":
        """确保至少有默认因子配置"""
        has_default_main = (
            self.defaults.main is not None
            and self.defaults.main.factors
            and len(self.defaults.main.factors) > 0
        )
        has_pair_factors = any(
            (pc.main is not None and pc.main.factors and len(pc.main.factors) > 0)
            for pc in self.pairs.values()
        )
        if not has_default_main and not has_pair_factors:
            raise ValueError(
                "配置必须至少包含一个因子：在 defaults.main.factors 或 pairs.<pair>.main.factors 中定义"
            )
        return self


class TimingPolicyValidationError(Exception):
    """配置验证错误"""
    def __init__(self, message: str, path: Path | None = None, details: Any = None):
        self.path = path
        self.details = details
        super().__init__(message)


def validate_timing_policy(data: dict[str, Any], *, path: Path | None = None) -> TimingPolicyConfig:
    """
    验证 timing_policy 配置字典。

    Args:
        data: 从 YAML 加载的配置字典
        path: 配置文件路径（用于错误信息）

    Returns:
        验证通过的 TimingPolicyConfig 对象

    Raises:
        TimingPolicyValidationError: 配置验证失败
    """
    try:
        return TimingPolicyConfig.model_validate(data)
    except Exception as e:
        path_str = path.as_posix() if path else "<unknown>"
        raise TimingPolicyValidationError(
            f"timing_policy 配置验证失败: {path_str}\n{e}",
            path=path,
            details=e,
        ) from e


def load_and_validate_timing_policy(path: Path) -> TimingPolicyConfig:
    """
    加载并验证 timing_policy YAML 文件。

    Args:
        path: YAML 文件路径

    Returns:
        验证通过的 TimingPolicyConfig 对象

    Raises:
        TimingPolicyValidationError: 文件不存在、解析失败或验证失败
    """
    if not path.is_file():
        raise TimingPolicyValidationError(f"timing_policy 文件不存在: {path.as_posix()}", path=path)

    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception as e:
        raise TimingPolicyValidationError(
            f"timing_policy YAML 解析失败: {path.as_posix()}\n{e}",
            path=path,
            details=e,
        ) from e

    if not isinstance(raw, dict):
        raise TimingPolicyValidationError(
            f"timing_policy 必须是 YAML dict: {path.as_posix()}",
            path=path,
        )

    return validate_timing_policy(raw, path=path)
