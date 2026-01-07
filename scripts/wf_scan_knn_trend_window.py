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
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Fold:
    name: str
    train_timerange: str
    test_timerange: str
    backtest_timerange: str


@dataclass(frozen=True)
class Variant:
    name: str
    sell_use_model_exit: bool
    sell_trend_exit: bool


def _parse_list_int(values: str) -> list[int]:
    return [int(x.strip()) for x in str(values).split(",") if x.strip()]


def _pair_slug(pair: str) -> str:
    return pair.replace("/", "_").lower()


def _uv_env() -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    return env


def _run(cmd: list[str], *, cwd: Path, env: dict[str, str], timeout_sec: int) -> str:
    joined = " ".join(cmd)
    print("")
    print(f"运行命令：{joined}")
    completed = subprocess.run(
        cmd,
        cwd=str(cwd),
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=int(timeout_sec),
    )
    output = completed.stdout or ""
    if completed.returncode != 0:
        raise RuntimeError(f"命令执行失败(exit={completed.returncode}): {joined}\n{output}")
    return output


def _build_default_folds(*, years: list[int], train_start: str, mid_mmdd: str) -> list[Fold]:
    folds: list[Fold] = []
    for y in years:
        y = int(y)
        folds.append(
            Fold(
                name=str(y),
                train_timerange=f"{train_start}-{y}0101",
                test_timerange=f"{y}0101-{y}{mid_mmdd}",
                backtest_timerange=f"{y}{mid_mmdd}-{y + 1}0101",
            )
        )
    return folds


def _signature(r: dict[str, Any]) -> dict[str, Any]:
    def f(key: str, digits: int = 4) -> float:
        return float(round(float(r.get(key, 0.0)), digits))

    return {
        "horizon": int(r.get("horizon", 0)),
        "min_return": f("min_return", 6),
        "buy_adx_min": int(r.get("buy_adx_min", 0)),
        "buy_proba_min": f("buy_proba_min", 4),
        "buy_require_pred": bool(r.get("buy_require_pred", True)),
        "max_hold_mult": f("max_hold_mult", 2),
        "sell_use_model_exit": bool(r.get("sell_use_model_exit", False)),
        "sell_trend_exit": bool(r.get("sell_trend_exit", False)),
        "trend_exit_confirm": int(r.get("trend_exit_confirm", 2)),
        "trend_exit_buffer": f("trend_exit_buffer", 4),
        "trend_exit_require_model": bool(r.get("trend_exit_require_model", False)),
        "loss_cut": f("loss_cut", 4),
        "roi": f("roi", 6),
    }


