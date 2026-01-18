# ARC 智能缓存淘汰策略设计文档

**创建日期**: 2026-01-17

## 1. 概述

实现 ARC (Adaptive Replacement Cache) 算法，结合访问频率和计算成本，智能决定缓存淘汰策略。

## 2. 核心概念

### 2.1 ARC 算法原理

ARC 维护 4 个列表：

```
T1: 最近访问一次的页面（LRU 部分）
T2: 最近访问多次的页面（LFU 部分）
B1: T1 的幽灵列表（已淘汰但记录访问历史）
B2: T2 的幽灵列表（已淘汰但记录访问历史）
```

**自适应参数 p**：
- 控制 T1 和 T2 的大小比例
- 根据访问模式动态调整
- p ∈ [0, c]，其中 c 是缓存容量

### 2.2 成本感知扩展

在标准 ARC 基础上，增加计算成本权重：

```
保留优先级 = 访问频率 × 计算成本 × 时间衰减
```

**计算成本分级**：
- 低成本（1x）：EMA、简单算术运算
- 中成本（5x）：SMA、滚动统计
- 高成本（10x）：skew、kurt、复杂指标

## 3. 实现策略

### 3.1 数据结构

```python
@dataclass
class CacheEntry:
    key: FactorCacheKey
    value: pd.Series
    access_count: int = 0
    last_access_time: float = 0.0
    compute_cost: float = 1.0  # 计算成本权重
    priority: float = 0.0      # 保留优先级
```

### 3.2 ARC 状态

```python
class ARCCache:
    def __init__(self, capacity: int):
        self.capacity = capacity
        self.p = 0  # 自适应参数

        self.t1 = OrderedDict()  # 最近访问一次
        self.t2 = OrderedDict()  # 最近访问多次
        self.b1 = OrderedDict()  # T1 幽灵列表
        self.b2 = OrderedDict()  # T2 幽灵列表
```

### 3.3 ARC 算法核心逻辑

#### 缓存命中（Cache Hit）

```python
def get(self, key: FactorCacheKey) -> Optional[pd.Series]:
    """获取缓存项"""
    # 情况 1: 在 T1 中命中
    if key in self.t1:
        entry = self.t1.pop(key)
        entry.access_count += 1
        entry.last_access_time = time.time()
        self.t2[key] = entry  # 移动到 T2（频繁访问）
        return entry.value

    # 情况 2: 在 T2 中命中
    if key in self.t2:
        entry = self.t2.pop(key)
        entry.access_count += 1
        entry.last_access_time = time.time()
        self.t2[key] = entry  # 移动到 T2 末尾（LRU 更新）
        return entry.value

    return None  # 缓存未命中
```

#### 缓存未命中（Cache Miss）

```python
def set(self, key: FactorCacheKey, value: pd.Series, compute_cost: float = 1.0) -> None:
    """设置缓存项"""
    # 情况 1: 在 B1 中（曾经在 T1 中被淘汰）
    if key in self.b1:
        # 增加 p，偏向 LRU（T1）
        self.p = min(self.p + max(len(self.b2) // len(self.b1), 1), self.capacity)
        self._replace(key, in_b1=True)
        self.b1.pop(key)
        entry = CacheEntry(key, value, access_count=1, compute_cost=compute_cost)
        self.t2[key] = entry  # 直接放入 T2
        return

    # 情况 2: 在 B2 中（曾经在 T2 中被淘汰）
    if key in self.b2:
        # 减少 p，偏向 LFU（T2）
        self.p = max(self.p - max(len(self.b1) // len(self.b2), 1), 0)
        self._replace(key, in_b1=False)
        self.b2.pop(key)
        entry = CacheEntry(key, value, access_count=1, compute_cost=compute_cost)
        self.t2[key] = entry  # 直接放入 T2
        return

    # 情况 3: 全新的键
    if len(self.t1) + len(self.b1) == self.capacity:
        if len(self.t1) < self.capacity:
            self.b1.popitem(last=False)  # 删除 B1 中最旧的
            self._replace(key, in_b1=True)
        else:
            self.t1.popitem(last=False)  # 删除 T1 中最旧的
    elif len(self.t1) + len(self.b1) < self.capacity:
        total = len(self.t1) + len(self.t2) + len(self.b1) + len(self.b2)
        if total >= self.capacity:
            if total == 2 * self.capacity:
                self.b2.popitem(last=False)  # 删除 B2 中最旧的
            self._replace(key, in_b1=True)

    entry = CacheEntry(key, value, access_count=1, compute_cost=compute_cost)
    self.t1[key] = entry  # 新键放入 T1
```

#### 替换逻辑（Replace）

```python
def _replace(self, key: FactorCacheKey, in_b1: bool) -> None:
    """执行缓存替换"""
    # 情况 1: T1 不为空且满足条件
    if len(self.t1) > 0 and (
        (in_b1 and len(self.t1) == self.p) or
        (len(self.t1) > self.p)
    ):
        # 从 T1 中淘汰
        old_key, old_entry = self.t1.popitem(last=False)
        self.b1[old_key] = None  # 移动到 B1 幽灵列表
    else:
        # 从 T2 中淘汰
        if len(self.t2) > 0:
            old_key, old_entry = self.t2.popitem(last=False)
            self.b2[old_key] = None  # 移动到 B2 幽灵列表
```

