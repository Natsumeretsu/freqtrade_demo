"""
stress_test.py - 回测结果压力测试

基于历史交易记录进行蒙特卡洛模拟，评估策略在不同交易顺序下的风险。

用法:
    uv run python scripts/analysis/stress_test.py --help
"""
from __future__ import annotations

import argparse
import json
import math
import random
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np

# 添加 scripts/lib 到路径
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))

from backtest_utils import pick_strategy_name, read_backtest_zip_with_config


@dataclass(frozen=True)
class TradePnl:
    profit_abs: float
    profit_ratio: float
    stake_amount: float


@dataclass(frozen=True)
class TradePolicy:
    profit_ratio: float
    stake_fraction: float


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "压力测试：对 Freqtrade 回测结果做参数敏感性/蒙特卡洛（交易序列洗牌）\n"
            "- 适用：评估“运气好/坏”对回撤与最终收益的影响\n"
            "- 输入：01_freqtrade/backtest_results/*.zip（Freqtrade 回测输出）\n"
        )
    )
    parser.add_argument(
        "--zip",
        required=True,
        help="回测结果 zip 路径，例如 01_freqtrade/backtest_results/backtest-result-xxx.zip",
    )
    parser.add_argument(
        "--strategy",
        default="",
        help="策略名（留空表示自动取 zip 内唯一策略）。",
    )
    parser.add_argument(
        "--simulations",
        type=int,
        default=5000,
        help="蒙特卡洛次数（建议 2000-20000，越大越稳但越慢）。",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="随机种子（保证结果可复现）。",
    )
    parser.add_argument(
        "--mode",
        choices=["abs", "ratio", "policy"],
        default="abs",
        help=(
            "模拟模式："
            "abs=按 profit_abs 加总（更贴近回测记录，但忽略复利/动态仓位）；"
            "ratio=按 profit_ratio 复利（需要 stake_fraction 假设）；"
            "policy=按“每笔实际 stake_fraction”复利（从回测交易记录推导，更适合动态仓位）。"
        ),
    )
    parser.add_argument(
        "--stake-fraction",
        type=float,
        default=-1.0,
        help=(
            "仅 ratio 模式使用：每笔交易使用资金占比（0-1）。"
            "默认自动从回测 config 读取 tradable_balance_ratio（若不存在则 0.95）。"
        ),
    )
    parser.add_argument(
        "--slippage",
        type=float,
        default=0.0,
        help=(
            "滑点假设（单边比例，例如 0.0005=0.05%%）。"
            "会近似从每笔交易 profit_ratio 扣除 2*slippage（买入+卖出）。"
        ),
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="以 JSON 一行输出摘要，便于脚本/CI 解析。",
    )
    return parser.parse_args()


def _extract_trades(data: dict, strategy_name: str) -> tuple[float, list[TradePnl]]:
    strat = (data.get("strategy") or {}).get(strategy_name) or {}
    starting_balance = float(strat.get("starting_balance", 0.0))
    trades = strat.get("trades") or []
    pnl_list: list[TradePnl] = []
    for t in trades:
        try:
            pnl_list.append(
                TradePnl(
                    profit_abs=float(t.get("profit_abs", 0.0)),
                    profit_ratio=float(t.get("profit_ratio", 0.0)),
                    stake_amount=float(t.get("stake_amount", 0.0)),
                )
            )
        except (TypeError, ValueError):
            continue
    if starting_balance <= 0:
        raise ValueError("回测结果缺少 starting_balance，无法做资金曲线模拟")
    if not pnl_list:
        raise ValueError("回测结果未包含 trades 列表，无法做蒙特卡洛")
    return starting_balance, pnl_list


def _resolve_stake_fraction(config: dict, user_value: float) -> float:
    if user_value is not None and float(user_value) > 0:
        return float(user_value)
    try:
        tradable = float(config.get("tradable_balance_ratio", 0.95))
        max_open_trades = int(config.get("max_open_trades", 0) or 0)
        stake_amount = str(config.get("stake_amount", "")).strip().lower()

        # Freqtrade 常见配置：stake_amount=unlimited 时，会按 max_open_trades 做等额分配
        # 这里用 tradable_balance_ratio/max_open_trades 近似每笔交易的资金占比。
        if stake_amount == "unlimited" and max_open_trades > 0:
            return float(tradable / max_open_trades)

        return float(tradable)
    except (TypeError, ValueError):
        return 0.95


