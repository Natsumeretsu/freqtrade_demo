"""配置加载器

从多个来源加载和合并配置。

创建日期: 2026-01-17
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class ConfigLoader:
    """配置加载器

    支持从文件和环境变量加载配置，并按优先级合并。
    """

    def __init__(self):
        """初始化配置加载器"""
        self._config: Dict[str, Any] = {}

    def load_from_file(self, file_path: str) -> Dict[str, Any]:
        """从文件加载配置

        Args:
            file_path: 配置文件路径

        Returns:
            配置字典

        Raises:
            FileNotFoundError: 如果文件不存在
            ValueError: 如果文件格式不支持
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"配置文件不存在: {file_path}")

        suffix = path.suffix.lower()
        if suffix == '.json':
            return self._load_json(path)
        else:
            raise ValueError(f"不支持的配置文件格式: {suffix}")

    def _load_json(self, path: Path) -> Dict[str, Any]:
        """加载 JSON 配置文件

        Args:
            path: 文件路径

        Returns:
            配置字典
        """
        with open(path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        logger.debug(f"从 JSON 文件加载配置: {path}")
        return config

    def load_from_env(self, prefix: str = "TRADING_") -> Dict[str, Any]:
        """从环境变量加载配置

        Args:
            prefix: 环境变量前缀

        Returns:
            配置字典
        """
        config = {}
        for key, value in os.environ.items():
            if key.startswith(prefix):
                # 移除前缀并转换为小写
                config_key = key[len(prefix):].lower()
                # 尝试解析为 JSON（支持复杂类型）
                try:
                    config[config_key] = json.loads(value)
                except json.JSONDecodeError:
                    config[config_key] = value

        logger.debug(f"从环境变量加载配置: {len(config)} 项")
        return config

    def merge_configs(self, *configs: Dict[str, Any]) -> Dict[str, Any]:
        """合并多个配置字典

        后面的配置会覆盖前面的配置（深度合并）。

        Args:
            *configs: 配置字典列表

        Returns:
            合并后的配置字典
        """
        result = {}
        for config in configs:
            result = self._deep_merge(result, config)
        return result

    def _deep_merge(self, base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """深度合并两个字典

        Args:
            base: 基础字典
            override: 覆盖字典

        Returns:
            合并后的字典
        """
        result = base.copy()
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        return result
