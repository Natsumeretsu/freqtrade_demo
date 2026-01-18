"""自定义异常类

定义交易系统的异常层次结构。

创建日期: 2026-01-17
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class TradingSystemError(Exception):
    """交易系统基础异常类"""

    def __init__(
        self,
        message: str,
        operation: Optional[str] = None,
        parameters: Optional[Dict[str, Any]] = None,
        original_error: Optional[Exception] = None
    ):
        """初始化异常

        Args:
            message: 错误消息
            operation: 操作名称
            parameters: 操作参数
            original_error: 原始异常
        """
        super().__init__(message)
        self.message = message
        self.operation = operation
        self.parameters = parameters or {}
        self.original_error = original_error
        self.timestamp = datetime.now()

    def __str__(self) -> str:
        """格式化错误消息"""
        parts = [self.message]
        if self.operation:
            parts.append(f"操作: {self.operation}")
        if self.parameters:
            parts.append(f"参数: {self.parameters}")
        return " | ".join(parts)


# ============ 数据相关错误 ============

class DataError(TradingSystemError):
    """数据相关错误基类"""
    pass


class DataNotFoundError(DataError):
    """数据未找到错误"""
    pass


class DataValidationError(DataError):
    """数据验证错误"""
    pass


class DataLoadError(DataError):
    """数据加载错误"""
    pass


# ============ 计算相关错误 ============

class ComputationError(TradingSystemError):
    """计算相关错误基类"""
    pass


class FactorComputationError(ComputationError):
    """因子计算错误"""
    pass


class InvalidParameterError(ComputationError):
    """无效参数错误"""
    pass


# ============ 缓存相关错误 ============

class CacheError(TradingSystemError):
    """缓存相关错误基类"""
    pass


class CacheFullError(CacheError):
    """缓存已满错误"""
    pass


class CacheCorruptedError(CacheError):
    """缓存损坏错误"""
    pass