def _derive_trade_policy(starting_balance: float, pnls: list[TradePnl]) -> list[TradePolicy]:
    """
    从历史交易序列推导“每笔 stake_fraction（相对账户权益的资金占比）”。

    思路：
    - 历史顺序下，回测记录里包含 stake_amount 与 profit_abs
    - 可用 profit_abs 递推还原每笔交易前的权益 equity_before
    - stake_fraction = stake_amount / equity_before

    该 stake_fraction 近似代表“策略的仓位政策”，用于蒙特卡洛洗牌时更贴近动态仓位行为。
    """
    equity = float(starting_balance)
    out: list[TradePolicy] = []
    for p in pnls:
        if not np.isfinite(equity) or equity <= 0:
            break

        stake_amount = float(p.stake_amount)
        frac = stake_amount / equity if equity > 0 else 0.0
        if not np.isfinite(frac) or frac <= 0:
            # 兜底：异常值直接当作“该笔不参与”
            equity += float(p.profit_abs)
            continue

        frac = float(max(0.0, min(1.0, frac)))
        out.append(TradePolicy(profit_ratio=float(p.profit_ratio), stake_fraction=frac))

        equity += float(p.profit_abs)

    if not out:
        raise ValueError("无法推导 policy stake_fraction（交易记录缺失或权益递推失败）")
    return out


def _apply_slippage(pnls: list[TradePnl], slippage: float) -> list[TradePnl]:
    slip = float(slippage)
    if slip <= 0:
        return pnls

    fee_like = 2.0 * slip
    out: list[TradePnl] = []
    for p in pnls:
        adj_ratio = float(p.profit_ratio) - fee_like
        adj_abs = float(p.profit_abs) - float(p.stake_amount) * fee_like
        out.append(TradePnl(profit_abs=adj_abs, profit_ratio=adj_ratio, stake_amount=p.stake_amount))
    return out


def _max_drawdown(equity_curve: list[float]) -> float:
    peak = -math.inf
    mdd = 0.0
    for v in equity_curve:
        if v > peak:
            peak = v
        if peak > 0:
            dd = (v - peak) / peak
            if dd < mdd:
                mdd = dd
    return float(mdd)


def _simulate_abs(starting_balance: float, pnls: list[TradePnl]) -> tuple[float, float]:
    equity = float(starting_balance)
    curve = [equity]
    for p in pnls:
        equity += float(p.profit_abs)
        curve.append(equity)
    return float(equity), _max_drawdown(curve)


def _simulate_ratio(
    starting_balance: float,
    pnls: list[TradePnl],
    stake_fraction: float,
) -> tuple[float, float]:
    equity = float(starting_balance)
    curve = [equity]
    frac = float(stake_fraction)
    if frac <= 0 or frac > 1:
        raise ValueError("stake_fraction 必须在 (0, 1] 区间内")

    for p in pnls:
        stake = equity * frac
        equity += stake * float(p.profit_ratio)
        curve.append(equity)
        if equity <= 0:
            break
    return float(equity), _max_drawdown(curve)


def _simulate_policy(
    starting_balance: float,
    policies: list[TradePolicy],
) -> tuple[float, float]:
    equity = float(starting_balance)
    curve = [equity]

    for p in policies:
        frac = float(p.stake_fraction)
        if frac <= 0 or frac > 1 or not np.isfinite(frac):
            continue

        stake = equity * frac
        equity += stake * float(p.profit_ratio)
        curve.append(equity)
        if equity <= 0:
            break

    return float(equity), _max_drawdown(curve)


