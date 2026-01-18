"""因子性能监控脚本

监控因子在生产环境中的表现，检测因子衰减。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import numpy as np

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from integration.factor_library import FactorLibrary
from research.factor_mining.factor_evaluator import FactorEvaluator
from integration.data_pipeline import calculate_forward_returns


def load_recent_data(data_dir: Path, pair: str, timeframe: str, days: int = 30) -> pd.DataFrame:
    """加载最近的数据

    Args:
        data_dir: 数据目录
        pair: 交易对
        timeframe: 时间框架
        days: 天数

    Returns:
        数据 DataFrame
    """
    # 构建数据文件路径
    pair_filename = pair.replace("/", "_").replace(":", "_")
    data_file = data_dir / f"{pair_filename}-{timeframe}.feather"

    if not data_file.exists():
        msg = f"数据文件不存在: {data_file}"
        raise FileNotFoundError(msg)

    # 加载数据
    df = pd.read_feather(data_file)

    # 筛选最近 N 天的数据
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"])
        cutoff_date = df["date"].max() - pd.Timedelta(days=days)
        df = df[df["date"] >= cutoff_date].copy()

    return df


def monitor_factor_performance(
    df: pd.DataFrame,
    factor_names: list[str],
    forward_periods: list[int] = [1, 4, 8],
) -> pd.DataFrame:
    """监控因子性能

    Args:
        df: 数据 DataFrame
        factor_names: 因子名称列表
        forward_periods: 未来收益周期

    Returns:
        性能监控结果 DataFrame
    """
    # 计算未来收益
    df = calculate_forward_returns(df, periods=forward_periods)

    # 计算因子
    factor_lib = FactorLibrary()
    df = factor_lib.calculate_factors(df, factor_names)

    # 评估因子
    evaluator = FactorEvaluator()
    results = []

    for factor_name in factor_names:
        if factor_name not in df.columns:
            continue

        for period in forward_periods:
            forward_return_col = f"forward_return_{period}p"
            if forward_return_col not in df.columns:
                continue

            result = evaluator.evaluate_factor(
                df[factor_name], df[forward_return_col], n_groups=5
            )
            result["factor"] = factor_name
            result["period"] = period
            results.append(result)

    return pd.DataFrame(results)


def detect_factor_decay(
    current_results: pd.DataFrame,
    historical_results: pd.DataFrame,
    ic_decay_threshold: float = 0.5,
) -> pd.DataFrame:
    """检测因子衰减

    Args:
        current_results: 当前评估结果
        historical_results: 历史评估结果
        ic_decay_threshold: IC 衰减阈值（相对变化）

    Returns:
        衰减因子列表
    """
    # 合并当前和历史结果
    merged = current_results.merge(
        historical_results,
        on=["factor", "period"],
        suffixes=("_current", "_historical"),
    )

    # 计算 IC 变化率
    merged["ic_change"] = (
        (merged["ic_current"] - merged["ic_historical"]) / merged["ic_historical"].abs()
    )

    # 筛选衰减因子
    decayed = merged[merged["ic_change"] < -ic_decay_threshold].copy()

    return decayed[["factor", "period", "ic_historical", "ic_current", "ic_change"]]


def generate_monitoring_report(
    current_results: pd.DataFrame,
    decayed_factors: pd.DataFrame,
    output_file: Path,
) -> None:
    """生成监控报告

    Args:
        current_results: 当前评估结果
        decayed_factors: 衰减因子列表
        output_file: 输出文件路径
    """
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with output_file.open("w", encoding="utf-8") as f:
        f.write("# 因子性能监控报告\n\n")
        f.write(f"**生成时间**: {pd.Timestamp.now()}\n\n")

        f.write("## 当前因子性能\n\n")
        f.write("| 因子名称 | 周期 | IC | Rank IC | t统计量 | 样本数 |\n")
        f.write("|---------|------|-----|---------|---------|--------|\n")

        for _, row in current_results.iterrows():
            f.write(
                f"| {row['factor']} | {row['period']}p | "
                f"{row['ic']:.4f} | {row['rank_ic']:.4f} | "
                f"{row['t_stat']:.2f} | {row['n_samples']} |\n"
            )

        f.write("\n## 因子衰减检测\n\n")
        if len(decayed_factors) > 0:
            f.write("⚠️ **发现衰减因子**\n\n")
            f.write("| 因子名称 | 周期 | 历史IC | 当前IC | 变化率 |\n")
            f.write("|---------|------|--------|--------|--------|\n")

            for _, row in decayed_factors.iterrows():
                f.write(
                    f"| {row['factor']} | {row['period']}p | "
                    f"{row['ic_historical']:.4f} | {row['ic_current']:.4f} | "
                    f"{row['ic_change']:.2%} |\n"
                )

            f.write("\n**建议**: 考虑禁用或替换衰减因子\n")
        else:
            f.write("✅ 未发现明显衰减因子\n")

        f.write("\n## 监控建议\n\n")
        f.write("1. 定期运行监控脚本（建议每周）\n")
        f.write("2. 关注 IC 和 t 统计量的变化\n")
        f.write("3. 及时调整衰减因子\n")
        f.write("4. 持续挖掘新因子补充\n")

    print(f"已生成监控报告: {output_file}")


def main():
    """主函数"""
    # 配置
    data_dir = project_root / "ft_userdir" / "data" / "okx" / "futures"
    pair = "BTC/USDT:USDT"
    timeframe = "5m"
    monitoring_days = 30

    # 因子列表（从配置文件读取启用的因子）
    factor_names = ["momentum_8h", "volatility_24h", "volume_surge"]

    # 输出路径
    current_results_file = project_root / "docs" / "reports" / "factor_monitoring" / "current_results.csv"
    report_file = project_root / "docs" / "reports" / "factor_monitoring" / "monitoring_report.md"

    print("=== 因子性能监控 ===\n")

    # 加载数据
    print(f"加载最近 {monitoring_days} 天的数据...")
    try:
        df = load_recent_data(data_dir, pair, timeframe, days=monitoring_days)
        print(f"数据行数: {len(df)}\n")
    except FileNotFoundError as e:
        print(f"错误: {e}")
        print("请先下载数据或调整数据路径")
        return

    # 监控因子性能
    print("评估因子性能...")
    current_results = monitor_factor_performance(df, factor_names)
    print(f"评估完成: {len(current_results)} 个结果\n")

    # 保存当前结果
    current_results_file.parent.mkdir(parents=True, exist_ok=True)
    current_results.to_csv(current_results_file, index=False)
    print(f"已保存当前结果: {current_results_file}\n")

    # 检测因子衰减（如果有历史结果）
    historical_results_file = project_root / "research" / "factor_mining" / "results" / "factor_evaluation_results.csv"
    if historical_results_file.exists():
        print("检测因子衰减...")
        historical_results = pd.read_csv(historical_results_file)
        decayed_factors = detect_factor_decay(current_results, historical_results)
        print(f"衰减因子数量: {len(decayed_factors)}\n")
    else:
        print("未找到历史结果，跳过衰减检测\n")
        decayed_factors = pd.DataFrame()

    # 生成报告
    print("生成监控报告...")
    generate_monitoring_report(current_results, decayed_factors, report_file)
    print()

    print("=== 完成 ===")


if __name__ == "__main__":
    main()
