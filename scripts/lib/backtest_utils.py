"""回测工具库

提供回测结果解析、指标计算、数据对比等功能。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd


class BacktestResult:
    """回测结果封装类"""

    def __init__(self, result_file: str | Path):
        """初始化回测结果

        Args:
            result_file: Freqtrade 回测结果 JSON 文件路径
        """
        self.result_file = Path(result_file)
        self.data = self._load_result()

    def _load_result(self) -> dict[str, Any]:
        """加载回测结果 JSON 文件

        Returns:
            回测结果字典
        """
        if not self.result_file.exists():
            msg = f"回测结果文件不存在: {self.result_file}"
            raise FileNotFoundError(msg)

        with open(self.result_file, encoding="utf-8") as f:
            return json.load(f)

    @property
    def strategy_name(self) -> str:
        """策略名称"""
        return self.data.get("strategy", {}).get("strategy_name", "Unknown")

    @property
    def total_trades(self) -> int:
        """总交易次数"""
        return self.data.get("results_per_pair", [{}])[-1].get("trades", 0)

    @property
    def winning_trades(self) -> int:
        """盈利交易次数"""
        return self.data.get("results_per_pair", [{}])[-1].get("wins", 0)

    @property
    def losing_trades(self) -> int:
        """亏损交易次数"""
        return self.data.get("results_per_pair", [{}])[-1].get("losses", 0)

    @property
    def win_rate(self) -> float:
        """胜率（百分比）"""
        if self.total_trades == 0:
            return 0.0
        return (self.winning_trades / self.total_trades) * 100

    @property
    def total_profit(self) -> float:
        """总收益（百分比）"""
        return self.data.get("results_per_pair", [{}])[-1].get("profit_total_abs", 0.0)

    @property
    def total_profit_pct(self) -> float:
        """总收益率（百分比）"""
        return self.data.get("results_per_pair", [{}])[-1].get("profit_total", 0.0)

    @property
    def max_drawdown(self) -> float:
        """最大回撤（百分比）"""
        return self.data.get("max_drawdown", 0.0)

    @property
    def sharpe_ratio(self) -> float:
        """夏普比率"""
        return self.data.get("sharpe", 0.0)

    @property
    def sortino_ratio(self) -> float:
        """索提诺比率"""
        return self.data.get("sortino", 0.0)

    def get_summary(self) -> dict[str, Any]:
        """获取回测结果摘要

        Returns:
            包含关键指标的字典
        """
        return {
            "strategy": self.strategy_name,
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "win_rate": round(self.win_rate, 2),
            "total_profit": round(self.total_profit, 2),
            "total_profit_pct": round(self.total_profit_pct, 2),
            "max_drawdown": round(self.max_drawdown, 2),
            "sharpe_ratio": round(self.sharpe_ratio, 3),
            "sortino_ratio": round(self.sortino_ratio, 3),
        }


def compare_results(result_files: list[str | Path]) -> pd.DataFrame:
    """对比多个回测结果

    Args:
        result_files: 回测结果文件路径列表

    Returns:
        包含所有策略对比数据的 DataFrame
    """
    summaries = []
    for file in result_files:
        try:
            result = BacktestResult(file)
            summaries.append(result.get_summary())
        except Exception as e:
            print(f"加载 {file} 失败: {e}")
            continue

    if not summaries:
        return pd.DataFrame()

    df = pd.DataFrame(summaries)
    # 按总收益率降序排序
    df = df.sort_values("total_profit_pct", ascending=False)
    return df


def generate_markdown_report(df: pd.DataFrame, output_file: str | Path) -> None:
    """生成 Markdown 格式的回测报告

    Args:
        df: 回测结果对比 DataFrame
        output_file: 输出文件路径
    """
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("# 回测结果对比报告\n\n")
        f.write(f"**生成时间**: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write("## 策略排名\n\n")
        f.write(df.to_markdown(index=False))
        f.write("\n\n## 关键指标说明\n\n")
        f.write("- **total_trades**: 总交易次数\n")
        f.write("- **win_rate**: 胜率（%）\n")
        f.write("- **total_profit_pct**: 总收益率（%）\n")
        f.write("- **max_drawdown**: 最大回撤（%）\n")
        f.write("- **sharpe_ratio**: 夏普比率（越高越好）\n")
        f.write("- **sortino_ratio**: 索提诺比率（越高越好）\n")
