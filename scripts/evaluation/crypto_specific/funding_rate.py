"""
资金费率回测逻辑 - 估算持仓成本对收益的影响

用途：
1. 计算期货合约的资金费率成本
2. 评估持仓时间对收益的影响
3. 识别高费率期间的额外成本

背景：
- OKX 永续合约每 8 小时收取一次资金费率
- 费率时间：00:00 UTC、08:00 UTC、16:00 UTC
- 费率范围：通常在 -0.05% 到 +0.05% 之间
- 多头持仓支付正费率，空头持仓收取正费率

使用方法：
    uv run python scripts/evaluation/funding_rate_analysis.py --zip <回测结果.zip>
"""

import argparse
import json
import sys
import zipfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


def read_backtest_zip(zip_path: Path) -> dict[str, Any]:
    """读取回测结果zip文件"""
    if not zip_path.is_file():
        raise FileNotFoundError(f"未找到zip文件: {zip_path}")

    json_name = zip_path.with_suffix(".json").name
    with zipfile.ZipFile(zip_path) as zf:
        data = json.loads(zf.read(json_name))
    return data


def pick_strategy(data: dict, requested: str = "") -> tuple[str, dict]:
    """选择策略并返回策略数据"""
    strategies = data.get("strategy", {})

    if requested:
        if requested not in strategies:
            raise ValueError(f"未找到策略: {requested}")
        return requested, strategies[requested]

    if len(strategies) != 1:
        raise ValueError(f"zip包含{len(strategies)}个策略，请用--strategy指定")

    name = list(strategies.keys())[0]
    return name, strategies[name]


def safe_float(value: Any, default: float = 0.0) -> float:
    """安全转换为float"""
    try:
        return float(value) if value is not None else default
    except (TypeError, ValueError):
        return default


# ============================================================================
# 资金费率计算
# ============================================================================


def get_funding_times(start_date: datetime, end_date: datetime) -> list[datetime]:
    """
    获取指定时间范围内的所有资金费率时间点

    资金费率时间：每天 00:00、08:00、16:00 UTC
    """
    funding_times = []
    current = start_date.replace(hour=0, minute=0, second=0, microsecond=0)

    # 找到第一个资金费率时间点
    hours = [0, 8, 16]
    while current < start_date:
        for hour in hours:
            test_time = current.replace(hour=hour)
            if test_time >= start_date:
                current = test_time
                break
        else:
            current += timedelta(days=1)
            current = current.replace(hour=0)

    # 生成所有资金费率时间点
    while current <= end_date:
        funding_times.append(current)
        # 下一个时间点
        if current.hour == 0:
            current = current.replace(hour=8)
        elif current.hour == 8:
            current = current.replace(hour=16)
        else:  # 16:00
            current = current.replace(hour=0) + timedelta(days=1)

    return funding_times


def calculate_funding_cost(
    trades: list[dict],
    avg_funding_rate: float = 0.0001,  # 默认 0.01% (年化约 10%)
    funding_rate_std: float = 0.0002,  # 标准差 0.02%
) -> dict[str, Any]:
    """
    计算资金费率成本

    参数：
        trades: 交易列表
        avg_funding_rate: 平均资金费率（默认 0.01%）
        funding_rate_std: 资金费率标准差（默认 0.02%）

    返回：
        包含资金费率分析结果的字典
    """
    if not trades:
        return {"error": "无交易数据"}

    results = []
    total_funding_cost = 0.0
    total_long_cost = 0.0
    total_short_cost = 0.0

    for t in trades:
        open_date = pd.to_datetime(t.get("open_date", ""))
        close_date = pd.to_datetime(t.get("close_date", ""))
        stake = safe_float(t.get("stake_amount", 0))
        is_short = t.get("is_short", False)

        # 获取持仓期间的所有资金费率时间点
        funding_times = get_funding_times(open_date, close_date)

        # 计算每个时间点的资金费率成本
        # 简化模型：使用正态分布模拟费率波动
        funding_costs = []
        for _ in funding_times:
            # 模拟资金费率（正态分布）
            rate = np.random.normal(avg_funding_rate, funding_rate_std)

            # 多头支付正费率，空头收取正费率
            if is_short:
                cost = -stake * rate  # 空头收取费率（负成本）
            else:
                cost = stake * rate   # 多头支付费率（正成本）

            funding_costs.append(cost)

        trade_funding_cost = sum(funding_costs)
        total_funding_cost += trade_funding_cost

        if is_short:
            total_short_cost += trade_funding_cost
        else:
            total_long_cost += trade_funding_cost

        results.append({
            "pair": t.get("pair", ""),
            "open_date": str(open_date),
            "close_date": str(close_date),
            "is_short": is_short,
            "stake": stake,
            "funding_periods": len(funding_times),
            "funding_cost": trade_funding_cost,
        })

    # 统计
    long_trades = [r for r in results if not r["is_short"]]
    short_trades = [r for r in results if r["is_short"]]

    return {
        "avg_funding_rate_pct": avg_funding_rate * 100,
        "funding_rate_std_pct": funding_rate_std * 100,
        "total_trades": len(trades),
        "long_trades": len(long_trades),
        "short_trades": len(short_trades),
        "total_funding_cost": total_funding_cost,
        "total_long_cost": total_long_cost,
        "total_short_cost": total_short_cost,
        "avg_funding_cost_per_trade": total_funding_cost / len(trades) if trades else 0,
        "avg_funding_periods": np.mean([r["funding_periods"] for r in results]) if results else 0,
        "max_funding_periods": max([r["funding_periods"] for r in results]) if results else 0,
        "trades": results,
    }


