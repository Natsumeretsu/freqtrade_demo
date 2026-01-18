"""因子基础类

定义因子的抽象接口和基础功能。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import pandas as pd


class BaseFactor(ABC):
    """因子抽象基类

    所有因子必须继承此类并实现 calculate 方法。
    """

    def __init__(self, **params: Any):
        """初始化因子

        Args:
            **params: 因子参数（如窗口大小、阈值等）
        """
        self.params = params
        self._validate_params()

    @property
    @abstractmethod
    def name(self) -> str:
        """因子名称（唯一标识符）"""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """因子描述"""
        pass

    @property
    def dependencies(self) -> list[str]:
        """依赖的数据列

        Returns:
            数据列名列表，默认为 OHLCV
        """
        return ["open", "high", "low", "close", "volume"]

    @property
    def category(self) -> str:
        """因子类别

        Returns:
            因子类别（technical/price_pattern/volume/composite）
        """
        return "technical"

    @abstractmethod
    def calculate(self, df: pd.DataFrame) -> pd.Series:
        """计算因子值

        Args:
            df: OHLCV 数据框，必须包含 dependencies 中指定的列

        Returns:
            因子值序列，索引与输入数据框一致
        """
        pass

    def _validate_params(self) -> None:
        """验证参数有效性

        子类可以重写此方法来实现自定义参数验证。

        Raises:
            ValueError: 参数无效时抛出
        """
        pass

    def __repr__(self) -> str:
        """字符串表示"""
        params_str = ", ".join(f"{k}={v}" for k, v in self.params.items())
        return f"{self.__class__.__name__}({params_str})"
