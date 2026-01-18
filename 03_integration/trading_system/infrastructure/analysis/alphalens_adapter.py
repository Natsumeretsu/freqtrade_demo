"""
Alphalens 数据格式适配器

将项目的数据格式转换为 Alphalens 要求的 MultiIndex 格式。

输入格式：
- Long format: DataFrame(date, pair, factor_value)
- Wide format: DataFrame with date as index, pairs as columns

输出格式：
- MultiIndex DataFrame with (date, asset) index
- Columns: factor values and forward returns
"""

from __future__ import annotations

from typing import Dict, List, Optional, Union

import numpy as np
import pandas as pd
from alphalens.utils import get_clean_factor_and_forward_returns


def convert_to_alphalens_format(
    factor_data: pd.DataFrame,
    pricing_data: Dict[str, pd.DataFrame],
    periods: List[int] = [1, 5, 10],
    quantiles: Optional[int] = 5,
    bins: Optional[int] = None,
) -> pd.DataFrame:
    """
    将项目数据格式转换为 Alphalens 格式

    参数：
        factor_data: 因子数据
            - Long format: columns=['date', 'pair', 'factor_value']
            - Wide format: index=date, columns=pairs
        pricing_data: 价格数据字典 {pair: DataFrame(date, close)}
        periods: 前瞻期列表（单位：K线数量）
        quantiles: 分位数数量（用于分层分析）
        bins: 自定义分箱边界

    返回：
        Alphalens 格式的 DataFrame
        - MultiIndex: (date, asset)
        - Columns: factor, period_1, period_5, period_10, ...
    """
    # 1. 标准化因子数据格式
    factor_wide = _standardize_factor_format(factor_data)

    # 2. 标准化价格数据格式
    pricing_wide = _standardize_pricing_format(pricing_data)

    # 3. 对齐时间索引
    factor_wide, pricing_wide = _align_timestamps(factor_wide, pricing_wide)

    # 4. 转换为 Alphalens 格式
    factor_data_alphalens = _convert_to_multiindex(factor_wide, pricing_wide, periods)

    # 5. 使用 Alphalens 的清洗函数
    clean_factor_data = get_clean_factor_and_forward_returns(
        factor=factor_data_alphalens['factor'],
        prices=pricing_wide,
        periods=periods,
        quantiles=quantiles,
        bins=bins,
    )

    return clean_factor_data


def _standardize_factor_format(factor_data: pd.DataFrame) -> pd.DataFrame:
    """
    标准化因子数据为 wide format

    输入：
        - Long format: columns=['date', 'pair', 'factor_value']
        - Wide format: index=date, columns=pairs

    输出：
        Wide format: index=date, columns=pairs
    """
    if 'date' in factor_data.columns and 'pair' in factor_data.columns:
        # Long format -> Wide format
        factor_wide = factor_data.pivot(
            index='date',
            columns='pair',
            values='factor_value'
        )
    else:
        # 已经是 Wide format
        factor_wide = factor_data.copy()

    # 确保索引是 datetime
    if not isinstance(factor_wide.index, pd.DatetimeIndex):
        factor_wide.index = pd.to_datetime(factor_wide.index)

    # 排序
    factor_wide = factor_wide.sort_index()

    return factor_wide


def _standardize_pricing_format(
    pricing_data: Dict[str, pd.DataFrame]
) -> pd.DataFrame:
    """
    标准化价格数据为 wide format

    输入：
        {pair: DataFrame(date, close)}

    输出：
        Wide format: index=date, columns=pairs, values=close
    """
    pricing_dict = {}

    for pair, df in pricing_data.items():
        if 'date' in df.columns:
            df = df.set_index('date')

        # 确保索引是 datetime
        if not isinstance(df.index, pd.DatetimeIndex):
            df.index = pd.to_datetime(df.index)

        # 提取 close 价格
        if 'close' in df.columns:
            pricing_dict[pair] = df['close']
        else:
            raise ValueError(f"价格数据缺少 'close' 列: {pair}")

    pricing_wide = pd.DataFrame(pricing_dict)
    pricing_wide = pricing_wide.sort_index()

    return pricing_wide


def _align_timestamps(
    factor_wide: pd.DataFrame,
    pricing_wide: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    对齐因子和价格数据的时间索引

    处理：
    - 时区统一
    - 索引对齐
    - 缺失值处理
    """
    # 统一时区（如果有）
    if factor_wide.index.tz is not None:
        factor_wide.index = factor_wide.index.tz_localize(None)
    if pricing_wide.index.tz is not None:
        pricing_wide.index = pricing_wide.index.tz_localize(None)

    # 对齐列（交易对）
    common_pairs = factor_wide.columns.intersection(pricing_wide.columns)
    if len(common_pairs) == 0:
        raise ValueError("因子数据和价格数据没有共同的交易对")

    factor_wide = factor_wide[common_pairs]
    pricing_wide = pricing_wide[common_pairs]

    # 对齐索引（时间）
    common_dates = factor_wide.index.intersection(pricing_wide.index)
    if len(common_dates) == 0:
        raise ValueError("因子数据和价格数据没有共同的时间点")

    factor_wide = factor_wide.loc[common_dates]
    pricing_wide = pricing_wide.loc[common_dates]

    return factor_wide, pricing_wide


def _convert_to_multiindex(
    factor_wide: pd.DataFrame,
    pricing_wide: pd.DataFrame,
    periods: List[int]
) -> pd.DataFrame:
    """
    转换为 MultiIndex 格式

    输入：
        factor_wide: index=date, columns=pairs
        pricing_wide: index=date, columns=pairs

    输出：
        MultiIndex DataFrame: (date, asset)
    """
    # Stack 转换为 MultiIndex
    factor_stacked = factor_wide.stack()
    factor_stacked.index.names = ['date', 'asset']

    # 创建 DataFrame
    result = pd.DataFrame({'factor': factor_stacked})

    return result


def validate_factor_data(factor_data: pd.DataFrame) -> None:
    """
    验证因子数据的有效性

    检查：
    - 数据类型
    - 缺失值比例
    - 异常值
    """
    if factor_data.empty:
        raise ValueError("因子数据为空")

    # 检查缺失值比例
    missing_ratio = factor_data.isnull().sum().sum() / factor_data.size
    if missing_ratio > 0.5:
        raise ValueError(f"因子数据缺失值过多: {missing_ratio:.1%}")

    # 检查是否全是 NaN
    if factor_data.isnull().all().all():
        raise ValueError("因子数据全部为 NaN")

    # 检查是否有无穷值
    if np.isinf(factor_data.select_dtypes(include=[np.number])).any().any():
        raise ValueError("因子数据包含无穷值")


def validate_pricing_data(pricing_data: Dict[str, pd.DataFrame]) -> None:
    """
    验证价格数据的有效性
    """
    if not pricing_data:
        raise ValueError("价格数据为空")

    for pair, df in pricing_data.items():
        if df.empty:
            raise ValueError(f"价格数据为空: {pair}")

        if 'close' not in df.columns and 'close' not in df.index.names:
            raise ValueError(f"价格数据缺少 'close' 列: {pair}")
