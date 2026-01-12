"""
backtest_metrics.py - 回测结果关键指标提取

用途：
  - 从 Freqtrade 回测结果 zip 中提取“稳定性评估”所需的关键指标
  - 输出一行 JSON（便于 PowerShell/CI 管道解析）

用法：
  uv run python scripts/analysis/backtest_metrics.py --zip "backtest_results/xxx.zip"
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

# 添加 scripts/lib 到路径
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))

from backtest_utils import pick_strategy_name, read_backtest_zip  # noqa: E402


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="从回测 zip 提取关键指标，输出 JSON。")
    parser.add_argument(
        "--zip",
        required=True,
        help="回测结果 zip 路径，例如 backtest_results/backtest-result-xxx.zip",
    )
    parser.add_argument(
        "--strategy",
        default="",
        help="策略名（留空表示自动取 zip 内唯一策略）。",
    )
    return parser.parse_args()


def _as_float(v: Any, default: float = 0.0) -> float:
    try:
        if v is None:
            return float(default)
        return float(v)
    except Exception:
        return float(default)


def _as_int(v: Any, default: int = 0) -> int:
    try:
        if v is None:
            return int(default)
        return int(v)
    except Exception:
        return int(default)


def main() -> int:
    args = _parse_args()
    zip_path = Path(str(args.zip))
    data, _ = read_backtest_zip(zip_path)

    strategy_name = pick_strategy_name(data, str(args.strategy))
    strat = (data.get("strategy") or {}).get(strategy_name) or {}
    if not strat:
        raise ValueError(f"zip 内未找到策略：{strategy_name}")

    profit_total = _as_float(strat.get("profit_total"))
    winrate = _as_float(strat.get("winrate"))
    market_change = _as_float(strat.get("market_change"))

    # max_relative_drawdown 在新版本里更稳定；没有则回退到 max_drawdown_account
    mdd = _as_float(strat.get("max_relative_drawdown"))
    if mdd <= 0:
        mdd = _as_float(strat.get("max_drawdown_account"))

    out = {
        "zip": zip_path.as_posix(),
        "zip_name": zip_path.name,
        "strategy": strategy_name,
        "timerange": str(strat.get("timerange") or "").strip(),
        "timeframe": str(strat.get("timeframe") or "").strip(),
        "backtest_start": str(strat.get("backtest_start") or "").strip(),
        "backtest_end": str(strat.get("backtest_end") or "").strip(),
        "starting_balance": _as_float(strat.get("starting_balance")),
        "final_balance": _as_float(strat.get("final_balance")),
        "max_open_trades": _as_int(strat.get("max_open_trades")),
        "total_trades": _as_int(strat.get("total_trades")),
        "profit_total": profit_total,
        "profit_total_pct": profit_total * 100.0,
        "profit_total_abs": _as_float(strat.get("profit_total_abs")),
        "profit_factor": _as_float(strat.get("profit_factor")),
        "winrate": winrate,
        "winrate_pct": winrate * 100.0,
        "max_relative_drawdown": mdd,
        "max_relative_drawdown_pct": mdd * 100.0,
        "sharpe": _as_float(strat.get("sharpe")),
        "sortino": _as_float(strat.get("sortino")),
        "calmar": _as_float(strat.get("calmar")),
        "market_change": market_change,
        "market_change_pct": market_change * 100.0,
    }

    print(json.dumps(out, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

