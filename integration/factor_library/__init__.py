"""因子库模块

提供统一的因子定义、注册和管理功能。
"""

from integration.factor_library.base import BaseFactor
from integration.factor_library.factor_library import FactorLibrary
from integration.factor_library.registry import (
    get_factor_class,
    list_all_factors,
    register_factor,
)

# 导入所有因子模块以触发注册
from integration.factor_library import technical  # noqa: F401

__all__ = [
    "BaseFactor",
    "FactorLibrary",
    "register_factor",
    "get_factor_class",
    "list_all_factors",
]
