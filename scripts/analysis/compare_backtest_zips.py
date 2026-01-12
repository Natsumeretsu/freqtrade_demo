"""
compare_backtest_zips.py - 对比两份 Freqtrade 回测结果 zip（逐笔交易 + 关键指标）

用途：
  - 当你觉得“资金曲线看起来没区别”时，用可复现的方式量化差异：
    - 核心指标（收益/回撤/交易数/胜率/ProfitFactor 等）
    - time-in-market（持仓时间占比）
    - exit_reason 分布
    - 逐笔交易差异（按 pair + open_timestamp 匹配）

用法：
  uv run python -X utf8 scripts/analysis/compare_backtest_zips.py \
    --left-zip "backtest_results/xxx.zip" \
    --right-zip "backtest_results/yyy.zip" \
    --strategy "YourStrategy" \
    --out-md "artifacts/benchmarks/compare.md"
"""

from __future__ import annotations

import argparse
import math
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

# 添加 scripts/lib 到路径
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))

from backtest_utils import pick_strategy_name, read_backtest_zip  # noqa: E402


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="对比两份回测 zip，输出 Markdown（到 stdout 或文件）。")
    parser.add_argument("--left-zip", required=True, help="左侧（旧）回测 zip 路径。")
    parser.add_argument("--right-zip", required=True, help="右侧（新）回测 zip 路径。")
    parser.add_argument("--strategy", default="", help="策略名（留空表示自动取 zip 内唯一策略）。")
    parser.add_argument(
        "--float-tol",
        type=float,
        default=1e-9,
        help="浮点差异阈值（profit_ratio 等），避免微小数值误差导致误判。",
    )
    parser.add_argument(
        "--max-items",
        type=int,
        default=20,
        help="最多输出多少条差异交易（added/removed/changed 合计）。",
    )
    parser.add_argument("--out-md", default="", help="输出 Markdown 路径（留空则打印到 stdout）。")
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


def _pct(x: float) -> float:
    return float(x) * 100.0


def _fmt_pct(v: float) -> str:
    if not math.isfinite(v):
        return ""
    return f"{v:.4f}%"


def _fmt_signed_pct(v: float) -> str:
    if not math.isfinite(v):
        return ""
    return f"{v:+.4f}%"


def _fmt_float(v: float) -> str:
    if not math.isfinite(v):
        return ""
    return f"{v:.6f}"


def _safe_str(v: Any) -> str:
    return str(v or "").strip()


def _time_in_market_pct(strategy_data: dict) -> float:
    start = pd.to_datetime(strategy_data.get("backtest_start"), utc=True, errors="coerce")
    end = pd.to_datetime(strategy_data.get("backtest_end"), utc=True, errors="coerce")
    if pd.isna(start) or pd.isna(end) or end <= start:
        return float("nan")

    total_min = (end - start).total_seconds() / 60.0
    if total_min <= 0:
        return float("nan")

    dur_min = 0.0
    for t in strategy_data.get("trades") or []:
        dur_min += _as_float((t or {}).get("trade_duration"), 0.0)

    return float(dur_min / total_min * 100.0)


@dataclass(frozen=True)
class ZipView:
    zip_path: Path
    strategy_name: str
    strategy_data: dict
    trades: list[dict]

    @property
    def timerange(self) -> str:
        return _safe_str(self.strategy_data.get("timerange"))

    @property
    def timeframe(self) -> str:
        return _safe_str(self.strategy_data.get("timeframe"))

    def metric_profit_total_pct(self) -> float:
        return _pct(_as_float(self.strategy_data.get("profit_total")))

    def metric_max_dd_pct(self) -> float:
        # max_relative_drawdown 在新版本里更稳定；没有则回退
        mdd = _as_float(self.strategy_data.get("max_relative_drawdown"))
        if mdd <= 0:
            mdd = _as_float(self.strategy_data.get("max_drawdown_account"))
        return _pct(float(mdd))

    def metric_total_trades(self) -> int:
        return _as_int(self.strategy_data.get("total_trades"))

    def metric_winrate_pct(self) -> float:
        return _pct(_as_float(self.strategy_data.get("winrate")))

    def metric_profit_factor(self) -> float:
        return _as_float(self.strategy_data.get("profit_factor"), float("nan"))

    def metric_sharpe(self) -> float:
        return _as_float(self.strategy_data.get("sharpe"), float("nan"))

    def metric_sortino(self) -> float:
        return _as_float(self.strategy_data.get("sortino"), float("nan"))

    def metric_calmar(self) -> float:
        return _as_float(self.strategy_data.get("calmar"), float("nan"))

    def metric_time_in_market_pct(self) -> float:
        return _time_in_market_pct(self.strategy_data)

    def exit_reason_counter(self) -> Counter[str]:
        c: Counter[str] = Counter()
        for t in self.trades:
            c[_safe_str(t.get("exit_reason"))] += 1
        return c

    def trade_index(self) -> dict[tuple[str, int], dict]:
        out: dict[tuple[str, int], dict] = {}
        for t in self.trades:
            pair = _safe_str(t.get("pair"))
            open_ts = _as_int(t.get("open_timestamp"))
            out[(pair, open_ts)] = t
        return out


