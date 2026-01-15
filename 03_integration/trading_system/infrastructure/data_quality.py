"""
data_quality.py - 数据质量检查模块

用于在因子计算前检测数据问题：
- 缺失值检测
- 异常值检测（Z-score）
- 重复时间戳检测
- 数据连续性检测
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd


@dataclass
class QualityIssue:
    """单个数据质量问题"""
    level: str  # "error" | "warning" | "info"
    category: str  # "missing" | "outlier" | "duplicate" | "gap"
    column: str | None
    message: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class QualityReport:
    """数据质量检查报告"""
    passed: bool
    total_rows: int
    issues: list[QualityIssue] = field(default_factory=list)

    def add_issue(self, issue: QualityIssue) -> None:
        self.issues.append(issue)
        if issue.level == "error":
            self.passed = False

    def summary(self) -> str:
        """生成可读的摘要"""
        lines = [
            f"数据质量检查: {'通过' if self.passed else '未通过'}",
            f"总行数: {self.total_rows}",
            f"问题数: {len(self.issues)}",
        ]
        for issue in self.issues[:10]:  # 最多显示10个
            lines.append(f"  [{issue.level}] {issue.category}: {issue.message}")
        if len(self.issues) > 10:
            lines.append(f"  ... 还有 {len(self.issues) - 10} 个问题")
        return "\n".join(lines)


@dataclass
class QualityConfig:
    """数据质量检查配置"""
    # 缺失值阈值
    missing_rate_error: float = 0.10  # >10% 报错
    missing_rate_warn: float = 0.01   # >1% 警告

    # 异常值阈值（Z-score）
    outlier_zscore: float = 5.0       # |Z| > 5 视为异常
    outlier_rate_error: float = 0.05  # >5% 报错
    outlier_rate_warn: float = 0.01   # >1% 警告

    # 时间间隔检测
    gap_multiplier: float = 2.0       # 间隔 > 2x 中位数视为异常


class DataQualityChecker:
    """数据质量检查器"""

    def __init__(self, config: QualityConfig | None = None) -> None:
        self.config = config or QualityConfig()

    def check(self, df: pd.DataFrame, *, required_cols: list[str] | None = None) -> QualityReport:
        """
        执行完整的数据质量检查。

        Args:
            df: 待检查的 DataFrame（index 应为 DatetimeIndex）
            required_cols: 必须存在的列（默认 OHLCV）

        Returns:
            QualityReport 对象
        """
        if df is None or df.empty:
            report = QualityReport(passed=False, total_rows=0)
            report.add_issue(QualityIssue(
                level="error", category="empty", column=None,
                message="数据为空"
            ))
            return report

        report = QualityReport(passed=True, total_rows=len(df))

        # 1. 检查必要列
        if required_cols is None:
            required_cols = ["open", "high", "low", "close", "volume"]
        self._check_required_columns(df, required_cols, report)

        # 2. 检查缺失值
        self._check_missing_values(df, report)

        # 3. 检查异常值
        self._check_outliers(df, report)

        # 4. 检查重复时间戳
        self._check_duplicates(df, report)

        # 5. 检查时间间隔
        self._check_time_gaps(df, report)

        return report

    def _check_required_columns(
        self, df: pd.DataFrame, required_cols: list[str], report: QualityReport
    ) -> None:
        """检查必要列是否存在"""
        missing = [c for c in required_cols if c not in df.columns]
        if missing:
            report.add_issue(QualityIssue(
                level="error", category="schema", column=None,
                message=f"缺少必要列: {missing}",
                details={"missing_columns": missing}
            ))

    def _check_missing_values(self, df: pd.DataFrame, report: QualityReport) -> None:
        """检查缺失值"""
        n = len(df)
        if n == 0:
            return

        for col in df.columns:
            missing_count = int(df[col].isna().sum())
            if missing_count == 0:
                continue

            rate = missing_count / n
            if rate > self.config.missing_rate_error:
                level = "error"
            elif rate > self.config.missing_rate_warn:
                level = "warning"
            else:
                level = "info"

            report.add_issue(QualityIssue(
                level=level, category="missing", column=col,
                message=f"列 {col} 缺失率 {rate:.2%} ({missing_count}/{n})",
                details={"missing_count": missing_count, "missing_rate": rate}
            ))

    def _check_outliers(self, df: pd.DataFrame, report: QualityReport) -> None:
        """检查异常值（Z-score）"""
        n = len(df)
        if n < 10:
            return

        numeric_cols = df.select_dtypes(include=[np.number]).columns
        for col in numeric_cols:
            s = df[col].dropna()
            if len(s) < 10:
                continue

            mean = float(s.mean())
            std = float(s.std())
            if std == 0 or not np.isfinite(std):
                continue

            z = np.abs((s - mean) / std)
            outlier_count = int((z > self.config.outlier_zscore).sum())
            if outlier_count == 0:
                continue

            rate = outlier_count / len(s)
            if rate > self.config.outlier_rate_error:
                level = "error"
            elif rate > self.config.outlier_rate_warn:
                level = "warning"
            else:
                level = "info"

            report.add_issue(QualityIssue(
                level=level, category="outlier", column=col,
                message=f"列 {col} 异常值率 {rate:.2%} (|Z|>{self.config.outlier_zscore})",
                details={"outlier_count": outlier_count, "outlier_rate": rate}
            ))

    def _check_duplicates(self, df: pd.DataFrame, report: QualityReport) -> None:
        """检查重复时间戳"""
        if not isinstance(df.index, pd.DatetimeIndex):
            return

        dup_count = int(df.index.duplicated().sum())
        if dup_count > 0:
            report.add_issue(QualityIssue(
                level="error", category="duplicate", column=None,
                message=f"发现 {dup_count} 个重复时间戳",
                details={"duplicate_count": dup_count}
            ))

    def _check_time_gaps(self, df: pd.DataFrame, report: QualityReport) -> None:
        """检查时间间隔异常"""
        if not isinstance(df.index, pd.DatetimeIndex):
            return
        if len(df) < 3:
            return

        diffs = df.index.to_series().diff().dropna()
        if diffs.empty:
            return

        median_diff = diffs.median()
        threshold = median_diff * self.config.gap_multiplier

        gaps = diffs[diffs > threshold]
        if len(gaps) > 0:
            report.add_issue(QualityIssue(
                level="warning", category="gap", column=None,
                message=f"发现 {len(gaps)} 个时间间隔异常 (>{threshold})",
                details={"gap_count": len(gaps), "median_interval": str(median_diff)}
            ))
