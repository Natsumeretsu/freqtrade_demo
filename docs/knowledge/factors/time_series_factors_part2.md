# 时序因子分类体系（第二部分）

更新日期：2026-01-17


本文档是 [时序因子分类体系（第一部分）](./time_series_factors_classification.md) 的延续，涵盖剩余三个因子类别。

---

## 第四类：流动性因子（Liquidity Factors）

**统计显著性**: ❌ 无显著性（学术研究未发现统计显著的 alpha）

**优先级**: P3（可选）

**核心发现**: 
- 流动性因子在加密货币市场中**不具备统计显著性**
- 主要用于风险监控和交易成本估算
- 可作为辅助信号，但不应作为主要决策依据

### 4.1 成交量流动性（Volume-Based Liquidity）

**因子列表**:
- `volume_z_<n>`: n 日成交量 Z-score（标准化成交量）
- `volume_ma_<n>`: n 日成交量移动平均
- `volume_std_<n>`: n 日成交量标准差
- `turnover_<n>`: n 日换手率（成交量/流通量）

**YAML 配置示例**:
```yaml
liquidity_volume:
  - volume_z_30        # 30 日成交量 Z-score
  - volume_ma_20       # 20 日成交量均值
  - volume_std_20      # 20 日成交量波动
  - turnover_30        # 30 日换手率
```

**Python 使用示例**:
```python
from trading_system.infrastructure.factor_engines.talib_engine import TalibFactorEngine

engine = TalibFactorEngine()
factors = engine.compute(
    dataframe=df,
    factor_names=['volume_z_30', 'volume_ma_20', 'turnover_30']
)

# 流动性监控：成交量异常检测
low_liquidity_mask = factors['volume_z_30'] < -2.0  # 成交量显著低于均值
```

**计算公式**:
- **volume_z_n**: `(volume - mean(volume_n)) / std(volume_n)`
- **volume_ma_n**: `mean(volume_n)`
- **volume_std_n**: `std(volume_n)`
- **turnover_n**: `sum(volume_n) / circulating_supply`

**解释**:
- 成交量 Z-score > 2: 异常放量（可能有重大事件）
- 成交量 Z-score < -2: 异常缩量（流动性风险）
- 换手率高: 市场活跃，但不一定预示方向

---

### 4.2 价格冲击（Price Impact）

**因子列表**:
- `amihud_<n>`: n 日 Amihud 非流动性指标
- `price_impact_<n>`: n 日价格冲击系数
- `obv_slope_<n>`: n 日 OBV 斜率（On-Balance Volume）

**YAML 配置示例**:
```yaml
liquidity_impact:
  - amihud_30          # 30 日 Amihud 非流动性
  - price_impact_20    # 20 日价格冲击
  - obv_slope_14       # 14 日 OBV 斜率
```

**Python 使用示例**:
```python
factors = engine.compute(
    dataframe=df,
    factor_names=['amihud_30', 'obv_slope_14']
)

# 流动性风险评估
high_impact_mask = factors['amihud_30'] > factors['amihud_30'].quantile(0.9)
print(f"高价格冲击期数: {high_impact_mask.sum()}")
```

**计算公式**:
- **amihud_n**: `mean(|ret| / volume)` over n days
- **price_impact_n**: `std(ret) / mean(volume)` over n days
- **obv_slope_n**: `slope(OBV)` over n days, where `OBV = cumsum(sign(ret) * volume)`

**解释**:
- Amihud 指标越高，流动性越差（单位成交量引起的价格变动越大）
- OBV 斜率为正且价格上涨：成交量确认趋势
- OBV 斜率为负但价格上涨：背离信号（趋势可能反转）

---

### 4.3 买卖价差（Bid-Ask Spread）

**因子列表**:
- `hl_range_<n>`: n 日高低价区间（High-Low Range）
- `hl_ratio_<n>`: n 日高低价比率
- `gap_<n>`: n 日跳空缺口

