from __future__ import annotations

"""
freqtrade_data.py - Freqtrade 运行时数据适配（不直接依赖 freqtrade 包）

用途：
- 统一处理 dp.get_analyzed_dataframe / dp.get_pair_dataframe 的取数与“按 current_time 裁剪”
- 解决回测/实盘中常见的 timezone/naive 差异导致的错位问题

说明：
- 本模块放在 infrastructure，因为 dp 属于外部依赖；但这里仅用 duck-typing，不 import freqtrade。
"""

from datetime import datetime, timezone
from typing import Any

import numpy as np
import pandas as pd


def _candidate_times(current_time: datetime) -> list[datetime]:
    """生成若干候选时间，用于兼容 tz-aware / naive 的比较。"""
    out: list[datetime] = []
    if not isinstance(current_time, datetime):
        return out

    out.append(current_time)
    try:
        out.append(current_time.replace(tzinfo=None))
    except Exception:
        pass
    try:
        out.append(current_time.replace(tzinfo=timezone.utc))
    except Exception:
        pass

    # 去重（按 timestamp/iso 表达去重即可）
    uniq: list[datetime] = []
    seen: set[str] = set()
    for t in out:
        k = str(t)
        if k in seen:
            continue
        seen.add(k)
        uniq.append(t)
    return uniq


def cut_dataframe_upto_time(df: pd.DataFrame, current_time: datetime) -> pd.DataFrame:
    """
    将 DataFrame 裁剪到 current_time 之前（包含等于）。

    - 若 df 无 date 列 / 裁剪失败，则返回原 df
    - 若裁剪后为空，则返回原 df（避免误伤导致 0 行）
    """
    if df is None or df.empty:
        return df
    if "date" not in df.columns:
        return df

    for t in _candidate_times(current_time):
        try:
            tmp = df[df["date"] <= t]
        except Exception:
            continue
        if tmp is not None and not tmp.empty:
            return tmp
    return df


def get_last_candle_timestamp(df: pd.DataFrame) -> pd.Timestamp | None:
    """从 DataFrame 的 date 列提取最后一根 K 线时间戳（utc）。"""
    if df is None or df.empty or "date" not in df.columns:
        return None
    try:
        ts = pd.to_datetime(df["date"].iloc[-1], utc=True, errors="coerce")
    except Exception:
        return None
    if ts is None or (isinstance(ts, pd.Timestamp) and pd.isna(ts)):
        return None
    return ts


def get_analyzed_dataframe_upto_time(
    dp: Any,
    *,
    pair: str,
    timeframe: str,
    current_time: datetime,
) -> pd.DataFrame | None:
    """
    读取 analyzed_dataframe，并尽量裁剪到 current_time 之前。

    dp 需提供：get_analyzed_dataframe(pair, timeframe) -> (DataFrame, metadata)
    """
    if dp is None:
        return None
    try:
        df, _ = dp.get_analyzed_dataframe(pair, timeframe)
    except Exception:
        return None
    if df is None or df.empty:
        return None
    return cut_dataframe_upto_time(df, current_time)


def get_pair_dataframe_upto_time(
    dp: Any,
    *,
    pair: str,
    timeframe: str,
    current_time: datetime,
    candle_type: str | None = None,
) -> pd.DataFrame | None:
    """
    读取 pair_dataframe，并尽量裁剪到 current_time 之前。

    dp 需提供：get_pair_dataframe(pair=..., timeframe=..., candle_type=...) -> DataFrame
    """
    if dp is None:
        return None
    try:
        if candle_type is None:
            df = dp.get_pair_dataframe(pair=pair, timeframe=timeframe)
        else:
            df = dp.get_pair_dataframe(pair=pair, timeframe=timeframe, candle_type=candle_type)
    except Exception:
        return None
    if df is None or df.empty:
        return None
    return cut_dataframe_upto_time(df, current_time)


def get_latest_funding_rate(
    dp: Any,
    *,
    pair: str,
    current_time: datetime,
    timeframe: str = "8h",
    candle_type: str = "funding_rate",
) -> float | None:
    """
    获取最新 funding_rate（仅当 DataProvider 提供该 candle_type 时可用）。

    - 返回 None 表示“无数据/不可用”，上层可选择 fail-open
    """
    df = get_pair_dataframe_upto_time(
        dp,
        pair=str(pair),
        timeframe=str(timeframe),
        candle_type=str(candle_type),
        current_time=current_time,
    )
    if df is None or df.empty:
        return None

    last = df.iloc[-1]
    for col in ("funding_rate", "fundingRate", "funding", "rate"):
        if col not in df.columns:
            continue
        try:
            v = float(last.get(col, np.nan))
        except Exception:
            continue
        if np.isfinite(v):
            return float(v)
        return None
    return None


def build_macro_sma_informative_dataframe(
    dp: Any,
    *,
    pair: str,
    timeframe: str,
    sma_period: int,
) -> pd.DataFrame | None:
    """
    构造“宏观体制”信息表（给策略 merge_informative_pair 用）。

    约定输出列：
    - date
    - macro_close
    - macro_sma

    说明：
    - 不在此处做 merge（避免引入 freqtrade 依赖）；由策略侧调用 merge_informative_pair 完成对齐。
    - 若 dp 不可用/数据缺失，则返回 None（上层可选择 fail-open）。
    """
    if dp is None:
        return None

    tf = str(timeframe or "").strip()
    if not tf:
        return None

    period = int(sma_period)
    if period <= 0:
        period = 1

    try:
        informative = dp.get_pair_dataframe(pair=str(pair), timeframe=tf)
    except Exception:
        return None
    if informative is None or informative.empty:
        return None

    if "date" not in informative.columns or "close" not in informative.columns:
        return None

    inf = informative.copy()
    inf["macro_close"] = inf["close"]
    inf["macro_sma"] = inf["macro_close"].rolling(period).mean()
    out = inf[["date", "macro_close", "macro_sma"]].copy()
    return out.replace([np.inf, -np.inf], np.nan)
