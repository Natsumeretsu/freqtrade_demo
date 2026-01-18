"""批量因子计算优化器

通过识别因子间的依赖关系和共享中间结果，优化批量计算性能。

核心优化策略：
1. 中间结果缓存：ret_1, rolling_mean, rolling_std 等
2. 批量计算相似因子：多个周期的 EMA、RSI 等
3. 依赖关系分析：按依赖顺序计算因子

创建日期: 2026-01-17
"""
from __future__ import annotations

import re
from typing import Dict, Set, List, Tuple
import pandas as pd
import numpy as np


class IntermediateResultCache:
    """中间结果缓存

    缓存常用的中间计算结果，避免重复计算。
    """

    def __init__(self):
        self._cache: Dict[str, pd.Series] = {}

    def get(self, key: str) -> pd.Series | None:
        """获取缓存的中间结果"""
        return self._cache.get(key)

    def set(self, key: str, value: pd.Series) -> None:
        """设置缓存的中间结果"""
        self._cache[key] = value

    def clear(self) -> None:
        """清空缓存"""
        self._cache.clear()

    def get_or_compute(self, key: str, compute_func) -> pd.Series:
        """获取或计算中间结果"""
        result = self.get(key)
        if result is None:
            result = compute_func()
            self.set(key, result)
        return result


class FactorDependencyAnalyzer:
    """因子依赖关系分析器

    分析因子间的依赖关系，识别可以批量计算的因子组。
    """

    # 因子类型正则表达式
    EMA_RE = re.compile(r"^(ema|ema_short|ema_long)_(\d+)$", re.IGNORECASE)
    RSI_RE = re.compile(r"^rsi_(\d+)$", re.IGNORECASE)
    CCI_RE = re.compile(r"^cci_(\d+)$", re.IGNORECASE)
    ATR_RE = re.compile(r"^atr_(\d+)$", re.IGNORECASE)
    VOL_RE = re.compile(r"^vol_(\d+)$", re.IGNORECASE)
    SKEW_RE = re.compile(r"^skew_(\d+)$", re.IGNORECASE)
    KURT_RE = re.compile(r"^kurt_(\d+)$", re.IGNORECASE)

    @classmethod
    def group_similar_factors(cls, factor_names: List[str]) -> Dict[str, List[Tuple[str, int]]]:
        """将相似的因子分组

        Returns:
            字典，键为因子类型，值为 (因子名, 周期) 的列表
        """
        groups: Dict[str, List[Tuple[str, int]]] = {
            'ema': [],
            'rsi': [],
            'cci': [],
            'atr': [],
            'vol': [],
            'skew': [],
            'kurt': [],
        }

        for name in factor_names:
            # EMA 因子
            m = cls.EMA_RE.match(name)
            if m:
                period = int(m.group(2))
                groups['ema'].append((name, period))
                continue

            # RSI 因子
            m = cls.RSI_RE.match(name)
            if m:
                period = int(m.group(1))
                groups['rsi'].append((name, period))
                continue

            # CCI 因子
            m = cls.CCI_RE.match(name)
            if m:
                period = int(m.group(1))
                groups['cci'].append((name, period))
                continue

            # ATR 因子
            m = cls.ATR_RE.match(name)
            if m:
                period = int(m.group(1))
                groups['atr'].append((name, period))
                continue

            # VOL 因子
            m = cls.VOL_RE.match(name)
            if m:
                period = int(m.group(1))
                groups['vol'].append((name, period))
                continue

            # SKEW 因子
            m = cls.SKEW_RE.match(name)
            if m:
                period = int(m.group(1))
                groups['skew'].append((name, period))
                continue

            # KURT 因子
            m = cls.KURT_RE.match(name)
            if m:
                period = int(m.group(1))
                groups['kurt'].append((name, period))
                continue

        # 移除空组
        return {k: v for k, v in groups.items() if v}

    @classmethod
    def identify_shared_dependencies(cls, factor_names: List[str]) -> Set[str]:
        """识别共享的依赖项

        Returns:
            共享依赖项的集合（如 'ret_1', 'close', 'volume'）
        """
        dependencies = set()

        # 检查是否需要 ret_1
        needs_ret1 = any(
            cls.VOL_RE.match(n) or cls.SKEW_RE.match(n) or cls.KURT_RE.match(n)
            for n in factor_names
        )
        if needs_ret1:
            dependencies.add('ret_1')

        # 检查是否需要 close
        if any(cls.EMA_RE.match(n) or cls.RSI_RE.match(n) for n in factor_names):
            dependencies.add('close')

        # 检查是否需要 high/low
        if any(cls.ATR_RE.match(n) or cls.CCI_RE.match(n) for n in factor_names):
            dependencies.add('high')
            dependencies.add('low')

        return dependencies


