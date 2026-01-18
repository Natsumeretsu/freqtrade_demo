"""
动态滑点模型 - 基于 ATR 的真实滑点估算

用途：
1. 根据市场波动率（ATR）动态调整滑点成本
2. 更准确地估算实盘交易成本
3. 识别高波动期的额外成本

使用方法：
    uv run python scripts/evaluation/dynamic_slippage.py --zip <回测结果.zip> --data-dir <数据目录>
"""

import argparse
import json
import sys
import zipfile
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
# ATR 数据加载与处理
# ============================================================================


def load_ohlcv_data(data_dir: Path, pair: str, timeframe: str) -> pd.DataFrame:
    """加载 OHLCV 数据"""
    # 转换交易对格式：ETH/USDT:USDT -> ETH_USDT_USDT-15m-futures.feather
    pair_clean = pair.replace("/", "_").replace(":", "_")
    filename = f"{pair_clean}-{timeframe}-futures.feather"
    filepath = data_dir / filename

    if not filepath.exists():
        raise FileNotFoundError(f"未找到数据文件: {filepath}")

    df = pd.read_feather(filepath)
    df["date"] = pd.to_datetime(df["date"])
    df.set_index("date", inplace=True)
    return df


def calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """计算 ATR（Average True Range）"""
    high = df["high"]
    low = df["low"]
    close = df["close"]

    # True Range = max(high-low, abs(high-prev_close), abs(low-prev_close))
    tr1 = high - low
    tr2 = abs(high - close.shift(1))
    tr3 = abs(low - close.shift(1))

    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(window=period).mean()

    return atr


def normalize_atr(atr: pd.Series, close: pd.Series) -> pd.Series:
    """标准化 ATR（相对于价格的百分比）"""
    return atr / close


# ============================================================================
# 动态滑点计算
# ============================================================================


def calculate_dynamic_slippage(
    trades: list[dict],
    data_dir: Path,
    timeframe: str,
    base_slippage: float = 0.0005,
    atr_multiplier: float = 2.0,
    atr_period: int = 14,
) -> dict[str, Any]:
    """
    计算动态滑点影响

    参数：
        trades: 交易列表
        data_dir: 数据目录
        timeframe: 时间周期
        base_slippage: 基础滑点（默认 0.05%）
        atr_multiplier: ATR 倍数（默认 2.0）
        atr_period: ATR 周期（默认 14）

    返回：
        包含动态滑点分析结果的字典
    """
    if not trades:
        return {"error": "无交易数据"}

    # 按交易对分组加载数据
    pair_data = {}
    unique_pairs = set(t.get("pair", "") for t in trades)

    print(f"加载 {len(unique_pairs)} 个交易对的数据...")
    for pair in unique_pairs:
        if not pair:
            continue
        try:
            df = load_ohlcv_data(data_dir, pair, timeframe)
            atr = calculate_atr(df, period=atr_period)
            atr_norm = normalize_atr(atr, df["close"])
            pair_data[pair] = {"df": df, "atr": atr, "atr_norm": atr_norm}
            print(f"  ✓ {pair}")
        except FileNotFoundError as e:
            print(f"  ✗ {pair}: {e}")
            continue

    if not pair_data:
        return {"error": "无法加载任何交易对数据"}

    # 计算每笔交易的动态滑点
    results = []
    total_cost_base = 0.0
    total_cost_dynamic = 0.0
    missing_data_count = 0

    for t in trades:
        pair = t.get("pair", "")
        if pair not in pair_data:
            missing_data_count += 1
            continue

        # 获取开仓时间的 ATR
        open_date = pd.to_datetime(t.get("open_date", ""))
        stake = safe_float(t.get("stake_amount", 0))

        # 查找最接近的 ATR 值
        data = pair_data[pair]
        try:
            # 使用 asof 查找最近的历史数据
            atr_norm_value = data["atr_norm"].asof(open_date)
            if pd.isna(atr_norm_value):
                atr_norm_value = data["atr_norm"].median()  # 使用中位数作为后备
        except Exception:
            atr_norm_value = 0.01  # 默认 1%

        # 计算滑点
        # 基础滑点：双边成本
        cost_base = stake * base_slippage * 2

        # 动态滑点：基础滑点 × (1 + ATR倍数 × ATR标准化值)
        slippage_factor = 1 + atr_multiplier * atr_norm_value
        cost_dynamic = cost_base * slippage_factor

        total_cost_base += cost_base
        total_cost_dynamic += cost_dynamic

        results.append(
            {
                "pair": pair,
                "open_date": str(open_date),
                "atr_norm": atr_norm_value,
                "slippage_factor": slippage_factor,
                "cost_base": cost_base,
                "cost_dynamic": cost_dynamic,
            }
        )

    return {
        "base_slippage_pct": base_slippage * 100,
        "atr_multiplier": atr_multiplier,
        "atr_period": atr_period,
        "total_trades": len(trades),
        "trades_with_data": len(results),
        "missing_data_count": missing_data_count,
        "total_cost_base": total_cost_base,
        "total_cost_dynamic": total_cost_dynamic,
        "additional_cost": total_cost_dynamic - total_cost_base,
        "cost_increase_pct": (
            (total_cost_dynamic / total_cost_base - 1) * 100 if total_cost_base > 0 else 0
        ),
        "avg_slippage_factor": np.mean([r["slippage_factor"] for r in results]) if results else 1.0,
        "max_slippage_factor": max([r["slippage_factor"] for r in results]) if results else 1.0,
        "trades": results,
    }


