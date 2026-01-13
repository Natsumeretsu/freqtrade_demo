"""
param_sweep.py - FreqAI 参数网格扫描

批量运行回测，遍历阈值/入场过滤参数组合，输出 CSV 汇总。
用于评估策略在不同参数下的稳健性。

用法:
    uv run python scripts/archive/freqai/param_sweep.py --help
"""
from __future__ import annotations

import argparse
import csv
import itertools
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable


@dataclass(frozen=True)
class BacktestMetrics:
    zip_path: Path
    strategy_name: str
    freqai_identifier: str
    pair: str
    timerange: str
    total_trades: int
    profit_total: float
    profit_total_abs: float
    profit_factor: float
    winrate: float
    max_relative_drawdown: float
    sharpe: float
    sortino: float
    calmar: float
    market_change: float


def _parse_float_list(raw: str) -> list[float]:
    raw = (raw or "").strip()
    if not raw:
        return []
    out: list[float] = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        out.append(float(part))
    return out


def _parse_int_list(raw: str) -> list[int]:
    raw = (raw or "").strip()
    if not raw:
        return []
    out: list[int] = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        out.append(int(part))
    return out


def _parse_bool_list(raw: str) -> list[bool]:
    raw = (raw or "").strip()
    if not raw:
        return []
    out: list[bool] = []
    for part in raw.split(","):
        part = part.strip().lower()
        if not part:
            continue
        if part in {"1", "true", "t", "yes", "y"}:
            out.append(True)
            continue
        if part in {"0", "false", "f", "no", "n"}:
            out.append(False)
            continue
        raise ValueError(f"无法解析布尔值：{part!r}（支持 0/1/true/false/yes/no）")
    return out


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_strategy_params(
    param_file: Path,
    strategy_name: str,
    buy_params: dict[str, Any],
    sell_params: dict[str, Any],
) -> None:
    payload = {
        "strategy_name": strategy_name,
        "params": {
            "buy": buy_params,
            "sell": sell_params,
        },
    }
    _write_json(param_file, payload)


def _run_backtesting(
    *,
    repo_root: Path,
    run_dir: Path,
    config_path: Path,
    strategy_name: str,
    freqaimodel: str,
    timeframe: str,
    timeframe_detail: str | None,
    timerange: str,
    pair: str,
    use_live_models: bool,
    fee: float | None,
    log_path: Path,
) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    cmd: list[str] = [
        "uv",
        "run",
        "python",
        "-X",
        "utf8",
        "-m",
        "freqtrade",
        "backtesting",
        "--userdir",
        ".",
        "--config",
        str(config_path),
        "--strategy",
        strategy_name,
        "--freqaimodel",
        freqaimodel,
        "--timeframe",
        timeframe,
        "--timerange",
        timerange,
        "--pairs",
        pair,
        "--cache",
        "none",
        "--export",
        "trades",
        "--backtest-directory",
        str(run_dir.as_posix()),
    ]
    if timeframe_detail:
        cmd += ["--timeframe-detail", str(timeframe_detail)]
    if fee is not None and float(fee) > 0:
        cmd += ["--fee", str(float(fee))]
    if use_live_models:
        cmd.append("--freqai-backtest-live-models")

    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"

    with log_path.open("w", encoding="utf-8") as fp:
        fp.write("命令：\n")
        fp.write(" ".join(cmd) + "\n\n")
        fp.flush()

        proc = subprocess.run(
            cmd,
            cwd=str(repo_root),
            env=env,
            stdout=fp,
            stderr=subprocess.STDOUT,
            text=True,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"回测失败（exit={proc.returncode}）。日志：{log_path}")


def _read_latest_zip_from_run_dir(run_dir: Path) -> Path:
    last_file = run_dir / ".last_result.json"
    if not last_file.is_file():
        raise FileNotFoundError(f"未找到 {last_file}，无法定位回测输出。")
    last = _read_json(last_file)
    name = str(last.get("latest_backtest", "")).strip()
    if not name:
        raise ValueError(f"{last_file} 缺少 latest_backtest 字段。")
    zip_path = run_dir / name
    if not zip_path.is_file():
        raise FileNotFoundError(f"未找到回测输出：{zip_path}")
    return zip_path


