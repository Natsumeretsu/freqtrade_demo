"""
plot_equity.py - 策略资金曲线 vs 大盘对比图

从回测结果 zip 生成归一化资金曲线与大盘对比的 Plotly HTML 图表。

用法:
    uv run python scripts/analysis/plot_equity.py --help
"""
from __future__ import annotations

import argparse
import json
import zipfile
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "生成“策略资金曲线 vs 大盘（归一化）”对比图（HTML）。\n"
            "\n"
            "输入：Freqtrade 回测结果 zip（backtest_results/*.zip）。\n"
            "输出：Plotly HTML（默认引用 CDN，无需本地 plotly.js）。\n"
        )
    )
    parser.add_argument(
        "--zip",
        required=True,
        help="回测结果 zip 路径，例如 backtest_results/backtest-result-xxx.zip",
    )
    parser.add_argument(
        "--out",
        default="",
        help="输出 HTML 路径（默认写入 plot/ 目录并按区间命名）。",
    )
    parser.add_argument(
        "--strategy",
        default="",
        help="策略名（留空表示自动取 zip 内唯一策略）。",
    )
    parser.add_argument(
        "--benchmark",
        choices=["bh", "rel_mean"],
        default="bh",
        help=(
            "大盘基准定义："
            "bh=交易对等权买入并持有（与 backtest JSON 的 market_change 口径一致）；"
            "rel_mean=zip 内 market_change.feather 的 rel_mean（等权逐小时收益的累加）。"
        ),
    )
    parser.add_argument(
        "--datadir",
        default="data/okx",
        help="历史数据目录（默认 data/okx）。用于 benchmark=bh 构建大盘曲线。",
    )
    parser.add_argument(
        "--timeframe",
        default="1h",
        help="历史数据 timeframe（默认 1h）。用于 benchmark=bh 构建大盘曲线。",
    )
    parser.add_argument(
        "--title",
        default="",
        help="自定义标题（留空则自动生成）。",
    )
    return parser.parse_args()


def _read_backtest_zip(zip_path: Path) -> tuple[dict, pd.DataFrame]:
    if not zip_path.is_file():
        raise FileNotFoundError(f"未找到 zip：{zip_path}")

    base = zip_path.with_suffix("").name
    json_name = f"{base}.json"
    feather_name = f"{base}_market_change.feather"

    with zipfile.ZipFile(zip_path) as zf:
        data = json.loads(zf.read(json_name))
        with zf.open(feather_name) as f:
            market = pd.read_feather(f)

    if market is None or market.empty:
        raise ValueError("zip 内 market_change.feather 为空，无法生成“大盘”曲线")

    return data, market


def _pick_strategy_name(data: dict, requested: str) -> str:
    requested = (requested or "").strip()
    if requested:
        return requested
    strategies = list((data.get("strategy") or {}).keys())
    if len(strategies) != 1:
        raise ValueError(f"无法自动判断策略名（zip 内策略数={len(strategies)}），请用 --strategy 指定")
    return strategies[0]


def _extract_backtest_range(strategy_data: dict) -> tuple[pd.Timestamp, pd.Timestamp]:
    start_raw = strategy_data.get("backtest_start")
    end_raw = strategy_data.get("backtest_end")
    if not start_raw or not end_raw:
        raise ValueError("回测结果缺少 backtest_start/backtest_end，无法构建对齐的时间轴")

    start = pd.to_datetime(start_raw, utc=True, errors="coerce")
    end = pd.to_datetime(end_raw, utc=True, errors="coerce")
    if pd.isna(start) or pd.isna(end):
        raise ValueError("backtest_start/backtest_end 无法解析为时间")
    if end <= start:
        raise ValueError("backtest_end 必须晚于 backtest_start")
    return start, end


def _build_daily_index(backtest_start: pd.Timestamp, backtest_end: pd.Timestamp) -> pd.DatetimeIndex:
    start_day = backtest_start.floor("D")
    end_day = backtest_end.floor("D")
    return pd.date_range(start=start_day, end=end_day, freq="D", tz="UTC")


