"""并行化因子计算模块

提供多进程/多线程并行计算因子的能力，提升大规模因子计算性能。
"""
from __future__ import annotations

import logging
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Callable, Optional

import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class ParallelConfig:
    """并行计算配置"""
    enabled: bool = True  # 是否启用并行计算
    max_workers: Optional[int] = None  # 最大工作进程数（None = CPU 核心数）
    use_processes: bool = True  # True=多进程，False=多线程
    min_factors_for_parallel: int = 10  # 最少因子数才启用并行（避免小任务开销）
    min_rows_for_processes: int = 5000  # 最少数据行数才使用多进程（小数据集用线程）
    chunk_size: int = 3  # 每个工作进程处理的因子数


class ParallelFactorComputer:
    """并行因子计算器

    将因子计算任务分配到多个进程/线程中并行执行。
    """

    def __init__(self, config: Optional[ParallelConfig] = None):
        self._config = config or ParallelConfig()

    def compute_parallel(
        self,
        data: pd.DataFrame,
        factor_names: list[str],
        compute_func: Callable[[pd.DataFrame, str], pd.Series],
    ) -> dict[str, pd.Series]:
        """并行计算多个因子

        Args:
            data: OHLCV 数据
            factor_names: 因子名称列表
            compute_func: 单个因子计算函数 (data, factor_name) -> Series

        Returns:
            因子名称到 Series 的字典
        """
        # 检查是否满足并行条件
        if not self._config.enabled or len(factor_names) < self._config.min_factors_for_parallel:
            # 不满足并行条件，使用串行计算
            logger.debug(f"使用串行计算: enabled={self._config.enabled}, factors={len(factor_names)}")
            return self._compute_serial(data, factor_names, compute_func)

        # 数据量自适应：小数据集使用线程，大数据集使用进程
        data_rows = len(data)
        use_processes = self._config.use_processes and data_rows >= self._config.min_rows_for_processes

        if not use_processes and self._config.use_processes:
            logger.debug(f"数据量较小({data_rows}行)，自动切换到线程模式")

        try:
            if use_processes:
                return self._compute_with_processes(data, factor_names, compute_func)
            else:
                return self._compute_with_threads(data, factor_names, compute_func)
        except Exception as e:
            logger.warning(f"并行计算失败，回退到串行: {e}")
            return self._compute_serial(data, factor_names, compute_func)

    def _compute_serial(
        self,
        data: pd.DataFrame,
        factor_names: list[str],
        compute_func: Callable[[pd.DataFrame, str], pd.Series],
    ) -> dict[str, pd.Series]:
        """串行计算（回退方案）"""
        results = {}
        for factor_name in factor_names:
            try:
                results[factor_name] = compute_func(data, factor_name)
            except Exception as e:
                logger.error(f"计算因子 {factor_name} 失败: {e}")
                results[factor_name] = pd.Series(index=data.index, dtype=float)
        return results

    def _compute_with_processes(
        self,
        data: pd.DataFrame,
        factor_names: list[str],
        compute_func: Callable[[pd.DataFrame, str], pd.Series],
    ) -> dict[str, pd.Series]:
        """使用多进程并行计算"""
        results = {}

        with ProcessPoolExecutor(max_workers=self._config.max_workers) as executor:
            # 提交所有任务
            future_to_factor = {
                executor.submit(_compute_single_factor, data, factor_name, compute_func): factor_name
                for factor_name in factor_names
            }

            # 收集结果
            for future in as_completed(future_to_factor):
                factor_name = future_to_factor[future]
                try:
                    results[factor_name] = future.result()
                except Exception as e:
                    logger.error(f"计算因子 {factor_name} 失败: {e}")
                    results[factor_name] = pd.Series(index=data.index, dtype=float)

        return results

    def _compute_with_threads(
        self,
        data: pd.DataFrame,
        factor_names: list[str],
        compute_func: Callable[[pd.DataFrame, str], pd.Series],
    ) -> dict[str, pd.Series]:
        """使用多线程并行计算（适用于 I/O 密集型任务）"""
        results = {}

        with ThreadPoolExecutor(max_workers=self._config.max_workers) as executor:
            # 提交所有任务
            future_to_factor = {
                executor.submit(compute_func, data, factor_name): factor_name
                for factor_name in factor_names
            }

            # 收集结果
            for future in as_completed(future_to_factor):
                factor_name = future_to_factor[future]
                try:
                    results[factor_name] = future.result()
                except Exception as e:
                    logger.error(f"计算因子 {factor_name} 失败: {e}")
                    results[factor_name] = pd.Series(index=data.index, dtype=float)

        return results


def _compute_single_factor(
    data: pd.DataFrame,
    factor_name: str,
    compute_func: Callable[[pd.DataFrame, str], pd.Series],
) -> pd.Series:
    """单个因子计算（用于多进程）

    注意：此函数必须在模块顶层定义，以便 pickle 序列化。
    """
    return compute_func(data, factor_name)
