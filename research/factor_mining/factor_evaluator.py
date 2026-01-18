"""因子评估器

提供系统化的因子评估功能，包括 IC、IR、分组回测等。
"""

from __future__ import annotations

import pandas as pd
import numpy as np
from scipy import stats


class FactorEvaluator:
    """因子评估器

    用于评估因子的有效性和稳定性。
    """

    def __init__(self):
        """初始化因子评估器"""
        pass

    def calculate_ic(
        self, factor_values: pd.Series, forward_returns: pd.Series
    ) -> float:
        """计算信息系数（IC）

        IC 衡量因子与未来收益的线性相关性。

        Args:
            factor_values: 因子值序列
            forward_returns: 未来收益序列

        Returns:
            IC 值（Pearson 相关系数）
        """
        # 移除 NaN 值
        valid_mask = ~(factor_values.isna() | forward_returns.isna())
        factor_clean = factor_values[valid_mask]
        returns_clean = forward_returns[valid_mask]

        if len(factor_clean) < 2:
            return np.nan

        return factor_clean.corr(returns_clean)

    def calculate_rank_ic(
        self, factor_values: pd.Series, forward_returns: pd.Series
    ) -> float:
        """计算秩相关 IC（Rank IC）

        使用 Spearman 秩相关系数，对异常值更稳健。

        Args:
            factor_values: 因子值序列
            forward_returns: 未来收益序列

        Returns:
            Rank IC 值（Spearman 相关系数）
        """
        # 移除 NaN 值
        valid_mask = ~(factor_values.isna() | forward_returns.isna())
        factor_clean = factor_values[valid_mask]
        returns_clean = forward_returns[valid_mask]

        if len(factor_clean) < 2:
            return np.nan

        return factor_clean.corr(returns_clean, method="spearman")

    def calculate_ir(self, ic_series: pd.Series) -> float:
        """计算信息比率（IR）

        IR = IC 均值 / IC 标准差，衡量 IC 的稳定性。

        Args:
            ic_series: IC 时间序列

        Returns:
            IR 值
        """
        ic_clean = ic_series.dropna()
        if len(ic_clean) < 2:
            return np.nan

        ic_mean = ic_clean.mean()
        ic_std = ic_clean.std()

        if ic_std == 0:
            return np.nan

        return ic_mean / ic_std

    def group_backtest(
        self,
        factor_values: pd.Series,
        forward_returns: pd.Series,
        n_groups: int = 5,
    ) -> pd.DataFrame:
        """分组回测

        按因子值分组，计算每组的平均收益。

        Args:
            factor_values: 因子值序列
            forward_returns: 未来收益序列
            n_groups: 分组数量，默认5

        Returns:
            分组回测结果（包含每组的平均收益、样本数等）
        """
        # 创建数据框
        df = pd.DataFrame({
            "factor": factor_values,
            "return": forward_returns,
        }).dropna()

        if len(df) < n_groups:
            return pd.DataFrame()

        # 按因子值分组
        df["group"] = pd.qcut(
            df["factor"],
            q=n_groups,
            labels=[f"Q{i+1}" for i in range(n_groups)],
            duplicates="drop",
        )

        # 计算每组的统计指标
        result = df.groupby("group", observed=True).agg({
            "return": ["mean", "std", "count"],
        }).round(6)

        result.columns = ["mean_return", "std_return", "count"]
        return result.reset_index()

    def evaluate_factor(
        self,
        factor_values: pd.Series,
        forward_returns: pd.Series,
        n_groups: int = 5,
    ) -> dict:
        """综合评估单个因子

        Args:
            factor_values: 因子值序列
            forward_returns: 未来收益序列
            n_groups: 分组数量，默认5

        Returns:
            评估报告字典，包含 IC、IR、分组回测结果等
        """
        # 计算 IC 和 Rank IC
        ic = self.calculate_ic(factor_values, forward_returns)
        rank_ic = self.calculate_rank_ic(factor_values, forward_returns)

        # 计算 t 统计量（显著性检验）
        valid_mask = ~(factor_values.isna() | forward_returns.isna())
        n_samples = valid_mask.sum()

        if n_samples > 2:
            t_stat = ic * np.sqrt(n_samples - 2) / np.sqrt(1 - ic**2) if abs(ic) < 1 else np.nan
        else:
            t_stat = np.nan

        # 分组回测
        group_result = self.group_backtest(factor_values, forward_returns, n_groups)

        return {
            "ic": ic,
            "rank_ic": rank_ic,
            "t_stat": t_stat,
            "n_samples": int(n_samples),
            "group_backtest": group_result,
        }
