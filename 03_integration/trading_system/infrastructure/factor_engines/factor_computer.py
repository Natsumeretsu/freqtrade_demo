"""因子计算器接口和基础实现

定义因子计算器的统一接口，用于拆分 TalibFactorEngine 的巨型方法。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
import pandas as pd
import re


class IFactorComputer(ABC):
    """因子计算器接口"""

    @abstractmethod
    def can_compute(self, factor_name: str) -> bool:
        """判断是否可以计算该因子

        Args:
            factor_name: 因子名称

        Returns:
            True 如果可以计算，否则 False
        """
        pass

    @abstractmethod
    def compute(self, data: pd.DataFrame, factor_name: str) -> pd.Series:
        """计算因子

        Args:
            data: OHLCV 数据
            factor_name: 因子名称

        Returns:
            计算后的因子值
        """
        pass


class FactorComputerRegistry:
    """因子计算器注册表"""

    def __init__(self):
        self._computers: list[IFactorComputer] = []

    def register(self, computer: IFactorComputer) -> None:
        """注册因子计算器

        Args:
            computer: 因子计算器实例
        """
        self._computers.append(computer)

    def get_computer(self, factor_name: str) -> IFactorComputer | None:
        """根据因子名称获取对应的计算器

        Args:
            factor_name: 因子名称

        Returns:
            对应的计算器，如果没有则返回 None
        """
        for computer in self._computers:
            if computer.can_compute(factor_name):
                return computer
        return None

    def get_all_computers(self) -> list[IFactorComputer]:
        """获取所有注册的计算器"""
        return self._computers.copy()
