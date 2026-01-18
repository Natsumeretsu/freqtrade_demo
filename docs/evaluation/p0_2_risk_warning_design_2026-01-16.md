# P0-2 风险预警因子设计文档

更新日期：2026-01-16


**日期**: 2026-01-16
**目标**: 降低止损率从 33.2% 至 < 20%
**状态**: 设计阶段

---

## 设计原则

1. **复用现有因子**：使用 talib_engine 已有的 ATR、volume_ratio、MACD 因子
2. **最小化侵入**：在策略中添加风险预警逻辑，不修改核心因子计算流程
3. **可配置化**：所有阈值通过策略参数控制，便于后续优化

---

## 风险预警因子设计

### 1. ATR 突破因子（异常波动检测）

**原理**: 当 ATR 突然放大（相对于历史均值），表明市场进入高波动状态，持仓风险增加。

**实现**:
```python
# 计算 ATR 的 Z-score（标准化偏离度）
atr_mean = dataframe['atr'].rolling(window=20).mean()
atr_std = dataframe['atr'].rolling(window=20).std()
atr_zscore = (dataframe['atr'] - atr_mean) / atr_std

# 风险预警：ATR Z-score > 2.0（超过 2 个标准差）
risk_atr_spike = atr_zscore > 2.0
```

**退出逻辑**:
- 当 `risk_atr_spike == True` 且持有多头时，触发 `exit_long`
- 当 `risk_atr_spike == True` 且持有空头时，触发 `exit_short`

---

### 2. 成交量异常因子（恐慌性抛售检测）

**原理**: 当成交量突然放大（volume_ratio > 阈值），可能是恐慌性抛售或大资金出逃，应提前退出。

**实现**:
```python
# 使用 talib_engine 计算的 volume_ratio（已在因子库中）
# volume_ratio = volume / rolling_mean(volume, 20)

# 风险预警：volume_ratio > 3.0（成交量是均值的 3 倍以上）
risk_volume_spike = dataframe['volume_ratio'] > 3.0
```

**退出逻辑**:
- 当 `risk_volume_spike == True` 且持有多头时，触发 `exit_long`
- 当 `risk_volume_spike == True` 且持有空头时，触发 `exit_short`

---

### 3. 趋势反转因子（MACD 信号反转检测）

**原理**: 当 MACD 信号线发生反转（从正转负或从负转正），表明趋势可能反转，应提前退出。

**实现**:
```python
# 使用 talib_engine 计算的 MACD（已在因子库中）
# macd, macdsignal, macdhist

# 检测 MACD 信号线反转
macd_cross_down = (dataframe['macd'].shift(1) > dataframe['macdsignal'].shift(1)) & \
                  (dataframe['macd'] < dataframe['macdsignal'])
macd_cross_up = (dataframe['macd'].shift(1) < dataframe['macdsignal'].shift(1)) & \
                (dataframe['macd'] > dataframe['macdsignal'])

# 风险预警
risk_macd_reversal_long = macd_cross_down  # 多头持仓时 MACD 下穿信号线
risk_macd_reversal_short = macd_cross_up   # 空头持仓时 MACD 上穿信号线
```

**退出逻辑**:
- 当 `risk_macd_reversal_long == True` 且持有多头时，触发 `exit_long`
- 当 `risk_macd_reversal_short == True` 且持有空头时，触发 `exit_short`

---

## 实施计划

### 步骤 1: 在策略中添加风险因子计算

修改 `SmallAccountFuturesTimingExecV1.populate_indicators`:

1. 确保 `atr`、`volume_ratio`、`macd` 因子已计算（通过 factor_usecase）
2. 添加风险预警因子计算逻辑
3. 将风险预警信号存储到 dataframe 列中

### 步骤 2: 修改退出逻辑

修改 `SmallAccountFuturesTimingExecV1.populate_exit_trend`:

1. 读取风险预警信号列
2. 在原有退出逻辑基础上，增加风险预警触发的提前退出
3. 使用 OR 逻辑组合：`exit_long = 原有退出逻辑 | 风险预警退出`

### 步骤 3: 添加策略参数

添加可配置参数：
- `risk_atr_zscore_threshold`: ATR Z-score 阈值（默认 2.0）
- `risk_volume_ratio_threshold`: volume_ratio 阈值（默认 3.0）
- `risk_enable_atr_spike`: 是否启用 ATR 突破预警（默认 True）
- `risk_enable_volume_spike`: 是否启用成交量异常预警（默认 True）
- `risk_enable_macd_reversal`: 是否启用 MACD 反转预警（默认 True）

---

## 预期效果

| 指标 | 当前值 | 目标值 | 改善幅度 |
|------|--------|--------|----------|
| 止损率 | 33.2% | < 20% | -40% |
| 盈亏比 | 0.67 | > 0.8 | +20% |
| 平均持仓时间 | ~2 天 | 8-12 小时 | -75% |

---

## 风险与限制

1. **过度退出风险**: 风险预警可能导致过早退出，错失后续盈利
2. **参数敏感性**: 阈值设置不当可能导致误报或漏报
3. **市场适应性**: 不同市场状态下最优阈值可能不同

**缓解措施**:
- 通过回测验证阈值合理性
- 后续可考虑动态调整阈值（根据市场状态）
- 保留原有退出逻辑作为兜底

---

## 验收标准

- [ ] 风险预警因子计算正确（无 NaN、无异常值）
- [ ] 退出逻辑正确触发（回测日志验证）
- [ ] 止损率 < 20%（回测验证）
- [ ] 盈亏比 > 0.8（回测验证）
- [ ] 总收益 > 0%（回测验证）

---

**文档版本**: v1.0
**创建日期**: 2026-01-16
**作者**: Claude (Sonnet 4.5)
