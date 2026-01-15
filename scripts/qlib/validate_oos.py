"""
validate_oos.py - 样本外验证（Out-of-Sample）自动化脚本

目标：
- 评估因子/策略在样本外的表现，检测过拟合风险
- 支持时间序列交叉验证（Purged K-Fold）
- 输出 OOS 报告（IC 衰减、收益衰减）

用法示例：
  uv run python -X utf8 scripts/qlib/validate_oos.py ^
    --timing-summary artifacts/timing_audit/xxx/timing_summary.csv ^
    --n-splits 5 ^
    --purge-days 7
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "03_integration"))


@dataclass
class OOSConfig:
    """OOS 验证配置"""
    n_splits: int = 5           # 交叉验证折数
    purge_days: int = 7         # 训练/测试间隔天数（避免数据泄露）
    min_train_days: int = 60    # 最小训练天数
    min_test_days: int = 14     # 最小测试天数


@dataclass
class OOSResult:
    """单个因子的 OOS 验证结果"""
    factor: str
    pair: str
    horizon: int
    is_mean: float      # 样本内 IC 均值
    is_std: float       # 样本内 IC 标准差
    oos_mean: float     # 样本外 IC 均值
    oos_std: float      # 样本外 IC 标准差
    ic_decay: float     # IC 衰减率 = (IS - OOS) / IS
    is_ret: float       # 样本内收益均值
    oos_ret: float      # 样本外收益均值
    ret_decay: float    # 收益衰减率


def purged_kfold_split(
    dates: pd.DatetimeIndex,
    n_splits: int,
    purge_days: int,
) -> list[tuple[pd.DatetimeIndex, pd.DatetimeIndex]]:
    """
    Purged K-Fold 时间序列分割。

    每个 fold 的测试集在训练集之后，中间有 purge_days 的间隔。
    """
    if len(dates) < 2:
        return []

    sorted_dates = dates.sort_values()
    n = len(sorted_dates)
    fold_size = n // n_splits

    splits = []
    for i in range(n_splits):
        test_start = i * fold_size
        test_end = (i + 1) * fold_size if i < n_splits - 1 else n

        # 训练集：测试集之前的所有数据（减去 purge 间隔）
        purge_idx = max(0, test_start - purge_days)
        train_idx = sorted_dates[:purge_idx]
        test_idx = sorted_dates[test_start:test_end]

        if len(train_idx) > 0 and len(test_idx) > 0:
            splits.append((train_idx, test_idx))

    return splits


def compute_ic(x: pd.Series, y: pd.Series) -> float:
    """计算 Spearman IC"""
    m = x.notna() & y.notna()
    if m.sum() < 3:
        return float("nan")
    return float(x[m].corr(y[m], method="spearman"))


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="样本外验证（OOS）")
    p.add_argument("--timing-summary", required=True, help="timing_summary.csv 路径")
    p.add_argument("--n-splits", type=int, default=5, help="交叉验证折数")
    p.add_argument("--purge-days", type=int, default=7, help="训练/测试间隔天数")
    p.add_argument("--outdir", default="", help="输出目录")
    return p.parse_args()


def main() -> int:
    args = _parse_args()

    summary_path = Path(args.timing_summary).resolve()
    if not summary_path.is_file():
        print(f"错误: timing_summary 不存在: {summary_path}")
        return 1

    summary = pd.read_csv(summary_path)
    if summary.empty:
        print("错误: timing_summary 为空")
        return 1

    print(f"加载 timing_summary: {len(summary)} 行")
    print(f"OOS 配置: n_splits={args.n_splits}, purge_days={args.purge_days}")

    # 按 verdict=pass 筛选
    passed = summary[summary.get("verdict", "") == "pass"]
    print(f"通过验收的因子: {len(passed)} 个")

    if passed.empty:
        print("警告: 没有通过验收的因子，跳过 OOS 验证")
        return 0

    # 输出 OOS 报告摘要
    print("\n=== OOS 验证摘要 ===")
    print("注意: 完整 OOS 验证需要原始数据，当前仅输出框架")
    print(f"待验证因子数: {len(passed)}")

    # 输出目录
    if args.outdir:
        outdir = Path(args.outdir).resolve()
    else:
        outdir = summary_path.parent / "oos_validation"
    outdir.mkdir(parents=True, exist_ok=True)

    # 保存待验证列表
    passed.to_csv(outdir / "factors_to_validate.csv", index=False)
    print(f"\n输出目录: {outdir}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
