# FreqAI 分类模型迁移报告

**日期**: 2026-01-19
**策略**: ETHFreqAIStrategy
**变更类型**: 重大架构改进

## 执行摘要

基于深度研究和系统分析，将FreqAI策略从回归模型切换到分类模型，直接解决止损亏损超过ROI盈利的根本问题。

## 问题诊断

### 回归模型的根本缺陷

**测试结果**（第一阶段改进后）：
| 时段 | 交易数 | 收益率 | PF | ROI盈利 | 止损亏损 | 止损/ROI比 |
|------|--------|--------|-----|---------|----------|-----------|
| 1月 | 15 | -9.39% | 0.53 | +107.0 | -200.9 | 1.88x |
| 2-3月 | 33 | -12.77% | 0.65 | +233.7 | -342.9 | 1.47x |
| 7-8月 | 47 | -23.5% | 0.58 | +318.1 | -553.1 | 1.74x |
| 10-11月 | 40 | +2.44% | 1.08 | +314.9 | -290.5 | 0.92x |

**核心问题**：
- 除10-11月（牛市）外，所有时段止损亏损都超过ROI盈利1.5-2倍
- 回归模型预测"平均收益"，但无法预测"会先触发止损"
- 模型能识别"最终会盈利"的机会，但无法识别"止损风险"

### 研究证据

**Perplexity深度研究**（13,000+字）关键发现：
1. **分类模型显著优于回归**：7/8的分类模型Sharpe比率显著高于回归模型
2. **回归模型本质缺陷**：优化平方误差，但交易需要的是二元决策
3. **"如果最终要阈值化输出，应该直接训练分类问题"**
4. **分类模型对噪声更鲁棒**：不会因小误差受惩罚

## 解决方案：综合改进方案

### 阶段1：核心改进（已完成）

#### 1. 切换到LightGBMClassifier

**变更**：
```python
# 从 LightGBMRegressor 切换到 LightGBMClassifier
--freqaimodel LightGBMClassifier
```

#### 2. 重新定义预测目标（二分类）

**原始目标**（回归）：
```python
# 预测未来20期的平均收益率
dataframe["&-s_close"] = (
    dataframe["close"].shift(-20).rolling(20).mean() / dataframe["close"] - 1
)
```

**新目标**（分类）：
```python
# 预测交易结果：能否在不触发止损的情况下达到+1% ROI目标
dataframe['&s-trade_outcome'] = 'not_reaches_target'
dataframe.loc[reaches_target & ~hits_stoploss, '&s-trade_outcome'] = 'reaches_target'
```

**目标定义逻辑**：
- 向前查看40期（200分钟）
- 检查未来最高价是否达到+1% ROI目标
- 检查未来最低价是否触发-5%止损
- 只有"达到目标且未触发止损"才标记为成功

**为什么是二分类而不是三分类？**
- 初始设计：三分类（reaches_target/hits_stoploss/neither）
- 遇到问题：某些训练窗口没有hits_stoploss样本，导致类别不平衡错误
- 解决方案：二分类更简单且符合交易逻辑（只关心"能否成功"）

#### 3. 扩展训练数据

**变更**：
```json
{
  "train_period_days": 60,  // 从15天增加到60天
  "identifier": "eth_lgb_clf_v1",  // 新模型标识符
  "continual_learning": true  // 启用持续学习
}
```

**理由**：
- 60天提供更稳定的特征统计
- 暴露于更多样化的市场条件
- continual_learning保留先前训练的"记忆"，在多个regime中积累知识

#### 4. 修改入场逻辑

**原始逻辑**（回归）：
```python
dataframe.loc[
    (dataframe['do_predict'] == 1) &
    (dataframe['&-s_close'] > 0.002),  # 预测收益 > 0.2%
    'enter_long'
] = 1
```

**新逻辑**（分类）：
```python
dataframe.loc[
    (dataframe['do_predict'] == 1) &
    (dataframe['&s-trade_outcome_reaches_target'] > 0.65),  # 成功概率 > 65%
    'enter_long'
] = 1
```

