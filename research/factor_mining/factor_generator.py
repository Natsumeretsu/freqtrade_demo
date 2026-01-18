"""因子生成器

批量生成候选因子用于研究和测试。
"""

from __future__ import annotations

import sys
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / "integration"))

from factor_library import list_all_factors


class FactorGenerator:
    """因子生成器

    用于批量生成不同参数的候选因子。
    """

    def __init__(self):
        """初始化因子生成器"""
        pass

    def generate_momentum_factors(
        self, windows: list[int] | None = None
    ) -> list[str]:
        """生成不同窗口的动量因子

        Args:
            windows: 窗口列表（K线数量），默认 [12, 24, 48, 72, 96, 144, 288]

        Returns:
            因子名称列表
        """
        if windows is None:
            windows = [12, 24, 48, 72, 96, 144, 288]

        factor_names = []
        for window in windows:
            # 转换为小时数（假设 5 分钟 K 线）
            hours = window // 12
            factor_names.append(f"momentum_{hours}h")

        return factor_names

    def generate_volatility_factors(
        self, windows: list[int] | None = None
    ) -> list[str]:
        """生成不同窗口的波动率因子

        Args:
            windows: 窗口列表（K线数量），默认 [24, 48, 96, 144, 288]

        Returns:
            因子名称列表
        """
        if windows is None:
            windows = [24, 48, 96, 144, 288]

        factor_names = []
        for window in windows:
            hours = window // 12
            factor_names.append(f"volatility_{hours}h")

        return factor_names

    def generate_volume_factors(self) -> list[str]:
        """生成成交量相关因子

        Returns:
            因子名称列表
        """
        return ["volume_surge"]

    def generate_all_factors(self) -> list[str]:
        """批量生成所有候选因子

        自动从因子库中获取所有已注册因子的名称。

        Returns:
            所有因子名称列表
        """
        # 从因子注册表获取所有已注册因子
        all_factor_names = list_all_factors()
        return all_factor_names
