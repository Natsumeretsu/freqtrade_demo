"""
因子验证模块 - MVP版本

提供 IC 分析、t 值检验、分位数分析等核心验证功能。
"""

from __future__ import annotations

import pandas as pd
import numpy as np
from scipy import stats
from typing import Dict, Tuple


def calculate_ic(
    factor: pd.Series,
    forward_return: pd.Series,
    method: str = 'pearson'
) -> float:
    """
    计算信息系数（IC）

    Args:
        factor: 因子值序列
        forward_return: 未来收益序列
        method: 相关系数方法 ('pearson' 或 'spearman')

    Returns:
        IC 值
    """
    # 移除 NaN 值
    valid_mask = factor.notna() & forward_return.notna()
    factor_clean = factor[valid_mask]
    return_clean = forward_return[valid_mask]

    if len(factor_clean) < 10:
        return np.nan

    if method == 'pearson':
        ic, _ = stats.pearsonr(factor_clean, return_clean)
    elif method == 'spearman':
        ic, _ = stats.spearmanr(factor_clean, return_clean)
    else:
        raise ValueError(f"不支持的方法: {method}")

    return ic


def calculate_ic_stats(
    factor: pd.Series,
    forward_return: pd.Series,
    method: str = 'pearson'
) -> Dict[str, float]:
    """
    计算 IC 和 t 统计量

    Args:
        factor: 因子值序列
        forward_return: 未来收益序列
        method: 相关系数方法

    Returns:
        包含 IC 和 t 值的字典
    """
    ic = calculate_ic(factor, forward_return, method)

    # 计算 t 值
    valid_mask = factor.notna() & forward_return.notna()
    n = valid_mask.sum()

    if n < 10:
        return {
            'ic': np.nan,
            't_stat': np.nan
        }

    # t = IC * sqrt(n-2) / sqrt(1-IC^2)
    if abs(ic) < 0.9999:
        t_stat = ic * np.sqrt(n - 2) / np.sqrt(1 - ic**2)
    else:
        t_stat = np.inf if ic > 0 else -np.inf

    return {
        'ic': ic,
        't_stat': t_stat
    }


def quantile_analysis(
    df: pd.DataFrame,
    factor_col: str,
    return_col: str,
    n_quantiles: int = 5
) -> pd.DataFrame:
    """
    分位数分析

    Args:
        df: 包含因子和收益的 DataFrame
        factor_col: 因子列名
        return_col: 收益列名
        n_quantiles: 分位数数量

    Returns:
        各分位数的统计信息
    """
    # 移除 NaN
    valid_df = df[[factor_col, return_col]].dropna()

    if len(valid_df) < n_quantiles * 2:
        return pd.DataFrame()

    # 分位数分组
    valid_df['quantile'] = pd.qcut(
        valid_df[factor_col],
        q=n_quantiles,
        labels=range(1, n_quantiles + 1),
        duplicates='drop'
    )

    # 计算各组统计
    stats_df = valid_df.groupby('quantile', observed=True)[return_col].agg([
        ('mean_return', 'mean'),
        ('std_return', 'std'),
        ('count', 'count')
    ]).reset_index()

    return stats_df


def validate_factor(
    df: pd.DataFrame,
    factor_col: str,
    return_col: str,
    ic_threshold: float = 0.05,
    t_threshold: float = 2.0
) -> Tuple[bool, Dict[str, float]]:
    """
    验证因子是否有效

    Args:
        df: 包含因子和收益的 DataFrame
        factor_col: 因子列名
        return_col: 收益列名
        ic_threshold: IC 阈值（默认 0.05）
        t_threshold: t 值阈值（默认 2.0）

    Returns:
        (是否通过验证, 统计指标字典)
    """
    stats = calculate_ic_stats(df[factor_col], df[return_col])

    # 验证标准
    passed = (
        abs(stats['ic']) >= ic_threshold and
        abs(stats['t_stat']) >= t_threshold
    )

    return passed, stats
