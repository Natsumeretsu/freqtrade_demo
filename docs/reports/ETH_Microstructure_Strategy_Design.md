# ETH Microstructure Strategy - 设计文档

## 设计背景

### 问题分析

之前的 FreqAI 策略（ROI 优化系列）存在严重问题：

1. **季节性失败**：2024 年上半年盈利（+139 USDT），下半年完全崩溃（-141 USDT），6-7 月产生 0 笔交易
2. **无法跑赢市场**：全年收益 -0.17% vs 市场 +46.67%，落后 46.84 个百分点
3. **传统指标失效**：EMA、RSI、MACD 等技术指标无法捕捉加密货币市场的真实动态
4. **过拟合**：在特定时间段表现良好，但无法泛化到不同市场状态

### 核心洞察

通过深入研究学术论文和市场微观结构理论，发现：

1. **订单簿信息比价格更重要**：Order book imbalance 可以预测短期价格变化
2. **知情交易检测**：VPIN 可以识别大户活动和市场风险
3. **市场状态切换**：需要 Hidden Markov Model 检测牛市/熊市/震荡市
4. **传统指标的局限性**：技术指标是价格的滞后函数，无法捕捉市场微观结构

## 理论基础

### 1. Order Flow Imbalance (订单流不平衡)

**定义**：
```
OFI = (V_bid - V_ask) / (V_bid + V_ask)
```

**理论依据**：
- Cartea et al. (2015): 订单簿不平衡与价格变化存在正相关
- 深度越深（L=5 vs L=1），预测能力越强
- 最佳预测窗口：10 秒 - 1 分钟

**实现**：
- 多层次加权：L1-3 (50%), L4-10 (30%), L11-20 (20%)
- 信号阈值：OFI > +0.4 强买压，OFI < -0.4 强卖压

### 2. VPIN (Volume-Synchronized Probability of Informed Trading)

**定义**：
```
VPIN = Σ|V_buy - V_sell| / Σ(V_buy + V_sell)
```

**理论依据**：
- Easley et al. (2012): VPIN 可以预测 Flash Crash 等极端事件
- 基于成交量桶（volume buckets）而非时间桶
- 高 VPIN 表示知情交易者活跃，市场风险增加

**实现**：
- VPIN > 0.7: 极端风险，避免新开仓
- VPIN 0.5-0.7: 高风险，减少仓位
- VPIN < 0.5: 正常交易

### 3. Microprice (真实公允价)

**定义**：
```
Microprice = (V_ask × P_bid + V_bid × P_ask) / (V_bid + V_ask)
```

**理论依据**：
- Stoikov (2017): Microprice 比简单中间价更准确预测短期价格
- 考虑了订单簿深度的影响
- 价格更可能向流动性较少的一侧移动

### 4. Kyle's Lambda (市场冲击成本)

**定义**：
```
Kyle's Lambda = ΔPrice / Volume
```

**理论依据**：
- Kyle (1985): 衡量流动性和信息不对称
- 高 lambda = 低流动性 = 高交易成本
- 反映市场深度和知情交易程度

### 5. Market Regime Detection (市场状态检测)

**方法**：Hidden Markov Model (HMM)

**理论依据**：
- 加密货币市场存在明显的状态切换（牛市/熊市/震荡）
- 不同状态下最优策略不同
- 解决季节性失败问题的关键

**实现**：
- 状态 0: 熊市（下跌 + 高波动）
- 状态 1: 震荡（低波动）
- 状态 2: 牛市（上涨 + 高波动）

## 特征工程

### 特征集设计

```python
# 1. Order Book Features (订单簿特征)
- ofi_5, ofi_10, ofi_20: 多周期订单流不平衡
- bid_ask_spread: 买卖价差
- depth_imbalance: 深度不平衡

# 2. Trade Flow Features (交易流特征)
- vpin: 知情交易概率
- buy_pressure: 买方压力
- sell_pressure: 卖方压力
- volume_imbalance: 成交量不平衡

# 3. Microprice Features (微观价格特征)
- microprice: 成交量加权公允价
- microprice_vs_close: Microprice 与当前价偏离

# 4. Market Impact Features (市场冲击特征)
- kyle_lambda: 市场冲击成本
- amihud: 非流动性指标

# 5. Volatility Features (波动率特征)
- realized_vol: 已实现波动率
- price_range: 价格区间
- volume_vol: 成交量波动率

# 6. Market Regime Features (市场状态特征)
- regime_state: 市场状态（0=熊市, 1=震荡, 2=牛市）
- trend: 趋势强度
```

### 数据限制与近似

**问题**：Freqtrade 只提供 OHLCV 数据，没有实时订单簿

**解决方案**：使用 OHLCV 数据近似微观结构特征

```python
# 订单流近似
buy_pressure = volume (when price_up & volume_up)
sell_pressure = volume (when price_down & volume_up)

# 订单簿近似
bid_approx = low
ask_approx = high
```

**局限性**：
- 精度低于真实订单簿数据
- 无法捕捉订单簿深度的细节
- 适合中低频交易（5 分钟级别）

## 预测目标设计

### 多分类目标

```python
# 3 类分类
0: 不交易（收益不足以覆盖成本）
1: 做多（long return > 1.5%）
2: 做空（short return > 1.5%）
```

### 收益计算

