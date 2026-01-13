from __future__ import annotations

"""
factor_engine.py - 因子计算引擎抽象（DIP 的核心）

策略应尽量只依赖本模块提供的抽象（接口），而不是直接依赖 talib / qlib 等具体实现。
"""

from abc import ABC, abstractmethod

import pandas as pd


class IFactorEngine(ABC):
    """因子计算引擎接口：给定 OHLCV DataFrame，输出若干因子列。"""

    @abstractmethod
    def supports(self, factor_name: str) -> bool:
        """该引擎是否支持该因子名（支持带参数的命名约定）。"""

    @abstractmethod
    def compute(self, data: pd.DataFrame, factor_names: list[str]) -> pd.DataFrame:
        """
        计算若干因子，返回 DataFrame（index 与 data 对齐）。

        - data: 需要包含 open/high/low/close/volume 等列（具体看实现）。
        - factor_names: 因子名称列表（建议使用项目约定的命名规则）。
        """

