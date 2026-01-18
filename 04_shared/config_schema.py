"""
Freqtrade 配置验证模块 - MVP版本

使用 Pydantic 进行配置验证，确保配置文件格式正确。
"""

from __future__ import annotations

from typing import Optional, Literal, List, Dict, Any
from pydantic import BaseModel, Field, field_validator


class UnfilledTimeoutConfig(BaseModel):
    """未成交订单超时配置"""
    entry: int = Field(ge=1, description="入场订单超时时间")
    exit: int = Field(ge=1, description="出场订单超时时间")
    exit_timeout_count: int = Field(ge=0, description="出场超时计数")
    unit: Literal["minutes", "seconds"] = Field(default="minutes", description="时间单位")


class DepthOfMarketConfig(BaseModel):
    """市场深度检查配置"""
    enabled: bool = Field(default=False, description="是否启用")
    bids_to_ask_delta: float = Field(ge=0, description="买卖盘比例")


class EntryPricingConfig(BaseModel):
    """入场定价配置"""
    price_side: Literal["same", "other", "ask", "bid"] = Field(description="价格方向")
    use_order_book: bool = Field(default=True, description="是否使用订单簿")
    order_book_top: int = Field(ge=1, le=50, default=1, description="订单簿深度")
    price_last_balance: float = Field(ge=0, le=1, default=0.0, description="最新价格权重")
    check_depth_of_market: DepthOfMarketConfig = Field(default_factory=DepthOfMarketConfig)


class ExitPricingConfig(BaseModel):
    """出场定价配置"""
    price_side: Literal["same", "other", "ask", "bid"] = Field(description="价格方向")
    use_order_book: bool = Field(default=True, description="是否使用订单簿")
    order_book_top: int = Field(ge=1, le=50, default=1, description="订单簿深度")


class ExchangeConfig(BaseModel):
    """交易所配置"""
    name: str = Field(description="交易所名称")
    key: str = Field(default="", description="API Key")
    secret: str = Field(default="", description="API Secret")
    ccxt_config: Dict[str, Any] = Field(default_factory=dict, description="CCXT 配置")
    ccxt_async_config: Dict[str, Any] = Field(default_factory=dict, description="CCXT 异步配置")
    pair_whitelist: List[str] = Field(default_factory=list, description="交易对白名单")
    pair_blacklist: List[str] = Field(default_factory=list, description="交易对黑名单")

    @field_validator('name')
    @classmethod
    def validate_exchange_name(cls, v: str) -> str:
        """验证交易所名称"""
        valid_exchanges = ['binance', 'okx', 'bybit', 'gate', 'huobi', 'kraken']
        if v.lower() not in valid_exchanges:
            raise ValueError(f"不支持的交易所: {v}")
        return v.lower()


class PairListConfig(BaseModel):
    """交易对列表配置"""
    method: str = Field(description="方法名称")


class TelegramConfig(BaseModel):
    """Telegram 配置"""
    enabled: bool = Field(default=False, description="是否启用")
    token: str = Field(default="", description="Bot Token")
    chat_id: str = Field(default="", description="Chat ID")


class APIServerConfig(BaseModel):
    """API 服务器配置"""
    enabled: bool = Field(default=False, description="是否启用")
    listen_ip_address: str = Field(default="127.0.0.1", description="监听地址")
    listen_port: int = Field(ge=1024, le=65535, default=8080, description="监听端口")
    verbosity: Literal["error", "info", "debug"] = Field(default="error", description="日志级别")
    enable_openapi: bool = Field(default=False, description="是否启用 OpenAPI")
    jwt_secret_key: str = Field(default="", description="JWT 密钥")
    ws_token: str = Field(default="", description="WebSocket Token")
    CORS_origins: List[str] = Field(default_factory=list, description="CORS 来源")
    username: str = Field(default="freqtrader", description="用户名")
    password: str = Field(default="", description="密码")


class InternalsConfig(BaseModel):
    """内部配置"""
    process_throttle_secs: int = Field(ge=1, default=5, description="处理节流秒数")


class FreqtradeConfig(BaseModel):
    """Freqtrade 主配置"""
    max_open_trades: int = Field(ge=-1, description="最大开仓数量（-1 表示无限制）")
    stake_currency: str = Field(description="计价货币")
    stake_amount: str | float = Field(description="每单投入金额")
    tradable_balance_ratio: float = Field(ge=0, le=1, default=0.99, description="可交易余额比例")
    fiat_display_currency: str = Field(default="USD", description="法币显示货币")
    dry_run: bool = Field(default=True, description="是否模拟运行")
    dry_run_wallet: float = Field(ge=0, default=1000, description="模拟钱包金额")
    cancel_open_orders_on_exit: bool = Field(default=False, description="退出时取消未成交订单")
    trading_mode: Literal["spot", "futures", "margin"] = Field(default="spot", description="交易模式")
    strategy: str = Field(description="策略名称")

    # 嵌套配置
    unfilledtimeout: UnfilledTimeoutConfig
    entry_pricing: EntryPricingConfig
    exit_pricing: ExitPricingConfig
    exchange: ExchangeConfig
    pairlists: List[PairListConfig]
    telegram: Optional[TelegramConfig] = None
    api_server: Optional[APIServerConfig] = None
    internals: Optional[InternalsConfig] = None

    # 可选字段
    bot_name: str = Field(default="freqtrade", description="机器人名称")
    initial_state: Literal["running", "stopped"] = Field(default="running", description="初始状态")
    force_entry_enable: bool = Field(default=False, description="是否允许强制入场")

    @field_validator('stake_amount')
    @classmethod
    def validate_stake_amount(cls, v: str | float) -> str | float:
        """验证投入金额"""
        if isinstance(v, str) and v != "unlimited":
            raise ValueError("stake_amount 必须是数字或 'unlimited'")
        if isinstance(v, (int, float)) and v <= 0:
            raise ValueError("stake_amount 必须大于 0")
        return v


def load_config(config_path: str) -> FreqtradeConfig:
    """
    加载并验证配置文件

    Args:
        config_path: 配置文件路径

    Returns:
        验证后的配置对象

    Raises:
        ValueError: 配置验证失败
    """
    import json
    from pathlib import Path

    config_file = Path(config_path)
    if not config_file.exists():
        raise FileNotFoundError(f"配置文件不存在: {config_path}")

    with open(config_file, 'r', encoding='utf-8') as f:
        config_data = json.load(f)

    # 移除 $schema 字段（Pydantic 不需要）
    config_data.pop('$schema', None)

    return FreqtradeConfig(**config_data)