def _extract_metrics(zip_path: Path, strategy_name: str) -> BacktestMetrics:
    import zipfile

    json_name = zip_path.with_suffix(".json").name
    with zipfile.ZipFile(zip_path) as zf:
        data = json.loads(zf.read(json_name))

    strat_map = data.get("strategy") or {}
    strat = strat_map.get(strategy_name)
    if strat is None:
        # 兼容：zip 内可能只包含 1 个策略
        if len(strat_map) == 1:
            strat = next(iter(strat_map.values()))
        else:
            raise KeyError(f"回测结果中未找到策略 {strategy_name}（zip={zip_path.name}）。")

    def f(key: str, default: float = 0.0) -> float:
        try:
            return float(strat.get(key, default))
        except Exception:
            return float(default)

    def i(key: str, default: int = 0) -> int:
        try:
            return int(strat.get(key, default))
        except Exception:
            return int(default)

    return BacktestMetrics(
        zip_path=zip_path,
        strategy_name=str(strategy_name),
        freqai_identifier=str(strat.get("freqai_identifier", "")),
        pair=str(strat.get("pairlist", [None])[0] or ""),
        timerange=str(strat.get("timerange", "")),
        total_trades=i("total_trades"),
        profit_total=f("profit_total"),
        profit_total_abs=f("profit_total_abs"),
        profit_factor=f("profit_factor"),
        winrate=f("winrate"),
        max_relative_drawdown=f("max_relative_drawdown"),
        sharpe=f("sharpe"),
        sortino=f("sortino"),
        calmar=f("calmar"),
        market_change=f("market_change"),
    )


