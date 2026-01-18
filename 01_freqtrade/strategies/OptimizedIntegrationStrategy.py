"""
OptimizedIntegrationStrategy - 完整优化功能集成示例

本策略展示如何集成所有优化功能：
- P0.1: 因子缓存
- P2.1: 并行计算
- P2.2: 数据预加载
- P2.3: 内存优化
- P1.1: 策略基类

创建日期: 2026-01-17
"""

from datetime import datetime
from typing import Optional

import pandas as pd
from pandas import DataFrame

from freqtrade.strategy import IStrategy

# 导入优化模块
from trading_system.infrastructure.factor_engines.talib_engine import (
    TalibFactorEngine,
    TalibEngineParams,
)
from trading_system.infrastructure.factor_engines.factor_cache import FactorCache
from trading_system.infrastructure.factor_engines.parallel_computer import (
    ParallelConfig,
)
from trading_system.infrastructure.data_preloader import (
    PreloadConfig,
    DataPreloader,
)
from trading_system.infrastructure.memory_optimizer import (
    MemoryConfig,
    MemoryOptimizer,
)


class OptimizedIntegrationStrategy(IStrategy):
    """
    完整优化功能集成示例策略

    优化功能：
    1. 因子缓存 - 减少重复计算
    2. 并行计算 - 加速因子计算
    3. 数据预加载 - 减少 I/O 操作
    4. 内存优化 - 降低内存占用
    """

    # Freqtrade 基本配置
    INTERFACE_VERSION = 3
    minimal_roi = {"0": 0.10}
    stoploss = -0.10
    timeframe = '1h'

    def __init__(self, config: dict) -> None:
        super().__init__(config)

        # 1. 初始化因子缓存（P0.1）
        self._factor_cache = FactorCache(max_size=1000)
        print(f"✓ 因子缓存已初始化: max_size=1000")

        # 2. 初始化并行计算配置（P2.1）
        parallel_config = ParallelConfig(
            enabled=True,
            max_workers=4,  # 根据 CPU 核心数调整
            use_processes=True,
            min_factors_for_parallel=5,
        )
        print(f"✓ 并行计算已配置: max_workers=4, use_processes=True")

        # 3. 初始化因子引擎（带缓存和并行计算）
        engine_params = TalibEngineParams()
        self._factor_engine = TalibFactorEngine(
            params=engine_params,
            cache=self._factor_cache,
            parallel_config=parallel_config,
        )
        print(f"✓ 因子引擎已初始化（带缓存和并行计算）")

        # 4. 初始化数据预加载器（P2.2）
        preload_config = PreloadConfig(
            enabled=True,
            cache_size=100,
            ttl_seconds=3600,  # 1 小时
        )
        self._preloader = DataPreloader(preload_config)
        print(f"✓ 数据预加载器已初始化: cache_size=100, ttl=3600s")

        # 5. 初始化内存优化器（P2.3）
        memory_config = MemoryConfig(
            enabled=True,
            downcast_numeric=False,  # 实盘环境保持精度
            use_categorical=True,
        )
        self._memory_optimizer = MemoryOptimizer(memory_config)
        print(f"✓ 内存优化器已初始化: downcast_numeric=False")

        # 定义需要计算的因子列表
        self._factor_names = [
            'ema_short_10',
            'ema_long_50',
            'rsi_14',
            'bb_width_20_2',
            'adx_14',
            'atr_14',
            'volume_ratio_72',
        ]
        print(f"✓ 因子列表已定义: {len(self._factor_names)} 个因子")

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        计算技术指标（集成所有优化功能）
        """
        pair = metadata.get('pair', 'UNKNOWN')

        # 设置因子引擎的上下文（用于缓存键生成）
        self._factor_engine.set_context(pair=pair, timeframe=self.timeframe)

        # 数据加载前记录内存使用
        memory_before = dataframe.memory_usage(deep=True).sum() / 1024**2

        # 应用内存优化（P2.3）
        dataframe = self._memory_optimizer.optimize_dataframe(dataframe)
        memory_after = dataframe.memory_usage(deep=True).sum() / 1024**2
        memory_reduction = (1 - memory_after / memory_before) * 100

        print(f"[{pair}] 内存优化: {memory_before:.1f}MB → {memory_after:.1f}MB "
              f"(减少 {memory_reduction:.1f}%)")

        # 使用因子引擎计算因子（带缓存和并行计算）
        try:
            factors_df = self._factor_engine.compute(dataframe, self._factor_names)

            # 将因子合并到 dataframe
            for col in factors_df.columns:
                dataframe[col] = factors_df[col]

            # 获取缓存统计
            cache_stats = self._factor_cache.get_stats()
            print(f"[{pair}] 因子计算完成: {len(self._factor_names)} 个因子")
            print(f"[{pair}] 缓存命中率: {cache_stats['hit_rate']:.2%}, "
                  f"缓存大小: {cache_stats['size']}/{cache_stats['max_size']}")

        except Exception as e:
            print(f"[{pair}] 因子计算失败: {e}")

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        定义入场信号
        """
        dataframe.loc[
            (
                # 趋势条件：短期 EMA 上穿长期 EMA
                (dataframe['ema_short_10'] > dataframe['ema_long_50']) &
                # 动量条件：RSI 在合理区间
                (dataframe['rsi_14'] > 30) &
                (dataframe['rsi_14'] < 70) &
                # 波动率条件：ADX 显示趋势强度
                (dataframe['adx_14'] > 20) &
                # 成交量条件：成交量放大
                (dataframe['volume_ratio_72'] > 1.2)
            ),
            'enter_long'] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        定义出场信号
        """
        dataframe.loc[
            (
                # 趋势反转：短期 EMA 下穿长期 EMA
                (dataframe['ema_short_10'] < dataframe['ema_long_50']) |
                # 超买：RSI 过高
                (dataframe['rsi_14'] > 70)
            ),
            'exit_long'] = 1

        return dataframe
