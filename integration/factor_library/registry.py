"""因子库核心模块

提供因子注册、加载和管理功能。
"""

from __future__ import annotations

from typing import Any

from integration.factor_library.base import BaseFactor


class FactorRegistry:
    """因子注册中心

    管理所有已注册的因子类。
    """

    def __init__(self):
        self._factors: dict[str, type[BaseFactor]] = {}

    def register(self, factor_class: type[BaseFactor]) -> type[BaseFactor]:
        """注册因子类

        Args:
            factor_class: 因子类（必须继承 BaseFactor）

        Returns:
            原因子类（用于装饰器）

        Raises:
            ValueError: 因子名称重复时抛出
        """
        # 创建临时实例以获取因子名称
        temp_instance = factor_class()
        factor_name = temp_instance.name

        if factor_name in self._factors:
            msg = f"因子 '{factor_name}' 已注册"
            raise ValueError(msg)

        self._factors[factor_name] = factor_class
        return factor_class

    def get(self, factor_name: str) -> type[BaseFactor] | None:
        """获取因子类

        Args:
            factor_name: 因子名称

        Returns:
            因子类，如果不存在则返回 None
        """
        return self._factors.get(factor_name)

    def list_factors(self) -> list[str]:
        """列出所有已注册的因子名称

        Returns:
            因子名称列表
        """
        return list(self._factors.keys())

    def clear(self) -> None:
        """清空注册表（主要用于测试）"""
        self._factors.clear()


# 全局因子注册表
_registry = FactorRegistry()


def register_factor(factor_class: type[BaseFactor]) -> type[BaseFactor]:
    """因子注册装饰器

    用法:
        @register_factor
        class MyFactor(BaseFactor):
            ...

    Args:
        factor_class: 因子类

    Returns:
        原因子类
    """
    return _registry.register(factor_class)


def get_factor_class(factor_name: str) -> type[BaseFactor] | None:
    """获取因子类

    Args:
        factor_name: 因子名称

    Returns:
        因子类，如果不存在则返回 None
    """
    return _registry.get(factor_name)


def list_all_factors() -> list[str]:
    """列出所有已注册的因子

    Returns:
        因子名称列表
    """
    return _registry.list_factors()