# ============================================================================
# 输出格式化
# ============================================================================


def print_funding_report(
    strategy_name: str,
    strategy_data: dict,
    funding_result: dict,
) -> None:
    """打印资金费率报告"""
    print("\n" + "=" * 80)
    print("资金费率分析报告")
    print("=" * 80)

    print(f"\n策略: {strategy_name}")
    print(f"时间范围: {strategy_data.get('timerange', 'N/A')}")
    print(f"时间周期: {strategy_data.get('timeframe', 'N/A')}")

    print(f"\n【参数设置】")
    print(f"  平均资金费率: {funding_result['avg_funding_rate_pct']:.3f}%")
    print(f"  费率标准差: {funding_result['funding_rate_std_pct']:.3f}%")
    print(f"  年化费率: {funding_result['avg_funding_rate_pct'] * 3 * 365:.1f}%")

    print(f"\n【交易统计】")
    print(f"  总交易笔数: {funding_result['total_trades']}")
    print(f"  多头交易: {funding_result['long_trades']}")
    print(f"  空头交易: {funding_result['short_trades']}")

    print(f"\n【持仓时间】")
    print(f"  平均资金费率周期: {funding_result['avg_funding_periods']:.1f} 次")
    print(f"  最大资金费率周期: {funding_result['max_funding_periods']} 次")
    avg_hours = funding_result['avg_funding_periods'] * 8
    print(f"  平均持仓时间: {avg_hours:.1f} 小时 ({avg_hours/24:.1f} 天)")

    print(f"\n【资金费率成本】")
    print(f"  总成本: {funding_result['total_funding_cost']:.4f} USDT")
    print(f"  多头成本: {funding_result['total_long_cost']:.4f} USDT")
    print(f"  空头成本: {funding_result['total_short_cost']:.4f} USDT")
    print(f"  平均每笔成本: {funding_result['avg_funding_cost_per_trade']:.4f} USDT")

    print(f"\n【收益影响】")
    original_profit = safe_float(strategy_data.get("profit_total", 0)) * 100
    starting_balance = safe_float(strategy_data.get("starting_balance", 10.0))
    adjusted_profit = original_profit - (funding_result["total_funding_cost"] / starting_balance * 100)

    print(f"  原始收益: {original_profit:.2f}%")
    print(f"  扣除资金费率后: {adjusted_profit:.2f}%")
    print(f"  收益缩水: {original_profit - adjusted_profit:.2f}%")

    if adjusted_profit < 0:
        print(f"  [X] 策略在扣除资金费率后亏损")
    elif adjusted_profit < original_profit * 0.5:
        print(f"  [!] 真实收益大幅缩水（> 50%）")
    else:
        print(f"  [OK] 策略在扣除资金费率后仍可盈利")

    print("\n" + "=" * 80 + "\n")


# ============================================================================
# 主函数
# ============================================================================


def main() -> int:
    """主函数"""
    parser = argparse.ArgumentParser(
        description="资金费率分析",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法：
  uv run python scripts/evaluation/funding_rate_analysis.py \\
      --zip 01_freqtrade/backtest_results/backtest-result-2026-01-16_02-28-47.zip

  uv run python scripts/evaluation/funding_rate_analysis.py \\
      --zip backtest-result.zip \\
      --avg-rate 0.00015 \\
      --rate-std 0.0003
        """,
    )

    parser.add_argument(
        "--zip",
        required=True,
        help="回测结果zip文件路径",
    )
    parser.add_argument(
        "--strategy",
        default="",
        help="策略名（留空则自动选择）",
    )
    parser.add_argument(
        "--avg-rate",
        type=float,
        default=0.0001,
        help="平均资金费率（默认0.01%%）",
    )
    parser.add_argument(
        "--rate-std",
        type=float,
        default=0.0002,
        help="资金费率标准差（默认0.02%%）",
    )

    args = parser.parse_args()

    try:
        # 读取数据
        zip_path = Path(args.zip)
        data = read_backtest_zip(zip_path)
        strategy_name, strategy_data = pick_strategy(data, args.strategy)

        # 提取交易数据
        trades = strategy_data.get("trades", [])

        if not trades:
            print("错误：回测结果中没有交易数据")
            return 1

        # 执行分析
        funding_result = calculate_funding_cost(
            trades=trades,
            avg_funding_rate=args.avg_rate,
            funding_rate_std=args.rate_std,
        )

        if "error" in funding_result:
            print(f"错误: {funding_result['error']}")
            return 1

        # 打印报告
        print_funding_report(strategy_name, strategy_data, funding_result)

        return 0

    except Exception as e:
        print(f"错误: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
