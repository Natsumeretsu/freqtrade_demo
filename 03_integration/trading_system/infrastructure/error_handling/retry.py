"""重试装饰器

提供自动重试机制。

创建日期: 2026-01-17
"""
from __future__ import annotations

import time
import logging
import functools
from typing import Callable, Tuple, Type, Any

logger = logging.getLogger(__name__)


def retry(
    max_attempts: int = 3,
    backoff: float = 2.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,)
):
    """重试装饰器

    Args:
        max_attempts: 最大重试次数
        backoff: 退避系数（指数退避）
        exceptions: 需要重试的异常类型

    Returns:
        装饰器函数
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            last_exception = None

            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_attempts:
                        wait_time = backoff ** (attempt - 1)
                        logger.warning(
                            f"第 {attempt}/{max_attempts} 次尝试失败: {e}, "
                            f"等待 {wait_time:.1f} 秒后重试"
                        )
                        time.sleep(wait_time)
                    else:
                        logger.error(f"重试 {max_attempts} 次后仍然失败: {e}")

            # 抛出最后一次的异常
            raise last_exception

        return wrapper
    return decorator