class BatchFactorComputer:
    """批量因子计算器

    使用中间结果缓存和批量计算优化因子计算性能。
    """

    def __init__(self):
        self._cache = IntermediateResultCache()
        self._analyzer = FactorDependencyAnalyzer()

    def compute_batch(
        self,
        data: pd.DataFrame,
        factor_names: List[str],
        compute_func
    ) -> Dict[str, pd.Series]:
        """批量计算因子

        Args:
            data: OHLCV 数据
            factor_names: 因子名称列表
            compute_func: 单因子计算函数

        Returns:
            因子名到因子值的字典
        """
        # 清空缓存
        self._cache.clear()

        # 预计算共享依赖项
        self._precompute_dependencies(data, factor_names)

        # 分组相似因子
        groups = self._analyzer.group_similar_factors(factor_names)

        # 批量计算结果
        results = {}

        # 批量计算 EMA 因子
        if 'ema' in groups:
            ema_results = self._batch_compute_ema(data, groups['ema'])
            results.update(ema_results)

        # 批量计算统计因子（vol, skew, kurt）
        if 'vol' in groups or 'skew' in groups or 'kurt' in groups:
            stat_results = self._batch_compute_stats(
                data, groups.get('vol', []), groups.get('skew', []), groups.get('kurt', [])
            )
            results.update(stat_results)

        # 其他因子使用原始计算函数
        remaining_factors = [
            name for name in factor_names
            if name not in results
        ]
        for name in remaining_factors:
            result = compute_func(data, name)
            if result is not None:
                results[name] = result

        return results

    def _precompute_dependencies(self, data: pd.DataFrame, factor_names: List[str]) -> None:
        """预计算共享依赖项"""
        dependencies = self._analyzer.identify_shared_dependencies(factor_names)

        # 预计算 ret_1
        if 'ret_1' in dependencies:
            close = data['close'].astype('float64')
            ret1 = close.pct_change(1)
            self._cache.set('ret_1', ret1)

        # 预计算 close
        if 'close' in dependencies:
            close = data['close'].astype('float64')
            self._cache.set('close', close)

        # 预计算 high/low
        if 'high' in dependencies:
            high = data['high'].astype('float64')
            self._cache.set('high', high)
        if 'low' in dependencies:
            low = data['low'].astype('float64')
            self._cache.set('low', low)

    def _batch_compute_ema(
        self,
        data: pd.DataFrame,
        ema_factors: List[Tuple[str, int]]
    ) -> Dict[str, pd.Series]:
        """批量计算 EMA 因子

        Args:
            data: OHLCV 数据
            ema_factors: (因子名, 周期) 的列表

        Returns:
            因子名到因子值的字典
        """
        import talib.abstract as ta

        results = {}
        close = self._cache.get('close')
        if close is None:
            close = data['close'].astype('float64')

        # 批量计算所有周期的 EMA
        for name, period in ema_factors:
            if period <= 0:
                continue
            ema = ta.EMA(data, timeperiod=period)
            results[name] = ema

        return results

    def _batch_compute_stats(
        self,
        data: pd.DataFrame,
        vol_factors: List[Tuple[str, int]],
        skew_factors: List[Tuple[str, int]],
        kurt_factors: List[Tuple[str, int]]
    ) -> Dict[str, pd.Series]:
        """批量计算统计因子（vol, skew, kurt）

        使用共享的 ret_1，一次性计算多个统计量。

        Args:
            data: OHLCV 数据
            vol_factors: vol 因子列表
            skew_factors: skew 因子列表
            kurt_factors: kurt 因子列表

        Returns:
            因子名到因子值的字典
        """
        results = {}

        # 获取或计算 ret_1
        ret1 = self._cache.get('ret_1')
        if ret1 is None:
            close = data['close'].astype('float64')
            ret1 = close.pct_change(1)
            self._cache.set('ret_1', ret1)

        # 批量计算 vol 因子
        for name, period in vol_factors:
            if period <= 0:
                continue
            vol = ret1.rolling(period).std()
            results[name] = vol

        # 批量计算 skew 因子
        for name, period in skew_factors:
            if period <= 0:
                continue
            skew = ret1.rolling(period).skew()
            results[name] = skew

        # 批量计算 kurt 因子
        for name, period in kurt_factors:
            if period <= 0:
                continue
            kurt = ret1.rolling(period).kurt()
            results[name] = kurt

        return results
