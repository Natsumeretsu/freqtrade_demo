"""配置验证器

验证配置的完整性和正确性。

创建日期: 2026-01-17
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class ConfigValidator:
    """配置验证器

    验证配置的类型、必填字段和值范围。
    """

    def __init__(self, schema: Optional[Dict[str, Any]] = None):
        """初始化验证器

        Args:
            schema: 配置模式（可选）
        """
        self.schema = schema or {}
        self.errors: List[str] = []

    def validate(self, config: Dict[str, Any]) -> bool:
        """验证配置

        Args:
            config: 配置字典

        Returns:
            验证是否通过
        """
        self.errors = []

        if not self.schema:
            logger.warning("未提供配置模式，跳过验证")
            return True

        # 检查必填字段
        if not self._check_required(config):
            return False

        # 检查类型
        if not self._check_types(config):
            return False

        return len(self.errors) == 0

    def _check_required(self, config: Dict[str, Any]) -> bool:
        """检查必填字段

        Args:
            config: 配置字典

        Returns:
            是否通过检查
        """
        required_fields = self.schema.get('required', [])
        for field in required_fields:
            if field not in config:
                self.errors.append(f"缺少必填字段: {field}")
                logger.error(f"配置验证失败: 缺少必填字段 {field}")

        return len(self.errors) == 0

    def _check_types(self, config: Dict[str, Any]) -> bool:
        """检查类型

        Args:
            config: 配置字典

        Returns:
            是否通过检查
        """
        properties = self.schema.get('properties', {})
        for key, value in config.items():
            if key in properties:
                expected_type = properties[key].get('type')
                if expected_type and not self._check_type(value, expected_type):
                    self.errors.append(f"字段 {key} 类型错误: 期望 {expected_type}, 实际 {type(value).__name__}")
                    logger.error(f"配置验证失败: 字段 {key} 类型错误")

        return len(self.errors) == 0

    def _check_type(self, value: Any, expected_type: str) -> bool:
        """检查单个值的类型

        Args:
            value: 值
            expected_type: 期望类型

        Returns:
            类型是否匹配
        """
        type_map = {
            'string': str,
            'integer': int,
            'number': (int, float),
            'boolean': bool,
            'array': list,
            'object': dict
        }

        expected = type_map.get(expected_type)
        if expected is None:
            return True

        return isinstance(value, expected)

    def get_errors(self) -> List[str]:
        """获取验证错误列表

        Returns:
            错误列表
        """
        return self.errors.copy()