### 3.4 成本感知优化

#### 优先级计算

```python
def _calculate_priority(self, entry: CacheEntry) -> float:
    """计算缓存项的保留优先级"""
    # 时间衰减因子（越久未访问，优先级越低）
    time_decay = 1.0 / (1.0 + (time.time() - entry.last_access_time) / 3600)

    # 访问频率归一化（假设最大访问次数为 100）
    access_freq = min(entry.access_count / 100.0, 1.0)

    # 综合优先级
    priority = access_freq * entry.compute_cost * time_decay

    return priority
```

#### 成本感知淘汰

```python
def _replace_with_cost_awareness(self, key: FactorCacheKey, in_b1: bool) -> None:
    """基于成本感知的缓存替换"""
    # 更新所有缓存项的优先级
    for entry in self.t1.values():
        entry.priority = self._calculate_priority(entry)
    for entry in self.t2.values():
        entry.priority = self._calculate_priority(entry)

    # 从 T1 或 T2 中选择优先级最低的淘汰
    if len(self.t1) > 0 and (
        (in_b1 and len(self.t1) == self.p) or
        (len(self.t1) > self.p)
    ):
        # 从 T1 中找到优先级最低的
        min_key = min(self.t1.keys(), key=lambda k: self.t1[k].priority)
        old_entry = self.t1.pop(min_key)
        self.b1[min_key] = None
    else:
        # 从 T2 中找到优先级最低的
        if len(self.t2) > 0:
            min_key = min(self.t2.keys(), key=lambda k: self.t2[k].priority)
            old_entry = self.t2.pop(min_key)
            self.b2[min_key] = None
```

### 3.5 计算成本映射

```python
# 因子计算成本映射表
FACTOR_COMPUTE_COST = {
    # 低成本因子（1x）
    'ema_short_10': 1.0,
    'ema_short_20': 1.0,
    'ema_long_50': 1.0,
    'ema_long_200': 1.0,

    # 中成本因子（5x）
    'sma_10': 5.0,
    'sma_20': 5.0,
    'vol_20': 5.0,
    'rsi_14': 5.0,
    'atr_14': 5.0,

    # 高成本因子（10x）
    'skew_20': 10.0,
    'kurt_20': 10.0,
    'adx_14': 10.0,
}

def get_compute_cost(factor_name: str) -> float:
    """获取因子的计算成本"""
    return FACTOR_COMPUTE_COST.get(factor_name, 1.0)
```

## 4. 性能预期

### 4.1 缓存命中率提升

| 场景 | LRU | ARC | ARC+成本感知 | 提升幅度 |
|-----|-----|-----|-------------|---------|
| 均匀访问 | 60% | 65% | 70% | +10-17% |
| 偏斜访问 | 55% | 68% | 75% | +23-36% |
| 混合模式 | 58% | 66% | 72% | +14-24% |

### 4.2 计算时间节省

假设缓存容量为 100，每次计算耗时：
- 低成本因子：0.5ms
- 中成本因子：2.5ms
- 高成本因子：5.0ms

**预期收益**：
- 缓存命中率提升 10-20%
- 高成本因子优先保留，节省 15-25% 计算时间
- 总体性能提升 12-22%

## 5. 使用示例

```python
# 初始化 ARC 缓存
arc_cache = ARCCache(capacity=100)

# 计算因子时自动使用 ARC 缓存
engine = TalibFactorEngine(cache=arc_cache)

# 第一次计算（缓存未命中）
result1 = engine.compute(data, ['ema_short_10', 'skew_20'])

# 第二次计算（缓存命中，skew_20 因成本高被优先保留）
result2 = engine.compute(data, ['ema_short_10', 'skew_20'])

# 查看缓存统计
print(f"命中率: {arc_cache.hit_rate():.2%}")
print(f"T1 大小: {len(arc_cache.t1)}")
print(f"T2 大小: {len(arc_cache.t2)}")
print(f"自适应参数 p: {arc_cache.p}")
```

## 6. 实现优先级

### P0 - 核心功能
1. ARCCache 基础实现（T1、T2、B1、B2）
2. 标准 ARC 算法（get、set、replace）
3. 基础测试用例

### P1 - 成本感知
4. 计算成本映射表
5. 优先级计算函数
6. 成本感知淘汰策略
7. 性能对比测试

### P2 - 优化与监控
8. 自适应参数 p 的动态调整优化
9. 缓存统计与监控
10. 性能分析报告

## 7. 注意事项

### 7.1 内存管理
- 幽灵列表（B1、B2）只存储键，不存储值
- 总内存占用 ≈ 2 × capacity（T1+T2 存储值，B1+B2 只存储键）
- 定期清理过期的幽灵列表项

### 7.2 性能权衡
- 成本感知淘汰需要遍历所有缓存项计算优先级
- 可以采用采样策略：只计算部分项的优先级
- 或者使用增量更新：只在访问时更新优先级

### 7.3 参数调优
- 时间衰减因子：默认 1 小时，可根据实际场景调整
- 访问频率归一化：默认最大 100 次，可根据实际情况调整
- 计算成本权重：根据性能分析报告调整

---

**下一步**：实现 ARCCache 类并集成到 FactorCache 中
