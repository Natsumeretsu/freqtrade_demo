"""因子可视化工具

使用 plotly 生成交互式图表。
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots


class FactorVisualizer:
    """因子可视化工具

    生成因子分析的交互式图表。
    """

    def __init__(self):
        """初始化可视化工具"""
        pass

    def plot_ic_series(
        self, ic_series: pd.Series, title: str = "IC 时间序列"
    ) -> go.Figure:
        """绘制 IC 时间序列图

        Args:
            ic_series: IC 时间序列
            title: 图表标题

        Returns:
            plotly Figure 对象
        """
        fig = go.Figure()

        # 添加 IC 折线
        fig.add_trace(
            go.Scatter(
                x=ic_series.index,
                y=ic_series.values,
                mode="lines",
                name="IC",
                line={"color": "#1f77b4", "width": 2},
            )
        )

        # 添加零线
        fig.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.5)

        # 设置布局
        fig.update_layout(
            title=title,
            xaxis_title="时间",
            yaxis_title="IC 值",
            hovermode="x unified",
            template="plotly_white",
        )

        return fig

    def plot_group_returns(
        self, group_result: pd.DataFrame, title: str = "分组收益分析"
    ) -> go.Figure:
        """绘制分组收益柱状图

        Args:
            group_result: 分组回测结果
            title: 图表标题

        Returns:
            plotly Figure 对象
        """
        fig = go.Figure()

        # 添加平均收益柱状图
        fig.add_trace(
            go.Bar(
                x=group_result["group"],
                y=group_result["mean_return"] * 100,  # 转换为百分比
                name="平均收益",
                marker_color="#1f77b4",
            )
        )

        # 添加零线
        fig.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.5)

        # 设置布局
        fig.update_layout(
            title=title,
            xaxis_title="分组",
            yaxis_title="平均收益率 (%)",
            template="plotly_white",
        )

        return fig

    def plot_factor_distribution(
        self, factor_values: pd.Series, title: str = "因子值分布"
    ) -> go.Figure:
        """绘制因子值分布直方图

        Args:
            factor_values: 因子值序列
            title: 图表标题

        Returns:
            plotly Figure 对象
        """
        fig = go.Figure()

        # 添加直方图
        fig.add_trace(
            go.Histogram(
                x=factor_values.dropna(),
                nbinsx=50,
                name="因子分布",
                marker_color="#1f77b4",
            )
        )

        # 设置布局
        fig.update_layout(
            title=title,
            xaxis_title="因子值",
            yaxis_title="频数",
            template="plotly_white",
        )

        return fig

    def generate_report(
        self, evaluation_result: dict, output_path: str | Path
    ) -> None:
        """生成完整的 HTML 评估报告

        Args:
            evaluation_result: 评估结果字典
            output_path: 输出文件路径
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # 创建子图
        fig = make_subplots(
            rows=2,
            cols=1,
            subplot_titles=("分组收益分析", "因子值分布"),
            vertical_spacing=0.15,
        )

        # 添加分组收益图
        group_result = evaluation_result.get("group_backtest", pd.DataFrame())
        if not group_result.empty:
            fig.add_trace(
                go.Bar(
                    x=group_result["group"],
                    y=group_result["mean_return"] * 100,
                    name="平均收益",
                    marker_color="#1f77b4",
                ),
                row=1,
                col=1,
            )

        # 设置布局
        fig.update_layout(
            title="因子评估报告",
            height=800,
            template="plotly_white",
        )

        # 保存 HTML
        fig.write_html(str(output_path))