def _read_results(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        raise FileNotFoundError(f"未找到结果文件：{path}")
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError(f"结果文件格式错误（应为 list）：{path}")
    return [x for x in raw if isinstance(x, dict)]


def _read_exit_reason_counts(zip_path: Path, *, strategy_name: str) -> dict[str, int]:
    if not zip_path.is_file():
        return {}
    json_name = zip_path.with_suffix(".json").name
    with zipfile.ZipFile(zip_path) as zf:
        if json_name not in set(zf.namelist()):
            return {}
        data = json.loads(zf.read(json_name))
    strat = (data.get("strategy") or {}).get(strategy_name) or {}
    summary = strat.get("exit_reason_summary") or []
    counts: dict[str, int] = {}
    for row in summary:
        if not isinstance(row, dict):
            continue
        key = str(row.get("key", "")).strip()
        if not key:
            continue
        try:
            counts[key] = int(row.get("trades", 0))
        except (TypeError, ValueError):
            continue
    return counts


def _pick_best_stable(
    aggregated: list[dict[str, Any]],
    *,
    require_folds: int,
    min_trades: int,
) -> dict[str, Any] | None:
    for row in aggregated:
        if int(row.get("support", 0)) != int(require_folds):
            continue
        if int(row.get("trades_min", 0)) < int(min_trades):
            continue
        if float(row.get("profit_min", -1e9)) <= 0:
            continue
        return row
    return None


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Walk-forward 扫描：在多个折上扫描参数稳定性，重点验证退出逻辑是否真的压住尾部大亏。\n"
            "说明：本脚本会调用 scripts/scan_knn_trend_window.py，多次回测会较耗时。"
        )
    )
    parser.add_argument("--datadir", default="data/okx", help="Freqtrade 数据目录")
    parser.add_argument("--pair", default="ETH/USDT", help="交易对，例如 ETH/USDT")
    parser.add_argument("--timeframe", default="1h", help="K线周期，例如 1h")
    parser.add_argument(
        "--run-tag",
        default="",
        help="本次运行的标识（用于区分不同标签/参数组合的输出文件）。留空将自动生成。",
    )

    parser.add_argument("--years", default="2022,2023,2024", help="折的年份列表（逗号分隔）")
    parser.add_argument("--train-start", default="20180101", help="训练集起始日期 YYYYMMDD")
    parser.add_argument("--mid-mmdd", default="0701", help="折中点（月日），默认 0701")

    parser.add_argument("--horizons", default="6", help="horizon 列表（逗号分隔）")
    parser.add_argument("--min-returns", default="0.009", help="min-return 列表（逗号分隔）")
    parser.add_argument("--rois", default="0.008", help="策略 ROI 列表（逗号分隔）")
    parser.add_argument(
        "--label-mode",
        choices=["end_close", "max_high"],
        default="end_close",
        help="训练标签模式",
    )
    parser.add_argument(
        "--model",
        choices=["knn", "logreg"],
        default="logreg",
        help="分类器类型（建议 logreg 作为更稳健对照）。",
    )
    parser.add_argument("--window", type=int, default=8, help="特征窗口 N")
    parser.add_argument("--neighbors", type=int, default=25, help="KNN 邻居数 k（logreg 下会被忽略）")
    parser.add_argument(
        "--balance",
        choices=["none", "downsample", "upsample"],
        default="downsample",
        help="训练集类别平衡方式",
    )
    parser.add_argument(
        "--filter-trend",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="是否只用上升趋势样本训练（默认 true，与策略一致）",
    )
    parser.add_argument(
        "--include-trend-features",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="是否把趋势上下文特征加入模型输入向量",
    )
    parser.add_argument("--adx-min", type=float, default=10.0, help="训练用趋势过滤 ADX 阈值")

    parser.add_argument("--buy-adx-mins", default="30", help="策略入场 ADX 阈值列表（逗号分隔）")
    parser.add_argument("--buy-proba-mins", default="0.50,0.55,0.60", help="策略入场 proba 阈值列表（逗号分隔）")
    parser.add_argument("--max-hold-mults", default="0,2.0", help="time_exit 最大持仓倍数列表（逗号分隔）")
    parser.add_argument(
        "--buy-require-pred",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="入场是否要求 knn_pred==1",
    )

    parser.add_argument(
        "--trend-exit-confirms",
        default="2,3",
        help="趋势破坏确认根数列表（仅在 sell_trend_exit=true 时生效）",
    )
    parser.add_argument(
        "--trend-exit-buffers",
        default="0.0,0.005",
        help="趋势破位缓冲列表（仅在 sell_trend_exit=true 时生效）",
    )
    parser.add_argument(
        "--trend-exit-require-model",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="趋势退出是否要求模型翻空确认",
    )
    parser.add_argument("--loss-cuts", default="", help="浮亏截断阈值列表（逗号分隔，默认禁用）")

    parser.add_argument("--min-trades", type=int, default=20, help="每折至少交易笔数（过滤偶然结果）")
    parser.add_argument("--dd-weight", type=float, default=0.0, help="扫描脚本内的回撤惩罚权重（建议 0，聚合时再评估）")
    parser.add_argument("--timeout-sec", type=int, default=1800, help="单次 scan 命令超时（秒）")

    parser.add_argument(
        "--final-train-timerange",
        default="20180101-20250101",
        help="最终模型训练区间（严格不包含样本外），用于输出 final 模型",
    )
    parser.add_argument(
        "--final-model-out",
        default="",
        help="最终模型输出路径（留空则自动生成到 models/final/ 下）",
    )
    parser.add_argument(
        "--apply",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="是否把筛选出的最佳稳定参数写回 strategies/knn_trend_window_strategy.json（默认 true）",
    )
    args = parser.parse_args()

    cwd = PROJECT_ROOT
    env = _uv_env()
    pair = str(args.pair)
    tf = str(args.timeframe)
    years = _parse_list_int(args.years)
    folds = _build_default_folds(years=years, train_start=str(args.train_start), mid_mmdd=str(args.mid_mmdd))
    if not folds:
        raise SystemExit("years 为空，无法生成 folds。")

    variants = [
        Variant(name="base", sell_use_model_exit=False, sell_trend_exit=False),
        Variant(name="model_exit", sell_use_model_exit=True, sell_trend_exit=False),
        Variant(name="trend_exit", sell_use_model_exit=False, sell_trend_exit=True),
        Variant(name="both_exit", sell_use_model_exit=True, sell_trend_exit=True),
    ]

    run_tag = str(args.run_tag).strip()
    if not run_tag:
        run_tag = f"{args.model}_{args.label_mode}_h{args.horizons}_r{args.min_returns}_roi{args.rois}"
    run_slug = re.sub(r"[^0-9a-zA-Z]+", "_", run_tag).strip("_").lower() or "run"

    out_dir = cwd / "backtest_results" / "wf" / run_slug
    out_dir.mkdir(parents=True, exist_ok=True)

    all_results: dict[str, dict[str, list[dict[str, Any]]]] = {}

    for variant in variants:
        all_results[variant.name] = {}
        print("")
        print(f"=== 变体：{variant.name} ===")
        for fold in folds:
            results_out = out_dir / f"knn_tw_wf_{_pair_slug(pair)}_{tf.lower()}_{variant.name}_fold{fold.name}.json"

            cmd: list[str] = [
                "uv",
                "run",
                "python",
                "-X",
                "utf8",
                "scripts/scan_knn_trend_window.py",
                "--datadir",
                str(args.datadir),
                "--pair",
                pair,
                "--timeframe",
                tf,
                "--train-timerange",
                fold.train_timerange,
                "--test-timerange",
                fold.test_timerange,
                "--backtest-timerange",
                fold.backtest_timerange,
                "--horizons",
                str(args.horizons),
                "--min-returns",
                str(args.min_returns),
                "--rois",
                str(args.rois),
                "--label-mode",
                str(args.label_mode),
                "--model",
                str(args.model),
                "--window",
                str(int(args.window)),
                "--neighbors",
                str(int(args.neighbors)),
                "--balance",
                str(args.balance),
                "--adx-min",
                str(float(args.adx_min)),
                "--buy-adx-mins",
                str(args.buy_adx_mins),
                "--buy-proba-mins",
                str(args.buy_proba_mins),
                "--max-hold-mults",
                str(args.max_hold_mults),
                "--loss-cuts",
                str(args.loss_cuts),
                "--min-trades",
                str(int(args.min_trades)),
                "--dd-weight",
                str(float(args.dd_weight)),
                "--results-out",
                str(results_out.as_posix()),
            ]

            cmd.append("--filter-trend" if bool(args.filter_trend) else "--no-filter-trend")
            cmd.append(
                "--include-trend-features"
                if bool(args.include_trend_features)
                else "--no-include-trend-features"
            )
            cmd.append("--buy-require-pred" if bool(args.buy_require_pred) else "--no-buy-require-pred")

            cmd.append("--sell-use-model-exit" if variant.sell_use_model_exit else "--no-sell-use-model-exit")
            cmd.append("--sell-trend-exit" if variant.sell_trend_exit else "--no-sell-trend-exit")
            if variant.sell_trend_exit:
                cmd += [
                    "--trend-exit-confirms",
                    str(args.trend_exit_confirms),
                    "--trend-exit-buffers",
                    str(args.trend_exit_buffers),
                ]
                cmd.append(
                    "--trend-exit-require-model"
                    if bool(args.trend_exit_require_model)
                    else "--no-trend-exit-require-model"
                )

            _run(cmd, cwd=cwd, env=env, timeout_sec=int(args.timeout_sec))
            all_results[variant.name][fold.name] = _read_results(results_out)

    # 聚合：按“支持折数/最差折收益/最大回撤”排序，挑稳健组合
    best_by_variant: dict[str, dict[str, Any] | None] = {}
    aggregated_by_variant: dict[str, list[dict[str, Any]]] = {}
    n_folds = len(folds)

    for variant in variants:
        per_fold = all_results.get(variant.name, {})
        sig_to_metrics: dict[str, dict[str, dict[str, Any]]] = {}

        for fold_name, rows in per_fold.items():
            filtered = [r for r in rows if int(r.get("trades", 0)) >= int(args.min_trades)]
            pool = filtered if filtered else rows
            for r in pool:
                sig = _signature(r)
                sig_key = json.dumps(sig, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
                sig_to_metrics.setdefault(sig_key, {})[fold_name] = {
                    "fold": fold_name,
                    "trades": int(r.get("trades", 0)),
                    "profit_total_pct": float(r.get("profit_total_pct", 0.0)),
                    "max_drawdown_account": float(r.get("max_drawdown_account", 0.0)),
                    "backtest_zip": str(r.get("backtest_zip", "")),
                }

        aggregated: list[dict[str, Any]] = []
        for sig_key, metrics_by_fold in sig_to_metrics.items():
            support = len(metrics_by_fold)
            profits = [float(x["profit_total_pct"]) for x in metrics_by_fold.values()]
            dds = [float(x["max_drawdown_account"]) for x in metrics_by_fold.values()]
            trades = [int(x["trades"]) for x in metrics_by_fold.values()]
            aggregated.append(
                {
                    "variant": variant.name,
                    "support": support,
                    "profit_min": min(profits) if profits else float("nan"),
                    "profit_mean": (sum(profits) / len(profits)) if profits else float("nan"),
                    "dd_max": max(dds) if dds else float("nan"),
                    "trades_min": min(trades) if trades else 0,
                    "params": json.loads(sig_key),
                    "folds": list(metrics_by_fold.values()),
                }
            )

        aggregated.sort(
            key=lambda x: (
                int(x.get("support", 0)),
                float(x.get("profit_min", -1e9)),
                float(x.get("profit_mean", -1e9)),
                -float(x.get("dd_max", 1e9)),
                int(x.get("trades_min", 0)),
            ),
            reverse=True,
        )
        aggregated_by_variant[variant.name] = aggregated

        best = _pick_best_stable(
            aggregated,
            require_folds=n_folds,
            min_trades=int(args.min_trades),
        )
        best_by_variant[variant.name] = best

        print("")
        print(f"=== 聚合结果：{variant.name}（Top 5）===")
        for row in aggregated[:5]:
            p = row["params"]
            print(
                f"- support={row['support']}/{n_folds}  "
                f"profit_min={row['profit_min']:.2f}%  profit_mean={row['profit_mean']:.2f}%  "
                f"dd_max={row['dd_max']:.1%}  trades_min={row['trades_min']}  "
                f"model_exit={p['sell_use_model_exit']}  trend_exit={p['sell_trend_exit']}  "
                f"proba>={p['buy_proba_min']:.2f}  hold_mult={p['max_hold_mult']:.1f}  "
                f"trend_confirm={p['trend_exit_confirm']}  trend_buf={p['trend_exit_buffer']:.3f}"
            )

    # 选择全折稳定且 profit_min>0 的最佳变体
    winners = [x for x in best_by_variant.values() if isinstance(x, dict)]
    winners.sort(
        key=lambda x: (
            float(x.get("profit_min", -1e9)),
            float(x.get("profit_mean", -1e9)),
            -float(x.get("dd_max", 1e9)),
        ),
        reverse=True,
    )
    chosen = winners[0] if winners else None

    print("")
    print("=== 最终选择 ===")
    if not chosen:
        print("未找到“所有折都为正且 trades 足够”的稳定组合。下一步建议：改标签(max_high/波动率自适应)或换周期/扩币对。")
        return 0

    chosen_params = chosen["params"]
    print(
        f"- variant={chosen['variant']}  support={chosen['support']}/{n_folds}  "
        f"profit_min={chosen['profit_min']:.2f}%  profit_mean={chosen['profit_mean']:.2f}%  "
        f"dd_max={chosen['dd_max']:.1%}"
    )

    # 抽样展示该组合在每折的 exit_reason 分布（重点看 stop_loss / time_exit）
    print("")
    print("=== 各折退出结构（trades）===")
    for frow in chosen.get("folds", []):
        zip_name = str(frow.get("backtest_zip", "")).strip()
        zip_path = (cwd / "backtest_results" / zip_name) if zip_name else Path()
        counts = _read_exit_reason_counts(zip_path, strategy_name="KNNTrendWindowStrategy")
        print(
            f"- fold={frow.get('fold')}  profit={float(frow.get('profit_total_pct', 0.0)):.2f}%  "
            f"dd={float(frow.get('max_drawdown_account', 0.0)):.1%}  "
            f"stop_loss={counts.get('stop_loss', 0)}  time_exit={counts.get('time_exit', 0)}  "
            f"trend_break={counts.get('TREND_BREAK', 0)}  model_pred={counts.get('MODEL_PRED', 0)}  "
            f"roi={counts.get('roi', 0)}"
        )

    # 训练最终模型（严格不触碰样本外）
    min_returns = [float(x.strip()) for x in str(args.min_returns).split(",") if x.strip()]
    horizons = _parse_list_int(args.horizons)
    if len(min_returns) != 1 or len(horizons) != 1:
        print("")
        print("⚠️ 当前 horizons/min-returns 不是单值，final 模型输出将无法自动命名，请用 --final-model-out 指定。")
    horizon = int(horizons[0]) if horizons else 6
    min_return = float(min_returns[0]) if min_returns else 0.009

    final_model_out = str(args.final_model_out).strip()
    if not final_model_out:
        tf_slug = tf.lower()
        bp = int(round(min_return * 10000))
        suffix = str(args.model).strip().lower()
        final_model_out = f"models/final/knn_tw_{_pair_slug(pair)}_{tf_slug}_h{horizon}_r{bp:04d}_{suffix}_train{str(args.final_train_timerange).split('-')[0]}_{str(args.final_train_timerange).split('-')[1]}.pkl"

    train_cmd = [
        "uv",
        "run",
        "python",
        "-X",
        "utf8",
        "scripts/train_knn_trend_window.py",
        "--datadir",
        str(args.datadir),
        "--pair",
        pair,
        "--timeframe",
        tf,
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
        str(args.final_train_timerange),
        "--final",
        "--model-out",
        str(Path(final_model_out).as_posix()),
    ]
    if bool(args.filter_trend):
        train_cmd.append("--filter-trend")
    if bool(args.include_trend_features):
        train_cmd.append("--include-trend-features")

    _run(train_cmd, cwd=cwd, env=env, timeout_sec=int(args.timeout_sec))

    if not bool(args.apply):
        print("")
        print("已跳过写回参数文件（--no-apply）。")
        print(f"最终模型：{final_model_out}")
        return 0

    # 写回策略参数文件（只改当前 pair 的覆盖配置，避免污染其它币对）
    param_path = cwd / "strategies" / "knn_trend_window_strategy.json"
    payload = json.loads(param_path.read_text(encoding="utf-8"))
    params = payload.get("params")
    if not isinstance(params, dict):
        params = {}
        payload["params"] = params
    overrides = params.get("pair_overrides")
    if not isinstance(overrides, dict):
        overrides = {}
        params["pair_overrides"] = overrides

    overrides[str(pair)] = {
        "buy_adx_min": int(chosen_params["buy_adx_min"]),
        "buy_proba_min": float(chosen_params["buy_proba_min"]),
        "buy_require_pred": bool(chosen_params["buy_require_pred"]),
        "max_hold_mult": float(chosen_params["max_hold_mult"]),
        "sell_use_model_exit": bool(chosen_params["sell_use_model_exit"]),
        "sell_trend_exit": bool(chosen_params["sell_trend_exit"]),
        "sell_trend_exit_confirm": int(chosen_params["trend_exit_confirm"]),
        "sell_trend_exit_buffer": float(chosen_params["trend_exit_buffer"]),
        "sell_trend_exit_require_model": bool(chosen_params["trend_exit_require_model"]),
        "sell_time_loss_cut": float(chosen_params["loss_cut"]),
        "model_path": str(Path(final_model_out).as_posix()),
    }

    param_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # 输出聚合结果，便于回溯
    summary_path = out_dir / f"knn_tw_wf_{_pair_slug(pair)}_{tf.lower()}_summary.json"
    summary_path.write_text(
        json.dumps(
            {
                "pair": pair,
                "timeframe": tf,
                "folds": [f.__dict__ for f in folds],
                "chosen": chosen,
                "best_by_variant": best_by_variant,
                "top10_by_variant": {
                    k: v[:10] for k, v in aggregated_by_variant.items()
                },
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    print("")
    print("=== 已写回参数文件 ===")
    print(f"- 参数文件: {param_path}")
    print(f"- 最终模型: {final_model_out}")
    print(f"- 聚合摘要: {summary_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
