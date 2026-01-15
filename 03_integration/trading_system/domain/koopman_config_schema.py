"""
koopman_config_schema.py - Koopman 配置 Pydantic Schema

用于验证 trading_system.yaml 中的 koopman 配置节。
"""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class KoopmanConfig(BaseModel):
    """Koopman-lite 特征生成配置"""

    window: int = Field(default=512, ge=32, le=4096)
    embed_dim: int = Field(default=16, ge=2, le=64)
    stride: int = Field(default=10, ge=1, le=100)
    ridge: float = Field(default=0.001, ge=0.0, le=1.0)
    pred_horizons: list[int] = Field(default_factory=lambda: [1, 4])
    fft_window: int = Field(default=512, ge=8, le=4096)
    fft_topk: int = Field(default=8, ge=1, le=64)

    @field_validator("pred_horizons")
    @classmethod
    def validate_horizons(cls, v: list[int]) -> list[int]:
        if not v:
            return [1, 4]
        for h in v:
            if h < 1 or h > 100:
                raise ValueError(f"pred_horizon 必须在 1-100 之间: {h}")
        return sorted(set(v))

    @field_validator("window")
    @classmethod
    def validate_window(cls, v: int) -> int:
        if v < 32:
            raise ValueError("window 过小，建议 >= 128")
        return v


def load_koopman_config(raw: dict | None) -> KoopmanConfig:
    """从 YAML dict 加载并验证 Koopman 配置"""
    if raw is None:
        return KoopmanConfig()
    return KoopmanConfig.model_validate(raw)
