# 时间序列因子分类体系（单标的择时）

更新日期：2026-01-17


**版本**: v2.0  
**更新日期**: 2026-01-16  
**基于研究**: 加密货币视角下时间序列因子分类研究报告

---

## 概述

本文档定义了项目中时间序列因子的六大分类体系，基于学术研究和业界实践，为单标的择时策略提供系统化的因子框架。

### 核心发现

根据 Baybutt (2024) 等学术研究：

- **仅动量和风险类因子**（previous returns 的函数）具有统计显著性
- **最优参数**：28日 lookback + 5日持有期
- **短期反转** Sharpe 4.58，**2周动量** Sharpe 0.78
- **链上指标**在严格可交易性筛选后统计不显著

### 因子优先级

| 优先级 | 因子类型 | 统计显著性 | 周度超额收益 | Sharpe 比率 |
|--------|----------|-----------|-------------|------------|
| **P0** | 时间序列动量 | ✓✓✓ | 1.2-1.5% | 0.75-0.87 |
| **P0** | 短期反转 | ✓✓ | 0.8% | 4.58 |
| **P0** | 下行风险 | ✓✓✓ | 1.2-1.4% | 0.76-0.79 |
| **P1** | 流动性 | ✓ | 0.6% | - |
| **P2** | 技术指标 | - | - | - |
| **P3** | 链上指标 | ✗ | 0.6-0.8 | 0.54-0.61 |

---

## 第一类：动量因子（Momentum Factors）

### 理论基础

资产过往表现良好会继续上涨（趋势持续假说）

### 统计显著性

✓✓✓ **强统计显著**

### 子分类

#### 1.1 时间序列动量（Time-Series Momentum）

**定义**: 单资产过往收益预测其未来收益

**学术证据**:
- 2周动量：周度超额收益 1.5%（Sharpe 0.78）
- 1月动量：周度超额收益 1.2%（Sharpe 0.75）
- 2月动量：周度超额收益 1.4%（Sharpe 0.87）

**最优参数**: 28日 lookback + 5日持有期

**因子集**: `momentum_ts`

```yaml
momentum_ts:
  # 短期动量（1-7日）
  - ret_1               # 1日收益
  - ret_3               # 3日收益
  - ret_5               # 5日收益
  - ret_7               # 7日收益（1周）
  # 中期动量（14-28日）- 最优区间
  - ret_14              # 14日收益（2周）- Sharpe 0.78
  - ret_21              # 21日收益（3周）
  - ret_28              # 28日收益（4周）- 最优 lookback
  # 长期动量（56日）
  - ret_56              # 56日收益（2月）- Sharpe 0.87
```

**使用示例**:

```python
from trading_system.application.factor_sets import get_factor_templates

# 获取时间序列动量因子
factors = get_factor_templates("momentum_ts")
# ['ret_1', 'ret_3', 'ret_5', 'ret_7', 'ret_14', 'ret_21', 'ret_28', 'ret_56']
```

#### 1.2 价格动量（Price Momentum）

**定义**: 当前价格相对过往高点/低点的距离

**因子集**: `momentum_price`

```yaml
momentum_price:
  - ema_spread          # EMA(10)/EMA(50) - 1
  - ema_spread_20_50    # EMA(20)/EMA(50) - 1
  - ema_spread_50_200   # EMA(50)/EMA(200) - 1
  - price_to_high_20    # close / highest(20) - 1
  - price_to_low_20     # close / lowest(20) - 1
  - price_to_high_50    # close / highest(50) - 1
  - price_to_low_50     # close / lowest(50) - 1
```

**计算方法**:

- `ema_spread`: 短期 EMA 与长期 EMA 的偏离度
- `price_to_high`: 当前价格距离历史高点的距离（负值表示低于高点）
- `price_to_low`: 当前价格距离历史低点的距离（正值表示高于低点）

#### 1.3 动量变化率（Rate of Change）

**定义**: 价格变化速率

**因子集**: `momentum_roc`

```yaml
momentum_roc:
  - roc_5               # 5日变化率
  - roc_10              # 10日变化率
  - roc_14              # 14日变化率
  - roc_21              # 21日变化率
  - roc_28              # 28日变化率
```

**计算公式**: `ROC(n) = (close - close[n]) / close[n] * 100`

---

## 第二类：反转因子（Reversal Factors）

### 理论基础

极端价格偏离均值后倾向回归（过度反应假说）

### 统计显著性

✓✓ **经济显著**（Sharpe 4.58）

### 子分类

#### 2.1 短期反转（1-5日）

**驱动机制**: 流动性供给和市场微观结构

**学术证据**: Sharpe 比率 4.58

**因子集**: `reversal_short`

```yaml
reversal_short:
  - reversal_1          # 1日反转信号
  - reversal_3          # 3日反转信号
  - reversal_5          # 5日反转信号
```

**计算方法**: `reversal_n = -ret_n`（过去 n 日收益的负值）

**使用场景**: 
- 日内交易
- 短期波段交易
- 与动量因子配合使用（背离识别）

#### 2.2 中期反转（7-30日）

**学术证据**: 周度超额收益 -1.0%（Sharpe 0.57）

**因子集**: `reversal_medium`

```yaml
reversal_medium:
  - reversal_7          # 7日反转信号
  - reversal_14         # 14日反转信号
  - reversal_21         # 21日反转信号
  - reversal_30         # 30日反转信号
```

