#!/usr/bin/env python3
"""
统一的因子分析命令行工具

替代所有旧的独立分析脚本，提供统一的接口。

使用方法：
    python scripts/evaluation/factor_analysis.py \
        --data-dir 01_freqtrade/data/okx/futures \
        --factor-file artifacts/factors.csv \
        --analysis ic,turnover,returns \
        --output-dir artifacts/factor_reports
"""

import argparse
import sys
from pathlib import Path
from typing import Dict, List

import pandas as pd

# 添加项目路径
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "03_integration"))

from trading_system.infrastructure.analysis.unified_analyzer import FactorAnalyzer


def load_factor_data(factor_file: Path) -> pd.DataFrame:
    """
    加载因子数据

    支持格式：
    - CSV: columns=['date', 'pair', 'factor_value']
    - Feather: 同上
    """
    if factor_file.suffix == '.csv':
        df = pd.read_csv(factor_file)
    elif factor_file.suffix == '.feather':
        df = pd.read_feather(factor_file)
    else:
        raise ValueError(f"不支持的文件格式: {factor_file.suffix}")

    df['date'] = pd.to_datetime(df['date'])
    return df


def load_pricing_data(data_dir: Path, pairs: List[str], timeframe: str = '15m') -> Dict[str, pd.DataFrame]:
    """
    加载价格数据

    格式：{pair: DataFrame(date, close)}
    """
    pricing_data = {}

    for pair in pairs:
        # 转换交易对格式：ETH/USDT:USDT -> ETH_USDT_USDT-15m-futures.feather
        pair_clean = pair.replace("/", "_").replace(":", "_")
        filename = f"{pair_clean}-{timeframe}-futures.feather"
        filepath = data_dir / filename

        if not filepath.exists():
            print(f"警告：未找到价格数据: {filepath}")
            continue

        df = pd.read_feather(filepath)
        df['date'] = pd.to_datetime(df['date'])
        pricing_data[pair] = df[['date', 'close']].set_index('date')

    return pricing_data


def main():
    parser = argparse.ArgumentParser(
        description="统一的因子分析工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--data-dir",
        required=True,
        type=Path,
        help="OHLCV 数据目录路径",
    )
    parser.add_argument(
        "--factor-file",
        required=True,
        type=Path,
        help="因子数据文件路径（CSV 或 Feather）",
    )
    parser.add_argument(
        "--analysis",
        default="all",
        help="分析类型（逗号分隔）：ic,turnover,returns,all",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("artifacts/factor_reports"),
        help="输出目录路径",
    )
    parser.add_argument(
        "--periods",
        default="1,5,10",
        help="前瞻期列表（逗号分隔，单位：K线数量）",
    )
    parser.add_argument(
        "--quantiles",
        type=int,
        default=5,
        help="分位数数量",
    )
    parser.add_argument(
        "--timeframe",
        default="15m",
        help="时间周期（默认 15m）",
    )

    args = parser.parse_args()

    try:
        # 1. 加载因子数据
        print(f"加载因子数据: {args.factor_file}")
        factor_data = load_factor_data(args.factor_file)
        print(f"  因子数据行数: {len(factor_data)}")
        print(f"  交易对数量: {factor_data['pair'].nunique()}")

        # 2. 加载价格数据
        unique_pairs = factor_data['pair'].unique().tolist()
        print(f"\n加载 {len(unique_pairs)} 个交易对的价格数据...")
        pricing_data = load_pricing_data(args.data_dir, unique_pairs, args.timeframe)
        print(f"  成功加载: {len(pricing_data)} 个交易对")

        if not pricing_data:
            print("错误：无法加载任何价格数据")
            return 1

        # 3. 解析参数
        periods = [int(p) for p in args.periods.split(",")]
        analysis_types = args.analysis.split(",")

        # 4. 创建分析器
        print(f"\n创建因子分析器...")
        analyzer = FactorAnalyzer(
            factor_data=factor_data,
            pricing_data=pricing_data,
            periods=periods,
            quantiles=args.quantiles,
        )

        # 5. 执行分析
        args.output_dir.mkdir(parents=True, exist_ok=True)

        if "all" in analysis_types:
            print(f"\n生成完整报告...")
            analyzer.create_full_report(args.output_dir)
        else:
            if "ic" in analysis_types:
                print(f"\n执行 IC 分析...")
                ic_result = analyzer.analyze_ic(args.output_dir)
                print(f"  IC 均值: {ic_result['ic_mean']}")

            if "returns" in analysis_types:
                print(f"\n执行收益分析...")
                returns_result = analyzer.analyze_returns(args.output_dir)
                print(f"  Long-Short 收益: {returns_result['mean_return_by_quantile']}")

            if "turnover" in analysis_types:
                print(f"\n执行换手率分析...")
                turnover_result = analyzer.analyze_turnover(args.output_dir)
                print(f"  平均换手率: {turnover_result['mean_turnover']}")

        # 6. 打印摘要
        print(f"\n" + "=" * 80)
        print("分析摘要")
        print("=" * 80)
        summary = analyzer.get_summary()
        for key, value in summary.items():
            print(f"{key}: {value}")

        print(f"\n报告已保存到: {args.output_dir}")
        return 0

    except Exception as e:
        print(f"错误: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