**YAML 配置示例**:
```yaml
liquidity_spread:
  - hl_range_14        # 14 日高低价区间
  - hl_ratio_20        # 20 日高低价比率
  - gap_5              # 5 日跳空缺口
```

**Python 使用示例**:
```python
factors = engine.compute(
    dataframe=df,
    factor_names=['hl_range_14', 'gap_5']
)

# 波动率与流动性关系
high_volatility_mask = factors['hl_range_14'] > factors['hl_range_14'].quantile(0.8)
```

**计算公式**:
- **hl_range_n**: `(high - low) / close` over n days
- **hl_ratio_n**: `high / low` over n days
- **gap_n**: `|open - close_prev|` over n days

**解释**:
- 高低价区间扩大：波动率上升，可能伴随流动性下降
- 跳空缺口频繁：市场不连续，流动性不足

---

## 第五类：技术因子（Technical Factors）

**统计显著性**: ❌ 无显著性（学术研究未发现统计显著的 alpha）

**优先级**: P3（可选）

**核心发现**: 
- 传统技术指标（RSI、MACD、布林带等）在加密货币市场中**不具备统计显著性**
- 可用于辅助判断超买超卖、趋势确认，但不应作为主要信号
- 建议与统计显著因子（动量、反转、风险）结合使用

### 5.1 趋势跟踪（Trend Following）

**因子列表**:
- `sma_<n>`: n 日简单移动平均
- `ema_<n>`: n 日指数移动平均
- `dema_<n>`: n 日双重指数移动平均
- `tema_<n>`: n 日三重指数移动平均
- `adx_<n>`: n 日平均趋向指标（Average Directional Index）
- `aroon_<n>`: n 日阿隆指标

**YAML 配置示例**:
```yaml
technical_trend:
  - sma_20             # 20 日均线
  - ema_12             # 12 日指数均线
  - ema_26             # 26 日指数均线
  - adx_14             # 14 日 ADX
  - aroon_25           # 25 日 Aroon
```

**Python 使用示例**:
```python
factors = engine.compute(
    dataframe=df,
    factor_names=['sma_20', 'ema_12', 'ema_26', 'adx_14']
)

# 趋势判断：价格在均线之上 + ADX > 25
uptrend_mask = (df['close'] > factors['sma_20']) & (factors['adx_14'] > 25)
```

**计算公式**:
- **sma_n**: `mean(close_n)`
- **ema_n**: 指数加权移动平均（权重递减）
- **adx_n**: 基于 +DI 和 -DI 的趋势强度指标（0-100）
- **aroon_n**: `(n - days_since_high) / n * 100` 和 `(n - days_since_low) / n * 100`

**解释**:
- ADX > 25: 趋势强劲（但不指示方向）
- Aroon Up > 70 且 Aroon Down < 30: 上升趋势
- 价格突破均线：可能的趋势转折点

---

### 5.2 动量振荡器（Momentum Oscillators）

**因子列表**:
- `rsi_<n>`: n 日相对强弱指标（Relative Strength Index）
- `stoch_<n>`: n 日随机指标（Stochastic Oscillator）
- `cci_<n>`: n 日商品通道指标（Commodity Channel Index）
- `mfi_<n>`: n 日资金流量指标（Money Flow Index）
- `willr_<n>`: n 日威廉指标（Williams %R）

**YAML 配置示例**:
```yaml
technical_oscillator:
  - rsi_14             # 14 日 RSI
  - stoch_14           # 14 日随机指标
  - cci_20             # 20 日 CCI
  - mfi_14             # 14 日 MFI
  - willr_14           # 14 日 Williams %R
```

**Python 使用示例**:
```python
factors = engine.compute(
    dataframe=df,
    factor_names=['rsi_14', 'stoch_14', 'mfi_14']
)

# 超买超卖判断
oversold_mask = (factors['rsi_14'] < 30) & (factors['mfi_14'] < 20)
overbought_mask = (factors['rsi_14'] > 70) & (factors['mfi_14'] > 80)
```

