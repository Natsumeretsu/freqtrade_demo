"""系统配置

集成所有新功能的配置管理。

创建日期: 2026-01-17
"""
from typing import Dict, Any
from pathlib import Path


class SystemConfig:
    """系统配置管理器"""

    def __init__(self):
        self.config: Dict[str, Any] = self._load_default_config()

    def _load_default_config(self) -> Dict[str, Any]:
        """加载默认配置"""
        return {
            'cache': {
                'enabled': True,
                'max_size': 1000
            },
            'degradation': {
                'enabled': True,
                'failure_threshold': 5,
                'timeout': 60
            }
        }

    def get(self, key: str, default: Any = None) -> Any:
        """获取配置值"""
        keys = key.split('.')
        value = self.config
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return default
        return value if value is not None else default

    def set(self, key: str, value: Any) -> None:
        """设置配置值"""
        keys = key.split('.')
        config = self.config
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        config[keys[-1]] = value
