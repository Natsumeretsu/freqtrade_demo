from __future__ import annotations

"""
factor_usecase.py - 因子计算用例（编排层）
"""

import pandas as pd

from trading_system.domain.factor_engine import IFactorEngine


class FactorComputationUseCase:
    """用例：给 DataFrame 补齐所需因子列（覆盖同名列）。"""

    def __init__(self, engine: IFactorEngine) -> None:
        self._engine = engine

    def execute(self, dataframe: pd.DataFrame, factor_names: list[str]) -> pd.DataFrame:
        if dataframe is None or dataframe.empty:
            return dataframe

        names = [str(n).strip() for n in (factor_names or []) if str(n).strip()]
        if not names:
            return dataframe

        unsupported = [n for n in names if not self._engine.supports(n)]
        if unsupported:
            raise ValueError(f"不支持的因子名：{unsupported}")

        factors = self._engine.compute(dataframe, names)
        if factors is None or factors.empty:
            return dataframe

        # 以“覆盖同名列”的方式合并，避免 join 后出现重复列或旧值残留
        out = dataframe.copy()
        for col in factors.columns:
            out[col] = factors[col]
        return out