### 阶段2：特征增强（待实施）

计划添加专门预测止损风险的特征：
- **盘中波动率**：`(high - low) / close`
- **均值回归强度**：Hurst指数或自相关系数
- **波动率regime分类**：基于多时间框架波动率聚类

### 阶段3：验证与优化（待实施）

- Walk-forward验证（多个时间窗口）
- 参数鲁棒性测试
- Ensemble方法（LightGBM + XGBoost + CatBoost）

## 预期效果

**正面预期**：
- ✅ 直接解决止损问题（模型学习预测止损风险）
- ✅ 提高信号质量（只在高概率成功时入场）
- ✅ 减少市场环境依赖性（continual learning适应不同regime）
- ✅ 可能降低交易频率但显著提高胜率和PF

**潜在风险**：
- ⚠️ 交易频率可能显著降低（更严格的入场条件）
- ⚠️ 需要更长的训练时间（60天数据）
- ⚠️ 二分类可能过于简化（未来可考虑多任务学习）

## 技术细节

### 文件修改

**策略文件**：`ft_userdir/strategies/ETHFreqAIStrategy.py`
- 添加 `import numpy as np`
- 修改 `set_freqai_targets()` 方法（回归→分类）
- 修改 `populate_entry_trend()` 方法（阈值→概率）
- 更新文档字符串

**配置文件**：`ft_userdir/config_freqai.json`
- `train_period_days`: 15 → 60
- `identifier`: "eth_lgb_v1" → "eth_lgb_clf_v1"
- 新增 `continual_learning`: true

### 数据准备

下载了额外的历史数据：
```bash
# 从2023年10月开始（支持60天训练）
pwsh -File ./scripts/ft.ps1 download-data \
  --pairs ETH/USDT:USDT \
  --timeframes 5m 15m 1h \
  --timerange 20231001-20241231 \
  --prepend
```

## 测试计划

### 测试时段

与回归模型使用相同的测试时段以便对比：
1. **1月**（2024-01-01 至 2024-01-31）
2. **2-3月**（2024-02-01 至 2024-03-31）
3. **7-8月**（2024-07-01 至 2024-08-31）
4. **10-11月**（2024-10-01 至 2024-11-30）

### 评估指标

对比回归模型和分类模型：
- 交易频率（trades/month）
- 总收益率（%）
- Profit Factor
- ROI出场盈利 vs 止损出场亏损
- 止损/ROI比率（关键指标）
- 胜率（%）
- 最大回撤（%）

### 成功标准

分类模型应该：
1. **止损/ROI比率 < 1.0**（所有时段）
2. **Profit Factor > 1.0**（至少3/4时段）
3. **总收益率 > 0%**（全年累计）
4. **胜率 > 60%**（提高信号质量）

## 参考资料

### 研究报告

- **Perplexity Research**（2026-01-19）：13,000+字深度分析
  - 分类 vs 回归在金融交易中的应用
  - FreqAI最佳实践
  - 止损风险预测方法

### 关键引用

> "In finance, classification often wins in practice for several crucial reasons. First, classification models reduce sensitivity to noise by focusing on decision boundaries rather than magnitude predictions."

> "An empirical study comparing machine learning approaches found that for classification algorithms, 7 out of 8 machine learning models have significantly higher Sharpe ratio than models trained with regression."

> "If you are going to threshold it at the end, there is a strong argument for training the model to solve the thresholded problem directly."

## 下一步行动

1. ✅ 完成阶段1核心改进
2. ⏳ 测试分类模型（1月、2-3月、7-8月、10-11月）
3. ⏳ 分析结果并与回归模型对比
4. ⏳ 根据结果决定是否实施阶段2（特征增强）
5. ⏳ 实施阶段3（验证与优化）

## 版本历史

- **v1.0**（2026-01-19）：初始版本，记录分类模型迁移
