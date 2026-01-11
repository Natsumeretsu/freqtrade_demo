"""
backtest_utils.py - 回测结果处理公共工具

提供回测 zip 文件读取、策略名解析、时间范围提取等通用功能。
"""
from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pandas as pd


def read_backtest_zip(zip_path: Path) -> tuple[dict, pd.DataFrame | None]:
    """
    读取回测结果 zip 文件。

    Args:
        zip_path: 回测结果 zip 路径

    Returns:
        (data, market_df): JSON 数据和 market_change DataFrame（如果存在）

    Raises:
        FileNotFoundError: zip 文件不存在
    """
    if not zip_path.is_file():
        raise FileNotFoundError(f"未找到 zip：{zip_path}")

    base = zip_path.with_suffix("").name
    json_name = f"{base}.json"
    feather_name = f"{base}_market_change.feather"

    with zipfile.ZipFile(zip_path) as zf:
        data = json.loads(zf.read(json_name))

        market_df = None
        if feather_name in zf.namelist():
            with zf.open(feather_name) as f:
                market_df = pd.read_feather(f)

    return data, market_df


def read_backtest_zip_with_config(zip_path: Path) -> tuple[dict, dict]:
    """
    读取回测结果 zip 文件（包含配置）。

    Args:
        zip_path: 回测结果 zip 路径

    Returns:
        (data, config): JSON 数据和配置字典

    Raises:
        FileNotFoundError: zip 文件不存在
    """
    if not zip_path.is_file():
        raise FileNotFoundError(f"未找到 zip：{zip_path}")

    json_name = zip_path.with_suffix(".json").name
    cfg_name = zip_path.with_suffix("").name + "_config.json"

    with zipfile.ZipFile(zip_path) as zf:
        data = json.loads(zf.read(json_name))
        config = json.loads(zf.read(cfg_name)) if cfg_name in set(zf.namelist()) else {}

    return data, config


def pick_strategy_name(data: dict, requested: str = "") -> str:
    """
    从回测结果中选择策略名。

    Args:
        data: 回测结果 JSON 数据
        requested: 用户指定的策略名（可选）

    Returns:
        策略名

    Raises:
        ValueError: 无法自动判断策略名
    """
    requested = (requested or "").strip()
    if requested:
        return requested

    strategies = list((data.get("strategy") or {}).keys())
    if len(strategies) != 1:
        raise ValueError(
            f"无法自动判断策略名（zip 内策略数={len(strategies)}），请用 --strategy 指定"
        )
    return strategies[0]


def extract_backtest_range(strategy_data: dict) -> tuple[pd.Timestamp, pd.Timestamp]:
    """
    从策略数据中提取回测时间范围。

    Args:
        strategy_data: 策略数据字典

    Returns:
        (start, end): 回测开始和结束时间

    Raises:
        ValueError: 缺少或无法解析时间范围
    """
    start_raw = strategy_data.get("backtest_start")
    end_raw = strategy_data.get("backtest_end")

    if not start_raw or not end_raw:
        raise ValueError("回测结果缺少 backtest_start/backtest_end")

    start = pd.to_datetime(start_raw, utc=True, errors="coerce")
    end = pd.to_datetime(end_raw, utc=True, errors="coerce")

    if pd.isna(start) or pd.isna(end):
        raise ValueError("backtest_start/backtest_end 无法解析为时间")
    if end <= start:
        raise ValueError("backtest_end 必须晚于 backtest_start")

    return start, end


def extract_pairs(strategy_data: dict) -> list[str]:
    """
    从策略数据中提取交易对列表。

    Args:
        strategy_data: 策略数据字典

    Returns:
        交易对列表（去重保序）
    """
    out: list[str] = []
    for row in strategy_data.get("results_per_pair") or []:
        if not isinstance(row, dict):
            continue
        pair = str(row.get("key") or "").strip()
        if not pair or pair.upper() == "TOTAL":
            continue
        out.append(pair)
    return list(dict.fromkeys(out))


def pair_to_data_filename(pair: str, timeframe: str) -> str:
    """
    将交易对转换为数据文件名。

    Args:
        pair: 交易对，如 "BTC/USDT"
        timeframe: 时间周期，如 "1h"

    Returns:
        文件名，如 "BTC_USDT-1h.feather"
    """
    return f"{pair.replace('/', '_')}-{timeframe}.feather"


def pair_to_data_path(
    datadir: Path,
    *,
    pair: str,
    timeframe: str,
    trading_mode: str = "spot",
) -> Path:
    """
    获取交易对数据文件路径。

    Args:
        datadir: 数据目录
        pair: 交易对
        timeframe: 时间周期
        trading_mode: 交易模式 (spot/futures)

    Returns:
        数据文件路径

    Raises:
        FileNotFoundError: 未找到数据文件
    """
    safe = pair.replace("/", "_").replace(":", "_")
    tf = str(timeframe).strip()
    mode = str(trading_mode).strip().lower()

    if mode == "futures":
        candidates = [
            datadir / "futures" / f"{safe}-{tf}-futures.feather",
            datadir / "futures" / f"{safe}-{tf}.feather",
        ]
    else:
        candidates = [
            datadir / f"{safe}-{tf}.feather",
            datadir / "spot" / f"{safe}-{tf}.feather",
        ]

    for p in candidates:
        if p.is_file():
            return p

    tried = "\n".join(f"- {p.as_posix()}" for p in candidates)
    raise FileNotFoundError(
        f"未找到交易对数据文件（pair={pair} timeframe={tf} mode={mode}）：\n{tried}"
    )


def build_daily_index(
    backtest_start: pd.Timestamp,
    backtest_end: pd.Timestamp,
) -> pd.DatetimeIndex:
    """
    构建日级别时间索引。

    Args:
        backtest_start: 回测开始时间
        backtest_end: 回测结束时间

    Returns:
        日级别 DatetimeIndex
    """
    start_day = backtest_start.floor("D")
    end_day = backtest_end.floor("D")
    return pd.date_range(start=start_day, end=end_day, freq="D", tz="UTC")
