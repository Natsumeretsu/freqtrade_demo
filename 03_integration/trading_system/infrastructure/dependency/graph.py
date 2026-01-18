"""因子依赖图

构建和管理因子之间的依赖关系。

创建日期: 2026-01-17
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


@dataclass
class FactorNode:
    """因子节点

    Attributes:
        name: 因子名称
        dependencies: 依赖的因子列表
        compute_func: 计算函数
        cache_key: 缓存键（可选）
    """
    name: str
    dependencies: List[str]
    compute_func: Optional[Callable] = None
    cache_key: Optional[str] = None


class DependencyGraph:
    """因子依赖图

    使用邻接表存储有向无环图（DAG）。
    """

    def __init__(self):
        """初始化依赖图"""
        self._nodes: Dict[str, FactorNode] = {}
        self._adjacency: Dict[str, Set[str]] = {}  # 邻接表：factor -> {依赖它的因子}
        self._in_degree: Dict[str, int] = {}       # 入度：factor -> 依赖数量

    def add_factor(self, node: FactorNode) -> None:
        """添加因子节点

        Args:
            node: 因子节点

        Raises:
            ValueError: 如果因子已存在且不是占位符节点
        """
        # 检查是否已存在
        if node.name in self._nodes:
            existing = self._nodes[node.name]
            # 如果已存在的是占位符节点（无计算函数且无依赖），允许更新
            if existing.compute_func is not None or existing.dependencies:
                raise ValueError(f"因子 '{node.name}' 已存在")
            # 更新占位符节点
            logger.debug(f"更新占位符节点: {node.name}")

        # 添加或更新节点
        old_in_degree = self._in_degree.get(node.name, 0)
        self._nodes[node.name] = node

        if node.name not in self._adjacency:
            self._adjacency[node.name] = set()

        self._in_degree[node.name] = len(node.dependencies)

        # 添加依赖关系
        for dep in node.dependencies:
            if dep not in self._nodes:
                # 自动创建依赖节点（无计算函数）
                self._nodes[dep] = FactorNode(name=dep, dependencies=[])
                self._adjacency[dep] = set()
                self._in_degree[dep] = 0

            self._adjacency[dep].add(node.name)

        logger.debug(f"添加因子: {node.name}, 依赖: {node.dependencies}")

    def get_node(self, name: str) -> Optional[FactorNode]:
        """获取因子节点

        Args:
            name: 因子名称

        Returns:
            因子节点，如果不存在返回 None
        """
        return self._nodes.get(name)

    def get_dependencies(self, name: str) -> List[str]:
        """获取因子的依赖列表

        Args:
            name: 因子名称

        Returns:
            依赖的因子名称列表
        """
        node = self._nodes.get(name)
        return node.dependencies if node else []

    def get_dependents(self, name: str) -> Set[str]:
        """获取依赖该因子的因子列表

        Args:
            name: 因子名称

        Returns:
            依赖该因子的因子名称集合
        """
        return self._adjacency.get(name, set()).copy()

    def detect_cycle(self) -> Optional[List[str]]:
        """检测循环依赖

        使用 DFS 检测图中是否存在环。

        Returns:
            如果存在环，返回环路径；否则返回 None
        """
        visited = set()
        rec_stack = set()
        path = []

        def dfs(node: str) -> Optional[List[str]]:
            visited.add(node)
            rec_stack.add(node)
            path.append(node)

            for neighbor in self._adjacency.get(node, []):
                if neighbor not in visited:
                    cycle = dfs(neighbor)
                    if cycle:
                        return cycle
                elif neighbor in rec_stack:
                    # 找到环
                    cycle_start = path.index(neighbor)
                    return path[cycle_start:] + [neighbor]

            path.pop()
            rec_stack.remove(node)
            return None

        for node in self._nodes:
            if node not in visited:
                cycle = dfs(node)
                if cycle:
                    logger.error(f"检测到循环依赖: {' -> '.join(cycle)}")
                    return cycle

        return None

    def get_all_factors(self) -> List[str]:
        """获取所有因子名称

        Returns:
            因子名称列表
        """
        return list(self._nodes.keys())

    def get_in_degree(self, name: str) -> int:
        """获取因子的入度

        Args:
            name: 因子名称

        Returns:
            入度（依赖数量）
        """
        return self._in_degree.get(name, 0)

    def __len__(self) -> int:
        """返回因子数量"""
        return len(self._nodes)

    def __contains__(self, name: str) -> bool:
        """检查因子是否存在"""
        return name in self._nodes
