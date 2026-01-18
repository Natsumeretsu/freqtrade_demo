"""
数据清洗模块 - MVP版本

功能：
1. 异常值检测与处理（闪崩、拉盘）
2. 缺失值填充
3. 数据质量报告

使用示例：
    from clean import clean_ohlcv
    df_clean = clean_ohlcv(df_raw)
"""

from __future__ import annotations

import pandas as pd
import numpy as np


def detect_outliers(df: pd.DataFrame, column: str = "close", threshold: float = 0.2) -> pd.Series:
    """
    检测异常值（单根K线涨跌幅超过阈值）

    Args:
        df: OHLCV DataFrame
        column: 检测的列名
        threshold: 涨跌幅阈值（默认20%）

    Returns:
        布尔Series，True表示异常值
    """
    returns = df[column].pct_change()
    is_outlier = returns.abs() > threshold
    return is_outlier


def clean_ohlcv(df: pd.DataFrame, remove_outliers: bool = True) -> pd.DataFrame:
    """
    清洗OHLCV数据

    Args:
        df: 原始OHLCV DataFrame
        remove_outliers: 是否移除异常值

    Returns:
        清洗后的DataFrame
    """
    df_clean = df.copy()

    # 1. 移除重复时间戳
    df_clean = df_clean[~df_clean.index.duplicated(keep="first")]

    # 2. 检测异常值
    outliers = detect_outliers(df_clean)
    if outliers.sum() > 0:
        print(f"检测到 {outliers.sum()} 个异常值")
        if remove_outliers:
            df_clean = df_clean[~outliers]
            print(f"已移除异常值，剩余 {len(df_clean)} 条数据")

    # 3. 填充缺失值（前向填充）
    df_clean = df_clean.fillna(method="ffill")

    # 4. 数据质量报告
    print("\n数据质量报告：")
    print(f"- 总行数：{len(df_clean)}")
    print(f"- 时间范围：{df_clean.index.min()} 至 {df_clean.index.max()}")
    print(f"- 缺失值：{df_clean.isnull().sum().sum()}")

    return df_clean


if __name__ == "__main__":
    # 测试代码
    from pathlib import Path

    data_path = Path("02_qlib_research/qlib_data/okx/BTC_USDT/15m.parquet")
    if data_path.exists():
        df = pd.read_parquet(data_path)
        df_clean = clean_ohlcv(df)
        print("\n清洗完成！")
    else:
        print(f"数据文件不存在：{data_path}")
