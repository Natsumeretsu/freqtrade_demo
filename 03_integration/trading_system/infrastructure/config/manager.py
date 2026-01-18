"""配置管理器

统一的配置管理接口。

创建日期: 2026-01-17
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from .loader import ConfigLoader
from .validator import ConfigValidator

logger = logging.getLogger(__name__)


class ConfigManager:
    """配置管理器

    提供统一的配置访问接口，支持配置加载、验证和访问。
    """

    def __init__(self, schema: Optional[Dict[str, Any]] = None):
        """初始化配置管理器

        Args:
            schema: 配置模式（可选）
        """
        self.loader = ConfigLoader()
        self.validator = ConfigValidator(schema)
        self._config: Dict[str, Any] = {}

    def load(self, file_path: str, environment: Optional[str] = None) -> None:
        """加载配置

        Args:
            file_path: 配置文件路径
            environment: 环境名称（可选）
        """
        # 加载基础配置
        base_config = self.loader.load_from_file(file_path)

        # 加载环境特定配置（如果指定）
        configs = [base_config]
        if environment:
            env_file = file_path.replace('.json', f'.{environment}.json')
            try:
                env_config = self.loader.load_from_file(env_file)
                configs.append(env_config)
                logger.info(f"加载环境配置: {environment}")
            except FileNotFoundError:
                logger.warning(f"环境配置文件不存在: {env_file}")

        # 加载环境变量
        env_config = self.loader.load_from_env()
        if env_config:
            configs.append(env_config)

        # 合并配置
        self._config = self.loader.merge_configs(*configs)
        logger.info(f"配置加载完成，共 {len(self._config)} 项")

    def get(self, key: str, default: Any = None) -> Any:
        """获取配置值

        支持点号分隔的嵌套键（如 "cache.max_size"）。

        Args:
            key: 配置键
            default: 默认值

        Returns:
            配置值
        """
        keys = key.split('.')
        value = self._config

        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default

        return value

    def set(self, key: str, value: Any) -> None:
        """设置配置值

        支持点号分隔的嵌套键（如 "cache.max_size"）。

        Args:
            key: 配置键
            value: 配置值
        """
        keys = key.split('.')
        config = self._config

        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]

        config[keys[-1]] = value
        logger.debug(f"设置配置: {key} = {value}")

    def validate(self) -> bool:
        """验证配置

        Returns:
            验证是否通过
        """
        is_valid = self.validator.validate(self._config)
        if not is_valid:
            errors = self.validator.get_errors()
            for error in errors:
                logger.error(f"配置验证错误: {error}")
        return is_valid

    def reload(self, file_path: str, environment: Optional[str] = None) -> None:
        """重新加载配置

        Args:
            file_path: 配置文件路径
            environment: 环境名称（可选）
        """
        logger.info("重新加载配置")
        self.load(file_path, environment)

    def get_all(self) -> Dict[str, Any]:
        """获取所有配置

        Returns:
            配置字典
        """
        return self._config.copy()
