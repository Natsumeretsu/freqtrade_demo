from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ScanResult:
    horizon: int
    min_return: float
    buy_adx_min: int
    buy_proba_min: float
    buy_require_pred: bool
    roi: float
    max_hold_mult: float
    sell_use_model_exit: bool
    sell_trend_exit: bool
    trend_exit_confirm: int
    trend_exit_buffer: float
    trend_exit_require_model: bool
    loss_cut: float
    model_path: str
    backtest_zip: str
    trades: int
    profit_total_pct: float
    profit_total_abs: float
    winrate: float
    max_drawdown_account: float
    score: float


_THRESHOLD_LINE_RE = re.compile(
    r"thr>=(?P<thr>\d+\.\d+):\s*"
    r"触发率=(?P<rate>\d+\.\d+)\s*"
    r"样本=(?P<samples>\d+)\s*"
    r"精确率=(?P<precision>(?:-?\d+\.\d+|nan))\s*"
    r"平均未来收益=(?P<avg_ret>(?:-?\d+\.\d+|nan))"
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _uv_env() -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    return env


def _run(cmd: list[str], cwd: Path, env: dict[str, str], print_on_success: bool = False) -> str:
    completed = subprocess.run(
        cmd,
        cwd=str(cwd),
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    output = completed.stdout or ""
    if completed.returncode != 0:
        print(output)
        raise RuntimeError(f"命令执行失败: {' '.join(cmd)} (exit={completed.returncode})")
    if print_on_success:
        print(output)
    return output


def _pick_best_threshold(train_output: str, min_samples: int = 200) -> float:
    rows: list[tuple[float, float, float, int]] = []
    for line in train_output.splitlines():
        match = _THRESHOLD_LINE_RE.search(line)
        if not match:
            continue
        thr = float(match.group("thr"))
        samples = int(match.group("samples"))
        precision_str = match.group("precision")
        avg_ret_str = match.group("avg_ret")
        try:
            precision = float(precision_str)
        except ValueError:
            precision = float("nan")
        try:
            avg_ret = float(avg_ret_str)
        except ValueError:
            avg_ret = float("nan")

        if samples < min_samples:
            continue
        if avg_ret != avg_ret:  # NaN
            continue
        rows.append((avg_ret, precision, thr, samples))

    if not rows:
        return 0.6

    rows.sort(key=lambda r: (r[0], r[1], r[2]), reverse=True)
    return float(rows[0][2])


def _read_json_if_exists(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _write_strategy_params(
    param_path: Path,
    *,
    pair: str,
    buy_adx_min: int,
    buy_proba_min: float,
    buy_require_pred: bool,
    roi: float,
    max_hold_mult: float,
    sell_use_model_exit: bool,
    sell_trend_exit: bool,
    trend_exit_confirm: int,
    trend_exit_buffer: float,
    trend_exit_require_model: bool,
    loss_cut: float,
    model_path: str,
) -> None:
    payload = _read_json_if_exists(param_path)
    payload["strategy_name"] = "KNNTrendWindowStrategy"

    params = payload.get("params")
    if not isinstance(params, dict):
        params = {}
        payload["params"] = params

    buy = params.get("buy")
    if not isinstance(buy, dict):
        buy = {}
        params["buy"] = buy
    buy.update(
        {
            "buy_adx_min": int(buy_adx_min),
            "buy_proba_min": float(round(buy_proba_min, 4)),
            "buy_require_pred": bool(buy_require_pred),
        }
    )

    sell = params.get("sell")
    if not isinstance(sell, dict):
        sell = {}
        params["sell"] = sell
    sell.update(
        {
            "max_hold_mult": float(round(max_hold_mult, 2)),
            "sell_use_model_exit": bool(sell_use_model_exit),
            "sell_trend_exit": bool(sell_trend_exit),
            "sell_trend_exit_confirm": int(trend_exit_confirm),
            "sell_trend_exit_buffer": float(round(trend_exit_buffer, 4)),
            "sell_trend_exit_require_model": bool(trend_exit_require_model),
            "sell_time_loss_cut": float(round(loss_cut, 4)),
        }
    )

    params["roi"] = {"0": float(roi)}
    params["model_path"] = model_path.replace("\\", "/")

    # 如果参数文件启用了 per-pair 覆盖，则同步写入当前 pair，保证扫描参数真实生效
    overrides = params.get("pair_overrides")
    if isinstance(overrides, dict):
        overrides[str(pair)] = {
            "buy_adx_min": int(buy_adx_min),
            "buy_proba_min": float(round(buy_proba_min, 4)),
            "buy_require_pred": bool(buy_require_pred),
            "max_hold_mult": float(round(max_hold_mult, 2)),
            "sell_use_model_exit": bool(sell_use_model_exit),
            "sell_trend_exit": bool(sell_trend_exit),
            "sell_trend_exit_confirm": int(trend_exit_confirm),
            "sell_trend_exit_buffer": float(round(trend_exit_buffer, 4)),
            "sell_trend_exit_require_model": bool(trend_exit_require_model),
            "sell_time_loss_cut": float(round(loss_cut, 4)),
            "model_path": model_path.replace("\\", "/"),
        }
    param_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _read_last_backtest_zip(cwd: Path) -> Path:
    last_path = cwd / "backtest_results" / ".last_result.json"
    last = json.loads(last_path.read_text(encoding="utf-8"))
    zip_name = last["latest_backtest"]
    return cwd / "backtest_results" / zip_name


def _read_strategy_summary(zip_path: Path) -> dict:
    json_name = zip_path.with_suffix(".json").name
    with zipfile.ZipFile(zip_path) as zf:
        data = json.loads(zf.read(json_name))
    if not data.get("strategy_comparison"):
        raise ValueError(f"无法解析回测摘要: {zip_path}")
    return data["strategy_comparison"][0]


def _parse_list(values: str) -> list[float]:
    return [float(x.strip()) for x in values.split(",") if x.strip()]


def _parse_list_int(values: str) -> list[int]:
    return [int(x.strip()) for x in values.split(",") if x.strip()]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "网格扫描：训练 +（可选）验证/回测，寻找更合适的 KNN 参数组合。\n"
            "建议做三段：Train=2018-2024，Val=2024，Test=2025-2026（只用 Test 做最终一次回测）。"
        )
    )
    parser.add_argument("--datadir", default="data/okx", help="Freqtrade 数据目录")
    parser.add_argument("--pair", default="BTC/USDT", help="交易对，例如 BTC/USDT")
    parser.add_argument("--timeframe", default="1h", help="K线周期，例如 1h")
    parser.add_argument("--train-timerange", default="20180101-20250101", help="训练集时间范围")
    parser.add_argument("--test-timerange", default="20250101-", help="测试/验证集时间范围（用于训练脚本评估/阈值扫描）")
    parser.add_argument("--backtest-timerange", default="20250101-20270101", help="回测区间（用于选参）")

    parser.add_argument("--horizons", default="4,6,8", help="horizon 列表（逗号分隔）")
    parser.add_argument("--min-returns", default="0.006,0.01,0.015", help="min-return 列表（逗号分隔）")
    parser.add_argument(
        "--label-mode",
        choices=["end_close", "max_high"],
        default="end_close",
        help=(
            "训练标签模式："
            "end_close=使用 close(t+h) 收益；"
            "max_high=使用未来 horizon 内最高价是否触达阈值（更贴近 ROI/止盈命中）。"
        ),
    )
    parser.add_argument(
        "--rois",
        default="",
        help=(
            "策略 ROI 列表（逗号分隔）。留空表示 roi=min-return（与训练标签保持一致）。"
        ),
    )

    parser.add_argument("--window", type=int, default=8, help="特征窗口 N")
    parser.add_argument("--neighbors", type=int, default=25, help="KNN 邻居数 k")
    parser.add_argument(
        "--model",
        choices=["knn", "logreg"],
        default="knn",
        help="分类器：knn=KNN；logreg=LogisticRegression（更稳健，通常更不容易过拟合）。",
    )
    parser.add_argument("--balance", default="downsample", choices=["none", "downsample", "upsample"], help="训练集类别平衡")
    parser.add_argument(
        "--include-trend-features",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="训练时将趋势上下文特征（EMA/ADX 相关）加入 KNN 输入向量",
    )
    parser.add_argument(
        "--filter-trend",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="仅训练上升趋势样本（与策略一致）",
    )
    parser.add_argument("--adx-min", type=float, default=10.0, help="训练用趋势过滤 ADX 阈值")
    parser.add_argument("--buy-adx-mins", default="20,30", help="策略入场 ADX 阈值列表（逗号分隔）")
    parser.add_argument("--buy-proba-mins", default="0.55,0.60,0.65,0.70", help="策略入场 proba 阈值列表（逗号分隔，或写 auto）")
    parser.add_argument(
        "--sell-use-model-exit",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="是否启用模型翻空退出（MODEL_PRED）。默认关闭（更稳健）。",
    )
    parser.add_argument(
        "--sell-trend-exit",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="是否启用趋势破坏退出（TREND_BREAK）。默认关闭（需在验证集选参后再启用）。",
    )
    parser.add_argument(
        "--trend-exit-confirms",
        default="2",
        help="趋势破坏确认根数列表（逗号分隔，1-3）。",
    )
    parser.add_argument(
        "--trend-exit-buffers",
        default="0.0",
        help="趋势破位缓冲列表（逗号分隔，0-0.02）。例如 0.005 表示跌破 EMA0.5% 才触发。",
    )
    parser.add_argument(
        "--trend-exit-require-model",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="趋势退出是否要求模型翻空确认（knn_pred==-1）。默认关闭。",
    )
    parser.add_argument(
        "--max-hold-mults",
        default="1.0",
        help="time_exit 最大持仓倍数列表（逗号分隔，乘以模型 horizon；0 表示禁用 time_exit）",
    )
    parser.add_argument(
        "--loss-cuts",
        default="",
        help="浮亏截断阈值列表（逗号分隔）。例如 0.01 表示 -1% 截断；0 表示禁用（默认）。",
    )
    parser.add_argument(
        "--buy-require-pred",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="入场是否要求 knn_pred==1（更严格，通常能显著减少噪音交易）",
    )

    parser.add_argument("--min-trades", type=int, default=10, help="筛选最佳结果时，至少需要的交易笔数（避免“偶然盈利的少量交易”）")
    parser.add_argument(
        "--dd-weight",
        type=float,
        default=0.0,
        help="评分时对回撤的惩罚权重：score = profit_total_pct - (max_drawdown_account*100*dd_weight)",
    )

    parser.add_argument("--max-runs", type=int, default=0, help="最多跑多少组（0 表示全量）")
    parser.add_argument("--max-backtests", type=int, default=0, help="最多跑多少次回测（0 表示全量）")
    parser.add_argument("--results-out", default="backtest_results/knn_tw_scan_results.json", help="结果输出文件")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    cwd = _repo_root()
    env = _uv_env()

    horizons = _parse_list_int(args.horizons)
    min_returns = _parse_list(args.min_returns)
    roi_list = _parse_list(args.rois) if str(args.rois).strip() else []
    max_hold_mults = _parse_list(args.max_hold_mults)
    loss_cuts = _parse_list(args.loss_cuts) if str(args.loss_cuts).strip() else [0.0]

    scan_dir = cwd / "models" / "scan"
    scan_dir.mkdir(parents=True, exist_ok=True)

    param_path = cwd / "strategies" / "knn_trend_window_strategy.json"

    results: list[ScanResult] = []
    run_count = 0
    backtest_count = 0

    buy_adx_mins = _parse_list_int(args.buy_adx_mins)
    buy_require_pred = bool(args.buy_require_pred)
    sell_use_model_exit = bool(args.sell_use_model_exit)
    sell_trend_exit = bool(args.sell_trend_exit)
    trend_exit_confirms = _parse_list_int(args.trend_exit_confirms) if sell_trend_exit else [2]
    trend_exit_buffers = _parse_list(args.trend_exit_buffers) if sell_trend_exit else [0.0]
    trend_exit_require_model = bool(args.trend_exit_require_model)

    min_trades = int(args.min_trades)
    dd_weight = float(args.dd_weight)

    for horizon in horizons:
        for min_return in min_returns:
            run_count += 1
            if args.max_runs and run_count > int(args.max_runs):
                break

            pair_slug = args.pair.replace("/", "_").lower()
            tf_slug = args.timeframe.lower()
            minret_bp = int(round(min_return * 10000))
            suffix_parts: list[str] = []
            if str(args.model).strip().lower() != "knn":
                suffix_parts.append(str(args.model).strip().lower())
            if bool(args.include_trend_features):
                suffix_parts.append("trendfeat")
            if str(args.label_mode).strip().lower() != "end_close":
                suffix_parts.append(str(args.label_mode).strip().lower())
            suffix = f"_{'_'.join(suffix_parts)}" if suffix_parts else ""
            model_rel = f"models/scan/knn_tw_{pair_slug}_{tf_slug}_h{horizon}_r{minret_bp:04d}{suffix}.pkl"
            model_out = cwd / model_rel

            print("")
            print(f"=== 扫描 {run_count}: horizon={horizon}  min_return={min_return:.4f} ===")

            train_cmd = [
                "uv",
                "run",
                "python",
                "-X",
                "utf8",
                "scripts/train_knn_trend_window.py",
                "--datadir",
                args.datadir,
                "--pair",
                args.pair,
                "--timeframe",
                args.timeframe,
                "--window",
                str(int(args.window)),
                "--horizon",
                str(int(horizon)),
                "--min-return",
                str(float(min_return)),
                "--label-mode",
                str(args.label_mode),
                "--neighbors",
                str(int(args.neighbors)),
                "--model",
                str(args.model),
                "--balance",
                str(args.balance),
                "--adx-min",
                str(float(args.adx_min)),
                "--train-timerange",
                str(args.train_timerange),
                "--test-timerange",
                str(args.test_timerange),
                "--model-out",
                str(model_out),
            ]
            if args.filter_trend:
                train_cmd.append("--filter-trend")
            if args.include_trend_features:
                train_cmd.append("--include-trend-features")

            train_output = _run(train_cmd, cwd=cwd, env=env, print_on_success=False)

            if str(args.buy_proba_mins).strip().lower() == "auto":
                buy_proba_mins = [float(_pick_best_threshold(train_output))]
            else:
                buy_proba_mins = _parse_list(args.buy_proba_mins)

            rois = roi_list if roi_list else [float(min_return)]

            for buy_adx_min in buy_adx_mins:
                for buy_proba_min in buy_proba_mins:
                    for max_hold_mult in max_hold_mults:
                        for trend_exit_confirm in trend_exit_confirms:
                            for trend_exit_buffer in trend_exit_buffers:
                                for loss_cut in loss_cuts:
                                    for roi in rois:
                                        backtest_count += 1
                                        if args.max_backtests and backtest_count > int(args.max_backtests):
                                            break

                                        _write_strategy_params(
                                            param_path,
                                            pair=str(args.pair),
                                            buy_adx_min=int(buy_adx_min),
                                            buy_proba_min=float(buy_proba_min),
                                            buy_require_pred=buy_require_pred,
                                            roi=float(roi),
                                            max_hold_mult=float(max_hold_mult),
                                            sell_use_model_exit=sell_use_model_exit,
                                            sell_trend_exit=sell_trend_exit,
                                            trend_exit_confirm=int(trend_exit_confirm),
                                            trend_exit_buffer=float(trend_exit_buffer),
                                            trend_exit_require_model=trend_exit_require_model,
                                            loss_cut=float(loss_cut),
                                            model_path=model_rel,
                                        )

                                        backtest_cmd = [
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
                                            "config.json",
                                            "--datadir",
                                            args.datadir,
                                            "--strategy",
                                            "KNNTrendWindowStrategy",
                                            "--timeframe",
                                            args.timeframe,
                                            "--timerange",
                                            args.backtest_timerange,
                                            "--pairs",
                                            args.pair,
                                        ]
                                        _run(backtest_cmd, cwd=cwd, env=env, print_on_success=False)

                                        zip_path = _read_last_backtest_zip(cwd)
                                        summary = _read_strategy_summary(zip_path)
                                        trades = int(summary["trades"])
                                        profit_total_pct = float(summary["profit_total_pct"])
                                        max_dd = float(summary["max_drawdown_account"])
                                        score = profit_total_pct - (max_dd * 100.0 * dd_weight)

                                        res = ScanResult(
                                            horizon=int(horizon),
                                            min_return=float(min_return),
                                            buy_adx_min=int(buy_adx_min),
                                            buy_proba_min=float(buy_proba_min),
                                            buy_require_pred=buy_require_pred,
                                            roi=float(roi),
                                            max_hold_mult=float(max_hold_mult),
                                            sell_use_model_exit=sell_use_model_exit,
                                            sell_trend_exit=sell_trend_exit,
                                            trend_exit_confirm=int(trend_exit_confirm),
                                            trend_exit_buffer=float(trend_exit_buffer),
                                            trend_exit_require_model=trend_exit_require_model,
                                            loss_cut=float(loss_cut),
                                            model_path=model_rel,
                                            backtest_zip=zip_path.name,
                                            trades=trades,
                                            profit_total_pct=profit_total_pct,
                                            profit_total_abs=float(summary["profit_total_abs"]),
                                            winrate=float(summary["winrate"]),
                                            max_drawdown_account=max_dd,
                                            score=float(score),
                                        )
                                        results.append(res)

                                        print(
                                            f"结果: trades={res.trades}  profit={res.profit_total_pct:.2f}%  "
                                            f"score={res.score:.2f}  winrate={res.winrate:.1%}  "
                                            f"max_dd={res.max_drawdown_account:.1%}  "
                                            f"adx>={res.buy_adx_min}  proba>={res.buy_proba_min:.2f}  "
                                            f"hold_mult={res.max_hold_mult:.1f}  "
                                            f"trend_exit={res.sell_trend_exit}  "
                                            f"trend_confirm={res.trend_exit_confirm}  "
                                            f"trend_buf={res.trend_exit_buffer:.3f}  "
                                            f"loss_cut={res.loss_cut:.3f}  "
                                            f"roi={res.roi:.4f}  h={res.horizon}  r(label)={res.min_return:.4f}"
                                        )

                if args.max_backtests and backtest_count >= int(args.max_backtests):
                    break

            if args.max_backtests and backtest_count >= int(args.max_backtests):
                break

        if args.max_runs and run_count >= int(args.max_runs):
            break

    if not results:
        raise SystemExit("未产生任何扫描结果，请检查参数/数据。")

    eligible = [r for r in results if r.trades >= min_trades]
    if eligible:
        pool = eligible
    else:
        pool = results
        print("")
        print(f"⚠️ 未找到 trades >= {min_trades} 的组合，将退回到“不过滤交易笔数”的最优结果。")

    pool.sort(key=lambda r: (r.score, r.profit_total_pct, -r.max_drawdown_account, r.trades), reverse=True)
    best = pool[0]

    results.sort(key=lambda r: (r.score, r.profit_total_pct, -r.max_drawdown_account, r.trades), reverse=True)

    print("")
    print("=== 扫描完成：Top 5 ===")
    for idx, r in enumerate(results[:5], 1):
        print(
            f"{idx}. score={r.score:.2f}  profit={r.profit_total_pct:.2f}%  trades={r.trades}  "
            f"dd={r.max_drawdown_account:.1%}  winrate={r.winrate:.1%}  "
            f"h={r.horizon}  r(label)={r.min_return:.4f}  roi={r.roi:.4f}  "
            f"adx>={r.buy_adx_min}  proba>={r.buy_proba_min:.2f}  "
            f"hold_mult={r.max_hold_mult:.1f}  "
            f"trend_exit={r.sell_trend_exit}  "
            f"trend_confirm={r.trend_exit_confirm}  "
            f"trend_buf={r.trend_exit_buffer:.3f}  "
            f"loss_cut={r.loss_cut:.3f}  "
            f"require_pred={r.buy_require_pred}  "
            f"zip={r.backtest_zip}"
        )

    # 写回最佳参数，方便你直接继续回测/实盘验证
    _write_strategy_params(
        param_path,
        pair=str(args.pair),
        buy_adx_min=int(best.buy_adx_min),
        buy_proba_min=float(best.buy_proba_min),
        buy_require_pred=bool(best.buy_require_pred),
        roi=float(best.roi),
        max_hold_mult=float(best.max_hold_mult),
        sell_use_model_exit=bool(best.sell_use_model_exit),
        sell_trend_exit=bool(best.sell_trend_exit),
        trend_exit_confirm=int(best.trend_exit_confirm),
        trend_exit_buffer=float(best.trend_exit_buffer),
        trend_exit_require_model=bool(best.trend_exit_require_model),
        loss_cut=float(best.loss_cut),
        model_path=best.model_path,
    )

    out_path = (cwd / args.results_out).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps([r.__dict__ for r in results], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print("")
    print("=== 已应用最佳参数 ===")
    print(f"- 参数文件: {param_path}")
    print(f"- 模型文件: {best.model_path}")
    print(f"- 对应回测: backtest_results/{best.backtest_zip}")
    print(f"- 最佳 buy_adx_min: {best.buy_adx_min}")
    print(f"- 最佳 buy_proba_min: {best.buy_proba_min:.2f}")
    print(f"- 最佳 buy_require_pred: {best.buy_require_pred}")
    print(f"- 最佳 max_hold_mult: {best.max_hold_mult:.1f}")
    print(f"- 最佳 sell_trend_exit: {best.sell_trend_exit}")
    print(f"- 最佳 trend_exit_confirm: {best.trend_exit_confirm}")
    print(f"- 最佳 trend_exit_buffer: {best.trend_exit_buffer:.3f}")
    print(f"- 最佳 trend_exit_require_model: {best.trend_exit_require_model}")
    print(f"- 最佳 loss_cut: {best.loss_cut:.3f}")
    print(f"- 最佳 roi: {best.roi:.4f}")
    print(f"- 汇总输出: {out_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
