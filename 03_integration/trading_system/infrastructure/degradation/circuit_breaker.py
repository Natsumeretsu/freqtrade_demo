"""熔断器

实现服务熔断机制，防止级联故障。

创建日期: 2026-01-17
"""
from typing import Callable, Optional
from enum import Enum
from datetime import datetime, timedelta
import threading


class CircuitState(Enum):
    """熔断器状态"""
    CLOSED = "closed"      # 正常状态
    OPEN = "open"          # 熔断状态
    HALF_OPEN = "half_open"  # 半开状态


class CircuitBreaker:
    """熔断器"""

    def __init__(
        self,
        failure_threshold: int = 5,
        timeout: int = 60,
        expected_exception: type = Exception
    ):
        self._failure_threshold = failure_threshold
        self._timeout = timeout
        self._expected_exception = expected_exception
        
        self._failure_count = 0
        self._last_failure_time: Optional[datetime] = None
        self._state = CircuitState.CLOSED
        self._lock = threading.Lock()

    def call(self, func: Callable, *args, **kwargs):
        """调用受保护的函数"""
        with self._lock:
            if self._state == CircuitState.OPEN:
                if self._should_attempt_reset():
                    self._state = CircuitState.HALF_OPEN
                else:
                    raise Exception("熔断器开启，服务不可用")
        
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except self._expected_exception as e:
            self._on_failure()
            raise e

    def _should_attempt_reset(self) -> bool:
        """判断是否应该尝试重置"""
        if self._last_failure_time is None:
            return False
        return datetime.now() - self._last_failure_time > timedelta(seconds=self._timeout)

    def _on_success(self) -> None:
        """成功时的处理"""
        with self._lock:
            self._failure_count = 0
            if self._state == CircuitState.HALF_OPEN:
                self._state = CircuitState.CLOSED

    def _on_failure(self) -> None:
        """失败时的处理"""
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = datetime.now()
            
            if self._failure_count >= self._failure_threshold:
                self._state = CircuitState.OPEN

    @property
    def state(self) -> CircuitState:
        """获取当前状态"""
        return self._state

    @property
    def failure_count(self) -> int:
        """获取失败次数"""
        return self._failure_count

    def reset(self) -> None:
        """手动重置熔断器"""
        with self._lock:
            self._failure_count = 0
            self._state = CircuitState.CLOSED
            self._last_failure_time = None
