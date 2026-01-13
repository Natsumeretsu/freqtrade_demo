"""
dashboard.py - 市场仪表盘

生成"交易对等权大盘"归一化走势图，以及每个交易对相对大盘的强弱/排名热力图。

用法:
    uv run python scripts/data/dashboard.py --help
"""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
from plotly.subplots import make_subplots


@dataclass(frozen=True)
class Timerange:
    start: pd.Timestamp
    end: pd.Timestamp  # 结束为“排他”（与 freqtrade timerange 语义一致）


def _parse_timerange(timerange: str) -> Timerange | None:
    tr = (timerange or "").strip()
    if not tr:
        return None

    parts = tr.split("-", 1)
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise ValueError("timerange 格式必须为 YYYYMMDD-YYYYMMDD（结束为排他）")

    start = pd.to_datetime(parts[0], utc=True, format="%Y%m%d", errors="raise")
    end = pd.to_datetime(parts[1], utc=True, format="%Y%m%d", errors="raise")
    if end <= start:
        raise ValueError("timerange 结束日期必须晚于开始日期")

    return Timerange(start=start, end=end)


def _read_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _read_pairs_from_config(config_path: Path) -> list[str]:
    cfg = _read_json(config_path)
    pairs = (((cfg.get("exchange") or {}).get("pair_whitelist")) or []) if isinstance(cfg, dict) else []
    pairs = [str(p).strip() for p in pairs if str(p).strip()]
    return list(dict.fromkeys(pairs))


def _read_pairs_from_file(pairs_file: Path) -> list[str]:
    if not pairs_file.is_file():
        raise FileNotFoundError(f"未找到 pairs-file：{pairs_file}")
    out: list[str] = []
    for raw in pairs_file.read_text(encoding="utf-8").splitlines():
        s = raw.strip()
        if not s or s.startswith("#"):
            continue
        out.append(s)
    return list(dict.fromkeys(out))


def _pair_to_filename(pair: str, timeframe: str) -> str:
    return f"{pair.replace('/', '_')}-{timeframe}.feather"


def _load_close_series(
    *,
    datadir: Path,
    pair: str,
    timeframe: str,
    resample: str,
) -> pd.Series | None:
    fp = datadir / _pair_to_filename(pair, timeframe)
    if not fp.is_file():
        return None

    df = pd.read_feather(fp, columns=["date", "close"])
    if df is None or df.empty:
        return None

    df["date"] = pd.to_datetime(df["date"], utc=True, errors="coerce")
    df = df.dropna(subset=["date"])
    if df.empty:
        return None

    df = df.sort_values("date").drop_duplicates(subset=["date"], keep="last")
    s = df.set_index("date")["close"].astype("float64")
    if resample:
        s = s.resample(resample).last()
    return s.rename(pair)


def _build_prices(
    *,
    datadir: Path,
    pairs: list[str],
    timeframe: str,
    resample: str,
    timerange: Timerange | None,
) -> tuple[pd.DataFrame, list[str]]:
    series: list[pd.Series] = []
    missing: list[str] = []

    for pair in pairs:
        s = _load_close_series(datadir=datadir, pair=pair, timeframe=timeframe, resample=resample)
        if s is None:
            missing.append(pair)
            continue
        series.append(s)

    if not series:
        raise ValueError("未加载到任何交易对数据：请检查 datadir/timeframe/pairs 是否匹配现有文件")

    prices = pd.concat(series, axis=1).sort_index()

    if timerange is not None:
        # 结束为排他：因此这里用 < end 过滤
        prices = prices[(prices.index >= timerange.start) & (prices.index < timerange.end)]
        if prices.empty:
            raise ValueError("timerange 过滤后无数据：请检查时间范围与本地数据是否覆盖")

    # 价格数据允许缺口：用 ffill 将缺口视为“当期无报价变化”（更贴近持有/指数计算）
    prices = prices.ffill()
    return prices, missing


