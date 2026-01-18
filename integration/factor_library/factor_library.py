"""因子库主模块

提供统一的因子加载和管理接口。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from integration.factor_library.base import BaseFactor
from integration.factor_library.registry import get_factor_class, list_all_factors


class FactorLibrary:
    """因子库管理类

    负责加载因子配置、创建因子实例、批量计算因子。
    """

    def __init__(self, config_path: str | Path | None = None):
        """初始化因子库

        Args:
            config_path: 因子配置文件路径，如果为 None 则使用默认路径
        """
        if config_path is None:
            config_path = Path(__file__).parent / "factor_config.yaml"
        else:
            config_path = Path(config_path)

        self.config_path = config_path
        self.config = self._load_config()

    def _load_config(self) -> dict[str, Any]:
        """加载因子配置文件

        Returns:
            因子配置字典
        """
        if not self.config_path.exists():
            return {"factors": {}}

        with open(self.config_path, encoding="utf-8") as f:
            return yaml.safe_load(f) or {"factors": {}}

    def get_factor(
        self, factor_name: str, params: dict[str, Any] | None = None
    ) -> BaseFactor:
        """获取因子实例

        Args:
            factor_name: 因子名称
            params: 因子参数，如果为 None 则使用配置文件中的参数

        Returns:
            因子实例

        Raises:
            ValueError: 因子不存在时抛出
        """
        factor_class = get_factor_class(factor_name)
        if factor_class is None:
            msg = f"因子 '{factor_name}' 未注册"
            raise ValueError(msg)

        # 使用配置文件中的参数或传入的参数
        if params is None:
            factor_config = self.config.get("factors", {}).get(factor_name, {})
            params = factor_config.get("params", {})

        return factor_class(**params)

    def calculate_factors(
        self, df: pd.DataFrame, factor_names: list[str] | None = None
    ) -> pd.DataFrame:
        """批量计算因子

        Args:
            df: OHLCV 数据框
            factor_names: 要计算的因子名称列表，如果为 None 则计算所有启用的因子

        Returns:
            包含原始数据和因子值的数据框
        """
        result = df.copy()

        # 如果未指定因子列表，则使用配置文件中启用的因子
        if factor_names is None:
            factor_names = self.get_enabled_factors()

        for factor_name in factor_names:
            try:
                factor = self.get_factor(factor_name)
                result[factor_name] = factor.calculate(df)
            except Exception as e:
                print(f"计算因子 '{factor_name}' 时出错: {e}")
                result[factor_name] = None

        return result

    def get_enabled_factors(self) -> list[str]:
        """获取配置文件中启用的因子列表

        Returns:
            启用的因子名称列表
        """
        enabled = []
        for factor_name, factor_config in self.config.get("factors", {}).items():
            if factor_config.get("enabled", True):
                enabled.append(factor_name)
        return enabled

    def list_available_factors(self) -> list[str]:
        """列出所有可用的因子

        Returns:
            因子名称列表
        """
        return list_all_factors()