# ============================================================================
# 输出格式化
# ============================================================================


def print_slippage_report(
    strategy_name: str,
    strategy_data: dict,
    slippage_result: dict,
) -> None:
    """打印动态滑点报告"""
    print("\n" + "=" * 80)
    print("动态滑点分析报告（基于 ATR）")
    print("=" * 80)

    print(f"\n策略: {strategy_name}")
    print(f"时间范围: {strategy_data.get('timerange', 'N/A')}")
    print(f"时间周期: {strategy_data.get('timeframe', 'N/A')}")

    print(f"\n【参数设置】")
    print(f"  基础滑点: {slippage_result['base_slippage_pct']:.3f}%")
    print(f"  ATR 倍数: {slippage_result['atr_multiplier']:.1f}")
    print(f"  ATR 周期: {slippage_result['atr_period']}")

    print(f"\n【数据覆盖】")
    print(f"  总交易笔数: {slippage_result['total_trades']}")
    print(f"  有数据笔数: {slippage_result['trades_with_data']}")
    print(f"  缺失数据笔数: {slippage_result['missing_data_count']}")
    coverage = (
        slippage_result["trades_with_data"] / slippage_result["total_trades"] * 100
        if slippage_result["total_trades"] > 0
        else 0
    )
    print(f"  数据覆盖率: {coverage:.1f}%")

    print(f"\n【滑点成本】")
    print(f"  基础滑点成本: {slippage_result['total_cost_base']:.4f} USDT")
    print(f"  动态滑点成本: {slippage_result['total_cost_dynamic']:.4f} USDT")
    print(f"  额外成本: {slippage_result['additional_cost']:.4f} USDT")
    print(f"  成本增加: {slippage_result['cost_increase_pct']:.1f}%")

    print(f"\n【滑点倍数统计】")
    print(f"  平均滑点倍数: {slippage_result['avg_slippage_factor']:.3f}x")
    print(f"  最大滑点倍数: {slippage_result['max_slippage_factor']:.3f}x")

    print(f"\n【收益影响】")
    original_profit = safe_float(strategy_data.get("profit_total", 0)) * 100
    starting_balance = safe_float(strategy_data.get("starting_balance", 10.0))
    adjusted_profit = original_profit - (slippage_result["additional_cost"] / starting_balance * 100)

    print(f"  原始收益: {original_profit:.2f}%")
    print(f"  扣除动态滑点后: {adjusted_profit:.2f}%")
    print(f"  收益缩水: {original_profit - adjusted_profit:.2f}%")

    if adjusted_profit < 0:
        print(f"  [X] 策略在真实成本下亏损")
    elif adjusted_profit < original_profit * 0.5:
        print(f"  [!] 真实收益大幅缩水（> 50%）")
    else:
        print(f"  [OK] 策略在真实成本下仍可盈利")

    print("\n" + "=" * 80 + "\n")


# ============================================================================
# 主函数
# ============================================================================


def main() -> int:
    """主函数"""
    parser = argparse.ArgumentParser(
        description="动态滑点分析（基于 ATR）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法：
  uv run python scripts/evaluation/dynamic_slippage.py \\
      --zip 01_freqtrade/backtest_results/backtest-result-2026-01-16_02-28-47.zip \\
      --data-dir 01_freqtrade/user_data/data/okx
        """,
    )

    parser.add_argument(
        "--zip",
        required=True,
        help="回测结果zip文件路径",
    )
    parser.add_argument(
        "--data-dir",
        required=True,
        help="OHLCV 数据目录路径",
    )
    parser.add_argument(
        "--strategy",
        default="",
        help="策略名（留空则自动选择）",
    )
    parser.add_argument(
        "--base-slippage",
        type=float,
        default=0.0005,
        help="基础滑点（默认0.05%%）",
    )
    parser.add_argument(
        "--atr-multiplier",
        type=float,
        default=2.0,
        help="ATR 倍数（默认2.0）",
    )
    parser.add_argument(
        "--atr-period",
        type=int,
        default=14,
        help="ATR 周期（默认14）",
    )

    args = parser.parse_args()

    try:
        # 读取数据
        zip_path = Path(args.zip)
        data_dir = Path(args.data_dir)

        if not data_dir.exists():
            print(f"错误：数据目录不存在: {data_dir}")
            return 1

        data = read_backtest_zip(zip_path)
        strategy_name, strategy_data = pick_strategy(data, args.strategy)

        # 提取交易数据
        trades = strategy_data.get("trades", [])
        timeframe = strategy_data.get("timeframe", "15m")

        if not trades:
            print("错误：回测结果中没有交易数据")
            return 1

        # 执行分析
        slippage_result = calculate_dynamic_slippage(
            trades=trades,
            data_dir=data_dir,
            timeframe=timeframe,
            base_slippage=args.base_slippage,
            atr_multiplier=args.atr_multiplier,
            atr_period=args.atr_period,
        )

        if "error" in slippage_result:
            print(f"错误: {slippage_result['error']}")
            return 1

        # 打印报告
        print_slippage_report(strategy_name, strategy_data, slippage_result)

        return 0

    except Exception as e:
        print(f"错误: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
