"""系统管理器

集成所有新功能的统一管理接口。

创建日期: 2026-01-17
"""
from typing import Optional
from .system_config import SystemConfig
from .infrastructure.cache import AdaptiveCache
from .infrastructure.degradation import DegradationManager
from .infrastructure.monitoring import PerformanceMonitor
from .backtest import IncrementalBacktest


class SystemManager:
    """系统管理器"""

    def __init__(self, config: Optional[SystemConfig] = None):
        self.config = config or SystemConfig()
        self._initialize_components()

    def _initialize_components(self) -> None:
        """初始化各个组件"""
        # 初始化缓存
        if self.config.get('cache.enabled', True):
            cache_size = self.config.get('cache.max_size', 1000)
            self.cache = AdaptiveCache(initial_size=cache_size)
        else:
            self.cache = None
        
        # 初始化降级管理器
        if self.config.get('degradation.enabled', True):
            self.degradation = DegradationManager()
        else:
            self.degradation = None
        
        # 初始化性能监控
        self.monitor = PerformanceMonitor(interval=1.0)
        
        # 初始化增量回测
        self.backtest = IncrementalBacktest()

    def start(self) -> None:
        """启动系统"""
        if self.monitor:
            self.monitor.start()

    def stop(self) -> None:
        """停止系统"""
        if self.monitor:
            self.monitor.stop()

    def get_status(self) -> dict:
        """获取系统状态"""
        return {
            'cache_enabled': self.cache is not None,
            'degradation_enabled': self.degradation is not None,
            'monitor_running': self.monitor._running if self.monitor else False
        }
