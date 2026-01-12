"""
capacity_snapshot.py - 交易对容量（流动性/滑点）快照

用途：
  - 从交易所实时订单簿抓取深度，估算“在给定滑点（bps）以内可成交的名义金额（USDT）”。
  - 用于把“策略容量”从抽象概念落到可核验数字（注意：这是实时快照，不代表历史分布）。

示例：
  uv run python -X utf8 scripts/analysis/capacity_snapshot.py --pair "BTC/USDT" --limit 400 --bps "5,10,20,50"
"""

from __future__ import annotations

import argparse
from typing import Iterable

import ccxt  # type: ignore


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "交易对容量快照（订单簿深度）\n"
            "- 输出：在不同滑点(bps)以内的买入/卖出名义金额(USDT)\n"
            "- 说明：这是“当前时刻”的快照，不等价于历史统计容量\n"
        )
    )
    parser.add_argument("--pair", default="BTC/USDT", help='交易对，例如 "BTC/USDT"。')
    parser.add_argument("--limit", type=int, default=400, help="订单簿档位数量（越大越慢）。")
    parser.add_argument(
        "--bps",
        default="5,10,20,50",
        help='滑点阈值（bps，逗号分隔），例如 "5,10,20,50" 表示 0.05%/0.10%/0.20%/0.50%。',
    )
    return parser.parse_args()


def _parse_bps_list(raw: str) -> list[int]:
    out: list[int] = []
    for part in (raw or "").split(","):
        part = part.strip()
        if not part:
            continue
        out.append(int(part))
    if not out:
        raise ValueError("bps 不能为空")
    return out


def _depth_notional(levels: Iterable[list[float]], *, ref_price: float, slip_ratio: float, side: str) -> float:
    if ref_price <= 0:
        return 0.0
    slip_ratio = float(slip_ratio)
    if slip_ratio < 0:
        return 0.0

    total = 0.0
    if side == "buy":
        max_price = ref_price * (1.0 + slip_ratio)
        for row in levels:
            px = float(row[0])
            qty = float(row[1])
            if px > max_price:
                break
            total += px * qty
    else:
        min_price = ref_price * (1.0 - slip_ratio)
        for row in levels:
            px = float(row[0])
            qty = float(row[1])
            if px < min_price:
                break
            total += px * qty
    return total


def main() -> int:
    args = _parse_args()
    pair = str(args.pair).strip()
    limit = int(args.limit)
    bps_list = _parse_bps_list(str(args.bps))

    ex = ccxt.okx({"enableRateLimit": True})
    ob = ex.fetch_order_book(pair, limit=limit)
    asks = ob.get("asks") or []
    bids = ob.get("bids") or []
    if not asks or not bids:
        raise ValueError("订单簿为空或拉取失败")

    # OKX/ccxt: [price, amount, count]，这里只取前两列
    best_ask = float(asks[0][0])
    best_bid = float(bids[0][0])
    mid = (best_ask + best_bid) / 2.0
    spread_bps = ((best_ask - best_bid) / mid * 10000.0) if mid > 0 else float("nan")

    print("=== 容量快照（订单簿）===")
    print(f"- pair: {pair}")
    print(f"- levels: bids={len(bids)} asks={len(asks)} (limit={limit})")
    print(f"- best_bid: {best_bid}")
    print(f"- best_ask: {best_ask}")
    print(f"- spread_bps: {spread_bps:.2f}")

    for bps in bps_list:
        slip = float(bps) / 10000.0
        buy = _depth_notional(asks, ref_price=best_ask, slip_ratio=slip, side="buy")
        sell = _depth_notional(bids, ref_price=best_bid, slip_ratio=slip, side="sell")
        print(f"- depth_within_{bps}bps: buy_notional_usdt={buy:,.0f} sell_notional_usdt={sell:,.0f}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

