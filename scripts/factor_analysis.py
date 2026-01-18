"""因子分析可视化脚本

分析因子（momentum_8h, volatility_24h, volume_surge）与交易结果的关系。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# 添加项目路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "integration"))

from data_pipeline import calculate_forward_returns, clean_ohlcv_data
from simple_factors.basic_factors import calculate_all_factors


def load_backtest_data(data_dir: Path, pair: str, timeframe: str) -> pd.DataFrame:
    """加载回测数据"""
    # 转换交易对格式：BTC/USDT:USDT -> BTC_USDT_USDT
    pair_filename = pair.replace("/", "_").replace(":", "_")
    # 期货数据在 futures 子目录下
    data_file = data_dir / "futures" / f"{pair_filename}-{timeframe}-futures.feather"

    if not data_file.exists():
        msg = f"数据文件不存在: {data_file}"
        raise FileNotFoundError(msg)

    df = pd.read_feather(data_file)
    return df


def analyze_factors(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """分析因子与未来收益的关系"""
    # 计算因子
    df = calculate_all_factors(df)

    # 计算未来收益
    df = calculate_forward_returns(df, periods=[1, 4, 8])

    # 移除 NaN 值
    df = df.dropna()

    # 分析每个因子
    results = {}

    for factor in ["momentum_8h", "volatility_24h", "volume_surge"]:
        # 按因子值分组（五分位）
        df[f"{factor}_quantile"] = pd.qcut(
            df[factor], q=5, labels=["Q1", "Q2", "Q3", "Q4", "Q5"], duplicates="drop"
        )

        # 计算每组的平均未来收益
        quantile_returns = (
            df.groupby(f"{factor}_quantile", observed=True)[
                ["forward_return_1p", "forward_return_4p", "forward_return_8p"]
            ]
            .mean()
            .reset_index()
        )

        results[factor] = quantile_returns

    return results


def plot_factor_analysis(results: dict[str, pd.DataFrame], output_file: Path) -> None:
    """绘制因子分析图表"""
    fig = make_subplots(
        rows=3,
        cols=1,
        subplot_titles=(
            "动量因子 (momentum_8h) vs 未来收益",
            "波动率因子 (volatility_24h) vs 未来收益",
            "成交量激增因子 (volume_surge) vs 未来收益",
        ),
        vertical_spacing=0.1,
    )

    factors = ["momentum_8h", "volatility_24h", "volume_surge"]
    colors = ["#1f77b4", "#ff7f0e", "#2ca02c"]

    for idx, factor in enumerate(factors, start=1):
        data = results[factor]

        # 添加三条线（1期、4期、8期未来收益）
        for period, color in zip([1, 4, 8], colors):
            fig.add_trace(
                go.Scatter(
                    x=data[f"{factor}_quantile"],
                    y=data[f"forward_return_{period}p"] * 100,  # 转换为百分比
                    mode="lines+markers",
                    name=f"{period}期未来收益",
                    line={"color": color, "width": 2},
                    marker={"size": 8},
                    legendgroup=f"period_{period}",
                    showlegend=(idx == 1),  # 只在第一个子图显示图例
                ),
                row=idx,
                col=1,
            )

        # 添加零线
        fig.add_hline(
            y=0,
            line_dash="dash",
            line_color="gray",
            opacity=0.5,
            row=idx,
            col=1,
        )

        # 设置 y 轴标签
        fig.update_yaxes(title_text="平均收益率 (%)", row=idx, col=1)

    # 设置布局
    fig.update_layout(
        title_text="因子分析：因子分位数 vs 未来收益",
        height=1200,
        showlegend=True,
        legend={
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.02,
            "xanchor": "right",
            "x": 1,
        },
    )

    # 保存图表
    fig.write_html(str(output_file))
    print(f"因子分析图表已保存: {output_file}")


def main() -> None:
    """主函数"""
    # 配置
    project_root = Path(__file__).parent.parent
    data_dir = project_root / "ft_userdir" / "data" / "okx"
    output_dir = project_root / "ft_userdir" / "plot"
    output_dir.mkdir(parents=True, exist_ok=True)

    pair = "BTC/USDT:USDT"
    timeframe = "5m"

    # 加载数据
    print(f"加载数据: {pair} {timeframe}")
    df = load_backtest_data(data_dir, pair, timeframe)
    print(f"数据行数: {len(df)}")

    # 分析因子
    print("分析因子...")
    results = analyze_factors(df)

    # 绘制图表
    output_file = output_dir / "factor-analysis.html"
    plot_factor_analysis(results, output_file)

    # 打印统计信息
    print("\n因子分析结果:")
    for factor, data in results.items():
        print(f"\n{factor}:")
        print(data.to_string(index=False))


if __name__ == "__main__":
    main()
