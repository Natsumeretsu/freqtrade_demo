# ETH 微观结构策略 - 回归模型基线（2026-01-19）

## 概述

这是 ETHMicrostructureStrategy 的第一个成功基线配置，使用 **LightGBMRegressor 回归模型**预测未来收益率，实现了真正的高频剥头皮交易。

## 核心突破

从二分类模型（trade/no_trade）切换到回归模型（预测实际收益率），解决了以下根本性问题：
1. **信息丢失**：分类模型只预测是否交易，丢失了收益幅度信息
2. **训练样本不足**：0.5% 阈值只有 0.91% 的正样本，模型无法有效学习
3. **阈值固化**：分类模型的阈值在训练时固定，无法动态调整

## 回测结果（2024-04-01 至 2024-06-30）

### 核心指标
- **交易笔数**：139 笔（日均 1.54 笔）
- **总收益**：+10.06% (+100.585 USDT)
- **胜率**：98.6%（137胜2负）
- **平均持仓时间**：15小时31分
- **最大回撤**：-1.33% (-14.823 USDT)

### 风险收益指标
- **Sharpe 比率**：15.50（优秀）
- **Sortino 比率**：2.88
- **Calmar 比率**：160.67
- **Profit Factor**：7.79
- **CAGR**：47.50%

### 出场统计
- **ROI 止盈**：123 笔（100% 胜率，平均 +0.25%）
- **追踪止损**：15 笔（93.3% 胜率，平均 +0.16%）
- **Force Exit**：1 笔（-4.04%，持仓 5 天 7 小时）

### 多空表现
- **做多**：55 笔，+4.19% (+41.884 USDT)
- **做空**：84 笔，+5.87% (+58.700 USDT)

## 技术架构

### 模型配置
- **模型类型**：LightGBMRegressor（回归）
- **预测目标**：未来 5 分钟最大可获得收益率（`&-s_target_roi`）
- **训练周期**：30 天
- **回测周期**：7 天
- **模型参数**：
  - n_estimators: 800
  - learning_rate: 0.05
  - num_leaves: 64

### 特征工程
基于市场微观结构的特征（无传统技术指标）：
1. **买卖压力**：Money Flow Multiplier 方法
2. **VPIN**：Volume-synchronized Probability of Informed Trading
3. **ATR 归一化**：波动率特征（区分度 2.11）
4. **已实现波动率**：多窗口（12/24/48）
5. **价格动量**：多窗口（5/10/15）
6. **成交量相对强度**
7. **Microprice**：订单簿近似价格

### 入场条件
```python
# 做多
(do_predict == 1) &
(&-s_target_roi > 0.005) &  # 预测收益率 > 0.5%
(vpin < 0.7) &              # 风险控制
(volume > 0) &              # 有成交量
(momentum_signal > 0)       # 正动量

# 做空
(do_predict == 1) &
(&-s_target_roi > 0.005) &  # 预测收益率 > 0.5%
(vpin < 0.7) &              # 风险控制
(volume > 0) &              # 有成交量
(momentum_signal < 0)       # 负动量
```

### 风险管理
- **ROI 目标**：
  - 0 分钟：0.5%（立即止盈）
  - 3 分钟：0.3%
  - 5 分钟：0.2%
- **动态止损**：1.5 × ATR（限制在 0.2%-0.5%）
- **追踪止损**：
  - 激活阈值：+0.2%
  - 开始追踪：+0.3%
  - 只在达到阈值后追踪

## 关键参数

### FreqAI 配置
```json
{
  "enabled": true,
  "purge_old_models": true,
  "train_period_days": 30,
  "backtest_period_days": 7,
  "identifier": "scheme_d_atr_regressor",
  "freqaimodel": "LightGBMRegressor"
}
```

### 策略参数
```python
timeframe = '1m'
can_short = True
max_open_trades = 3
stake_amount = "unlimited"
tradable_balance_ratio = 0.99

minimal_roi = {
    "0": 0.005,   # 0.5%
    "3": 0.003,   # 0.3%
    "5": 0.002    # 0.2%
}

stoploss = -0.99  # 使用 custom_stoploss
trailing_stop = True
trailing_stop_positive = 0.002
trailing_stop_positive_offset = 0.003
trailing_only_offset_is_reached = True
```

## 与分类模型对比

| 指标 | 分类模型（失败） | 回归模型（成功） | 改善 |
|------|-----------------|-----------------|------|
| 交易笔数 | 7 笔 | 139 笔 | +1,886% |
| 平均持仓 | 10天15小时 | 15小时31分 | -93.8% |
| 总收益 | -3.85% | +10.06% | 扭亏为盈 |
| 最大回撤 | -13.02% | -1.33% | -89.8% |
| 胜率 | N/A | 98.6% | 极高 |

## 技术原理

### 为什么回归优于分类？

1. **信息保留**：
   - 回归：预测实际收益率（+0.3%, +0.8%），保留幅度信息
   - 分类：只预测 trade/no_trade，丢失幅度信息

2. **训练样本**：
   - 回归：使用所有数据训练（预测连续值）
   - 分类：只能从 0.91% 的正样本中学习（0.5% 阈值）

3. **灵活过滤**：
   - 回归：执行时动态调整阈值（只交易预测收益 > 0.5% 的信号）
   - 分类：阈值在训练时固定

## 文件清单

- `ETHMicrostructureStrategy.py`：策略源代码
- `config.json`：FreqAI 配置文件
- `backtest_regressor.log`：完整回测日志
- `README.md`：本文档

## 使用方法

### 回测
```bash
./scripts/ft.ps1 backtesting \
  --strategy ETHMicrostructureStrategy \
  --freqaimodel LightGBMRegressor \
  --timerange 20240401-20240630
```

### 实盘（谨慎）
```bash
./scripts/ft.ps1 trade \
  --strategy ETHMicrostructureStrategy \
  --freqaimodel LightGBMRegressor
```

## 后续优化方向

1. **特征优化**：
   - 添加更多微观结构特征（订单簿深度、价格冲击）
   - 测试不同窗口参数

2. **模型优化**：
   - 尝试其他回归模型（XGBoost, CatBoost, Neural Networks）
   - 超参数优化（Hyperopt）

3. **风险管理优化**：
   - 动态调整 ROI 目标（基于波动率）
   - 优化追踪止损参数

4. **多币种扩展**：
   - 测试其他高波动币种（BTC, SOL, BNB）
   - 多币种组合策略

## 注意事项

1. **回测 ≠ 实盘**：回测结果优秀不代表实盘一定盈利
2. **滑点和手续费**：实盘滑点可能高于回测假设的 0.1%
3. **市场环境变化**：策略在不同市场环境下表现可能差异很大
4. **过拟合风险**：需要在不同时间段验证策略稳定性
5. **资金管理**：建议从小资金开始测试

## 版本历史

- **2026-01-19**：初始版本，回归模型基线建立
  - 从分类模型切换到回归模型
  - 实现高频剥头皮交易（139 笔/3 个月）
  - 胜率 98.6%，收益 +10.06%

## 参考文献

1. Easley et al. (2012): VPIN - Volume-Synchronized Probability of Informed Trading
2. Cartea et al. (2015): Order Book Imbalance and Price Impact
3. Kyle (1985): Market Microstructure and Market Impact
4. FreqAI Documentation: https://www.freqtrade.io/en/stable/freqai/
5. LightGBM Documentation: https://lightgbm.readthedocs.io/

---

**创建日期**：2026-01-19
**创建者**：Claude (Sonnet 4.5)
**状态**：已验证基线
**用途**：后续优化的参考基准
