"""并行调度器

管理因子的并行计算调度。

创建日期: 2026-01-17
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from .graph import DependencyGraph
from .sorter import TopologicalSorter

logger = logging.getLogger(__name__)


class ParallelScheduler:
    """并行调度器

    根据因子依赖图生成执行计划，并支持串行/并行执行。
    """

    def __init__(self, graph: DependencyGraph):
        """初始化调度器

        Args:
            graph: 因子依赖图
        """
        self.graph = graph
        self.sorter = TopologicalSorter(graph)

    def schedule(self) -> List[List[str]]:
        """生成执行计划

        Returns:
            执行计划（层级列表）
        """
        return self.sorter.get_layers()

    def execute(self, data: Any, cache: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """执行因子计算（串行版本）

        Args:
            data: 输入数据
            cache: 缓存字典（可选）

        Returns:
            计算结果字典 {因子名称: 计算结果}
        """
        if cache is None:
            cache = {}

        results = {}
        layers = self.schedule()

        logger.info(f"开始执行因子计算，共 {len(layers)} 个层级")

        for layer_idx, layer in enumerate(layers):
            logger.debug(f"执行第 {layer_idx + 1} 层级: {layer}")

            for factor_name in layer:
                # 检查缓存
                if factor_name in cache:
                    results[factor_name] = cache[factor_name]
                    logger.debug(f"  从缓存加载: {factor_name}")
                    continue

                # 获取因子节点
                node = self.graph.get_node(factor_name)
                if not node or not node.compute_func:
                    logger.warning(f"  跳过因子（无计算函数）: {factor_name}")
                    continue

                # 准备依赖数据
                dep_data = {dep: results.get(dep) for dep in node.dependencies}

                # 执行计算
                try:
                    result = node.compute_func(data, **dep_data)
                    results[factor_name] = result
                    logger.debug(f"  计算完成: {factor_name}")
                except Exception as e:
                    logger.error(f"  计算失败: {factor_name}, 错误: {e}")
                    raise

        logger.info(f"因子计算完成，共计算 {len(results)} 个因子")
        return results