#### 2.3 均值回归指标

**定义**: 价格偏离均值的程度

**因子集**: `reversal_mean_reversion`

```yaml
reversal_mean_reversion:
  - zscore_close_20     # 20日价格 Z-score
  - zscore_close_50     # 50日价格 Z-score
  - bb_percent_b_20_2   # 布林带位置（20日，2倍标准差）
  - bb_percent_b_50_2   # 布林带位置（50日，2倍标准差）
```

**计算方法**:
- `zscore_close_n = (close - mean(close, n)) / std(close, n)`
- `bb_percent_b = (close - lower_band) / (upper_band - lower_band)`

**解释**:
- Z-score > 2: 价格显著高于均值（可能反转向下）
- Z-score < -2: 价格显著低于均值（可能反转向上）
- bb_percent_b > 1: 价格突破上轨（超买）
- bb_percent_b < 0: 价格突破下轨（超卖）

---

## 第三类：风险因子（Risk Factors）

### 理论基础

高风险资产应提供更高收益补偿

### 统计显著性

✓✓✓ **强统计显著**

### 子分类

#### 3.1 波动率风险（Volatility Risk）

**因子集**: `risk_volatility`

```yaml
risk_volatility:
  - vol_7               # 7日波动率
  - vol_14              # 14日波动率
  - vol_21              # 21日波动率
  - vol_28              # 28日波动率
  - vol_56              # 56日波动率
  - hl_range            # 日内振幅（high/low - 1）
  - atr_14              # 14日 ATR
  - atr_pct_14          # 14日 ATR%
```

**计算方法**:
- `vol_n = std(ret_1, n)`: n 日收益率标准差
- `hl_range = high / low - 1`: 日内振幅
- `atr_pct = atr / close`: ATR 百分比

#### 3.2 下行风险/尾部风险（Downside Risk / Tail Risk）

**学术证据**:
- 5% ES：周度超额收益 1.4%（Sharpe 0.76）
- 特质偏度：周度超额收益 1.2%（Sharpe 0.79）

**因子集**: `risk_downside`

```yaml
risk_downside:
  - var_5_30            # 30日 5% VaR
  - es_5_30             # 30日 5% ES（Expected Shortfall）
  - skew_30             # 30日偏度
  - skew_60             # 60日偏度
  - kurt_30             # 30日峰度
  - kurt_60             # 60日峰度
  - tail_ratio_30       # 30日尾部比率
  - tail_ratio_60       # 60日尾部比率
  - downside_vol_30     # 30日下行波动率
```

**计算方法**:
- `var_p_n = quantile(ret, p, n)`: n 日 p% 分位数
- `es_p_n = mean(ret[ret <= var_p_n])`: 条件 VaR
- `downside_vol_n = std(ret[ret < 0], n)`: 仅负收益的标准差
- `tail_ratio_n = abs(q95 / q05)`: 上尾/下尾比率

**解释**:
- VaR/ES 越负，下行风险越大
- 偏度 < 0: 左偏（负收益尾部更厚）
- 峰度 > 3: 尖峰厚尾（极端值更频繁）
- tail_ratio > 1: 上行尾部更厚（正偏）

#### 3.3 波动率的波动（Volatility of Volatility）

**因子集**: `risk_vol_of_vol`

```yaml
risk_vol_of_vol:
  - vol_of_vol_14       # 14日波动率的波动
  - vol_of_vol_28       # 28日波动率的波动
```

**计算方法**: `vol_of_vol_n = pct_change(vol_n, n)`

**用途**: 识别波动率制度切换

---

## 使用指南

### 因子选择策略

#### 第一优先：时间序列动量 + 短期反转

```python
priority_1 = get_factor_templates("priority_1_momentum_reversal")
# ['ret_14', 'ret_28', 'ret_56', 'reversal_1', 'reversal_3', 'reversal_5']
```

**理由**: 统计证据最强，加密市场应用最成熟

#### 第二优先：下行风险因子 + 动量确认

```python
priority_2 = get_factor_templates("priority_2_risk")
# ['var_5_30', 'es_5_30', 'skew_30', 'vol_28', 'downside_vol_30']
```

**理由**: 风险调整能力强，适合 volatility scaling

### 组合使用示例

```python
from trading_system.infrastructure.factor_engines.talib_engine import TalibFactorEngine
import pandas as pd

# 初始化因子引擎
engine = TalibFactorEngine()

# 准备 OHLCV 数据
data = pd.DataFrame({
    'open': [...],
    'high': [...],
    'low': [...],
    'close': [...],
    'volume': [...]
})

# 计算核心因子
core_factors = [
    'ret_14', 'ret_28',           # 动量
    'reversal_1', 'reversal_5',   # 反转
    'var_5_30', 'es_5_30',        # 风险
    'vol_28', 'downside_vol_30'   # 波动率
]

result = engine.compute(data, core_factors)
```

---

## 参考文献

1. Baybutt, A. (2024). "Empirical Crypto Asset Pricing"
2. Bianchi, D. & Babiak, M. (2022). "A Factor Model for Cryptocurrency Returns"
3. Liu, Z., Tsyvinski, A. & Wu, X. (2021). "Time-Series and Cross-Sectional Momentum"

---

**下一部分**: [第四类：流动性因子](./time_series_factors_part2.md)