**计算公式**:
- **rsi_n**: `100 - 100 / (1 + RS)`, where `RS = mean(gain_n) / mean(loss_n)`
- **stoch_n**: `(close - low_n) / (high_n - low_n) * 100`
- **cci_n**: `(typical_price - sma(typical_price_n)) / (0.015 * mean_deviation_n)`
- **mfi_n**: 类似 RSI，但基于成交量加权的价格变动
- **willr_n**: `(high_n - close) / (high_n - low_n) * -100`

**解释**:
- RSI < 30: 超卖（可能反弹，但不保证）
- RSI > 70: 超买（可能回调，但不保证）
- 多个振荡器同时超买/超卖：信号更强

---

### 5.3 波动率通道（Volatility Bands）

**因子列表**:
- `bbands_upper_<n>`: n 日布林带上轨
- `bbands_middle_<n>`: n 日布林带中轨
- `bbands_lower_<n>`: n 日布林带下轨
- `bbands_width_<n>`: n 日布林带宽度
- `keltner_upper_<n>`: n 日肯特纳通道上轨
- `keltner_lower_<n>`: n 日肯特纳通道下轨

**YAML 配置示例**:
```yaml
technical_bands:
  - bbands_upper_20    # 20 日布林带上轨
  - bbands_middle_20   # 20 日布林带中轨
  - bbands_lower_20    # 20 日布林带下轨
  - bbands_width_20    # 20 日布林带宽度
```

**Python 使用示例**:
```python
factors = engine.compute(
    dataframe=df,
    factor_names=['bbands_upper_20', 'bbands_middle_20', 'bbands_lower_20', 'bbands_width_20']
)

# 布林带突破策略
breakout_up = df['close'] > factors['bbands_upper_20']
breakout_down = df['close'] < factors['bbands_lower_20']

# 布林带收窄（波动率压缩）
squeeze_mask = factors['bbands_width_20'] < factors['bbands_width_20'].quantile(0.2)
```

**计算公式**:
- **bbands_middle_n**: `sma(close_n)`
- **bbands_upper_n**: `sma(close_n) + 2 * std(close_n)`
- **bbands_lower_n**: `sma(close_n) - 2 * std(close_n)`
- **bbands_width_n**: `(upper - lower) / middle`

**解释**:
- 价格触及上轨：可能超买（但趋势强劲时可持续）
- 价格触及下轨：可能超卖（但趋势疲弱时可持续）
- 布林带收窄：波动率压缩，可能预示大行情

---

## 第六类：市场状态因子（Market Regime Factors）

**统计显著性**: ⚠️ 部分显著（波动率状态切换有一定预测能力）

**优先级**: P2（建议使用）

**核心发现**: 
- 市场状态识别（高波动/低波动、趋势/震荡）对策略表现有显著影响
- 波动率状态切换（低波动 → 高波动）具有一定预测能力
- 建议用于动态调整仓位和止损参数

### 6.1 波动率状态（Volatility Regime）

**因子列表**:
- `vol_regime_<n>`: n 日波动率状态（高/中/低）
- `vol_percentile_<n>`: n 日波动率分位数
- `vol_expansion_<n>`: n 日波动率扩张信号
- `vol_contraction_<n>`: n 日波动率收缩信号

**YAML 配置示例**:
```yaml
regime_volatility:
  - vol_regime_30      # 30 日波动率状态
  - vol_percentile_60  # 60 日波动率分位数
  - vol_expansion_20   # 20 日波动率扩张
  - vol_contraction_20 # 20 日波动率收缩
```

**Python 使用示例**:
```python
factors = engine.compute(
    dataframe=df,
    factor_names=['vol_regime_30', 'vol_percentile_60', 'vol_expansion_20']
)

# 波动率状态切换检测
high_vol_regime = factors['vol_regime_30'] == 2  # 高波动状态
vol_expanding = factors['vol_expansion_20'] > 0   # 波动率正在扩张

# 动态仓位调整：高波动时降低仓位
position_size = np.where(high_vol_regime, 0.5, 1.0)
```

