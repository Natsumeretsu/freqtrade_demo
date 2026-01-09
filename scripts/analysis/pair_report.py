"""
pair_report.py - 逐交易对回测表现报告

从回测结果 zip 生成"交易对表现 vs Market Change"汇总报表（HTML + CSV）。

用法:
    uv run python scripts/analysis/pair_report.py --help
"""
from __future__ import annotations

import argparse
import json
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "生成“逐交易对表现 vs 交易对自身 Market Change”的汇总报表（HTML + CSV）。\n"
            "\n"
            "输出要求（固定规范）：\n"
            "- 纵轴=交易对（行）\n"
            "- 横轴=指标（列），包含策略表现 + Market change 对比\n"
            "- HTML 优先，其次 CSV\n"
        )
    )
    parser.add_argument(
        "--zip",
        required=True,
        help="回测结果 zip 路径，例如 backtest_results/backtest-result-xxx.zip",
    )
    parser.add_argument(
        "--datadir",
        default="data/okx",
        help="历史数据目录（默认 data/okx）。用于计算每个交易对自身的 market change。",
    )
    parser.add_argument(
        "--timeframe",
        default="",
        help="用于计算 market change 的 timeframe（留空则自动从回测结果读取；读取失败则报错）。",
    )
    parser.add_argument(
        "--trading-mode",
        choices=["spot", "futures"],
        default="futures",
        help="交易模式（决定数据文件目录/后缀）。默认 futures。",
    )
    parser.add_argument(
        "--strategy",
        default="",
        help="策略名（留空表示自动取 zip 内唯一策略）。",
    )
    parser.add_argument(
        "--out-html",
        default="",
        help="输出 HTML 路径（默认写入 plot/ 并按区间命名）。",
    )
    parser.add_argument(
        "--out-csv",
        default="",
        help="输出 CSV 路径（默认与 HTML 同名，仅扩展名不同）。",
    )
    parser.add_argument(
        "--sort-by",
        default="alpha_equal_alloc_pct",
        help="排序列（默认 alpha_equal_alloc_pct）。",
    )
    return parser.parse_args()


def _read_backtest_zip(zip_path: Path) -> dict:
    if not zip_path.is_file():
        raise FileNotFoundError(f"未找到 zip：{zip_path}")

    json_name = zip_path.with_suffix(".json").name
    with zipfile.ZipFile(zip_path) as zf:
        return json.loads(zf.read(json_name))


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
        raise ValueError("回测结果缺少 backtest_start/backtest_end，无法计算 market change")

    start = pd.to_datetime(start_raw, utc=True, errors="coerce")
    end = pd.to_datetime(end_raw, utc=True, errors="coerce")
    if pd.isna(start) or pd.isna(end):
        raise ValueError("backtest_start/backtest_end 无法解析为时间")
    if end <= start:
        raise ValueError("backtest_end 必须晚于 backtest_start")
    return start, end


def _resolve_timeframe(strategy_data: dict, cli_value: str) -> str:
    cli_value = (cli_value or "").strip()
    if cli_value:
        return cli_value

    tf = str(strategy_data.get("timeframe") or "").strip()
    if tf:
        return tf

    raise ValueError("无法自动获取 timeframe，请显式传入 --timeframe（例如 5m/1h/4h）。")


def _pair_to_data_path(datadir: Path, *, pair: str, timeframe: str, trading_mode: str) -> Path:
    safe = pair.replace("/", "_").replace(":", "_")
    tf = str(timeframe).strip()
    mode = str(trading_mode).strip().lower()

    # futures: data/okx/futures/BTC_USDT_USDT-5m-futures.feather
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
    raise FileNotFoundError(f"未找到交易对数据文件（pair={pair} timeframe={tf} mode={mode}）：\n{tried}")


