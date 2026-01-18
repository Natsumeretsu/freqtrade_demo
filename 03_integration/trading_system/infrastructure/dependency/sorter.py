"""拓扑排序器

使用 Kahn 算法对因子依赖图进行拓扑排序。

创建日期: 2026-01-17
"""
from __future__ import annotations

import logging
from collections import deque
from typing import List

from .graph import DependencyGraph

logger = logging.getLogger(__name__)


class TopologicalSorter:
    """拓扑排序器

    使用 Kahn 算法对因子依赖图进行拓扑排序，
    并识别可并行计算的层级。
    """

    def __init__(self, graph: DependencyGraph):
        """初始化排序器

        Args:
            graph: 因子依赖图
        """
        self.graph = graph

    def validate(self) -> bool:
        """验证图的有效性

        Returns:
            如果图有效（无环）返回 True，否则返回 False
        """
        cycle = self.graph.detect_cycle()
        if cycle:
            logger.error(f"图包含循环依赖: {' -> '.join(cycle)}")
            return False
        return True

    def sort(self) -> List[str]:
        """拓扑排序（Kahn 算法）

        Returns:
            排序后的因子名称列表

        Raises:
            ValueError: 如果图包含循环依赖
        """
        if not self.validate():
            raise ValueError("图包含循环依赖，无法进行拓扑排序")

        # 复制入度字典（避免修改原图）
        in_degree = {name: self.graph.get_in_degree(name) 
                     for name in self.graph.get_all_factors()}

        # 初始化队列：入度为 0 的节点
        queue = deque([name for name, degree in in_degree.items() if degree == 0])
        result = []

        while queue:
            # 取出入度为 0 的节点
            current = queue.popleft()
            result.append(current)

            # 更新邻居节点的入度
            for neighbor in self.graph.get_dependents(current):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        # 检查是否所有节点都被访问
        if len(result) != len(self.graph):
            raise ValueError("拓扑排序失败：图可能包含循环依赖")

        logger.debug(f"拓扑排序结果: {result}")
        return result

    def get_layers(self) -> List[List[str]]:
        """获取计算层级

        将因子分组到不同层级，同一层级的因子可以并行计算。

        Returns:
            层级列表，每个层级包含可并行计算的因子名称列表

        Raises:
            ValueError: 如果图包含循环依赖
        """
        if not self.validate():
            raise ValueError("图包含循环依赖，无法划分层级")

        # 复制入度字典
        in_degree = {name: self.graph.get_in_degree(name) 
                     for name in self.graph.get_all_factors()}

        layers = []
        remaining = set(self.graph.get_all_factors())

        while remaining:
            # 当前层级：入度为 0 的节点
            current_layer = [name for name in remaining if in_degree[name] == 0]
            
            if not current_layer:
                raise ValueError("无法划分层级：图可能包含循环依赖")

            layers.append(current_layer)

            # 从剩余节点中移除当前层级
            for name in current_layer:
                remaining.remove(name)
                # 更新依赖该节点的节点的入度
                for neighbor in self.graph.get_dependents(name):
                    in_degree[neighbor] -= 1

        logger.debug(f"层级划分结果: {layers}")
        return layers
