"""增量计算引擎

只计算新增数据点，避免重复计算历史数据。

核心组件：
1. StateManager - 状态管理器
2. IncrementalComputer - 增量计算器
3. FactorState - 因子状态

创建日期: 2026-01-17
"""
from __future__ import annotations

from dataclasses import dataclass, field
from collections import deque
from typing import Dict, Optional, Any
import pandas as pd
import numpy as np


@dataclass
class FactorState:
    """因子状态

    存储因子计算所需的状态信息。
    """
    factor_name: str                          # 因子名称
    last_timestamp: Optional[int] = None      # 最后计算时间戳
    last_value: Optional[float] = None        # 最后计算值

    # A类因子（简单增量）状态
    ema_value: Optional[float] = None         # EMA 当前值

    # B类因子（窗口增量）状态
    window_buffer: deque = field(default_factory=deque)  # 窗口缓冲区
    window_sum: float = 0.0                   # 窗口和

    # 滚动统计状态（Welford 算法）
    count: int = 0                            # 样本数
    mean: float = 0.0                         # 均值
    m2: float = 0.0                           # 二阶矩

    # 元数据
    metadata: Dict[str, Any] = field(default_factory=dict)


class StateManager:
    """状态管理器

    管理所有因子的状态，支持保存、加载和清空。
    """

    def __init__(self):
        self._states: Dict[str, FactorState] = {}

    def get_state(self, factor_name: str) -> Optional[FactorState]:
        """获取因子状态"""
        return self._states.get(factor_name)

    def set_state(self, factor_name: str, state: FactorState) -> None:
        """设置因子状态"""
        self._states[factor_name] = state

    def has_state(self, factor_name: str) -> bool:
        """检查是否存在因子状态"""
        return factor_name in self._states

    def clear_state(self, factor_name: Optional[str] = None) -> None:
        """清空状态

        Args:
            factor_name: 因子名称，如果为 None 则清空所有状态
        """
        if factor_name is None:
            self._states.clear()
        elif factor_name in self._states:
            del self._states[factor_name]

    def get_all_states(self) -> Dict[str, FactorState]:
        """获取所有状态"""
        return self._states.copy()


class IncrementalComputer:
    """增量计算器

    实现各类因子的增量计算逻辑。
    """

    def __init__(self, state_manager: StateManager):
        self._state_manager = state_manager

    def update_ema(self, factor_name: str, new_price: float, period: int) -> float:
        """增量更新 EMA

        Args:
            factor_name: 因子名称
            new_price: 新价格
            period: EMA 周期

        Returns:
            新的 EMA 值
        """
        state = self._state_manager.get_state(factor_name)
        if state is None:
            # 初始化状态
            state = FactorState(factor_name=factor_name, ema_value=new_price)
            self._state_manager.set_state(factor_name, state)
            return new_price

        # 增量计算
        alpha = 2.0 / (period + 1)
        new_ema = alpha * new_price + (1 - alpha) * state.ema_value
        state.ema_value = new_ema
        state.last_value = new_ema
        return new_ema

    def update_sma(self, factor_name: str, new_price: float, period: int) -> float:
        """增量更新 SMA

        Args:
            factor_name: 因子名称
            new_price: 新价格
            period: SMA 周期

        Returns:
            新的 SMA 值
        """
        state = self._state_manager.get_state(factor_name)
        if state is None:
            # 初始化状态
            state = FactorState(factor_name=factor_name)
            state.window_buffer = deque(maxlen=period)
            self._state_manager.set_state(factor_name, state)

        # 增量计算
        # 如果窗口已满，需要先减去即将被移除的旧值
        if len(state.window_buffer) == period:
            old_price = state.window_buffer[0]
            state.window_sum -= old_price

        state.window_buffer.append(new_price)
        state.window_sum += new_price

        sma = state.window_sum / len(state.window_buffer)
        state.last_value = sma
        return sma