def _rank_by_robustness(
    rows: list[dict[str, Any]],
    *,
    min_trades_each: int,
    min_trades_total: int,
) -> list[dict[str, Any]]:
    """
    对同一套参数在多个窗口的表现做汇总排序。
    目标：更关注“最差窗口”而不是单窗口爆炸。
    """

    grouped: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
    for r in rows:
        key = (
            float(r["buy_pred_threshold"]),
            float(r["sell_smart_exit_pred_threshold"]),
            str(r.get("sell_sl_min", "")).strip(),
            str(r.get("sell_tp_atr_mult", "")).strip(),
            str(r.get("buy_use_ema_long_slope_filter", "")).strip(),
            str(r.get("buy_ema_long_slope_lookback", "")).strip(),
            str(r.get("buy_use_max_atr_pct_filter", "")).strip(),
            str(r.get("buy_max_atr_pct", "")).strip(),
            str(r.get("buy_use_adx_filter", "")).strip(),
            str(r.get("buy_adx_period", "")).strip(),
            str(r.get("buy_adx_min", "")).strip(),
        )
        grouped.setdefault(key, []).append(r)

    summary: list[dict[str, Any]] = []
    for key, items in grouped.items():
        (
            buy_thr,
            smart_thr,
            sl_key,
            tp_key,
            buy_use_ema_long_slope_filter,
            buy_ema_long_slope_lookback,
            buy_use_max_atr_pct_filter,
            buy_max_atr_pct,
            buy_use_adx_filter,
            buy_adx_period,
            buy_adx_min,
        ) = key
        profits = [float(x["profit_total"]) for x in items]
        dds = [float(x["max_relative_drawdown"]) for x in items]
        trades = [int(x["total_trades"]) for x in items]
        trades_sum = sum(trades)

        has_all = all(t >= min_trades_each for t in trades)
        has_total = trades_sum >= min_trades_total
        # 评分：优先最大化最差收益，同时惩罚最大回撤
        profit_min = min(profits) if profits else float("-inf")
        profit_mean = sum(profits) / len(profits) if profits else float("-inf")
        dd_max = max(dds) if dds else float("inf")
        score = profit_min + 0.25 * profit_mean - 0.5 * dd_max

        summary.append(
            {
                "buy_pred_threshold": buy_thr,
                "sell_smart_exit_pred_threshold": smart_thr,
                "sell_sl_min": sl_key,
                "sell_tp_atr_mult": tp_key,
                "buy_use_ema_long_slope_filter": buy_use_ema_long_slope_filter,
                "buy_ema_long_slope_lookback": buy_ema_long_slope_lookback,
                "buy_use_max_atr_pct_filter": buy_use_max_atr_pct_filter,
                "buy_max_atr_pct": buy_max_atr_pct,
                "buy_use_adx_filter": buy_use_adx_filter,
                "buy_adx_period": buy_adx_period,
                "buy_adx_min": buy_adx_min,
                "windows": len(items),
                "trades_min": min(trades) if trades else 0,
                "trades_mean": (sum(trades) / len(trades)) if trades else 0.0,
                "trades_sum": trades_sum,
                "profit_min": profit_min,
                "profit_mean": profit_mean,
                "profit_max": max(profits) if profits else float("-inf"),
                "dd_max": dd_max,
                "score": score,
                "meets_min_trades_each": has_all,
                "meets_min_trades_total": has_total,
            }
        )

    summary.sort(
        key=lambda x: (
            bool(x["meets_min_trades_total"]),
            bool(x["meets_min_trades_each"]),
            x["score"],
        ),
        reverse=True,
    )
    return summary


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "FreqAI 参数扫参（跨多个回测窗口）\n"
            "- 目标：跨窗口评估 buy_pred_threshold / sell_smart_exit_pred_threshold，并可联动扫描入场过滤参数\n"
            "- 约束：会覆盖写入策略参数文件，运行结束会自动恢复\n"
        )
    )

    parser.add_argument(
        "--configs",
        nargs="+",
        default=["04_shared/configs/archive/freqai/lgbm_trend_v1_eval.json"],
        help="Freqtrade 配置文件列表（支持多个，用于对比 v1/v2）。",
    )
    parser.add_argument("--strategy", default="FreqaiLGBMTrendStrategy", help="策略类名。")
    parser.add_argument("--freqaimodel", default="LightGBMRegressor", help="FreqAI 模型类名。")
    parser.add_argument("--timeframe", default="1h", help="K 线周期。")
    parser.add_argument(
        "--timeframe-detail",
        default="",
        help="可选：用于更精细的回测撮合（例如 5m）。需要本地存在对应的 detail 数据。",
    )
    parser.add_argument(
        "--fee",
        type=float,
        default=-1.0,
        help="可选：显式指定手续费（单边比例，例如 0.001=0.1%%）。默认不覆盖配置/交易所默认值。",
    )
    parser.add_argument("--pairs", nargs="+", default=["BTC/USDT"], help="交易对列表（建议先从单币种开始）。")
    parser.add_argument(
        "--timeranges",
        nargs="+",
        default=[
            # 牛市：2020Q4 -> 2021Q1
            "20201010-20210108",
            # 震荡：2021Q4 -> 2022Q1
            "20211230-20220330",
            # 熊市：2022Q2
            "20220401-20220630",
        ],
        help="回测窗口列表（YYYYMMDD-YYYYMMDD）。",
    )
    parser.add_argument(
        "--buy-thresholds",
        default="0.006,0.008,0.010,0.012,0.014",
        help="buy_pred_threshold 扫参列表（逗号分隔）。",
    )
    parser.add_argument(
        "--sell-smart-thresholds",
        default="0.0,0.003,0.006",
        help="sell_smart_exit_pred_threshold 扫参列表（逗号分隔）。",
    )
    parser.add_argument(
        "--buy-use-ema-long-slope-filters",
        default="",
        help="可选：buy_use_ema_long_slope_filter 扫参列表（0/1 或 false/true）。留空表示不覆盖默认值。",
    )
    parser.add_argument(
        "--buy-ema-long-slope-lookbacks",
        default="",
        help="可选：buy_ema_long_slope_lookback 扫参列表（逗号分隔，例如 24,48,72）。留空表示不覆盖默认值。",
    )
    parser.add_argument(
        "--buy-use-max-atr-pct-filters",
        default="",
        help="可选：buy_use_max_atr_pct_filter 扫参列表（0/1 或 false/true）。留空表示不覆盖默认值。",
    )
    parser.add_argument(
        "--buy-max-atr-pcts",
        default="",
        help="可选：buy_max_atr_pct 扫参列表（逗号分隔，例如 0.03,0.04）。留空表示不覆盖默认值。",
    )
    parser.add_argument(
        "--buy-use-adx-filters",
        default="",
        help="可选：buy_use_adx_filter 扫参列表（0/1 或 false/true）。留空表示不覆盖默认值。",
    )
    parser.add_argument(
        "--buy-adx-periods",
        default="",
        help="可选：buy_adx_period 扫参列表（逗号分隔，例如 10,14）。留空表示不覆盖默认值。",
    )
    parser.add_argument(
        "--buy-adx-mins",
        default="",
        help="可选：buy_adx_min 扫参列表（逗号分隔，例如 15,20,25）。留空表示不覆盖默认值。",
    )
    parser.add_argument(
        "--sell-sl-mins",
        default="",
        help="可选：sell_sl_min 扫参列表（逗号分隔，例如 0.01,0.02）。留空表示不覆盖默认值。",
    )
    parser.add_argument(
        "--sell-tp-mults",
        default="",
        help="可选：sell_tp_atr_mult 扫参列表（逗号分隔，例如 2.0,3.0）。留空表示不覆盖默认值。",
    )
    parser.add_argument(
        "--min-trades-each",
        type=int,
        default=3,
        help="每个窗口最少成交笔数（用于稳健性筛选）。",
    )
    parser.add_argument(
        "--min-trades-total",
        type=int,
        default=20,
        help="所有窗口累计最少成交笔数（避免“几乎不交易”的参数组合被误判为最优）。",
    )
    parser.add_argument(
        "--run-id",
        default="",
        help="可选：指定输出目录名（默认自动生成时间戳）。",
    )
    parser.add_argument(
        "--strategy-param-file",
        default="01_freqtrade/strategies_archive/FreqaiLGBMTrendStrategy.json",
        help="策略参数文件路径（会被覆盖写入）。",
    )
    parser.add_argument(
        "--no-live-models",
        action="store_true",
        help="禁用 --freqai-backtest-live-models（每次都训练，速度更慢但最稳妥）。",
    )

    return parser.parse_args()


