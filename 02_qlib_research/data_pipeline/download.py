"""
数据下载模块 - MVP版本

功能：
1. 从交易所下载OHLCV数据
2. 保存为Parquet格式（高效存储）
3. 支持增量更新

使用示例：
    python download.py --symbol BTC/USDT --timeframe 15m --days 90
"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta
from pathlib import Path

import ccxt
import pandas as pd


def download_ohlcv(
    exchange_id: str = "okx",
    symbol: str = "BTC/USDT",
    timeframe: str = "15m",
    days: int = 90,
    output_dir: str = "02_qlib_research/qlib_data",
) -> pd.DataFrame:
    """
    下载OHLCV数据并保存为Parquet格式

    Args:
        exchange_id: 交易所ID（okx, binance等）
        symbol: 交易对（BTC/USDT）
        timeframe: 时间周期（15m, 1h, 4h, 1d）
        days: 下载天数
        output_dir: 输出目录

    Returns:
        DataFrame with columns: timestamp, open, high, low, close, volume
    """
    # 初始化交易所
    exchange_class = getattr(ccxt, exchange_id)
    exchange = exchange_class({"enableRateLimit": True})

    # 计算时间范围
    end_time = datetime.now()
    start_time = end_time - timedelta(days=days)
    since = int(start_time.timestamp() * 1000)

    print(f"下载 {symbol} {timeframe} 数据，时间范围：{start_time} 至 {end_time}")

    # 下载数据
    all_ohlcv = []
    while since < int(end_time.timestamp() * 1000):
        try:
            ohlcv = exchange.fetch_ohlcv(symbol, timeframe, since=since, limit=1000)
            if not ohlcv:
                break
            all_ohlcv.extend(ohlcv)
            since = ohlcv[-1][0] + 1
            print(f"已下载 {len(all_ohlcv)} 条数据...")
        except Exception as e:
            print(f"下载出错：{e}")
            break

    # 转换为DataFrame
    df = pd.DataFrame(
        all_ohlcv,
        columns=["timestamp", "open", "high", "low", "close", "volume"]
    )
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    df = df.set_index("timestamp")

    # 保存为Parquet
    output_path = Path(output_dir) / exchange_id / symbol.replace("/", "_")
    output_path.mkdir(parents=True, exist_ok=True)
    file_path = output_path / f"{timeframe}.parquet"
    df.to_parquet(file_path)

    print(f"数据已保存至：{file_path}")
    print(f"数据形状：{df.shape}")
    print(f"时间范围：{df.index.min()} 至 {df.index.max()}")

    return df


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="下载加密货币OHLCV数据")
    parser.add_argument("--exchange", default="okx", help="交易所ID")
    parser.add_argument("--symbol", default="BTC/USDT", help="交易对")
    parser.add_argument("--timeframe", default="15m", help="时间周期")
    parser.add_argument("--days", type=int, default=90, help="下载天数")
    parser.add_argument("--output", default="02_qlib_research/qlib_data", help="输出目录")

    args = parser.parse_args()

    download_ohlcv(
        exchange_id=args.exchange,
        symbol=args.symbol,
        timeframe=args.timeframe,
        days=args.days,
        output_dir=args.output,
    )
