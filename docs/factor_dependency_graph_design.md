# 因子依赖图优化设计文档

**创建日期**: 2026-01-17

## 1. 概述

实现因子依赖图（Factor Dependency Graph）优化，通过分析因子间的依赖关系，优化计算顺序并支持并行计算。

## 2. 核心概念

### 2.1 问题分析

**当前问题**：
- 因子计算顺序未优化，可能重复计算
- 无法识别可并行计算的因子
- 依赖关系不明确，难以维护

**优化目标**：
- 构建因子依赖图（DAG）
- 使用拓扑排序优化计算顺序
- 识别并行计算机会
- 避免重复计算

### 2.2 依赖图基础

**有向无环图（DAG）**：
- 节点：因子
- 边：依赖关系（A → B 表示 B 依赖 A）
- 无环：不存在循环依赖

**示例**：
```
价格数据 → SMA_10 → MACD
         → SMA_20 ↗
         → RSI
```

## 3. 架构设计

### 3.1 核心组件

**1. DependencyGraph（依赖图）**
- 存储因子节点和依赖关系
- 检测循环依赖
- 提供图遍历接口

**2. TopologicalSorter（拓扑排序器）**
- Kahn 算法实现
- 返回优化的计算顺序
- 识别可并行计算的层级

**3. ParallelScheduler（并行调度器）**
- 将因子分组到计算层级
- 同一层级的因子可并行计算
- 管理计算资源

### 3.2 数据结构

**因子节点**：
```python
@dataclass
class FactorNode:
    name: str                    # 因子名称
    dependencies: List[str]      # 依赖的因子列表
    compute_func: Callable       # 计算函数
    cache_key: Optional[str]     # 缓存键
```

**依赖图**：
```python
class DependencyGraph:
    def __init__(self):
        self._nodes: Dict[str, FactorNode] = {}
        self._adjacency: Dict[str, Set[str]] = {}  # 邻接表
        self._in_degree: Dict[str, int] = {}       # 入度
```

## 4. 算法设计

### 4.1 拓扑排序（Kahn 算法）

**步骤**：
1. 计算所有节点的入度
2. 将入度为 0 的节点加入队列
3. 从队列取出节点，输出到结果
4. 将该节点的所有邻居节点入度减 1
5. 如果邻居节点入度变为 0，加入队列
6. 重复 3-5 直到队列为空

**时间复杂度**：O(V + E)，V 是节点数，E 是边数

### 4.2 层级划分

**目标**：将因子分组到不同层级，同一层级可并行计算

**算法**：
1. 第 0 层：无依赖的因子（入度为 0）
2. 第 i 层：依赖的因子都在第 0 到 i-1 层

**示例**：
```
层级 0: [价格数据]
层级 1: [SMA_10, SMA_20, RSI]  # 可并行
层级 2: [MACD]
```

## 5. 实现策略

### 5.1 P0 - 核心功能

1. **DependencyGraph 类**
   - add_factor() - 添加因子节点
   - add_dependency() - 添加依赖关系
   - detect_cycle() - 检测循环依赖
   - get_dependencies() - 获取因子依赖

2. **TopologicalSorter 类**
   - sort() - 拓扑排序
   - get_layers() - 获取计算层级
   - validate() - 验证图的有效性

3. **ParallelScheduler 类**
   - schedule() - 生成执行计划
   - execute() - 执行计算（串行版本）

### 5.2 P1 - 高级功能

4. **并行执行**
   - 使用 concurrent.futures.ThreadPoolExecutor
   - 层级内并行，层级间串行

5. **缓存集成**
   - 与现有缓存系统集成
   - 避免重复计算

## 6. 使用示例

```python
from trading_system.infrastructure.dependency import (
    DependencyGraph,
    TopologicalSorter,
    FactorNode
)

# 1. 构建依赖图
graph = DependencyGraph()

# 添加因子节点
graph.add_factor(FactorNode(
    name="price",
    dependencies=[],
    compute_func=load_price_data
))

graph.add_factor(FactorNode(
    name="sma_10",
    dependencies=["price"],
    compute_func=compute_sma_10
))

graph.add_factor(FactorNode(
    name="macd",
    dependencies=["sma_10", "sma_20"],
    compute_func=compute_macd
))

# 2. 拓扑排序
sorter = TopologicalSorter(graph)
order = sorter.sort()
# 结果: ['price', 'sma_10', 'sma_20', 'rsi', 'macd']

# 3. 获取计算层级
layers = sorter.get_layers()
# 结果: [[price], [sma_10, sma_20, rsi], [macd]]

# 4. 执行计算
scheduler = ParallelScheduler(graph)
results = scheduler.execute(data)
```

## 7. 性能优化

**优化点**：
1. 使用邻接表存储图（空间 O(V + E)）
2. Kahn 算法时间复杂度 O(V + E)
3. 层级内并行计算（理论加速比 = 层级内因子数）

**预期收益**：
- 避免重复计算：节省 20-30% 计算时间
- 并行计算：加速 2-3 倍（取决于因子数量）

---

**下一步**：实现 P0 核心功能（DependencyGraph + TopologicalSorter + ParallelScheduler）