def main() -> int:
    args = _parse_args()

    repo_root = Path(__file__).resolve().parents[2]  # scripts/analysis -> scripts -> repo_root
    param_file = repo_root / str(args.strategy_param_file)

    buy_thresholds = _parse_float_list(str(args.buy_thresholds))
    smart_thresholds = _parse_float_list(str(args.sell_smart_thresholds))
    buy_use_ema_long_slope_filters_raw = _parse_bool_list(str(args.buy_use_ema_long_slope_filters))
    buy_use_ema_long_slope_filters: list[bool | None] = (
        buy_use_ema_long_slope_filters_raw if buy_use_ema_long_slope_filters_raw else [None]
    )
    buy_ema_long_slope_lookbacks_raw = _parse_int_list(str(args.buy_ema_long_slope_lookbacks))
    buy_ema_long_slope_lookbacks: list[int | None] = (
        buy_ema_long_slope_lookbacks_raw if buy_ema_long_slope_lookbacks_raw else [None]
    )
    buy_use_max_atr_pct_filters_raw = _parse_bool_list(str(args.buy_use_max_atr_pct_filters))
    buy_use_max_atr_pct_filters: list[bool | None] = (
        buy_use_max_atr_pct_filters_raw if buy_use_max_atr_pct_filters_raw else [None]
    )
    buy_max_atr_pcts_raw = _parse_float_list(str(args.buy_max_atr_pcts))
    buy_max_atr_pcts: list[float | None] = buy_max_atr_pcts_raw if buy_max_atr_pcts_raw else [None]
    buy_use_adx_filters_raw = _parse_bool_list(str(args.buy_use_adx_filters))
    buy_use_adx_filters: list[bool | None] = buy_use_adx_filters_raw if buy_use_adx_filters_raw else [None]
    buy_adx_periods_raw = _parse_int_list(str(args.buy_adx_periods))
    buy_adx_periods: list[int | None] = buy_adx_periods_raw if buy_adx_periods_raw else [None]
    buy_adx_mins_raw = _parse_int_list(str(args.buy_adx_mins))
    buy_adx_mins: list[int | None] = buy_adx_mins_raw if buy_adx_mins_raw else [None]
    sell_sl_mins_raw = _parse_float_list(str(args.sell_sl_mins))
    sell_sl_mins: list[float | None] = sell_sl_mins_raw if sell_sl_mins_raw else [None]
    sell_tp_mults_raw = _parse_float_list(str(args.sell_tp_mults))
    sell_tp_mults: list[float | None] = sell_tp_mults_raw if sell_tp_mults_raw else [None]
    if not buy_thresholds or not smart_thresholds:
        raise SystemExit("buy/sell 扫参列表不能为空。")

    run_id = str(args.run_id).strip() or datetime.now().strftime("%Y%m%d_%H%M%S")
    sweep_root = repo_root / "01_freqtrade/backtest_results" / "sweeps" / run_id
    sweep_root.mkdir(parents=True, exist_ok=True)

    results_csv = sweep_root / "results.csv"
    rank_csv = sweep_root / "ranking.csv"

    # 备份参数文件，保证跑完能恢复
    had_param_file = param_file.exists()
    backup_text = param_file.read_text(encoding="utf-8") if had_param_file else ""

    rows: list[dict[str, Any]] = []
    try:
        total_runs = (
            len(args.configs)
            * len(args.timeranges)
            * len(args.pairs)
            * (
                len(buy_thresholds)
                * len(smart_thresholds)
                * len(buy_use_ema_long_slope_filters)
                * len(buy_ema_long_slope_lookbacks)
                * len(buy_use_max_atr_pct_filters)
                * len(buy_max_atr_pcts)
                * len(buy_use_adx_filters)
                * len(buy_adx_periods)
                * len(buy_adx_mins)
                * len(sell_sl_mins)
                * len(sell_tp_mults)
            )
        )
        idx = 0
        for config in args.configs:
            config_path = (repo_root / config).resolve()
            config_name = config_path.name
            config_data = _read_json(config_path)
            freqai_identifier = str(((config_data.get("freqai") or {}).get("identifier")) or "")

            for timerange in args.timeranges:
                for pair in args.pairs:
                    # 每个 (config, timerange, pair) 先做一次 warmup，生成模型，后续可用 live-models 加速
                    warmup_done = False

                    for (
                        buy_thr,
                        smart_thr,
                        buy_use_ema_long_slope_filter,
                        buy_ema_long_slope_lookback,
                        buy_use_max_atr_pct_filter,
                        buy_max_atr_pct,
                        buy_use_adx_filter,
                        buy_adx_period,
                        buy_adx_min,
                        sl_min,
                        tp_mult,
                    ) in itertools.product(
                        buy_thresholds,
                        smart_thresholds,
                        buy_use_ema_long_slope_filters,
                        buy_ema_long_slope_lookbacks,
                        buy_use_max_atr_pct_filters,
                        buy_max_atr_pcts,
                        buy_use_adx_filters,
                        buy_adx_periods,
                        buy_adx_mins,
                        sell_sl_mins,
                        sell_tp_mults,
                    ):
                        idx += 1
                        use_live = (not bool(args.no_live_models)) and warmup_done
                        step = f"[{idx}/{total_runs}]"
                        sl_desc = f"{sl_min:.3f}" if sl_min is not None else "-"
                        tp_desc = f"{tp_mult:.2f}" if tp_mult is not None else "-"
                        ema_long_slope_desc = (
                            str(int(bool(buy_use_ema_long_slope_filter))) if buy_use_ema_long_slope_filter is not None else "-"
                        )
                        ema_long_lb_desc = str(buy_ema_long_slope_lookback) if buy_ema_long_slope_lookback is not None else "-"
                        atr_filter_desc = (
                            str(int(bool(buy_use_max_atr_pct_filter))) if buy_use_max_atr_pct_filter is not None else "-"
                        )
                        atr_max_desc = f"{buy_max_atr_pct:.3f}" if buy_max_atr_pct is not None else "-"
                        adx_filter_desc = str(int(bool(buy_use_adx_filter))) if buy_use_adx_filter is not None else "-"
                        adx_period_desc = str(buy_adx_period) if buy_adx_period is not None else "-"
                        adx_min_desc = str(buy_adx_min) if buy_adx_min is not None else "-"

                        print(
                            (
                                f"{step} config={config_name} id={freqai_identifier} pair={pair} timerange={timerange} "
                                f"buy_thr={buy_thr:.3f} smart_thr={smart_thr:.3f} sell_sl_min={sl_desc} "
                                f"sell_tp_atr_mult={tp_desc} ema_long_slope={ema_long_slope_desc} "
                                f"ema_long_lb={ema_long_lb_desc} atr_filter={atr_filter_desc} atr_max={atr_max_desc} "
                                f"adx_filter={adx_filter_desc} adx_p={adx_period_desc} adx_min={adx_min_desc} "
                                f"live_models={use_live}"
                            ),
                            flush=True,
                        )

                        buy_params: dict[str, Any] = {"buy_pred_threshold": float(buy_thr)}
                        if buy_use_ema_long_slope_filter is not None:
                            buy_params["buy_use_ema_long_slope_filter"] = bool(buy_use_ema_long_slope_filter)
                        if buy_ema_long_slope_lookback is not None:
                            buy_params["buy_ema_long_slope_lookback"] = int(buy_ema_long_slope_lookback)
                        if buy_use_max_atr_pct_filter is not None:
                            buy_params["buy_use_max_atr_pct_filter"] = bool(buy_use_max_atr_pct_filter)
                        if buy_max_atr_pct is not None:
                            buy_params["buy_max_atr_pct"] = float(buy_max_atr_pct)
                        if buy_use_adx_filter is not None:
                            buy_params["buy_use_adx_filter"] = bool(buy_use_adx_filter)
                        if buy_adx_period is not None:
                            buy_params["buy_adx_period"] = int(buy_adx_period)
                        if buy_adx_min is not None:
                            buy_params["buy_adx_min"] = int(buy_adx_min)

                        sell_params: dict[str, Any] = {"sell_smart_exit_pred_threshold": float(smart_thr)}
                        if sl_min is not None:
                            sell_params["sell_sl_min"] = float(sl_min)
                        if tp_mult is not None:
                            sell_params["sell_tp_atr_mult"] = float(tp_mult)

                        _write_strategy_params(param_file, args.strategy, buy_params, sell_params)

                        run_dir = sweep_root / f"{config_path.stem}__{pair.replace('/', '_')}__{timerange}"
                        run_dir.mkdir(parents=True, exist_ok=True)
                        log_path = run_dir / f"run_{idx:04d}.log"

                        try:
                            _run_backtesting(
                                repo_root=repo_root,
                                run_dir=run_dir,
                                config_path=config_path,
                                strategy_name=args.strategy,
                                freqaimodel=args.freqaimodel,
                                timeframe=args.timeframe,
                                timeframe_detail=(str(args.timeframe_detail).strip() or None),
                                timerange=timerange,
                                pair=pair,
                                use_live_models=use_live,
                                fee=(float(args.fee) if float(args.fee) > 0 else None),
                                log_path=log_path,
                            )
                            warmup_done = True
                        except RuntimeError:
                            # live-models 可能因为模型缺失而失败：回退到“训练模式”再跑一次
                            if use_live:
                                _run_backtesting(
                                    repo_root=repo_root,
                                    run_dir=run_dir,
                                    config_path=config_path,
                                    strategy_name=args.strategy,
                                    freqaimodel=args.freqaimodel,
                                    timeframe=args.timeframe,
                                    timeframe_detail=(str(args.timeframe_detail).strip() or None),
                                    timerange=timerange,
                                    pair=pair,
                                    use_live_models=False,
                                    fee=(float(args.fee) if float(args.fee) > 0 else None),
                                    log_path=log_path,
                                )
                                warmup_done = True
                            else:
                                raise

                        zip_path = _read_latest_zip_from_run_dir(run_dir)
                        m = _extract_metrics(zip_path, args.strategy)

                        rows.append(
                            {
                                "config": str(config_path.as_posix()),
                                "config_name": config_name,
                                "freqai_identifier": freqai_identifier,
                                "pair": pair,
                                "timerange": timerange,
                                "buy_pred_threshold": buy_thr,
                                "sell_smart_exit_pred_threshold": smart_thr,
                                "buy_use_ema_long_slope_filter": (
                                    str(int(bool(buy_use_ema_long_slope_filter)))
                                    if buy_use_ema_long_slope_filter is not None
                                    else ""
                                ),
                                "buy_ema_long_slope_lookback": (
                                    str(int(buy_ema_long_slope_lookback)) if buy_ema_long_slope_lookback is not None else ""
                                ),
                                "buy_use_max_atr_pct_filter": (
                                    str(int(bool(buy_use_max_atr_pct_filter))) if buy_use_max_atr_pct_filter is not None else ""
                                ),
                                "buy_max_atr_pct": (f"{buy_max_atr_pct:.3f}" if buy_max_atr_pct is not None else ""),
                                "buy_use_adx_filter": (
                                    str(int(bool(buy_use_adx_filter))) if buy_use_adx_filter is not None else ""
                                ),
                                "buy_adx_period": (str(int(buy_adx_period)) if buy_adx_period is not None else ""),
                                "buy_adx_min": (str(int(buy_adx_min)) if buy_adx_min is not None else ""),
                                "sell_sl_min": (f"{sl_min:.3f}" if sl_min is not None else ""),
                                "sell_tp_atr_mult": (f"{tp_mult:.2f}" if tp_mult is not None else ""),
                                "use_live_models": bool(use_live),
                                "zip": str(zip_path.relative_to(repo_root).as_posix()),
                                "total_trades": m.total_trades,
                                "profit_total": m.profit_total,
                                "profit_total_pct": m.profit_total * 100.0,
                                "profit_total_abs": m.profit_total_abs,
                                "profit_factor": m.profit_factor,
                                "winrate": m.winrate,
                                "max_relative_drawdown": m.max_relative_drawdown,
                                "max_relative_drawdown_pct": m.max_relative_drawdown * 100.0,
                                "sharpe": m.sharpe,
                                "sortino": m.sortino,
                                "calmar": m.calmar,
                                "market_change": m.market_change,
                                "market_change_pct": m.market_change * 100.0,
                                "log": str(log_path.relative_to(repo_root).as_posix()),
                            }
                        )

        # 写出结果明细
        with results_csv.open("w", newline="", encoding="utf-8") as fp:
            writer = csv.DictWriter(fp, fieldnames=sorted(rows[0].keys()) if rows else [])
            writer.writeheader()
            writer.writerows(rows)

        # 只对第一份 config 做排序（常用于 v1 扫参选参）
        if rows:
            primary_config = str(Path(args.configs[0]).name)
            primary_rows = [r for r in rows if r.get("config_name") == primary_config]
            ranking = _rank_by_robustness(
                primary_rows,
                min_trades_each=int(args.min_trades_each),
                min_trades_total=int(args.min_trades_total),
            )

            with rank_csv.open("w", newline="", encoding="utf-8") as fp:
                writer = csv.DictWriter(fp, fieldnames=list(ranking[0].keys()) if ranking else [])
                writer.writeheader()
                writer.writerows(ranking)

        print("")
        print(f"已生成：{results_csv.relative_to(repo_root).as_posix()}")
        print(f"已生成：{rank_csv.relative_to(repo_root).as_posix()}")
        print("")
        return 0
    finally:
        # 无论成功失败，都恢复参数文件（避免污染默认行为）
        if had_param_file:
            param_file.write_text(backup_text, encoding="utf-8")
        else:
            try:
                if param_file.exists():
                    param_file.unlink()
            except Exception:
                pass


if __name__ == "__main__":
    raise SystemExit(main())