**计算公式**:
- **vol_regime_n**: 基于 n 日波动率的三分位数分类（0=低, 1=中, 2=高）
- **vol_percentile_n**: `percentile_rank(vol_current, vol_n)`
- **vol_expansion_n**: `vol_short / vol_long - 1` (short < long, e.g., 10/30)
- **vol_contraction_n**: `-vol_expansion_n`

**解释**:
- 波动率分位数 > 80%: 当前波动率处于历史高位
- 波动率扩张 > 0.2: 波动率快速上升（风险增加）
- 波动率收缩 > 0.2: 波动率快速下降（可能进入盘整）

---

### 6.2 趋势状态（Trend Regime）

**因子列表**:
- `trend_regime_<n>`: n 日趋势状态（上升/震荡/下降）
- `trend_strength_<n>`: n 日趋势强度
- `hurst_<n>`: n 日 Hurst 指数（趋势持续性）

**YAML 配置示例**:
```yaml
regime_trend:
  - trend_regime_30    # 30 日趋势状态
  - trend_strength_20  # 20 日趋势强度
  - hurst_60           # 60 日 Hurst 指数
```

**Python 使用示例**:
```python
factors = engine.compute(
    dataframe=df,
    factor_names=['trend_regime_30', 'trend_strength_20', 'hurst_60']
)

# 趋势状态判断
uptrend = factors['trend_regime_30'] == 1
downtrend = factors['trend_regime_30'] == -1
ranging = factors['trend_regime_30'] == 0

# Hurst 指数判断趋势持续性
persistent_trend = factors['hurst_60'] > 0.5  # H > 0.5: 趋势性
mean_reverting = factors['hurst_60'] < 0.5    # H < 0.5: 均值回归
```

**计算公式**:
- **trend_regime_n**: 基于 n 日收益率和 ADX 的综合判断
  - `ret_n > threshold and adx_n > 25`: 上升趋势 (1)
  - `ret_n < -threshold and adx_n > 25`: 下降趋势 (-1)
  - 其他: 震荡 (0)
- **trend_strength_n**: `|ret_n| * adx_n / 100`
- **hurst_n**: 基于 R/S 分析的 Hurst 指数（0-1）

**解释**:
- Hurst = 0.5: 随机游走（无趋势）
- Hurst > 0.5: 趋势性市场（动量策略有效）
- Hurst < 0.5: 均值回归市场（反转策略有效）

---

### 6.3 相关性状态（Correlation Regime）

**因子列表**:
- `corr_btc_<n>`: n 日与 BTC 的相关性
- `corr_eth_<n>`: n 日与 ETH 的相关性
- `corr_market_<n>`: n 日与市场指数的相关性
- `beta_market_<n>`: n 日市场 Beta

**YAML 配置示例**:
```yaml
regime_correlation:
  - corr_btc_30        # 30 日与 BTC 相关性
  - corr_eth_30        # 30 日与 ETH 相关性
  - beta_market_60     # 60 日市场 Beta
```

**Python 使用示例**:
```python
factors = engine.compute(
    dataframe=df,
    factor_names=['corr_btc_30', 'beta_market_60']
)

# 相关性状态判断
high_correlation = factors['corr_btc_30'] > 0.7  # 高度相关
low_correlation = factors['corr_btc_30'] < 0.3   # 低相关（独立行情）

# Beta 判断系统性风险暴露
high_beta = factors['beta_market_60'] > 1.2      # 高 Beta（高风险高收益）
low_beta = factors['beta_market_60'] < 0.8       # 低 Beta（防御性）
```

**计算公式**:
- **corr_btc_n**: `corr(ret_asset, ret_btc)` over n days
- **beta_market_n**: `cov(ret_asset, ret_market) / var(ret_market)` over n days

