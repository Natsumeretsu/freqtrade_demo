"""降级模块

提供服务降级和熔断机制。

创建日期: 2026-01-17
"""
from .circuit_breaker import CircuitBreaker, CircuitState
from .degradation_manager import DegradationManager

__all__ = ['CircuitBreaker', 'CircuitState', 'DegradationManager']