def _load_zip(zip_path: Path, requested_strategy: str) -> ZipView:
    data, _ = read_backtest_zip(zip_path)
    strategy_name = pick_strategy_name(data, requested_strategy)
    strat = (data.get("strategy") or {}).get(strategy_name) or {}
    if not strat:
        raise ValueError(f"zip 内未找到策略：{strategy_name}")

    trades = [t for t in (strat.get("trades") or []) if isinstance(t, dict)]
    return ZipView(zip_path=zip_path, strategy_name=strategy_name, strategy_data=strat, trades=trades)


def _trade_brief(t: dict) -> str:
    open_date = _safe_str(t.get("open_date"))
    close_date = _safe_str(t.get("close_date"))
    exit_reason = _safe_str(t.get("exit_reason"))
    enter_tag = _safe_str(t.get("enter_tag"))
    pr = _as_float(t.get("profit_ratio"))
    dur = _as_int(t.get("trade_duration"))
    return (
        f"- open={open_date} close={close_date} "
        f"profit_ratio={pr:+.6f} exit_reason={exit_reason} "
        f"duration_min={dur} enter_tag={enter_tag}"
    )


def _render_metrics(name: str, v: ZipView) -> list[str]:
    return [
        f"- {name}.zip: `{v.zip_path.as_posix()}`",
        f"- {name}.timerange: {v.timerange}",
        f"- {name}.timeframe: {v.timeframe}",
        f"- {name}.total_trades: {v.metric_total_trades()}",
        f"- {name}.profit_total_pct: {_fmt_pct(v.metric_profit_total_pct())}",
        f"- {name}.max_drawdown_pct: {_fmt_pct(v.metric_max_dd_pct())}",
        f"- {name}.winrate_pct: {_fmt_pct(v.metric_winrate_pct())}",
        f"- {name}.profit_factor: {_fmt_float(v.metric_profit_factor())}",
        f"- {name}.sharpe/sortino/calmar: {_fmt_float(v.metric_sharpe())} / {_fmt_float(v.metric_sortino())} / {_fmt_float(v.metric_calmar())}",
        f"- {name}.time_in_market_pct: {_fmt_pct(v.metric_time_in_market_pct())}",
    ]


def _render_delta(left: ZipView, right: ZipView) -> list[str]:
    return [
        f"- Δ.total_trades: {right.metric_total_trades() - left.metric_total_trades():+d}",
        f"- Δ.profit_total_pct: {_fmt_signed_pct(right.metric_profit_total_pct() - left.metric_profit_total_pct())}",
        f"- Δ.max_drawdown_pct: {_fmt_signed_pct(right.metric_max_dd_pct() - left.metric_max_dd_pct())}",
        f"- Δ.winrate_pct: {_fmt_signed_pct(right.metric_winrate_pct() - left.metric_winrate_pct())}",
        f"- Δ.time_in_market_pct: {_fmt_signed_pct(right.metric_time_in_market_pct() - left.metric_time_in_market_pct())}",
    ]


def _render_exit_reasons(name: str, v: ZipView) -> list[str]:
    c = v.exit_reason_counter()
    if not c:
        return [f"- {name}.exit_reason: (empty)"]
    parts = [f"{k or '(empty)'}={c[k]}" for k in sorted(c.keys())]
    return [f"- {name}.exit_reason: " + ", ".join(parts)]


