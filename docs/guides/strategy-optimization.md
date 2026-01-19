# 策略优化指南

本指南介绍如何优化策略性能和风险控制。

---

## 风险控制

### 使用风险管理模块

```python
from integration.risk_manager import RiskManager, RiskConfig

# 创建风险配置
risk_config = RiskConfig(
    stop_loss_pct=0.02,      # 2% 止损
    take_profit_pct=0.05,    # 5% 止盈
    max_drawdown_pct=0.15    # 15% 最大回撤
)

# 创建风险管理器
risk_manager = RiskManager(risk_config)

# 在策略中使用
if risk_manager.should_stop_loss(entry_price, current_price, "long"):
    # 执行止损
    pass

if risk_manager.should_take_profit(entry_price, current_price, "long"):
    # 执行止盈
    pass
```

---

## 性能优化建议

### 1. 指标计算优化

**问题**: 重复计算相同指标

**解决方案**: 缓存计算结果

```python
# 不推荐
def populate_indicators(self, dataframe, metadata):
    dataframe['sma_20'] = ta.SMA(dataframe, timeperiod=20)
    dataframe['sma_20_shifted'] = ta.SMA(dataframe, timeperiod=20).shift(1)

# 推荐
def populate_indicators(self, dataframe, metadata):
    sma_20 = ta.SMA(dataframe, timeperiod=20)
    dataframe['sma_20'] = sma_20
    dataframe['sma_20_shifted'] = sma_20.shift(1)
```

### 2. 向量化操作

**问题**: 使用循环处理数据

**解决方案**: 使用 pandas 向量化操作

```python
# 不推荐
for i in range(len(dataframe)):
    if dataframe['close'].iloc[i] > dataframe['sma'].iloc[i]:
        dataframe['signal'].iloc[i] = 1

# 推荐
dataframe['signal'] = (dataframe['close'] > dataframe['sma']).astype(int)
```

### 3. 减少数据复制

**问题**: 频繁复制 DataFrame

**解决方案**: 原地修改

```python
# 不推荐
df = dataframe.copy()
df['new_col'] = calculate_something(df)
return df

# 推荐
dataframe['new_col'] = calculate_something(dataframe)
return dataframe
```

---

## 风险控制最佳实践

### 1. 止损止盈

- 设置合理的止损比例（建议 1-3%）
- 止盈比例应大于止损（建议 2-5%）
- 考虑使用移动止损

### 2. 仓位管理

- 单个持仓不超过总资金的 10%
- 总敞口不超过总资金的 50%
- 根据波动率动态调整仓位

### 3. 回撤控制

- 设置最大回撤限制（建议 10-20%）
- 达到最大回撤时暂停交易
- 定期评估策略表现

---

**最后更新**: 2026-01-19
