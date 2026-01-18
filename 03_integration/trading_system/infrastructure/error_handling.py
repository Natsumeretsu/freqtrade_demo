"""错误处理工具模块

提供统一的错误处理、日志记录和异常管理功能。
"""
from __future__ import annotations

import functools
import logging
import traceback
from typing import Any, Callable, Optional, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar('T')


class StrategyError(Exception):
    """策略执行错误基类"""
    pass


class FactorComputationError(StrategyError):
    """因子计算错误"""
    pass


class DataValidationError(StrategyError):
    """数据验证错误"""
    pass


class RiskManagementError(StrategyError):
    """风险管理错误"""
    pass


def safe_execute(
    default_return: Any = None,
    log_level: int = logging.ERROR,
    raise_on_error: bool = False,
    error_message: Optional[str] = None,
):
    """安全执行装饰器

    捕获函数执行中的异常，记录日志并返回默认值。

    Args:
        default_return: 发生异常时的默认返回值
        log_level: 日志级别
        raise_on_error: 是否重新抛出异常
        error_message: 自定义错误消息

    Example:
        @safe_execute(default_return=pd.DataFrame())
        def compute_factors(data):
            # 可能抛出异常的代码
            return result
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> T:
            try:
                return func(*args, **kwargs)
            except Exception as e:
                msg = error_message or f"{func.__name__} 执行失败"
                logger.log(log_level, f"{msg}: {e}")
                logger.debug(traceback.format_exc())

                if raise_on_error:
                    raise

                return default_return

        return wrapper

    return decorator