def _calc_market_change_pct(data_path: Path, *, start: pd.Timestamp, end: pd.Timestamp) -> float:
    df = pd.read_feather(data_path, columns=["date", "close"])
    if df is None or df.empty:
        return float("nan")

    df = df.copy()
    df["date"] = pd.to_datetime(df["date"], utc=True, errors="coerce")
    df = df.dropna(subset=["date"]).sort_values("date")
    df = df[(df["date"] >= start) & (df["date"] <= end)]
    if len(df) < 2:
        return float("nan")

    first = float(df.iloc[0]["close"])
    last = float(df.iloc[-1]["close"])
    if not np.isfinite(first) or not np.isfinite(last) or first <= 0:
        return float("nan")

    return (last / first - 1.0) * 100.0


def _default_out_base(strategy_name: str, start: pd.Timestamp, end: pd.Timestamp) -> Path:
    safe = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in strategy_name)
    s = start.strftime("%Y%m%d")
    e = end.strftime("%Y%m%d")
    return Path("plot") / f"{safe}_per_pair_report_{s}_{e}"


def _fmt_pct(v: float) -> str:
    if not np.isfinite(v):
        return ""
    return f"{v:+.2f}%"


def _fmt_float(v: float, digits: int = 4) -> str:
    if not np.isfinite(v):
        return ""
    return f"{v:.{digits}f}"


