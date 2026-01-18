# 因子测试脚本深度分析报告

**日期**: 2026-01-17
**方法**: 在线资料搜索 + Sequential Thinking 交叉验证
**状态**: 识别出 8 个新问题，4 个 P1 优先级

---

## 执行摘要

基于在线搜索的学术文献和行业最佳实践，结合 Sequential Thinking 深度分析，我们识别出当前因子测试脚本的 8 个新问题。这些问题分为两个优先级：

- **P1（重要，应该修复）**: 4 个问题，直接影响因子筛选的可靠性
- **P2（可选，建议修复）**: 4 个问题，提升分析的完整性

---

## 问题清单

### P1 优先级（重要）

| # | 问题 | 影响 | 来源 |
|---|------|------|------|
| 1 | 自相关性检验缺失 | p-value 可能过于乐观 | Newey-West 文献 |
| 2 | 因子衰减分析缺失 | 无法确定最优持仓周期 | Factor Decay 文献 |
| 3 | 换手率分析缺失 | 无法评估实际可行性 | Turnover 文献 |
| 4 | 多重假设检验未校正 | 假阳性率过高 | 统计错误文献 |

### P2 优先级（可选）

| # | 问题 | 影响 | 来源 |
|---|------|------|------|
| 5 | 交易成本未考虑 | 高估策略收益 | AQR, BSIC 文献 |
| 6 | 因子分布未检查 | 异常值影响结果 | 心理学评估文献 |
| 7 | 样本外测试不足 | 稳健性证据不足 | 量化研究文献 |
| 8 | 因子正交性未检查 | 因子冗余 | Factor Analysis 文献 |

---

## 搜索资料来源

### 关键文献

1. **Newey-West 标准误**
   - Wikipedia: Newey-West estimator
   - UC Davis: Chapter 9 Correlated Errors
   - Princeton: HAC Corrections for Strongly Autocorrelated Time Series

2. **因子衰减分析**
   - tech-champion.com: Manage factor decay by adaptive weights
   - GitHub: machine-learning-for-trading/04_alpha_factor_research

3. **换手率与交易成本**
   - AQR Capital: Transactions Costs - Practical Application
   - BSIC: Backtesting Series Episode 5: Transaction Cost Modelling
   - Substack: Transaction-cost-aware Factors

4. **统计方法**
   - PMC: Ten common statistical mistakes
   - ResearchGate: Factor Analysis Common Pitfalls
   - Wiley: Ten common statistical errors from all phases of research

---

## 详细问题分析

### P1-1: 自相关性检验（Autocorrelation）

**问题**: 时间序列 IC 可能存在自相关，导致 p-value 过于乐观。

**解决方案**:
- 添加 Ljung-Box 检验检测自相关
- 使用 Newey-West 标准误调整 p-value
- 滞后阶数: `lag = floor(4 * (T/100)^(2/9))`

**优先级**: P1 - 影响统计推断有效性

---

### P1-2: 因子衰减分析（Factor Decay）

**问题**: 未分析 IC 随 horizon 的衰减模式。

**解决方案**:
- 绘制 IC vs horizon 曲线
- 计算半衰期
- 识别最优持仓周期

**优先级**: P1 - 影响交易策略设计

---

### P1-3: 换手率分析（Turnover）

**问题**: 未评估因子换手率，无法判断实际可行性。

**解决方案**:
- 计算因子值自相关性
- 估算预期换手率
- 评估 IC vs 换手率权衡

**优先级**: P1 - 影响策略实施

---

### P1-4: 多重假设检验（Multiple Testing）

**问题**: 测试 36 个假设（9 因子 × 4 horizon）未校正，假阳性率高。

**解决方案**:
- Bonferroni 校正: `α_adj = 0.05 / 36 = 0.0014`
- 或 FDR（Benjamini-Hochberg）校正
- 报告校正后 p-value

**优先级**: P1 - 影响因子筛选可靠性

---

## 实施计划

**阶段 1（立即执行）**:
1. 增强 IC 计算模块，添加自相关检验
2. 创建因子衰减分析脚本
3. 创建换手率分析脚本
4. 添加多重检验校正

**阶段 2（后续优化）**:
5. 添加交易成本估算
6. 添加因子分布检查
7. 增强样本外测试
8. 添加因子相关性分析

---