def _build_market_series_rel_mean(market: pd.DataFrame, daily_index: pd.DatetimeIndex) -> pd.Series:
    df = market.copy()
    df["date"] = pd.to_datetime(df["date"], utc=True, errors="coerce")
    df = df.dropna(subset=["date"])
    df = df.sort_values("date")

    if "rel_mean" not in df.columns:
        raise ValueError("market_change.feather 缺少 rel_mean 列")

    rel = df.set_index("date")["rel_mean"].astype(float)
    rel_daily = rel.resample("D").last().reindex(daily_index, method="ffill").fillna(0.0)
    return 1.0 + rel_daily


def _extract_pairs(strategy_data: dict) -> list[str]:
    out: list[str] = []
    for row in strategy_data.get("results_per_pair") or []:
        if not isinstance(row, dict):
            continue
        pair = str(row.get("key") or "").strip()
        if not pair or pair.upper() == "TOTAL":
            continue
        out.append(pair)
    # 保留顺序去重
    return list(dict.fromkeys(out))


def _pair_to_data_filename(pair: str, timeframe: str) -> str:
    return f"{pair.replace('/', '_')}-{timeframe}.feather"


def _build_market_series_buy_and_hold(
    *,
    strategy_data: dict,
    daily_index: pd.DatetimeIndex,
    datadir: Path,
    timeframe: str,
) -> pd.Series:
    pairs = _extract_pairs(strategy_data)
    if not pairs:
        raise ValueError("回测结果缺少 results_per_pair（或未包含任何交易对），无法构建大盘曲线")

    closes: list[pd.Series] = []
    skipped: list[str] = []
    for pair in pairs:
        fn = datadir / _pair_to_data_filename(pair, timeframe)
        if not fn.is_file():
            skipped.append(pair)
            continue

        df = pd.read_feather(fn, columns=["date", "close"])
        df["date"] = pd.to_datetime(df["date"], utc=True, errors="coerce")
        df = df.dropna(subset=["date"])
        df = df.set_index("date").sort_index()

        # 仅保留本区间，避免无谓 IO/内存；end 为包含式索引（daily_index 已包含 backtest_end 当天 00:00）
        df = df.loc[daily_index[0] : daily_index[-1]]
        s = df["close"].astype(float).reindex(daily_index, method="ffill")
        if s.isna().all():
            skipped.append(pair)
            continue

        start_close = float(s.iloc[0]) if pd.notna(s.iloc[0]) else float("nan")
        if not (start_close > 0 and pd.notna(start_close)):
            skipped.append(pair)
            continue

        closes.append((s / start_close).rename(pair))

    if not closes:
        raise ValueError("无法从本地 data 目录加载任何交易对的价格数据")

    if skipped:
        print(f"⚠️  跳过 {len(skipped)} 个交易对（缺少数据或起始价无效）：{', '.join(skipped[:10])}" + (" ..." if len(skipped) > 10 else ""))

    market_index = pd.concat(closes, axis=1).mean(axis=1)
    return market_index


def _build_equity_series(strategy_data: dict, daily_index: pd.DatetimeIndex) -> pd.Series:
    starting_balance = float(strategy_data.get("starting_balance", 0.0))
    if starting_balance <= 0:
        raise ValueError("回测结果缺少 starting_balance，无法生成资金曲线")

    # daily_profit 的日期粒度为天（YYYY-MM-DD），这里生成“每日起点”的资金曲线：
    # - x=某天 00:00:00，y=该时刻账户余额（不包含当天结束时的盈亏）
    # - 末尾额外追加 backtest_end（通常也是 00:00:00），使末值对齐 final_balance
    days = daily_index[:-1]
    profit_by_day = pd.Series(0.0, index=days, dtype="float64")
    for row in strategy_data.get("daily_profit") or []:
        try:
            day_str, profit_abs = row
            day = pd.to_datetime(day_str, utc=True, errors="coerce")
            if pd.isna(day):
                continue
            if day in profit_by_day.index:
                profit_by_day.loc[day] += float(profit_abs)
        except Exception:
            continue

    cum_profit = profit_by_day.cumsum()
    equity_at_day_start = starting_balance + cum_profit.shift(1, fill_value=0.0)
    final_equity = starting_balance + float(cum_profit.iloc[-1]) if len(cum_profit) else starting_balance
    equity = pd.concat([equity_at_day_start, pd.Series([final_equity], index=[daily_index[-1]])])
    return equity / starting_balance


