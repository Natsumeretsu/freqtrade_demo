"""技术指标因子

包含基于技术分析的因子实现。
"""

from __future__ import annotations

import pandas as pd

from integration.factor_library.base import BaseFactor
from integration.factor_library.registry import register_factor


@register_factor
class MomentumFactor(BaseFactor):
    """动量因子

    计算指定窗口期的价格变化率。
    """

    def __init__(self, window: int = 96):
        """初始化动量因子

        Args:
            window: 回看窗口（K线数量），默认96（8小时@5m）
        """
        self.window = window
        super().__init__(window=window)

    @property
    def name(self) -> str:
        return f"momentum_{self.window // 12}h"

    @property
    def description(self) -> str:
        return f"{self.window // 12}小时动量因子（价格变化率）"

    @property
    def category(self) -> str:
        return "technical"

    def calculate(self, df: pd.DataFrame) -> pd.Series:
        """计算动量因子

        Args:
            df: OHLCV 数据框

        Returns:
            动量因子值（价格变化率）
        """
        return df["close"].pct_change(self.window)

    def _validate_params(self) -> None:
        """验证参数"""
        if self.window <= 0:
            msg = f"window 必须大于0，当前值: {self.window}"
            raise ValueError(msg)


@register_factor
class VolatilityFactor(BaseFactor):
    """波动率因子

    计算指定窗口期的价格波动率（标准差）。
    """

    def __init__(self, window: int = 288):
        """初始化波动率因子

        Args:
            window: 回看窗口（K线数量），默认288（24小时@5m）
        """
        self.window = window
        super().__init__(window=window)

    @property
    def name(self) -> str:
        return f"volatility_{self.window // 12}h"

    @property
    def description(self) -> str:
        return f"{self.window // 12}小时波动率因子（收益率标准差）"

    @property
    def category(self) -> str:
        return "technical"

    def calculate(self, df: pd.DataFrame) -> pd.Series:
        """计算波动率因子

        Args:
            df: OHLCV 数据框

        Returns:
            波动率因子值（收益率标准差）
        """
        returns = df["close"].pct_change()
        return returns.rolling(window=self.window).std()

    def _validate_params(self) -> None:
        """验证参数"""
        if self.window <= 1:
            msg = f"window 必须大于1，当前值: {self.window}"
            raise ValueError(msg)


@register_factor
class VolumeSurgeFactor(BaseFactor):
    """成交量激增因子

    检测成交量相对于历史均值的激增程度。
    """

    def __init__(self, window: int = 96, threshold: float = 2.0):
        """初始化成交量激增因子

        Args:
            window: 回看窗口（K线数量），默认96（8小时@5m）
            threshold: 激增阈值（倍数），默认2.0
        """
        self.window = window
        self.threshold = threshold
        super().__init__(window=window, threshold=threshold)

    @property
    def name(self) -> str:
        return "volume_surge"

    @property
    def description(self) -> str:
        return f"成交量激增因子（当前成交量 / {self.window}期均值）"

    @property
    def category(self) -> str:
        return "volume"

    def calculate(self, df: pd.DataFrame) -> pd.Series:
        """计算成交量激增因子

        Args:
            df: OHLCV 数据框

        Returns:
            成交量激增因子值（当前成交量 / 历史均值）
        """
        volume_ma = df["volume"].rolling(window=self.window).mean()
        return df["volume"] / volume_ma

    def _validate_params(self) -> None:
        """验证参数"""
        if self.window <= 0:
            msg = f"window 必须大于0，当前值: {self.window}"
            raise ValueError(msg)
        if self.threshold <= 0:
            msg = f"threshold 必须大于0，当前值: {self.threshold}"
            raise ValueError(msg)

