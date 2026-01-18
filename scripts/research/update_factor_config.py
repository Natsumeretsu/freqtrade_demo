"""因子配置更新工具

从研究结果中筛选有效因子并更新到生产配置。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import yaml

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "integration"))

from factor_library import get_factor_class


def load_evaluation_results(results_file: Path) -> pd.DataFrame:
    """加载因子评估结果

    Args:
        results_file: 评估结果文件路径

    Returns:
        评估结果 DataFrame
    """
    if not results_file.exists():
        msg = f"评估结果文件不存在: {results_file}"
        raise FileNotFoundError(msg)

    return pd.read_csv(results_file)


def filter_effective_factors(
    results_df: pd.DataFrame,
    ic_threshold: float = 0.02,
    t_stat_threshold: float = 2.0,
) -> pd.DataFrame:
    """筛选有效因子

    Args:
        results_df: 评估结果 DataFrame
        ic_threshold: IC 阈值
        t_stat_threshold: t 统计量阈值

    Returns:
        筛选后的因子列表
    """
    # 筛选条件：IC 绝对值 > 阈值 且 t 统计量绝对值 > 阈值
    effective = results_df[
        (results_df["ic"].abs() > ic_threshold)
        & (results_df["t_stat"].abs() > t_stat_threshold)
    ].copy()

    # 按 IC 绝对值排序
    effective["ic_abs"] = effective["ic"].abs()
    effective = effective.sort_values("ic_abs", ascending=False)

    return effective


def update_factor_config(
    config_file: Path, selected_factors: list[str], backup: bool = True
) -> None:
    """更新因子配置文件

    Args:
        config_file: 配置文件路径
        selected_factors: 选中的因子列表
        backup: 是否备份原配置
    """
    # 备份原配置
    if backup and config_file.exists():
        backup_file = config_file.with_suffix(".yaml.bak")
        backup_file.write_text(config_file.read_text(), encoding="utf-8")
        print(f"已备份原配置: {backup_file}")

    # 读取现有配置
    if config_file.exists():
        with config_file.open(encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}
    else:
        config = {}

    if "factors" not in config:
        config["factors"] = {}

    # 为新因子生成配置条目
    for factor_name in selected_factors:
        if factor_name not in config["factors"]:
            # 获取因子类以提取默认参数
            try:
                factor_class = get_factor_class(factor_name)
                config["factors"][factor_name] = {
                    "class": factor_class.__name__,
                    "params": {},
                    "enabled": True,
                    "weight": 1.0 / len(selected_factors),  # 均匀分配权重
                    "description": factor_class.__doc__.strip() if factor_class.__doc__ else "",
                    "category": "technical",
                }
                print(f"添加新因子配置: {factor_name}")
            except Exception as e:
                print(f"警告: 无法获取因子 {factor_name} 的类信息: {e}")
                continue

    # 更新因子启用状态
    for factor_name, factor_config in config["factors"].items():
        if factor_name in selected_factors:
            factor_config["enabled"] = True
        else:
            factor_config["enabled"] = False

    # 保存配置
    with config_file.open("w", encoding="utf-8") as f:
        yaml.dump(config, f, allow_unicode=True, sort_keys=False)

    print(f"已更新配置文件: {config_file}")
    print(f"启用因子数量: {len(selected_factors)}")


def generate_deployment_report(
    effective_factors: pd.DataFrame, output_file: Path
) -> None:
    """生成部署报告

    Args:
        effective_factors: 有效因子 DataFrame
        output_file: 输出文件路径
    """
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with output_file.open("w", encoding="utf-8") as f:
        f.write("# 因子部署报告\n\n")
        f.write(f"**生成时间**: {pd.Timestamp.now()}\n\n")
        f.write(f"**有效因子数量**: {len(effective_factors)}\n\n")

        f.write("## 有效因子列表\n\n")
        f.write("| 因子名称 | 周期 | IC | Rank IC | t统计量 | 样本数 |\n")
        f.write("|---------|------|-----|---------|---------|--------|\n")

        for _, row in effective_factors.iterrows():
            f.write(
                f"| {row['factor']} | {row['period']}p | "
                f"{row['ic']:.4f} | {row['rank_ic']:.4f} | "
                f"{row['t_stat']:.2f} | {row['n_samples']} |\n"
            )

        f.write("\n## 部署建议\n\n")
        f.write("1. 在生产环境中启用上述因子\n")
        f.write("2. 监控因子表现，定期评估\n")
        f.write("3. 如发现因子衰减，及时调整\n")

    print(f"已生成部署报告: {output_file}")


def main():
    """主函数"""
    # 文件路径
    results_file = project_root / "research" / "factor_mining" / "results" / "factor_evaluation_results.csv"
    config_file = project_root / "integration" / "factor_library" / "factor_config.yaml"
    report_file = project_root / "docs" / "reports" / "factor_deployment_report.md"

    print("=== 因子配置更新工具 ===\n")

    # 加载评估结果
    print(f"加载评估结果: {results_file}")
    results_df = load_evaluation_results(results_file)
    print(f"总计评估结果: {len(results_df)} 条\n")

    # 筛选有效因子
    print("筛选有效因子...")
    effective_factors = filter_effective_factors(
        results_df, ic_threshold=0.02, t_stat_threshold=2.0
    )
    print(f"有效因子数量: {len(effective_factors)}\n")

    if len(effective_factors) == 0:
        print("未找到有效因子，退出")
        return

    # 获取唯一因子名称
    selected_factors = effective_factors["factor"].unique().tolist()
    print(f"选中因子: {selected_factors}\n")

    # 更新配置
    print("更新因子配置...")
    update_factor_config(config_file, selected_factors, backup=True)
    print()

    # 生成报告
    print("生成部署报告...")
    generate_deployment_report(effective_factors, report_file)
    print()

    print("=== 完成 ===")


if __name__ == "__main__":
    main()
