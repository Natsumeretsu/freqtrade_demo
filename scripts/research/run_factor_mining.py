"""因子挖掘研究主脚本

一键运行完整的因子挖掘流程。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import yaml

# 添加项目路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / "integration"))

from data_pipeline import calculate_forward_returns
from factor_library import FactorLibrary
from research.factor_mining.factor_evaluator import FactorEvaluator
from research.factor_mining.factor_generator import FactorGenerator


def load_config(config_path: str | Path) -> dict:
    """加载配置文件

    Args:
        config_path: 配置文件路径

    Returns:
        配置字典
    """
    with open(config_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_data(config: dict) -> pd.DataFrame:
    """加载历史数据

    Args:
        config: 配置字典

    Returns:
        OHLCV 数据框
    """
    data_config = config["data"]
    pair = data_config["pair"]
    timeframe = data_config["timeframe"]
    data_dir = Path(data_config["data_dir"])

    # 转换交易对格式：BTC/USDT:USDT -> BTC_USDT_USDT
    pair_filename = pair.replace("/", "_").replace(":", "_")
    data_file = data_dir / f"{pair_filename}-{timeframe}-futures.feather"

    if not data_file.exists():
        msg = f"数据文件不存在: {data_file}"
        raise FileNotFoundError(msg)

    df = pd.read_feather(data_file)
    print(f"加载数据: {len(df)} 行")
    return df


def main():
    """主函数"""
    # 加载配置
    config_path = project_root / "research" / "factor_mining" / "research_config.yaml"
    config = load_config(config_path)
    print(f"配置加载完成: {config_path}")

    # 加载数据
    df = load_data(config)

    # 计算未来收益
    eval_config = config["evaluation"]
    periods = eval_config["forward_return_periods"]
    df = calculate_forward_returns(df, periods=periods)
    print(f"计算未来收益: {periods}")

    # 生成候选因子
    generator = FactorGenerator()
    factor_names = generator.generate_all_factors()
    print(f"生成候选因子: {len(factor_names)} 个")

    # 计算因子
    factor_lib = FactorLibrary()
    df = factor_lib.calculate_factors(df, factor_names)
    print("因子计算完成")

    # 评估因子
    evaluator = FactorEvaluator()
    results = []

    for factor_name in factor_names:
        for period in periods:
            forward_return_col = f"forward_return_{period}p"
            if forward_return_col not in df.columns:
                continue

            result = evaluator.evaluate_factor(
                df[factor_name], df[forward_return_col], n_groups=eval_config["n_groups"]
            )
            result["factor"] = factor_name
            result["period"] = period
            results.append(result)

    print(f"评估完成: {len(results)} 个结果")

    # 保存结果
    output_dir = project_root / config["output"]["csv_dir"]
    output_dir.mkdir(parents=True, exist_ok=True)

    results_df = pd.DataFrame(results)
    output_file = output_dir / "factor_evaluation_results.csv"
    results_df.to_csv(output_file, index=False)
    print(f"结果已保存: {output_file}")


if __name__ == "__main__":
    main()

