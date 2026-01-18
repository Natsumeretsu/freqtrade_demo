"""
统一的因子分析接口

封装 Alphalens 功能，提供简洁的 API。
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Union

import pandas as pd
import alphalens
from alphalens import tears, plotting, performance, utils

from .alphalens_adapter import convert_to_alphalens_format


class FactorAnalyzer:
    """
    统一的因子分析器

    封装 Alphalens 的所有功能，提供简洁的接口。
    """

    def __init__(
        self,
        factor_data: pd.DataFrame,
        pricing_data: Dict[str, pd.DataFrame],
        periods: List[int] = [1, 5, 10],
        quantiles: int = 5,
    ):
        """
        初始化因子分析器

        参数：
            factor_data: 因子数据
            pricing_data: 价格数据字典
            periods: 前瞻期列表
            quantiles: 分位数数量
        """
        self.periods = periods
        self.quantiles = quantiles

        # 转换为 Alphalens 格式
        self.factor_data = convert_to_alphalens_format(
            factor_data=factor_data,
            pricing_data=pricing_data,
            periods=periods,
            quantiles=quantiles,
        )

    def analyze_ic(self, output_dir: Optional[Path] = None) -> Dict:
        """
        IC 分析

        返回：
            - ic_mean: IC 均值
            - ic_std: IC 标准差
            - ic_by_period: 各前瞻期的 IC
        """
        ic_data = performance.factor_information_coefficient(self.factor_data)

        result = {
            'ic_mean': ic_data.mean(),
            'ic_std': ic_data.std(),
            'ic_by_period': ic_data,
        }

        # 生成图表
        if output_dir:
            output_dir = Path(output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)

            plotting.plot_ic_ts(self.factor_data)
            import matplotlib.pyplot as plt
            plt.savefig(output_dir / 'ic_time_series.png')
            plt.close()

            plotting.plot_ic_hist(self.factor_data)
            plt.savefig(output_dir / 'ic_histogram.png')
            plt.close()

        return result

    def analyze_returns(self, output_dir: Optional[Path] = None) -> Dict:
        """
        收益分析

        返回：
            - mean_return_by_quantile: 各分位数的平均收益
            - cumulative_returns: 累计收益
        """
        mean_ret = performance.mean_return_by_quantile(
            self.factor_data,
            by_date=False,
            by_group=False,
        )

        result = {
            'mean_return_by_quantile': mean_ret[0],
            'std_return_by_quantile': mean_ret[1],
        }

        # 生成图表
        if output_dir:
            output_dir = Path(output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)

            plotting.plot_quantile_returns_bar(self.factor_data)
            import matplotlib.pyplot as plt
            plt.savefig(output_dir / 'quantile_returns.png')
            plt.close()

            plotting.plot_cumulative_returns(self.factor_data, period=self.periods[0])
            plt.savefig(output_dir / 'cumulative_returns.png')
            plt.close()

        return result

    def analyze_turnover(self, output_dir: Optional[Path] = None) -> Dict:
        """
        换手率分析

        返回：
            - turnover_by_quantile: 各分位数的换手率
        """
        turnover = performance.factor_rank_autocorrelation(self.factor_data)

        result = {
            'turnover': turnover,
            'mean_turnover': turnover.mean(),
        }

        # 生成图表
        if output_dir:
            output_dir = Path(output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)

            plotting.plot_turnover_table(self.factor_data)
            import matplotlib.pyplot as plt
            plt.savefig(output_dir / 'turnover_table.png')
            plt.close()

        return result

    def create_full_report(self, output_dir: Path) -> None:
        """
        生成完整的分析报告

        包括：
        - IC 分析
        - 收益分析
        - 换手率分析
        - 完整的 tear sheet
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # 生成完整的 tear sheet
        tears.create_full_tear_sheet(self.factor_data)

        import matplotlib.pyplot as plt
        plt.savefig(output_dir / 'full_tear_sheet.png', dpi=150, bbox_inches='tight')
        plt.close()

        print(f"完整报告已保存到: {output_dir}")

    def get_summary(self) -> Dict:
        """
        获取分析摘要

        返回：
            - ic_mean: IC 均值
            - ic_std: IC 标准差
            - mean_return: 平均收益
            - sharpe_ratio: Sharpe 比率
        """
        ic_data = performance.factor_information_coefficient(self.factor_data)
        mean_ret = performance.mean_return_by_quantile(
            self.factor_data,
            by_date=False,
            by_group=False,
        )

        # 计算 long-short 收益
        top_quantile = mean_ret[0].iloc[-1]
        bottom_quantile = mean_ret[0].iloc[0]
        long_short_return = top_quantile - bottom_quantile

        return {
            'ic_mean': ic_data.mean().to_dict(),
            'ic_std': ic_data.std().to_dict(),
            'long_short_return': long_short_return.to_dict(),
            'top_quantile_return': top_quantile.to_dict(),
            'bottom_quantile_return': bottom_quantile.to_dict(),
        }
