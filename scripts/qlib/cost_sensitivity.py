"""
cost_sensitivity.py - 交易成本敏感性分析工具

目标：
- 评估不同成本假设对策略净收益的影响
- 识别成本敏感的因子/策略
- 支持滑点、手续费、资金费率等多维成本分析

用法示例：
  uv run python -X utf8 scripts/qlib/cost_sensitivity.py ^
    --timing-summary artifacts/timing_audit/xxx/timing_summary.csv ^
    --cost-range 0.0001,0.0003,0.0005,0.001 ^
    --outdir artifacts/cost_analysis
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "03_integration"))


@dataclass
class CostConfig:
    """成本配置"""
    # 单边交易成本（手续费 + 滑点）
    trading_cost_bps: float = 3.0  # 3 bps = 0.03%
    # 资金费率（合约）
    funding_rate_8h: float = 0.0001  # 0.01% per 8h
    # 借贷利率（杠杆）
    borrow_rate_daily: float = 0.0001  # 0.01% per day


@dataclass
class CostImpactResult:
    """单个成本水平的影响结果"""
    cost_bps: float
    gross_return: float
    net_return: float
    cost_drag: float  # 成本拖累 = gross - net
    breakeven_trades: int  # 盈亏平衡所需交易次数
    profitable_ratio: float  # 扣成本后仍盈利的比例


@dataclass
class CostSensitivityReport:
    """成本敏感性分析报告"""
    factor_name: str
    results: list[CostImpactResult] = field(default_factory=list)
    max_viable_cost: float | None = None  # 最大可承受成本

    def summary(self) -> str:
        lines = [
            f"=== 成本敏感性分析: {self.factor_name} ===",
            f"测试成本水平数: {len(self.results)}",
        ]
        if self.max_viable_cost is not None:
            lines.append(f"最大可承受成本: {self.max_viable_cost:.4f} ({self.max_viable_cost*10000:.1f} bps)")

        lines.append("\n成本水平 | 毛收益 | 净收益 | 成本拖累 | 盈利比例")
        lines.append("-" * 55)
        for r in self.results:
            lines.append(
                f"{r.cost_bps*10000:>6.1f}bps | {r.gross_return:>6.2%} | "
                f"{r.net_return:>6.2%} | {r.cost_drag:>6.2%} | {r.profitable_ratio:>6.1%}"
            )
        return "\n".join(lines)


def analyze_cost_impact(
    gross_returns: pd.Series,
    cost_levels: list[float],
    trades_per_period: int = 2,
) -> CostSensitivityReport:
    """
    分析不同成本水平对收益的影响。

    Args:
        gross_returns: 毛收益序列
        cost_levels: 成本水平列表（小数形式，如 0.0003 = 3bps）
        trades_per_period: 每期交易次数（用于计算成本拖累）
    """
    report = CostSensitivityReport(factor_name="aggregate")

    if gross_returns.empty:
        return report

    gross_mean = float(gross_returns.mean())

    for cost in cost_levels:
        # 双边成本（开仓+平仓）
        total_cost = cost * trades_per_period
        net_returns = gross_returns - total_cost

        net_mean = float(net_returns.mean())
        profitable = (net_returns > 0).sum() / len(net_returns)

        # 盈亏平衡交易次数
        if gross_mean > 0 and cost > 0:
            breakeven = int(gross_mean / cost)
        else:
            breakeven = 0

        result = CostImpactResult(
            cost_bps=cost,
            gross_return=gross_mean,
            net_return=net_mean,
            cost_drag=gross_mean - net_mean,
            breakeven_trades=breakeven,
            profitable_ratio=profitable,
        )
        report.results.append(result)

    # 找最大可承受成本
    for r in report.results:
        if r.net_return > 0:
            report.max_viable_cost = r.cost_bps

    return report


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="交易成本敏感性分析")
    p.add_argument("--timing-summary", required=True, help="timing_summary.csv 路径")
    p.add_argument("--cost-range", default="0.0001,0.0003,0.0005,0.001", help="成本范围（逗号分隔）")
    p.add_argument("--return-col", default="ret_mean", help="收益列名")
    p.add_argument("--outdir", default="", help="输出目录")
    return p.parse_args()


def main() -> int:
    args = _parse_args()

    summary_path = Path(args.timing_summary).resolve()
    if not summary_path.is_file():
        print(f"错误: 文件不存在: {summary_path}")
        return 1

    data = pd.read_csv(summary_path)
    if data.empty:
        print("错误: 数据为空")
        return 1

    return_col = args.return_col
    if return_col not in data.columns:
        print(f"错误: 收益列 {return_col} 不存在")
        print(f"可用列: {list(data.columns)}")
        return 1

    # 解析成本范围
    try:
        cost_levels = [float(v.strip()) for v in args.cost_range.split(",")]
    except ValueError as e:
        print(f"错误: 无法解析成本范围: {e}")
        return 1

    print(f"成本敏感性分析")
    print(f"  数据: {summary_path}")
    print(f"  收益列: {return_col}")
    print(f"  成本范围: {[f'{c*10000:.1f}bps' for c in cost_levels]}")

    gross_returns = data[return_col].dropna()
    report = analyze_cost_impact(gross_returns, cost_levels)
    print("\n" + report.summary())

    # 保存结果
    if args.outdir:
        outdir = Path(args.outdir).resolve()
    else:
        outdir = summary_path.parent / "cost_analysis"
    outdir.mkdir(parents=True, exist_ok=True)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = outdir / f"cost_sensitivity_{ts}.csv"

    results_df = pd.DataFrame([
        {
            "cost_bps": r.cost_bps * 10000,
            "gross_return": r.gross_return,
            "net_return": r.net_return,
            "cost_drag": r.cost_drag,
            "profitable_ratio": r.profitable_ratio,
        }
        for r in report.results
    ])
    results_df.to_csv(out_path, index=False)
    print(f"\n结果已保存: {out_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
