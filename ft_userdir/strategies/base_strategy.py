"""策略公共基类

提取所有策略的公共模式，减少代码重复。
"""
from __future__ import annotations

from abc import ABC
from datetime import datetime
import logging
from typing import Optional

import numpy as np
from pandas import DataFrame

from freqtrade.strategy import IStrategy


logger = logging.getLogger(__name__)


class BaseStrategy(IStrategy, ABC):
    """策略公共基类

    提供所有策略的公共属性和方法，子类只需实现特定逻辑。
    """

    # 接口版本（所有策略统一）
    INTERFACE_VERSION = 3

    # 默认风险管理参数（子类可覆盖）
    minimal_roi = {"0": 100}
    stoploss = -0.10

    # 默认信号处理标志
    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False

    # 默认启动蜡烛数
    startup_candle_count = 240

    def __init__(self, config: dict) -> None:
        """初始化策略

        Args:
            config: Freqtrade 配置字典
        """
        super().__init__(config)
        self._init_caches()

    def _init_caches(self) -> None:
        """初始化缓存字典

        子类可以覆盖此方法添加自定义缓存。
        """
        self._macro_inf_df: dict = {}  # 改为字典,按 pair+timeframe+timestamp 缓存
        self._gate_funnel_cache: dict = {}

    def _safe_dataframe_operation(
        self,
        dataframe: DataFrame,
        operation_name: str,
        operation_func,
        *args,
        **kwargs
    ) -> DataFrame:
        """安全执行 DataFrame 操作

        统一的异常处理包装器。

        Args:
            dataframe: 输入 DataFrame
            operation_name: 操作名称（用于日志）
            operation_func: 要执行的函数
            *args: 位置参数
            **kwargs: 关键字参数

        Returns:
            处理后的 DataFrame
        """
        try:
            return operation_func(dataframe, *args, **kwargs)
        except Exception as e:
            logger.error(f"{operation_name} 失败: {e}")
            return dataframe

    def _clean_dataframe(self, dataframe: DataFrame) -> DataFrame:
        """清理 DataFrame 中的无效值

        Args:
            dataframe: 输入 DataFrame

        Returns:
            清理后的 DataFrame
        """
        return dataframe.replace([np.inf, -np.inf], np.nan)


class TrendStrategy(BaseStrategy, ABC):
    """趋势策略基类

    为趋势跟踪策略提供公共配置和方法。
    """

    # 追踪止损配置
    trailing_stop = True
    trailing_stop_positive_offset = 0.06
    trailing_stop_positive = 0.04
    trailing_only_offset_is_reached = True

    # 保护机制
    protections = [
        {"method": "CooldownPeriod", "stop_duration_candles": 1},
        {
            "method": "StoplossGuard",
            "lookback_period_candles": 48,
            "trade_limit": 1,
            "stop_duration_candles": 12,
            "required_profit": 0.0,
            "only_per_pair": True,
            "only_per_side": False,
        },
        {
            "method": "MaxDrawdown",
            "lookback_period_candles": 96,
            "trade_limit": 2,
            "stop_duration_candles": 24,
            "max_allowed_drawdown": 0.25,
        },
    ]


class MacroFilteredStrategy(BaseStrategy, ABC):
    """带宏观过滤的策略基类

    提供宏观时间框架（如1d）的过滤功能。
    """

    # 宏观时间框架
    informative_timeframe = "1d"

    def informative_pairs(self):
        """返回需要的宏观时间框架数据对

        Returns:
            时间框架数据对列表
        """
        dp = getattr(self, "dp", None)
        if dp is None:
            return []
        return [(pair, self.informative_timeframe) for pair in dp.current_whitelist()]

    def _get_macro_dataframe(self, metadata: dict) -> Optional[DataFrame]:
        """获取宏观时间框架的 DataFrame

        使用缓存避免重复获取。

        Args:
            metadata: 交易对元数据

        Returns:
            宏观 DataFrame 或 None
        """
        # 生成缓存键 (pair + timeframe + 最新时间戳)
        if not dataframe.empty:
            cache_key = f"{metadata['pair']}_{self.informative_timeframe}_{dataframe['date'].iloc[-1]}"
        else:
            cache_key = f"{metadata['pair']}_{self.informative_timeframe}_empty"

        # 检查缓存
        if cache_key in self._macro_inf_df:
            return self._macro_inf_df[cache_key]

        dp = getattr(self, "dp", None)
        if dp is None:
            return None

        try:
            inf = dp.get_pair_dataframe(
                pair=metadata["pair"],
                timeframe=self.informative_timeframe
            )
            if inf is not None and not inf.empty:
                self._macro_inf_df[cache_key] = inf.copy()
                return self._macro_inf_df[cache_key]
        except Exception as e:
            logger.warning(f"获取宏观数据失败: {e}")

        return None
