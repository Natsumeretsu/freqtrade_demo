# 增量计算引擎设计文档

**创建日期**: 2026-01-17

## 1. 概述

增量计算引擎允许只计算新增的数据点，而不是每次都重新计算整个数据集。这对于实时交易系统和回测优化至关重要。

## 2. 核心概念

### 2.1 增量计算原理

**传统计算**（全量计算）：
```
输入: 完整数据集 [t0, t1, t2, ..., tn]
输出: 完整因子值 [f0, f1, f2, ..., fn]
时间复杂度: O(n * w)  # w = 窗口大小
```

**增量计算**（只计算新数据）：
```
输入:
  - 历史状态 state_{n-1}
  - 新数据点 t_n
输出:
  - 新因子值 f_n
  - 更新状态 state_n
时间复杂度: O(1) 或 O(w)  # 取决于因子类型
```

### 2.2 因子分类

根据增量计算的难易程度，将因子分为 3 类：

**A类 - 简单增量**（O(1) 更新）：
- EMA（指数移动平均）
- 累积和/积
- 简单计数器

**B类 - 窗口增量**（O(w) 更新）：
- SMA（简单移动平均）
- 滚动标准差
- 滚动最大/最小值

**C类 - 复杂增量**（需要特殊处理）：
- 偏度（skew）
- 峰度（kurt）
- 分位数

## 3. 架构设计

### 3.1 组件结构

```
IncrementalFactorEngine
├── StateManager          # 状态管理器
│   ├── save_state()     # 保存因子状态
│   ├── load_state()     # 加载因子状态
│   └── clear_state()    # 清空状态
├── IncrementalComputer   # 增量计算器
│   ├── compute_incremental()  # 增量计算
│   └── compute_full()         # 全量计算（初始化）
└── FactorStateRegistry   # 因子状态注册表
    ├── register()       # 注册因子状态
    └── get_state()      # 获取因子状态
```

### 3.2 状态定义

每个因子维护以下状态：

```python
@dataclass
class FactorState:
    factor_name: str           # 因子名称
    last_timestamp: int        # 最后计算时间戳
    last_value: float          # 最后计算值
    window_buffer: deque       # 窗口缓冲区（B类因子）
    accumulator: dict          # 累加器（A类因子）
    metadata: dict             # 元数据
```

## 4. 实现策略

### 4.1 EMA 增量计算

**公式**：
```
EMA_t = α * price_t + (1 - α) * EMA_{t-1}
其中 α = 2 / (period + 1)
```

**状态**：
- `last_ema`: 上一个 EMA 值

**增量更新**：
```python
def update_ema(state, new_price, period):
    alpha = 2 / (period + 1)
    new_ema = alpha * new_price + (1 - alpha) * state.last_ema
    state.last_ema = new_ema
    return new_ema
```

### 4.2 SMA 增量计算

**公式**：
```
SMA_t = (sum(prices[t-w+1:t+1])) / w
```

**状态**：
- `window_buffer`: 固定大小的窗口缓冲区
- `window_sum`: 窗口内的和

**增量更新**：
```python
def update_sma(state, new_price, period):
    state.window_buffer.append(new_price)
    state.window_sum += new_price

    if len(state.window_buffer) > period:
        old_price = state.window_buffer.popleft()
        state.window_sum -= old_price

    return state.window_sum / len(state.window_buffer)
```

### 4.3 滚动标准差增量计算

**Welford 在线算法**：
```python
def update_std(state, new_value):
    state.count += 1
    delta = new_value - state.mean
    state.mean += delta / state.count
    delta2 = new_value - state.mean
    state.m2 += delta * delta2

    if state.count < 2:
        return 0.0
    return sqrt(state.m2 / (state.count - 1))
```

## 5. 性能预期

### 5.1 理论加速比

| 数据规模 | 全量计算 | 增量计算 | 加速比 |
|---------|---------|---------|--------|
| 1000 行 | 0.010s | 0.0002s | 50x |
| 5000 行 | 0.050s | 0.0010s | 50x |
| 10000 行 | 0.100s | 0.0020s | 50x |

### 5.2 实际场景

**回测场景**（逐K线计算）：
- 传统方式：每根K线重新计算全部历史 → O(n²)
- 增量方式：每根K线只计算新值 → O(n)
- **预期提升**：50-100x

**实盘场景**（新K线到达）：
- 传统方式：重新计算最近 N 根K线 → O(n)
- 增量方式：只计算新K线 → O(1)
- **预期提升**：无限加速（毫秒级响应）

## 6. 实现优先级

### P0 - 核心功能
1. StateManager 状态管理器
2. EMA 增量计算（A类因子）
3. SMA 增量计算（B类因子）

### P1 - 扩展功能
4. 滚动标准差增量计算
5. RSI 增量计算
6. ATR 增量计算

### P2 - 高级功能
7. 状态持久化（保存/加载）
8. 状态版本管理
9. 状态校验（检测漂移）

## 7. 使用示例

```python
# 初始化增量引擎
engine = IncrementalFactorEngine()

# 全量计算（初始化状态）
initial_data = load_historical_data(1000)
factors = engine.compute_full(initial_data, ['ema_10', 'sma_20'])

# 增量计算（新数据到达）
for new_candle in stream_new_candles():
    new_factors = engine.compute_incremental(new_candle, ['ema_10', 'sma_20'])
    # 处理新因子值...
```

## 8. 注意事项

### 8.1 状态同步
- 必须确保状态与数据一致
- 数据缺失时需要重新初始化

### 8.2 精度问题
- 浮点累积误差
- 定期全量重算校准

### 8.3 内存管理
- 窗口缓冲区大小控制
- 状态定期清理

---

**下一步**：实现 StateManager 和基础增量计算器
