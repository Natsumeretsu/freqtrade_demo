"""
param_sensitivity.py - 参数敏感性分析工具

目标：
- 评估关键参数对预测性能的影响
- 识别稳健的参数区间
- 支持网格搜索和单参数扫描

用法示例：
  uv run python -X utf8 scripts/qlib/param_sensitivity.py ^
    --param window --range 128,256,512,1024 ^
    --metric ic_mean ^
    --data artifacts/timing_audit/xxx/timing_summary.csv
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "03_integration"))


@dataclass
class SensitivityConfig:
    """敏感性分析配置"""
    param_name: str
    param_values: list[float]
    metric: str = "ic_mean"
    baseline_value: float | None = None


@dataclass
class SensitivityResult:
    """单个参数值的分析结果"""
    param_value: float
    metric_value: float
    metric_std: float
    sample_count: int
    is_baseline: bool = False


@dataclass
class SensitivityReport:
    """敏感性分析报告"""
    param_name: str
    metric: str
    results: list[SensitivityResult] = field(default_factory=list)
    best_value: float | None = None
    best_metric: float | None = None
    robustness_score: float | None = None

    def summary(self) -> str:
        """生成可读摘要"""
        lines = [
            f"=== 参数敏感性分析: {self.param_name} ===",
            f"评估指标: {self.metric}",
            f"测试值数: {len(self.results)}",
        ]
        if self.best_value is not None:
            lines.append(f"最优值: {self.best_value} (metric={self.best_metric:.4f})")
        if self.robustness_score is not None:
            lines.append(f"稳健性得分: {self.robustness_score:.2%}")

        lines.append("\n详细结果:")
        for r in self.results:
            marker = " *" if r.is_baseline else ""
            lines.append(
                f"  {r.param_value:>8}: {r.metric_value:>8.4f} "
                f"(std={r.metric_std:.4f}, n={r.sample_count}){marker}"
            )
        return "\n".join(lines)


def compute_robustness_score(results: list[SensitivityResult]) -> float:
    """
    计算稳健性得分。

    稳健性 = 1 - (metric 变异系数)
    得分越高表示参数变化对性能影响越小。
    """
    if len(results) < 2:
        return 1.0

    metrics = [r.metric_value for r in results if np.isfinite(r.metric_value)]
    if len(metrics) < 2:
        return 1.0

    mean = np.mean(metrics)
    std = np.std(metrics)

    if abs(mean) < 1e-10:
        return 0.0

    cv = std / abs(mean)
    return max(0.0, 1.0 - cv)


def analyze_sensitivity(
    data: pd.DataFrame,
    config: SensitivityConfig,
) -> SensitivityReport:
    """
    执行参数敏感性分析。

    Args:
        data: 包含不同参数值结果的 DataFrame
        config: 敏感性分析配置

    Returns:
        SensitivityReport 对象
    """
    report = SensitivityReport(
        param_name=config.param_name,
        metric=config.metric,
    )

    if data.empty:
        return report

    metric_col = config.metric
    if metric_col not in data.columns:
        print(f"警告: 指标列 {metric_col} 不存在")
        return report

    for val in config.param_values:
        subset = data[data.get(config.param_name, pd.Series()) == val]
        if subset.empty:
            continue

        metric_values = subset[metric_col].dropna()
        if metric_values.empty:
            continue

        result = SensitivityResult(
            param_value=val,
            metric_value=float(metric_values.mean()),
            metric_std=float(metric_values.std()) if len(metric_values) > 1 else 0.0,
            sample_count=len(metric_values),
            is_baseline=(config.baseline_value is not None and val == config.baseline_value),
        )
        report.results.append(result)

    if report.results:
        best = max(report.results, key=lambda r: r.metric_value)
        report.best_value = best.param_value
        report.best_metric = best.metric_value
        report.robustness_score = compute_robustness_score(report.results)

    return report


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="参数敏感性分析")
    p.add_argument("--data", required=True, help="输入数据 CSV 路径")
    p.add_argument("--param", required=True, help="要分析的参数名")
    p.add_argument("--range", required=True, help="参数值范围（逗号分隔）")
    p.add_argument("--metric", default="ic_mean", help="评估指标列名")
    p.add_argument("--baseline", type=float, default=None, help="基线参数值")
    p.add_argument("--outdir", default="", help="输出目录")
    return p.parse_args()


def main() -> int:
    args = _parse_args()

    data_path = Path(args.data).resolve()
    if not data_path.is_file():
        print(f"错误: 数据文件不存在: {data_path}")
        return 1

    data = pd.read_csv(data_path)
    if data.empty:
        print("错误: 数据为空")
        return 1

    # 解析参数范围
    try:
        param_values = [float(v.strip()) for v in args.range.split(",")]
    except ValueError as e:
        print(f"错误: 无法解析参数范围: {e}")
        return 1

    config = SensitivityConfig(
        param_name=args.param,
        param_values=param_values,
        metric=args.metric,
        baseline_value=args.baseline,
    )

    print(f"参数敏感性分析")
    print(f"  数据: {data_path}")
    print(f"  参数: {config.param_name}")
    print(f"  范围: {config.param_values}")
    print(f"  指标: {config.metric}")

    report = analyze_sensitivity(data, config)
    print("\n" + report.summary())

    # 保存结果
    if args.outdir:
        outdir = Path(args.outdir).resolve()
    else:
        outdir = data_path.parent / "sensitivity"
    outdir.mkdir(parents=True, exist_ok=True)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = outdir / f"sensitivity_{config.param_name}_{ts}.csv"

    results_df = pd.DataFrame([
        {
            "param_value": r.param_value,
            "metric_value": r.metric_value,
            "metric_std": r.metric_std,
            "sample_count": r.sample_count,
            "is_baseline": r.is_baseline,
        }
        for r in report.results
    ])
    results_df.to_csv(out_path, index=False)
    print(f"\n结果已保存: {out_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