def _default_title(strategy_name: str, daily_index: pd.DatetimeIndex, benchmark: str) -> str:
    start = daily_index[0].date().isoformat()
    end = daily_index[-1].date().isoformat()
    bench_text = "大盘(B&H等权)" if benchmark == "bh" else "大盘(rel_mean)"
    return f"资金曲线 vs {bench_text} | {strategy_name} | {start} ~ {end}"


def _default_out_path(strategy_name: str, daily_index: pd.DatetimeIndex) -> Path:
    start = daily_index[0].strftime("%Y%m%d")
    end = daily_index[-1].strftime("%Y%m%d")
    safe = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in strategy_name)
    return Path("plot") / f"{safe}_equity_vs_market_{start}_{end}.html"


def _pct_text(v: float) -> str:
    return f"{(v - 1.0) * 100.0:+.2f}%"


def main() -> int:
    args = _parse_args()
    zip_path = Path(str(args.zip))
    data, market = _read_backtest_zip(zip_path)

    strategy_name = _pick_strategy_name(data, str(args.strategy))
    strategy_data = ((data.get("strategy") or {}).get(strategy_name)) or {}
    if not strategy_data:
        raise ValueError(f"zip 内未找到策略：{strategy_name}")

    backtest_start, backtest_end = _extract_backtest_range(strategy_data)
    daily_index = _build_daily_index(backtest_start, backtest_end)

    benchmark = str(args.benchmark).strip().lower()
    if benchmark == "rel_mean":
        market_norm = _build_market_series_rel_mean(market, daily_index)
    else:
        datadir = Path(str(args.datadir))
        timeframe = str(args.timeframe).strip() or "1h"
        market_norm = _build_market_series_buy_and_hold(
            strategy_data=strategy_data,
            daily_index=daily_index,
            datadir=datadir,
            timeframe=timeframe,
        )
    equity_norm = _build_equity_series(strategy_data, daily_index)

    title = (str(args.title) or "").strip() or _default_title(strategy_name, daily_index, benchmark)
    out_path = Path(str(args.out)) if str(args.out).strip() else _default_out_path(strategy_name, daily_index)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    last_x = daily_index[-1]
    eq_last = float(equity_norm.iloc[-1])
    mk_last = float(market_norm.iloc[-1])

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=daily_index,
            y=equity_norm,
            name="策略资金曲线（归一化）",
            line={"width": 2},
        )
    )
    fig.add_trace(
        go.Scatter(
            x=daily_index,
            y=market_norm,
            name="大盘（归一化）",
            line={"width": 2},
        )
    )
    fig.update_layout(
        title=title,
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "left", "x": 0.0},
        xaxis={"title": "日期(UTC)"},
        yaxis={"title": "归一化指数（起点=1.0）"},
        annotations=[
            {
                "x": last_x,
                "y": eq_last,
                "text": f"策略末值: {eq_last:.3f}（{_pct_text(eq_last)}）",
                "showarrow": True,
                "arrowhead": 2,
            },
            {
                "x": last_x,
                "y": mk_last,
                "text": f"大盘末值: {mk_last:.3f}（{_pct_text(mk_last)}）",
                "showarrow": True,
                "arrowhead": 2,
            },
        ],
    )

    pio.write_html(fig, file=str(out_path), include_plotlyjs="cdn", full_html=True, config={"responsive": True})

    print("")
    print(f"已生成：{out_path.as_posix()}")
    print(f"- 策略末值：{eq_last:.6f}（{_pct_text(eq_last)}）")
    print(f"- 大盘末值：{mk_last:.6f}（{_pct_text(mk_last)}）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