def _render_html(
    *,
    title: str,
    meta: list[tuple[str, str]],
    table_html: str,
) -> str:
    meta_items = "\n".join(f"<li><b>{k}</b>: {v}</li>" for k, v in meta if k and v)
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, 'Noto Sans', 'Microsoft YaHei', sans-serif; margin: 24px; }}
    h1 {{ font-size: 20px; margin: 0 0 12px 0; }}
    ul {{ margin: 0 0 16px 18px; padding: 0; }}
    table {{ border-collapse: collapse; width: 100%; }}
    th, td {{ border: 1px solid #e5e7eb; padding: 6px 8px; font-size: 13px; }}
    th {{ background: #f3f4f6; text-align: right; position: sticky; top: 0; }}
    th:first-child, td:first-child {{ text-align: left; }}
    tr:nth-child(even) td {{ background: #fafafa; }}
    .num {{ text-align: right; white-space: nowrap; }}
  </style>
</head>
<body>
  <h1>{title}</h1>
  <ul>
    {meta_items}
  </ul>
  {table_html}
</body>
</html>
"""


def main() -> int:
    args = _parse_args()
    zip_path = Path(str(args.zip))
    datadir = Path(str(args.datadir))

    data = _read_backtest_zip(zip_path)
    strategy_name = _pick_strategy_name(data, str(args.strategy))
    strategy_data = ((data.get("strategy") or {}).get(strategy_name)) or {}
    if not strategy_data:
        raise ValueError(f"zip 内未找到策略：{strategy_name}")

    timeframe = _resolve_timeframe(strategy_data, str(args.timeframe))
    start, end = _extract_backtest_range(strategy_data)

    raw_rows = [r for r in (strategy_data.get("results_per_pair") or []) if isinstance(r, dict)]
    pair_rows = [r for r in raw_rows if str(r.get("key") or "").strip().upper() != "TOTAL"]
    pair_count = len(pair_rows)
    if pair_count <= 0:
        raise ValueError("results_per_pair 为空，无法生成逐交易对报表")

    starting_balance = float(strategy_data.get("starting_balance", 0.0) or 0.0)
    alloc = float(starting_balance / pair_count) if starting_balance > 0 else float("nan")

    rows: list[dict] = []
    for r in pair_rows:
        pair = str(r.get("key") or "").strip()
        if not pair:
            continue

        data_path = _pair_to_data_path(datadir, pair=pair, timeframe=timeframe, trading_mode=str(args.trading_mode))
        market_change_pct = _calc_market_change_pct(data_path, start=start, end=end)

        profit_total_abs = float(r.get("profit_total_abs", float("nan")))
        profit_total_pct = float(r.get("profit_total_pct", float("nan")))

        # 更直观的“等额资金回报率”：把每个交易对视为起始等权分配的一份资金（starting_balance/pair_count）
        # 注意：这是后处理指标，便于和 market_change_pct 做同口径对比。
        strategy_return_equal_alloc_pct = (profit_total_abs / alloc * 100.0) if np.isfinite(alloc) and alloc > 0 else float("nan")
        alpha_equal_alloc_pct = strategy_return_equal_alloc_pct - market_change_pct

        rows.append(
            {
                "pair": pair,
                "trades": int(r.get("trades", 0) or 0),
                "winrate_pct": float(r.get("winrate", float("nan"))) * 100.0,
                "profit_mean_pct": float(r.get("profit_mean_pct", float("nan"))),
                "profit_total_abs": profit_total_abs,
                "profit_total_pct": profit_total_pct,
                "strategy_return_equal_alloc_pct": strategy_return_equal_alloc_pct,
                "market_change_pct": market_change_pct,
                "alpha_equal_alloc_pct": alpha_equal_alloc_pct,
                "duration_avg": str(r.get("duration_avg", "") or "").strip(),
                "max_drawdown_account_pct": float(r.get("max_drawdown_account", float("nan"))) * 100.0,
                "profit_factor": float(r.get("profit_factor", float("nan"))),
                "expectancy_ratio": float(r.get("expectancy_ratio", float("nan"))),
                "sharpe": float(r.get("sharpe", float("nan"))),
                "sortino": float(r.get("sortino", float("nan"))),
                "calmar": float(r.get("calmar", float("nan"))),
            }
        )

    df = pd.DataFrame(rows)
    if df.empty:
        raise ValueError("逐交易对明细为空，无法生成报表")

    sort_by = str(args.sort_by).strip()
    if sort_by and sort_by in df.columns:
        df = df.sort_values(sort_by, ascending=False, kind="mergesort")

    df = df.set_index("pair")

    out_base = Path(str(args.out_html)).with_suffix("") if str(args.out_html).strip() else _default_out_base(strategy_name, start, end)
    out_html = out_base.with_suffix(".html") if not str(args.out_html).strip() else Path(str(args.out_html))
    out_csv = Path(str(args.out_csv)) if str(args.out_csv).strip() else out_base.with_suffix(".csv")
    out_html.parent.mkdir(parents=True, exist_ok=True)
    out_csv.parent.mkdir(parents=True, exist_ok=True)

    # CSV：保留数值，便于后续做二次分析
    df.to_csv(out_csv, encoding="utf-8-sig")

    # HTML：做更友好的格式化展示（不破坏 CSV 的可计算性）
    df_display = df.copy()
    pct_cols = [
        "winrate_pct",
        "profit_mean_pct",
        "profit_total_pct",
        "strategy_return_equal_alloc_pct",
        "market_change_pct",
        "alpha_equal_alloc_pct",
        "max_drawdown_account_pct",
    ]
    float_cols_3 = ["profit_total_abs"]
    float_cols_4 = ["profit_factor", "expectancy_ratio", "sharpe", "sortino", "calmar"]
    for c in pct_cols:
        if c in df_display.columns:
            df_display[c] = df_display[c].apply(_fmt_pct)
    for c in float_cols_3:
        if c in df_display.columns:
            df_display[c] = df_display[c].apply(lambda v: _fmt_float(float(v), 3))
    for c in float_cols_4:
        if c in df_display.columns:
            df_display[c] = df_display[c].apply(lambda v: _fmt_float(float(v), 4))

    title = f"逐交易对报表（vs Market change）| {strategy_name} | {start.date().isoformat()} ~ {end.date().isoformat()}"
    meta = [
        ("zip", zip_path.as_posix()),
        ("策略", strategy_name),
        ("区间(UTC)", f"{start.isoformat()} ~ {end.isoformat()}"),
        ("timeframe", timeframe),
        ("trading_mode", str(args.trading_mode)),
        ("交易对数量", str(pair_count)),
        ("starting_balance", f"{starting_balance:.2f}"),
        ("等权分配(估算)", f"{alloc:.2f}" if np.isfinite(alloc) else ""),
        ("排序", sort_by if sort_by else ""),
    ]

    table_html = df_display.reset_index().to_html(index=False, escape=False)
    html = _render_html(title=title, meta=meta, table_html=table_html)
    out_html.write_text(html, encoding="utf-8")

    print("")
    print(f"已生成：{out_html.as_posix()}")
    print(f"已生成：{out_csv.as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