def _diff_trades(
    *,
    left: ZipView,
    right: ZipView,
    float_tol: float,
) -> tuple[list[tuple[tuple[str, int], dict]], list[tuple[tuple[str, int], dict]], list[tuple[tuple[str, int], dict, dict]]]:
    li = left.trade_index()
    ri = right.trade_index()
    keys = sorted(set(li) | set(ri), key=lambda k: (k[0] or "", k[1]))

    added: list[tuple[tuple[str, int], dict]] = []
    removed: list[tuple[tuple[str, int], dict]] = []
    changed: list[tuple[tuple[str, int], dict, dict]] = []

    tol = float(float_tol)
    for k in keys:
        if k not in li:
            added.append((k, ri[k]))
            continue
        if k not in ri:
            removed.append((k, li[k]))
            continue

        a = li[k]
        b = ri[k]
        if (
            _as_int(a.get("close_timestamp")) != _as_int(b.get("close_timestamp"))
            or _safe_str(a.get("exit_reason")) != _safe_str(b.get("exit_reason"))
            or abs(_as_float(a.get("profit_ratio")) - _as_float(b.get("profit_ratio"))) > tol
        ):
            changed.append((k, a, b))

    return added, removed, changed


def main() -> int:
    args = _parse_args()
    left_zip = Path(str(args.left_zip))
    right_zip = Path(str(args.right_zip))
    out_md = Path(str(args.out_md)) if str(args.out_md).strip() else None

    left = _load_zip(left_zip, str(args.strategy))
    right = _load_zip(right_zip, str(args.strategy))
    if left.strategy_name != right.strategy_name:
        raise ValueError(f"两份 zip 策略名不一致：left={left.strategy_name} right={right.strategy_name}")

    added, removed, changed = _diff_trades(left=left, right=right, float_tol=float(args.float_tol))

    max_items = int(args.max_items)
    if max_items <= 0:
        max_items = 0

    lines: list[str] = []
    lines += [f"# 回测 zip 对比：{left.strategy_name}", ""]
    lines += ["## 元信息", ""]
    lines += [f"- left: `{left.zip_path.as_posix()}`", f"- right: `{right.zip_path.as_posix()}`", ""]

    if left.timerange and right.timerange and left.timerange == right.timerange:
        lines += [f"- timerange: {left.timerange}"]
    if left.timeframe and right.timeframe and left.timeframe == right.timeframe:
        lines += [f"- timeframe: {left.timeframe}"]
    lines += [""]

    lines += ["## 指标对比", ""]
    lines += ["### Left（旧）", ""]
    lines += _render_metrics("left", left)
    lines += ["", "### Right（新）", ""]
    lines += _render_metrics("right", right)
    lines += ["", "### Delta（新-旧）", ""]
    lines += _render_delta(left, right)
    lines += [""]

    lines += ["## 出场原因分布（exit_reason）", ""]
    lines += _render_exit_reasons("left", left)
    lines += _render_exit_reasons("right", right)
    lines += [""]

    lines += ["## 逐笔交易差异（按 pair + open_timestamp 匹配）", ""]
    lines += [f"- added: {len(added)}", f"- removed: {len(removed)}", f"- changed: {len(changed)}", ""]

    shown = 0
    if max_items > 0:
        if added:
            lines += ["### Added（仅 right 存在）", ""]
            for _, t in added:
                if shown >= max_items:
                    break
                lines.append(_trade_brief(t))
                shown += 1
            lines += [""]

        if removed and shown < max_items:
            lines += ["### Removed（仅 left 存在）", ""]
            for _, t in removed:
                if shown >= max_items:
                    break
                lines.append(_trade_brief(t))
                shown += 1
            lines += [""]

        if changed and shown < max_items:
            lines += ["### Changed（left vs right）", ""]
            for _, a, b in changed:
                if shown >= max_items:
                    break
                lines += ["- left:", _trade_brief(a), "- right:", _trade_brief(b), ""]
                shown += 1

    out_text = "\n".join(lines).rstrip() + "\n"
    if out_md is None:
        print(out_text)
    else:
        out_md.parent.mkdir(parents=True, exist_ok=True)
        out_md.write_text(out_text, encoding="utf-8")
        print(f"已写入：{out_md.as_posix()}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

