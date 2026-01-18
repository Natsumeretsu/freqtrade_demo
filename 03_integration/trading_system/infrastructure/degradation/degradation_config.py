"""降级策略配置

提供降级策略的配置管理。

创建日期: 2026-01-17
"""
from typing import Dict, Any, List
from dataclasses import dataclass


@dataclass
class DegradationStrategy:
    """降级策略配置"""
    service_name: str
    failure_threshold: int = 5
    timeout: int = 60
    enabled: bool = True


class DegradationConfig:
    """降级配置管理器"""

    def __init__(self):
        self._strategies: Dict[str, DegradationStrategy] = {}

    def add_strategy(self, strategy: DegradationStrategy) -> None:
        """添加降级策略"""
        self._strategies[strategy.service_name] = strategy

    def get_strategy(self, service_name: str) -> DegradationStrategy:
        """获取降级策略"""
        return self._strategies.get(service_name)

    def list_strategies(self) -> List[DegradationStrategy]:
        """列出所有策略"""
        return list(self._strategies.values())