```python
# 未来 20 根 K 线（100 分钟）
future_max = high.shift(-1).rolling(20).max()
future_min = low.shift(-1).rolling(20).min()

# 考虑交易成本
fee = 0.001  # 0.1%
slippage = 0.0005  # 0.05%
total_cost = 2 * (fee + slippage) = 0.003  # 0.3%

# 潜在收益
potential_long_return = (future_max / close - 1) - total_cost
potential_short_return = (1 - future_min / close) - total_cost

# 目标阈值
threshold = 0.015  # 1.5%
```

### 设计理由

1. **多分类 vs 二分类**：
   - 二分类只能做多或不交易
   - 多分类可以做多/做空/不交易，更灵活

2. **1.5% 目标收益**：
   - 高于交易成本（0.3%）
   - 低于之前失败的 2-3% 目标
   - 平衡交易频率和质量

3. **100 分钟预测窗口**：
   - 短于之前的 200 分钟（40 根 K 线）
   - 订单簿特征的有效预测窗口
   - 降低噪音影响

## 策略逻辑

### 入场条件

**做多**：
```python
1. 模型预测做多 (&s-action == 1)
2. 订单流支持 (ofi_10 > 0.1)
3. 风险可控 (vpin < 0.6)
4. 非熊市 (regime_state != 0)
5. 有成交量 (volume > 0)
```

**做空**：
```python
1. 模型预测做空 (&s-action == 2)
2. 订单流支持 (ofi_10 < -0.1)
3. 风险可控 (vpin < 0.6)
4. 非牛市 (regime_state != 2)
5. 有成交量 (volume > 0)
```

### 出场条件

**平多**：
```python
1. 订单流反转 (ofi_10 < -0.2) OR
2. 风险过高 (vpin > 0.7) OR
3. 进入熊市 (regime_state == 0)
```

**平空**：
```python
1. 订单流反转 (ofi_10 > 0.2) OR
2. 风险过高 (vpin > 0.7) OR
3. 进入牛市 (regime_state == 2)
```

### 风险管理

- **ROI**: 2% 目标收益
- **Stoploss**: -5% 止损
- **Max Open Trades**: 1（单一仓位）
- **VPIN 过滤**: 高风险时避免交易

## 与之前策略的对比

| 维度 | 旧策略（ROI 优化） | 新策略（微观结构） |
|------|-------------------|-------------------|
| **特征** | EMA, RSI, MACD 等技术指标 | Order Flow, VPIN, Microprice 等微观结构 |
| **预测目标** | 二分类（达到 ROI / 不达到） | 三分类（做多/做空/不交易） |
| **ROI 目标** | 2-3% | 1.5% |
| **预测窗口** | 200 分钟（40 根 K 线） | 100 分钟（20 根 K 线） |
| **市场状态** | 无状态检测 | HMM 状态检测 |
| **风险管理** | 仅 stoploss | VPIN + 状态过滤 |
| **理论基础** | 传统技术分析 | 市场微观结构理论 |

## 预期改进

1. **解决季节性失败**：
   - HMM 状态检测适应不同市场环境
   - 避免在不利状态下交易

2. **提高预测质量**：
   - 微观结构特征更接近市场本质
   - 减少滞后性

3. **更好的风险控制**：
   - VPIN 实时监控市场风险
   - 动态调整交易策略

4. **增加做空能力**：
   - 三分类支持双向交易
   - 熊市也能盈利

## 潜在风险

1. **数据近似误差**：
   - OHLCV 近似订单簿存在精度损失
   - 可能影响特征质量

2. **过拟合风险**：
   - 特征数量较多（~20 个）
   - 需要充分的样本外验证

3. **模型复杂度**：
   - 三分类比二分类更难训练
   - 可能需要更多数据

4. **计算成本**：
   - 特征计算较复杂
   - 可能影响实时性能

## 下一步计划

1. **回测验证**：
   - 2024 年 4-6 月（样本内）
   - 2024 年 7-12 月（样本外）
   - 全年对比

2. **参数优化**：
   - OFI 阈值调整
   - VPIN 阈值调整
   - ROI 目标优化

3. **特征选择**：
   - 分析特征重要性
   - 移除冗余特征
   - 降低过拟合风险

4. **实盘准备**：
   - 获取真实订单簿数据
   - 优化特征计算
   - 降低延迟

## 参考文献

1. Easley, D., López de Prado, M. M., & O'Hara, M. (2012). Flow toxicity and liquidity in a high-frequency world. The Review of Financial Studies, 25(5), 1457-1493.

2. Cartea, Á., Jaimungal, S., & Penalva, J. (2015). Algorithmic and high-frequency trading. Cambridge University Press.

3. Kyle, A. S. (1985). Continuous auctions and insider trading. Econometrica, 1315-1335.

4. Stoikov, S. (2017). The micro-price: A high frequency estimator of future prices. Available at SSRN 2970694.

5. Cont, R., Kukanov, A., & Stoikov, S. (2014). The price impact of order book events. Journal of financial econometrics, 12(1), 47-88.

## 总结

本策略基于市场微观结构理论，使用订单流、知情交易概率、市场状态等特征替代传统技术指标，旨在解决之前策略的季节性失败和无法跑赢市场的问题。核心创新在于：

1. **理论驱动**：基于学术研究而非经验规则
2. **微观视角**：关注订单簿而非价格图表
3. **状态适应**：根据市场状态动态调整
4. **风险感知**：实时监控市场风险

这是一次从"技术分析"到"市场微观结构"的范式转变。
