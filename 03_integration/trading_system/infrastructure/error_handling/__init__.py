"""错误处理模块

提供增强的错误处理功能。

核心组件：
1. 自定义异常类
2. 重试装饰器
3. 错误上下文

创建日期: 2026-01-17
"""
from .exceptions import (
    TradingSystemError,
    DataError,
    DataNotFoundError,
    DataValidationError,
    DataLoadError,
    ComputationError,
    FactorComputationError,
    InvalidParameterError,
    CacheError,
)
from .retry import retry

__all__ = [
    'TradingSystemError',
    'DataError',
    'DataNotFoundError',
    'DataValidationError',
    'DataLoadError',
    'ComputationError',
    'FactorComputationError',
    'InvalidParameterError',
    'CacheError',
    'retry',
]