def main() -> int:
    args = _parse_args()
    zip_path = Path(str(args.zip))
    data, config = read_backtest_zip_with_config(zip_path)
    strategy_name = pick_strategy_name(data, str(args.strategy))
    starting_balance, pnls_raw = _extract_trades(data, strategy_name)

    pnls = _apply_slippage(pnls_raw, float(args.slippage))

    mode = str(args.mode).strip().lower()
    stake_fraction = _resolve_stake_fraction(config, float(args.stake_fraction))

    # 不同模式下的“可洗牌序列”
    if mode == "abs":
        seq_any: list = list(pnls)
        simulate = lambda seq: _simulate_abs(starting_balance, seq)  # noqa: E731
    elif mode == "ratio":
        seq_any = list(pnls)
        simulate = lambda seq: _simulate_ratio(starting_balance, seq, stake_fraction)  # noqa: E731
    else:
        policy = _derive_trade_policy(starting_balance, pnls)
        seq_any = list(policy)
        simulate = lambda seq: _simulate_policy(starting_balance, seq)  # noqa: E731

    # 原始顺序（历史路径）
    orig_final, orig_mdd = simulate(seq_any)

    # 蒙特卡洛：洗牌交易序列，重构“平行宇宙”
    rng = random.Random(int(args.seed))
    sims = int(args.simulations)
    if sims <= 0:
        raise ValueError("simulations 必须为正整数")

    finals: list[float] = []
    mdds: list[float] = []
    seq = list(seq_any)
    for _ in range(sims):
        rng.shuffle(seq)
        fin, mdd = simulate(seq)
        finals.append(fin)
        mdds.append(mdd)

    final_p5 = float(np.percentile(finals, 5))
    final_p50 = float(np.percentile(finals, 50))
    final_p95 = float(np.percentile(finals, 95))
    mdd_p5 = float(np.percentile(mdds, 5))  # 更差（更负）的尾部
    mdd_p50 = float(np.percentile(mdds, 50))
    mdd_p95 = float(np.percentile(mdds, 95))

    if bool(args.json):
        out: dict[str, object] = {
            "zip": zip_path.as_posix(),
            "strategy": strategy_name,
            "trades": int(len(seq_any)),
            "mode": mode,
            "simulations": int(sims),
            "seed": int(args.seed),
            "slippage_one_way": float(args.slippage),
            "starting_balance": float(starting_balance),
            "orig_final_balance": float(orig_final),
            "orig_profit_ratio": float(orig_final / starting_balance - 1.0),
            "orig_max_drawdown": float(orig_mdd),
            "final_balance_p05": float(final_p5),
            "final_balance_p50": float(final_p50),
            "final_balance_p95": float(final_p95),
            "profit_ratio_p05": float(final_p5 / starting_balance - 1.0),
            "profit_ratio_p50": float(final_p50 / starting_balance - 1.0),
            "profit_ratio_p95": float(final_p95 / starting_balance - 1.0),
            "max_drawdown_p05": float(mdd_p5),
            "max_drawdown_p50": float(mdd_p50),
            "max_drawdown_p95": float(mdd_p95),
        }

        if mode == "ratio":
            out["stake_fraction"] = float(stake_fraction)
        if mode == "policy":
            fracs = [float(x.stake_fraction) for x in seq_any if np.isfinite(float(x.stake_fraction))]
            if fracs:
                out["stake_fraction_policy_min"] = float(np.min(fracs))
                out["stake_fraction_policy_p50"] = float(np.median(fracs))
                out["stake_fraction_policy_mean"] = float(np.mean(fracs))
                out["stake_fraction_policy_max"] = float(np.max(fracs))

        print(json.dumps(out, ensure_ascii=False))
        return 0

    print("")
    print("=== 压力测试摘要 ===")
    print(f"- zip: {zip_path.as_posix()}")
    print(f"- strategy: {strategy_name}")
    print(f"- trades: {len(seq_any)}")
    print(f"- mode: {mode}")
    if mode == "ratio":
        print(f"- stake_fraction: {stake_fraction:.3f}")
    if mode == "policy":
        fracs = [float(x.stake_fraction) for x in seq_any if np.isfinite(float(x.stake_fraction))]
        if fracs:
            print(
                f"- stake_fraction(policy) min/p50/mean/max: "
                f"{float(np.min(fracs)):.3f} / {float(np.median(fracs)):.3f} / {float(np.mean(fracs)):.3f} / {float(np.max(fracs)):.3f}"
            )
    print(f"- slippage(one-way): {float(args.slippage):.4f}")
    print("")
    print("【历史路径】")
    print(f"- final_balance: {orig_final:.6f}  (profit={orig_final/starting_balance-1:.2%})")
    print(f"- max_drawdown: {orig_mdd:.2%}")
    print("")
    print(f"【蒙特卡洛】simulations={sims} seed={int(args.seed)}")
    if abs(final_p95 - final_p5) < 1e-12:
        print(
            f"- final_balance: {final_p50:.6f}  (profit={(final_p50/starting_balance-1):.2%})"
            "  # 洗牌不改变总盈亏，主要看回撤分布"
        )
    else:
        print(f"- final_balance p05/p50/p95: {final_p5:.6f} / {final_p50:.6f} / {final_p95:.6f}")
        print(
            f"  profit p05/p50/p95: {(final_p5/starting_balance-1):.2%} / {(final_p50/starting_balance-1):.2%} / {(final_p95/starting_balance-1):.2%}"
        )
    print(f"- max_drawdown p05/p50/p95: {mdd_p5:.2%} / {mdd_p50:.2%} / {mdd_p95:.2%}")
    print("")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
