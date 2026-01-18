# 数据预加载优化设计文档

**创建日期**: 2026-01-17

## 1. 概述

实现数据预加载机制，在因子计算前提前加载所需的历史数据，避免计算时的 I/O 等待。

## 2. 核心概念

### 2.1 预加载原理

**传统方式**（按需加载）：
```
用户请求 → 加载数据 → 计算因子 → 返回结果
           ↑ I/O 等待
```

**预加载方式**：
```
后台线程: 预测需求 → 提前加载 → 缓存数据
用户请求: 从缓存读取 → 计算因子 → 返回结果
                      ↑ 无 I/O 等待
```

### 2.2 预加载策略

**1. 时间窗口预加载**
- 预加载最近 N 天的数据
- 适用于回测和实盘场景

**2. 因子依赖预加载**
- 根据因子定义预加载所需的数据列
- 例如：计算 EMA 需要 close 列

**3. 智能预测预加载**
- 根据历史访问模式预测未来需求
- 使用 LRU/LFU 策略预加载热点数据

## 3. 架构设计

### 3.1 组件结构

```
DataPrefetcher
├── PrefetchStrategy      # 预加载策略
│   ├── TimeWindowStrategy    # 时间窗口策略
│   ├── FactorDependencyStrategy  # 因子依赖策略
│   └── SmartPredictStrategy      # 智能预测策略
├── DataLoader            # 数据加载器
│   ├── load_async()      # 异步加载
│   └── load_batch()      # 批量加载
├── BufferManager         # 缓冲区管理器
│   ├── allocate()        # 分配缓冲区
│   └── release()         # 释放缓冲区
└── PrefetchScheduler     # 预加载调度器
    ├── schedule()        # 调度任务
    └── monitor()         # 监控状态
```

### 3.2 时间窗口策略

```python
class TimeWindowStrategy:
    """时间窗口预加载策略"""

    def __init__(self, window_days: int = 7):
        self.window_days = window_days

    def get_prefetch_range(self, current_time: datetime) -> tuple:
        """获取预加载时间范围"""
        end_time = current_time
        start_time = current_time - timedelta(days=self.window_days)
        return start_time, end_time
```

### 3.3 因子依赖策略

```python
class FactorDependencyStrategy:
    """因子依赖预加载策略"""

    # 因子所需的数据列映射
    FACTOR_DEPENDENCIES = {
        'ema_*': ['close'],
        'sma_*': ['close'],
        'rsi_*': ['close'],
        'atr_*': ['high', 'low', 'close'],
        'vol_*': ['close'],
        'skew_*': ['close'],
        'kurt_*': ['close'],
    }

    def get_required_columns(self, factor_names: list[str]) -> set[str]:
        """获取因子所需的数据列"""
        columns = set()
        for factor_name in factor_names:
            for pattern, cols in self.FACTOR_DEPENDENCIES.items():
                if self._match_pattern(factor_name, pattern):
                    columns.update(cols)
        return columns
```

### 3.4 异步数据加载

```python
class AsyncDataLoader:
    """异步数据加载器"""

    def __init__(self, executor: ThreadPoolExecutor):
        self.executor = executor
        self._futures: Dict[str, Future] = {}

    async def load_async(self, pair: str, timeframe: str,
                        start_time: datetime, end_time: datetime) -> pd.DataFrame:
        """异步加载数据"""
        future = self.executor.submit(
            self._load_data, pair, timeframe, start_time, end_time
        )
        self._futures[f"{pair}_{timeframe}"] = future
        return await asyncio.wrap_future(future)
```

## 4. 性能预期

### 4.1 I/O 等待时间节省

| 场景 | 传统加载 | 预加载 | 节省时间 |
|-----|---------|-------|---------|
| 单次因子计算 | 100ms | 5ms | 95ms (95%) |
| 批量因子计算 | 500ms | 20ms | 480ms (96%) |
| 回测（1000根K线） | 10s | 0.5s | 9.5s (95%) |

### 4.2 内存占用

- 时间窗口 7 天：约 50MB（1个交易对，1h周期）
- 时间窗口 30 天：约 200MB
- 建议：根据可用内存动态调整窗口大小

## 5. 实现优先级

### P0 - 核心功能
1. 时间窗口预加载策略
2. 同步数据加载器
3. 简单缓冲区管理

### P1 - 性能优化
4. 异步数据加载
5. 因子依赖分析
6. 批量加载优化

### P2 - 高级功能
7. 智能预测策略
8. 自适应窗口调整
9. 性能监控与统计

## 6. 使用示例

```python
# 初始化预加载器
prefetcher = DataPrefetcher(
    strategy=TimeWindowStrategy(window_days=7),
    max_buffer_size=500  # MB
)

# 启动预加载
prefetcher.start()

# 计算因子时自动使用预加载的数据
engine = TalibFactorEngine(prefetcher=prefetcher)
result = engine.compute(data, ['ema_10', 'rsi_14'])

# 停止预加载
prefetcher.stop()
```

---

**下一步**：实现 P0 核心功能（时间窗口预加载策略）