def _pick_start_end_by_min_pairs(prices: pd.DataFrame, min_pairs: int) -> pd.DataFrame:
    n = int(min_pairs)
    if n <= 1:
        return prices

    count = prices.notna().sum(axis=1)
    ok = count >= n
    if not ok.any():
        raise ValueError(f"min-pairs={n} 过高：数据中任意时刻都达不到该覆盖数量")

    start_ts = ok[ok].index[0]
    return prices.loc[start_ts:]


def _market_index_rebalanced(prices: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    """
    等权再平衡指数（更适合“动态 universe / 新交易对上市”场景）：
    - 对每个时间点，取各交易对收益率的等权均值（跳过 NaN）
    - 指数按 (1+mean_ret) 复利累积
    """
    rets = prices.pct_change()
    mean_ret = rets.mean(axis=1, skipna=True).fillna(0.0)
    idx = (1.0 + mean_ret).cumprod()
    idx.iloc[0] = 1.0

    count = rets.notna().sum(axis=1).astype("int64")
    return idx.rename("market_index"), count.rename("pair_count")


def _market_index_buy_and_hold(prices: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    """
    等权买入并持有（B&H）指数：
    - 仅统计在起点时刻具备有效价格的交易对（否则无法“买入”）
    - 指数 = mean_i (P_i(t) / P_i(t0))
    """
    base = prices.iloc[0].astype("float64")
    valid = base.replace([np.inf, -np.inf], np.nan)
    valid = valid[(valid.notna()) & (valid > 0)]
    cols = valid.index.tolist()
    if not cols:
        raise ValueError("基准无法构建：起点时刻没有任何交易对具备有效价格（可尝试调大 --min-pairs 或缩短 timerange）")

    ratio = prices[cols].div(valid, axis=1).replace([np.inf, -np.inf], np.nan)
    idx = ratio.mean(axis=1, skipna=True)
    idx.iloc[0] = 1.0

    count = ratio.notna().sum(axis=1).astype("int64")
    return idx.rename("market_index"), count.rename("pair_count")


def _relative_strength(
    *,
    prices: pd.DataFrame,
    market_index: pd.Series,
    anchor: str,
) -> pd.DataFrame:
    """
    相对大盘强弱：RS = (pair_norm) / (market_norm)

    anchor:
    - pair：以“交易对首次可用日期”为起点（RS 起点=1），更适合含新币/晚上市交易对的长期序列
    - global：以“全局起点”为起点（若交易对无起点价则全程 NaN），更适合固定 universe 的严格对比
    """
    anchor = (anchor or "").strip().lower()
    if anchor not in {"pair", "global"}:
        raise ValueError("anchor 必须是 pair 或 global")

    out = pd.DataFrame(index=prices.index)
    global_start = prices.index.min()
    market_at_global = float(market_index.loc[global_start])

    for pair in prices.columns:
        s = prices[pair]
        if anchor == "global":
            if global_start not in s.index or pd.isna(s.loc[global_start]):
                out[pair] = np.nan
                continue
            base_ts = global_start
        else:
            base_ts = s.first_valid_index()
            if base_ts is None:
                out[pair] = np.nan
                continue

        base_price = float(s.loc[base_ts])
        if not np.isfinite(base_price) or base_price <= 0:
            out[pair] = np.nan
            continue

        market_base = float(market_index.loc[base_ts]) if base_ts in market_index.index else market_at_global
        if not np.isfinite(market_base) or market_base <= 0:
            out[pair] = np.nan
            continue

        pair_norm = s / base_price
        market_norm = market_index / market_base
        out[pair] = (pair_norm / market_norm).replace([np.inf, -np.inf], np.nan)

    return out


def _rank_score(relative: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    输出：
    - rank：1=最强（相对大盘最强），数值越小越强
    - score：0-100，越大越强（用于热力图配色更直观）
    """
    rank = relative.rank(axis=1, ascending=False, method="min")
    count = relative.notna().sum(axis=1).astype("float64")

    # score = 1 - (rank-1)/(count-1)
    denom = (count - 1.0).replace(0.0, np.nan)
    score = rank.rsub(count, axis=0).div(denom, axis=0)
    score = (score * 100.0).clip(lower=0.0, upper=100.0)
    score = score.fillna(50.0)
    return rank, score


def _pct(v: float) -> str:
    return f"{v * 100.0:+.2f}%"


def _fmt_ratio(v: float) -> str:
    if not np.isfinite(v):
        return "-"
    return f"{v:.3f}（{_pct(v - 1.0)}）"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "市场仪表盘：从最早数据到最新，构建“大盘（交易对等权均值）”并跟踪各交易对相对大盘的变化。\n"
            "\n"
            "默认：以日线收盘价构建等权再平衡指数（mean daily return -> compound），\n"
            "并输出：大盘指数曲线、相对强弱排名热力图、最新相对强弱表。\n"
        )
    )
    parser.add_argument(
        "--config",
        default="",
        help="Freqtrade 配置文件（读取 exchange.pair_whitelist 作为 universe）。",
    )
    parser.add_argument(
        "--pairs-file",
        default="",
        help="交易对列表文件（每行一个，例如 04_shared/configs/archive/pairs_moonshot_top36.txt）。",
    )
    parser.add_argument(
        "--pairs",
        nargs="*",
        default=[],
        help="直接在命令行指定交易对（优先级最高）。",
    )
    parser.add_argument(
        "--datadir",
        default="01_freqtrade/data/okx",
        help="历史数据目录（默认 01_freqtrade/data/okx）。",
    )
    parser.add_argument(
        "--timeframe",
        default="1h",
        help="历史数据 timeframe（默认 1h，对应文件名 *-1h.feather）。",
    )
    parser.add_argument(
        "--resample",
        default="1D",
        help="重采样频率（默认 1D；也可用 4H/1H/1W 等 pandas 频率字符串）。",
    )
    parser.add_argument(
        "--timerange",
        default="",
        help="时间范围（YYYYMMDD-YYYYMMDD，结束为排他；留空表示全历史）。",
    )
    parser.add_argument(
        "--min-pairs",
        type=int,
        default=1,
        help="从“覆盖交易对数量>=min-pairs”的最早时刻开始（默认 1）。",
    )
    parser.add_argument(
        "--benchmark",
        choices=["rebalanced", "bh"],
        default="rebalanced",
        help="大盘基准口径：rebalanced=等权再平衡指数；bh=等权买入并持有。",
    )
    parser.add_argument(
        "--anchor",
        choices=["pair", "global"],
        default="pair",
        help="相对强弱的锚点：pair=按交易对起点对齐；global=按全局起点对齐。",
    )
    parser.add_argument(
        "--heatmap-resample",
        default="1W",
        help="热力图采样频率（默认 1W；用于展示“位置变化”更清晰）。",
    )
    parser.add_argument(
        "--out",
        default="",
        help="输出 HTML 路径（默认写入 01_freqtrade/plot/market_dashboard_*.html）。",
    )
    parser.add_argument(
        "--csv-out",
        default="",
        help="输出 CSV（最新相对强弱表）；默认与 out 同名 .csv。",
    )
    parser.add_argument(
        "--title",
        default="",
        help="标题（留空自动生成）。",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()

    pairs: list[str] = [str(p).strip() for p in (args.pairs or []) if str(p).strip()]
    if not pairs and str(args.pairs_file).strip():
        pairs = _read_pairs_from_file(Path(str(args.pairs_file)))
    if not pairs and str(args.config).strip():
        pairs = _read_pairs_from_config(Path(str(args.config)))
    if not pairs:
        raise ValueError("未指定任何交易对：请提供 --pairs / --pairs-file / --config")

    datadir = Path(str(args.datadir))
    timeframe = str(args.timeframe).strip() or "1h"
    resample = str(args.resample).strip() or "1D"
    timerange = _parse_timerange(str(args.timerange))

    prices_raw, missing = _build_prices(
        datadir=datadir,
        pairs=pairs,
        timeframe=timeframe,
        resample=resample,
        timerange=timerange,
    )
    prices = _pick_start_end_by_min_pairs(prices_raw, int(args.min_pairs))

    benchmark = str(args.benchmark).strip().lower()
    if benchmark == "bh":
        market_index, pair_count = _market_index_buy_and_hold(prices)
    else:
        market_index, pair_count = _market_index_rebalanced(prices)
    relative = _relative_strength(prices=prices, market_index=market_index, anchor=str(args.anchor))

    # Heatmap 用更低频采样，避免长时间范围下过密导致图太大
    heat_freq = str(args.heatmap_resample).strip() or "1W"
    relative_h = relative.resample(heat_freq).last()
    rank_h, score_h = _rank_score(relative_h)

    # 以最新 score 排序，便于观察“当前最强/最弱”
    last_scores = score_h.iloc[-1].sort_values(ascending=False)
    ordered_pairs = [p for p in last_scores.index.tolist() if p in score_h.columns]
    score_h = score_h[ordered_pairs]
    rank_h = rank_h[ordered_pairs]
    relative_h = relative_h[ordered_pairs]

    # 最新摘要表（使用日频相对强弱的末值）
    latest_rs = relative.iloc[-1].reindex(ordered_pairs)
    latest_rank = latest_rs.rank(ascending=False, method="min")
    latest_score = (len(latest_rs) - latest_rank) / max(1.0, float(len(latest_rs) - 1)) * 100.0

    def _rel_change(periods: int) -> pd.Series:
        if len(relative) <= periods:
            return pd.Series(index=relative.columns, dtype="float64")
        cur = relative.iloc[-1]
        prev = relative.iloc[-1 - periods]
        return (cur / prev - 1.0).replace([np.inf, -np.inf], np.nan)

    # 近 30/90 个采样周期（注意：这里按 resample 后的行数，不按自然日）
    rs_30 = _rel_change(30)
    rs_90 = _rel_change(90)

    summary = pd.DataFrame(
        {
            "pair": ordered_pairs,
            "rs_latest": latest_rs.values,
            "rank_latest": latest_rank.values,
            "score_latest": latest_score.values,
            "rs_change_30": rs_30.reindex(ordered_pairs).values,
            "rs_change_90": rs_90.reindex(ordered_pairs).values,
        }
    )

    # --- 图1：大盘指数（附带覆盖交易对数量） ---
    fig_market = make_subplots(specs=[[{"secondary_y": True}]])
    fig_market.add_trace(
        go.Scatter(
            x=market_index.index,
            y=market_index.values,
            name="大盘指数（等权再平衡，归一化）",
            line={"width": 2},
        ),
        secondary_y=False,
    )
    fig_market.add_trace(
        go.Scatter(
            x=pair_count.index,
            y=pair_count.values,
            name="覆盖交易对数量",
            line={"width": 1, "dash": "dot"},
            opacity=0.6,
        ),
        secondary_y=True,
    )
    fig_market.update_layout(
        title="大盘指数（全历史）",
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "left", "x": 0.0},
        xaxis={"title": "日期(UTC)"},
    )
    fig_market.update_yaxes(title_text="归一化指数（起点=1.0）", secondary_y=False)
    fig_market.update_yaxes(title_text="交易对数量", secondary_y=True)

    # --- 图2：相对强弱“位置变化”热力图 ---
    z = score_h.T.values
    x = score_h.index
    y = score_h.columns
    hover = []
    for p in y:
        rel_vals = relative_h[p].values
        rank_vals = rank_h[p].values
        score_vals = score_h[p].values
        hover.append(
            [
                f"交易对：{p}<br>时间：{pd.Timestamp(t).date()}<br>相对强弱：{_fmt_ratio(float(rv))}<br>排名：{int(rk) if np.isfinite(rk) else '-'}<br>Score：{float(sc):.1f}"
                for t, rv, rk, sc in zip(x, rel_vals, rank_vals, score_vals)
            ]
        )
    hover = np.array(hover)

    fig_heat = go.Figure(
        data=[
            go.Heatmap(
                z=z,
                x=x,
                y=y,
                colorscale=[
                    [0.0, "#d62728"],  # 红：弱
                    [0.5, "#f0f0f0"],
                    [1.0, "#2ca02c"],  # 绿：强
                ],
                zmin=0.0,
                zmax=100.0,
                colorbar={"title": "强弱(0-100)"},
                hoverinfo="text",
                text=hover,
            )
        ]
    )
    fig_heat.update_layout(
        title=f"相对大盘强弱（Score）热力图 | anchor={args.anchor} | freq={heat_freq}",
        xaxis={"title": "时间"},
        yaxis={"title": "交易对"},
        height=max(600, 18 * len(y)),
    )

    # --- 图3：最新相对强弱表 ---
    table = go.Figure(
        data=[
            go.Table(
                header={
                    "values": ["交易对", "RS(最新)", "排名", "Score", "RS变化(30)", "RS变化(90)"],
                    "fill_color": "#C8D4E3",
                    "align": "left",
                },
                cells={
                    "values": [
                        summary["pair"].tolist(),
                        [f"{v:.3f}" if np.isfinite(v) else "-" for v in summary["rs_latest"].tolist()],
                        [int(v) if np.isfinite(v) else "-" for v in summary["rank_latest"].tolist()],
                        [f"{v:.1f}" if np.isfinite(v) else "-" for v in summary["score_latest"].tolist()],
                        [_pct(float(v)) if np.isfinite(v) else "-" for v in summary["rs_change_30"].tolist()],
                        [_pct(float(v)) if np.isfinite(v) else "-" for v in summary["rs_change_90"].tolist()],
                    ],
                    "fill_color": "#EBF0F8",
                    "align": "left",
                },
            )
        ]
    )
    table.update_layout(title="最新相对强弱（相对大盘）")

    # --- 输出 ---
    start = prices.index.min().strftime("%Y%m%d")
    end = prices.index.max().strftime("%Y%m%d")
    universe = "custom"
    if str(args.config).strip():
        universe = Path(str(args.config)).stem
    elif str(args.pairs_file).strip():
        universe = Path(str(args.pairs_file)).stem

    default_out = Path("01_freqtrade/plot") / f"market_dashboard_{universe}_{timeframe}_{resample}_{start}_{end}.html"
    out_path = Path(str(args.out)) if str(args.out).strip() else default_out
    out_path.parent.mkdir(parents=True, exist_ok=True)

    csv_path = Path(str(args.csv_out)) if str(args.csv_out).strip() else out_path.with_suffix(".csv")

    title = (str(args.title) or "").strip()
    if not title:
        title = f"市场仪表盘 | universe={universe} | tf={timeframe} | resample={resample} | {start}-{end}"

    parts = [
        "<html>",
        "<head><meta charset=\"utf-8\" /></head>",
        "<body>",
        f"<h2>{title}</h2>",
        pio.to_html(fig_market, include_plotlyjs="cdn", full_html=False, config={"responsive": True}),
        "<hr/>",
        pio.to_html(fig_heat, include_plotlyjs=False, full_html=False, config={"responsive": True}),
        "<hr/>",
        pio.to_html(table, include_plotlyjs=False, full_html=False, config={"responsive": True}),
        "</body>",
        "</html>",
    ]
    out_path.write_text("\n".join(parts), encoding="utf-8")
    summary.to_csv(csv_path, index=False, encoding="utf-8")

    print("")
    print(f"已生成：{out_path.as_posix()}")
    print(f"已生成：{csv_path.as_posix()}")
    if missing:
        print(f"⚠️  缺少数据文件的交易对（已跳过 {len(missing)} 个）：{', '.join(missing[:10])}" + (" ..." if len(missing) > 10 else ""))
    print(f"- 数据区间：{prices.index.min()} -> {prices.index.max()}")
    print(f"- universe 数量：{len(pairs)}（有效加载 {prices.shape[1]}）")
    print(f"- 大盘末值：{float(market_index.iloc[-1]):.6f}（{_pct(float(market_index.iloc[-1]) - 1.0)}）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
