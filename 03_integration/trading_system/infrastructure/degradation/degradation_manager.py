"""降级管理器

管理服务降级策略和执行。

创建日期: 2026-01-17
"""
from typing import Callable, Dict, Optional, Any
from .circuit_breaker import CircuitBreaker
import logging


class DegradationManager:
    """降级管理器"""

    def __init__(self):
        self._strategies: Dict[str, Dict[str, Any]] = {}
        self._circuit_breakers: Dict[str, CircuitBreaker] = {}
        self._logger = logging.getLogger(__name__)

    def register_strategy(
        self,
        service_name: str,
        primary: Callable,
        fallback: Callable,
        failure_threshold: int = 5,
        timeout: int = 60
    ) -> None:
        """注册降级策略"""
        self._strategies[service_name] = {
            'primary': primary,
            'fallback': fallback
        }
        
        self._circuit_breakers[service_name] = CircuitBreaker(
            failure_threshold=failure_threshold,
            timeout=timeout
        )
        
        self._logger.info(f"已注册降级策略: {service_name}")

    def execute(self, service_name: str, *args, **kwargs) -> Any:
        """执行服务调用（带降级）"""
        if service_name not in self._strategies:
            raise ValueError(f"未注册的服务: {service_name}")
        
        strategy = self._strategies[service_name]
        breaker = self._circuit_breakers[service_name]
        
        try:
            # 尝试调用主服务
            return breaker.call(strategy['primary'], *args, **kwargs)
        except Exception as e:
            # 主服务失败，降级到备用服务
            self._logger.warning(f"服务 {service_name} 降级: {str(e)}")
            return strategy['fallback'](*args, **kwargs)

    def get_service_status(self, service_name: str) -> Dict[str, Any]:
        """获取服务状态"""
        if service_name not in self._circuit_breakers:
            return {'status': 'unknown'}
        
        breaker = self._circuit_breakers[service_name]
        return {
            'status': breaker.state.value,
            'failure_count': breaker.failure_count
        }

    def reset_service(self, service_name: str) -> None:
        """重置服务熔断器"""
        if service_name in self._circuit_breakers:
            self._circuit_breakers[service_name].reset()
            self._logger.info(f"已重置服务: {service_name}")