**解释**:
- 相关性 > 0.7: 资产跟随 BTC 走势（系统性风险高）
- 相关性 < 0.3: 资产独立行情（分散化价值高）
- Beta > 1: 资产波动大于市场（进攻型）
- Beta < 1: 资产波动小于市场（防御型）

---

## 因子使用建议

### 1. 优先级策略

根据学术研究的统计显著性，建议按以下优先级使用因子：

**P0（核心）**: 
- 时序动量（ret_14, ret_28）
- 短期反转（reversal_1, reversal_3, reversal_5）

**P1（重要）**:
- 下行风险（var_5_30, es_5_30, downside_vol_30）
- 波动率（vol_28, skew_30）

**P2（建议）**:
- 市场状态（vol_regime_30, trend_regime_30, hurst_60）
- 价格动量（ema_spread_12_26, price_to_high_28）

**P3（可选）**:
- 流动性（amihud_30, obv_slope_14）
- 技术指标（rsi_14, bbands_width_20）

### 2. 因子组合策略

**策略 A：纯统计显著因子**（推荐）
```yaml
strategy_a_factors:
  - ret_14              # 2 周动量
  - ret_28              # 4 周动量
  - reversal_1          # 1 日反转
  - reversal_3          # 3 日反转
  - var_5_30            # 30 日 VaR
  - es_5_30             # 30 日 ES
  - vol_28              # 28 日波动率
  - skew_30             # 30 日偏度
```

**策略 B：动量 + 市场状态**
```yaml
strategy_b_factors:
  - ret_14
  - ret_28
  - reversal_3
  - vol_regime_30       # 波动率状态
  - trend_regime_30     # 趋势状态
  - hurst_60            # 趋势持续性
```

**策略 C：全因子（研究用）**
```yaml
strategy_c_factors:
  - "@include priority_1_momentum_reversal"
  - "@include priority_2_risk"
  - "@include regime_volatility"
  - "@include regime_trend"
  - "@include technical_oscillator"
```

### 3. 动态因子选择

根据市场状态动态调整因子权重：

```python
def get_factor_weights(market_regime):
    """根据市场状态返回因子权重"""
    if market_regime == 'high_vol':
        # 高波动：降低动量权重，提高反转权重
        return {
            'momentum': 0.3,
            'reversal': 0.5,
            'risk': 0.2
        }
    elif market_regime == 'low_vol':
        # 低波动：提高动量权重，降低反转权重
        return {
            'momentum': 0.6,
            'reversal': 0.2,
            'risk': 0.2
        }
    else:
        # 正常波动：均衡配置
        return {
            'momentum': 0.4,
            'reversal': 0.4,
            'risk': 0.2
        }
```

---

## 参考文献

1. **Momentum and Reversal in Cryptocurrency Markets**
   - 2 周动量 Sharpe: 0.78
   - 短期反转 Sharpe: 4.58
   - 最优参数：28 日回看期 + 5 日持有期

2. **Risk Factors in Cryptocurrency Returns**
   - 下行风险因子（VaR, ES）具有显著预测能力
   - 偏度因子在极端市场中表现优异

3. **Market Microstructure in Crypto Markets**
   - 流动性因子不具备统计显著性
   - 价格冲击主要用于交易成本估算

4. **Technical Analysis in Cryptocurrency Trading**
   - 传统技术指标（RSI, MACD）无显著 alpha
   - 可用于辅助判断，但不应作为主要信号

---

## 附录：完整因子列表

完整因子列表请参考 `04_shared/config/factors.yaml`。

**快速查询**:
```bash
# 查看所有因子集
uv run python -c "import yaml; print(yaml.safe_load(open('04_shared/config/factors.yaml'))['factor_sets'].keys())"

# 查看特定因子集
uv run python -c "import yaml; print(yaml.safe_load(open('04_shared/config/factors.yaml'))['factor_sets']['priority_1_momentum_reversal'])"
```

---

**文档版本**: v1.0  
**最后更新**: 2026-01-16  
**维护者**: Claude (Serena)
