# 回归模型基线 - 关键参数速查表

## 模型配置

```json
{
  "freqaimodel": "LightGBMRegressor",
  "identifier": "scheme_d_atr_regressor",
  "train_period_days": 30,
  "backtest_period_days": 7,
  "model_training_parameters": {
    "n_estimators": 800,
    "learning_rate": 0.05,
    "num_leaves": 64
  }
}
```

## 策略参数

### 时间框架
- **timeframe**: `1m`（1分钟K线）
- **startup_candle_count**: 100

### 交易模式
- **trading_mode**: `futures`（期货）
- **margin_mode**: `isolated`（逐仓）
- **can_short**: `True`（允许做空）

### 仓位管理
- **max_open_trades**: 3
- **stake_amount**: `unlimited`
- **tradable_balance_ratio**: 0.99

### ROI 目标
```python
minimal_roi = {
    "0": 0.005,   # 0.5% 立即止盈
    "3": 0.003,   # 3分钟后降到 0.3%
    "5": 0.002    # 5分钟后降到 0.2%
}
```

### 止损配置
- **stoploss**: -0.99（使用 custom_stoploss）
- **custom_stoploss**: 1.5 × ATR（限制在 0.2%-0.5%）

### 追踪止损
- **trailing_stop**: True
- **trailing_stop_positive**: 0.002（达到 0.2% 后激活）
- **trailing_stop_positive_offset**: 0.003（0.3% 后开始追踪）
- **trailing_only_offset_is_reached**: True

## 预测目标

### 回归目标
```python
# 预测未来 5 分钟最大可获得收益率
dataframe['&-s_target_roi'] = np.maximum(
    potential_long_return,   # 做多收益
    potential_short_return   # 做空收益
)
```

### 计算公式
```python
forward_window = 5  # 未来 5 根 K 线
fee = 0.001         # 0.1% 交易费
slippage = 0.001    # 0.1% 滑点
total_cost = 0.004  # 双向成本 0.4%

potential_long_return = (future_max / close - 1) - total_cost
potential_short_return = (1 - future_min / close) - total_cost
```

## 入场条件

### 做多
```python
(do_predict == 1) &                    # FreqAI 启用预测
(&-s_target_roi > 0.005) &             # 预测收益率 > 0.5%
(vpin < 0.7) &                         # VPIN 风险控制
(volume > 0) &                         # 有成交量
(momentum_signal > 0)                  # 正动量（5分钟）
```

### 做空
```python
(do_predict == 1) &                    # FreqAI 启用预测
(&-s_target_roi > 0.005) &             # 预测收益率 > 0.5%
(vpin < 0.7) &                         # VPIN 风险控制
(volume > 0) &                         # 有成交量
(momentum_signal < 0)                  # 负动量（5分钟）
```

## 特征列表

### 买卖压力特征
- `%-price_change`: 价格变化率
- `%-vpin`: VPIN（成交量同步知情交易概率）

### 波动率特征
- `%-atr_14`: 14周期 ATR
- `%-atr_normalized`: ATR 归一化
- `%-realized_vol_12/24/48`: 已实现波动率（多窗口）

### 动量特征
- `%-momentum_5/10/15`: 价格动量（多窗口）

### 成交量特征
- `%-volume_sma_12`: 成交量 12 周期均线
- `%-volume_ratio`: 成交量相对强度

### 微观结构特征
- `%-microprice`: Microprice 近似
- `%-microprice_vs_close`: Microprice 偏离度
- `%-amihud`: Amihud 非流动性指标
- `%-kyle_lambda`: Kyle's Lambda 近似

### 市场状态特征
- `%-regime_state`: 市场状态（0=熊市, 1=震荡, 2=牛市）
- `%-trend`: 趋势强度（15周期）
- `%-realized_vol`: 已实现波动率（20周期）

## 回测结果摘要

### 核心指标
| 指标 | 值 |
|------|-----|
| 交易笔数 | 139 |
| 日均交易 | 1.54 |
| 总收益 | +10.06% |
| 绝对收益 | +100.585 USDT |
| 胜率 | 98.6% |
| 平均持仓 | 15:31:00 |
| 最大回撤 | -1.33% |

### 风险收益
| 指标 | 值 |
|------|-----|
| Sharpe | 15.50 |
| Sortino | 2.88 |
| Calmar | 160.67 |
| Profit Factor | 7.79 |
| CAGR | 47.50% |

### 出场统计
| 出场原因 | 笔数 | 胜率 | 平均收益 |
|---------|------|------|---------|
| ROI | 123 | 100% | +0.25% |
| 追踪止损 | 15 | 93.3% | +0.16% |
| Force Exit | 1 | 0% | -4.04% |

## 关键阈值

### 收益率阈值
- **训练标签**：无阈值（回归预测连续值）
- **入场过滤**：> 0.5%（行业标准）
- **ROI 目标**：0.5% / 0.3% / 0.2%（分级）

### 风险控制阈值
- **VPIN**：< 0.7（风险过滤）
- **ATR 止损**：1.5 × ATR（0.2%-0.5%）
- **追踪止损激活**：+0.2%
- **追踪止损开始**：+0.3%

### 市场状态阈值
- **牛市**：trend > +5% & 高波动
- **熊市**：trend < -5% & 高波动
- **震荡**：其他情况

## 数据要求

### 训练数据
- **时间范围**：30 天（train_period_days）
- **最小样本**：约 43,200 根 K 线（30天 × 24小时 × 60分钟）
- **数据质量**：需要完整的 OHLCV 数据，无大量缺失值

### 回测数据
- **时间范围**：7 天（backtest_period_days）
- **滚动窗口**：每 7 天重新训练一次模型
- **预热期**：100 根 K 线（startup_candle_count）

## 性能基准

### 与分类模型对比
| 指标 | 分类模型 | 回归模型 | 改善 |
|------|---------|---------|------|
| 交易笔数 | 7 | 139 | +1,886% |
| 平均持仓 | 10d 15h | 15h 31m | -93.8% |
| 总收益 | -3.85% | +10.06% | 扭亏为盈 |
| 最大回撤 | -13.02% | -1.33% | -89.8% |

### 市场基准
- **ETH 市场变化**：-7.27%（同期）
- **策略超额收益**：+17.33%
- **Alpha**：显著正值

## 注意事项

### 过拟合风险
- ⚠️ 回测期间仅 3 个月，需要更长时间验证
- ⚠️ 单一币种（ETH），需要多币种验证
- ⚠️ 特定市场环境（2024年4-6月），需要不同市场环境验证

### 实盘风险
- ⚠️ 实际滑点可能高于假设的 0.1%
- ⚠️ 高频交易对网络延迟敏感
- ⚠️ 交易所可能限制高频交易
- ⚠️ 资金费率（funding rate）未考虑

### 优化建议
1. 在更长时间段（1年+）验证策略稳定性
2. 测试不同市场环境（牛市/熊市/震荡）
3. 多币种验证（BTC, SOL, BNB 等）
4. 超参数优化（Hyperopt）
5. 特征重要性分析，移除冗余特征

---

**最后更新**：2026-01-19
**用途**：快速参考和参数复现
