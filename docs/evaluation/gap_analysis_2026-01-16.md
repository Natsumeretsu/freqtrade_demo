# 评估指标体系差距分析

更新日期：2026-01-16


## 执行摘要

当前项目已有基础的回测评估工具（Sharpe、Sortino、Calmar、最大回撤等），但与"加密货币因子测试评估指标体系完整指南"中提出的**100/100实战评估体系**相比，存在以下关键差距：

### 核心差距（P0 - 必须补齐）

1. **动态滑点模型缺失** - 当前使用固定滑点，未考虑波动率动态调整
2. **资金费率回测缺失** - 合约策略未扣除资金费率成本
3. **换手率调整后的IC缺失** - 无法评估因子的"净预测力"
4. **极端行情压力测试缺失** - 未针对3.12、5.19、FTX等极端事件单独测试
5. **参数平原测试缺失** - 无法识别过拟合的"参数孤岛"

### 次要差距（P1 - 强烈建议）

6. **IC衰减曲线分析缺失** - 无法确定最优持有期
7. **因子正交性检查缺失** - 可能存在高度相关的冗余因子
8. **回撤恢复时间未统计** - 只看MDD深度，不看恢复时长
9. **Omega比率缺失** - Sharpe假设正态分布，不适合加密市场
10. **Ulcer Index缺失** - 无法衡量"痛苦面积"

---

## 详细差距对比表

| 评估维度 | 100/100标准 | 当前项目状态 | 差距等级 | 影响 |
|---------|------------|------------|---------|------|
| **数据清洗层** |
| 时间戳对齐 | 强制T+1成交，禁止用Close价 | ✅ 已实现 | 无 | - |
| 资金费率 | 必须扣除每8h费率 | ❌ 未实现 | **P0** | 合约策略PnL虚高10-30% |
| 流动性过滤 | 盘口深度比率 > 5%剔除 | ⚠️ 部分实现 | P1 | 小币种回测价格失真 |
| **信号纯度层** |
| IC | ✅ 基础IC计算 | ✅ 已实现 | 无 | - |
| RankIC | ✅ 斯皮尔曼相关 | ❌ 未实现 | P2 | 排序策略评估不准 |
| 换手率调整IC | ✅ IC_adj = IC - 2×cost×turnover | ❌ 未实现 | **P0** | 高频因子虚假显著 |
| IC衰减曲线 | ✅ 1-28日IC对比 | ❌ 未实现 | **P0** | 持有期选择盲目 |
| 因子正交性 | ✅ 相关性矩阵+施密特正交 | ❌ 未实现 | P1 | 因子冗余，过拟合风险高 |
| **成本模型层** |
| 固定滑点 | ❌ 不推荐 | ✅ 当前使用 | **P0** | 低估极端行情成本 |
| 动态滑点 | ✅ slippage = base × (ATR_now / ATR_avg) | ❌ 未实现 | **P0** | 暴跌时滑点可达10倍 |
| 盈亏比分布 | ✅ 检查左尾肥尾 | ⚠️ 部分实现 | P1 | 未识别"黑天鹅"单笔 |
| **风险暴露层** |
| Sharpe | ✅ 已实现 | ✅ 已实现 | 无 | - |
| Sortino | ✅ 已实现 | ✅ 已实现 | 无 | - |
| Calmar | ✅ 已实现 | ✅ 已实现 | 无 | - |
| Omega比率 | ✅ 考虑高阶矩 | ❌ 未实现 | P1 | Sharpe对肥尾市场失效 |
| Ulcer Index | ✅ 回撤面积 | ❌ 未实现 | P1 | 无法衡量持续痛苦 |
| 最大回撤 | ✅ 已实现 | ✅ 已实现 | 无 | - |
| 回撤恢复时间 | ✅ 必须统计 | ❌ 未实现 | **P0** | 10% MDD恢复50笔 vs 25% MDD恢复5笔 |
| 极端压力测试 | ✅ 3.12/5.19/FTX单独测 | ❌ 未实现 | **P0** | 未知极端生存能力 |
| **稳健性层** |
| 参数平原测试 | ✅ ±15%参数波动 < 10% Sharpe变化 | ❌ 未实现 | **P0** | 无法识别过拟合 |
| 交易延迟敏感度 | ✅ 强制延迟1s/5s/10s | ❌ 未实现 | P1 | 高频策略实盘失效 |
| 市场状态适应性 | ✅ 牛/熊/震荡分层 | ⚠️ 部分实现 | P2 | 未量化Beta暴露 |
| Monte Carlo | ✅ 交易序列洗牌 | ✅ 已实现 | 无 | - |

---

## 当前项目已有工具盘点

### ✅ 已实现（可直接使用）

1. **[scripts/analysis/backtest_metrics.py](../../scripts/analysis/backtest_metrics.py)** - 提取基础指标（Sharpe/Sortino/Calmar/MDD/胜率/利润因子）
2. **[scripts/analysis/stress_test.py](../../scripts/analysis/stress_test.py)** - Monte Carlo压力测试（交易序列洗牌）
3. **[scripts/analysis/compare_backtest_zips.py](../../scripts/analysis/compare_backtest_zips.py)** - 回测结果对比
4. **[scripts/analysis/plot_equity.py](../../scripts/analysis/plot_equity.py)** - 资金曲线可视化
5. **[scripts/analysis/pair_report.py](../../scripts/analysis/pair_report.py)** - 逐交易对表现分析
6. **[01_freqtrade/archive/hyperopts/CompounderCalmarSortinoLoss.py](../../01_freqtrade/archive/hyperopts/CompounderCalmarSortinoLoss.py)** - 自定义HyperOpt损失函数（Calmar+Sortino）

### ⚠️ 部分实现（需增强）

1. **滑点处理** - `stress_test.py`支持固定滑点参数，但未实现动态滑点
2. **流动性过滤** - 数据下载时有成交量过滤，但回测时未动态检查盘口深度
3. **市场分层** - `pair_report.py`按交易对分层，但未按牛熊震荡分层

### ❌ 未实现（需新建）

1. **动态滑点模块** - 需新建 `scripts/lib/dynamic_slippage.py`
2. **资金费率回测** - 需修改 `scripts/lib/backtest_utils.py` 添加funding rate计算
3. **IC分析工具** - 需新建 `scripts/analysis/ic_analysis.py`
4. **因子正交性检查** - 需新建 `scripts/analysis/factor_orthogonality.py`
5. **参数平原测试** - 需新建 `scripts/analysis/parameter_plateau.py`
6. **极端行情测试** - 需新建 `scripts/analysis/extreme_events.py`
7. **回撤恢复时间** - 需修改 `backtest_metrics.py` 添加recovery duration计算

---

## 优先级实施路线图

### Phase 1: 数据地基修复（P0，预计2-3天）

**目标**: 确保回测数据不造假

1. **动态滑点模型** 
   - 文件: `scripts/lib/dynamic_slippage.py`
   - 功能: `calculate_dynamic_slippage(current_atr, avg_atr, base_slippage)`
   - 集成点: 修改 `stress_test.py` 的 `--slippage` 参数支持动态模式

2. **资金费率回测**
   - 文件: `scripts/lib/funding_rate.py`
   - 功能: `calculate_net_pnl_with_funding(trades, funding_rates)`
   - 数据源: 需下载OKX历史资金费率数据
   - 集成点: 修改 `backtest_metrics.py` 添加 `--include-funding` 参数

3. **回撤恢复时间统计**
   - 文件: 修改 `scripts/analysis/backtest_metrics.py`
   - 功能: 新增 `calculate_recovery_duration(equity_curve)` 函数
   - 输出: 在JSON结果中添加 `recovery_duration_trades` 和 `recovery_duration_days`

### Phase 2: 因子质量评估（P0，预计3-4天）

**目标**: 识别虚假因子和冗余因子

4. **IC衰减曲线分析**
   - 文件: `scripts/analysis/ic_decay.py`
   - 功能: 
     - `calculate_ic_by_holding_period(factor_values, forward_returns, periods=[1,3,7,14,28])`
     - `plot_ic_decay_curve(ic_dict)`
   - 输出: HTML图表 + CSV数据

5. **换手率调整后的IC**
   - 文件: 修改 `scripts/analysis/ic_decay.py`
   - 功能: `calculate_turnover_adjusted_ic(ic, cost, turnover)`
   - 阈值: IC_adj < 0.015 标记为"不可交易"

6. **因子正交性检查**
   - 文件: `scripts/analysis/factor_orthogonality.py`
   - 功能:
     - `calculate_factor_correlation_matrix(factors_df)`
     - `identify_redundant_factors(corr_matrix, threshold=0.7)`
     - `gram_schmidt_orthogonalization(factors_df)`
   - 输出: 相关性热力图 + 冗余因子列表

### Phase 3: 极端生存测试（P0，预计2天）

**目标**: 确保策略在极端行情下不爆仓

7. **极端行情压力测试**
   - 文件: `scripts/analysis/extreme_events.py`
   - 功能:
     - `test_extreme_period(backtest_zip, start_date, end_date, event_name)`
     - 硬编码测试区间:
       - `2020-03-12` to `2020-03-13` (3.12流动性枯竭)
       - `2021-05-19` to `2021-05-23` (5.19瀑布)
       - `2022-11-08` to `2022-11-10` (FTX崩盘)
   - 阈值: MDD < 20% 且无爆仓

8. **参数平原测试**
   - 文件: `scripts/analysis/parameter_plateau.py`
   - 功能:
     - `test_parameter_sensitivity(strategy, param_name, base_value, range_pct=0.15)`
     - 生成3D热力图（双参数扫描）
   - 阈值: ±15%参数变化，Sharpe变化 < 20%

### Phase 4: 高级风险指标（P1，预计2天）

**目标**: 补齐Sharpe/Sortino/Calmar之外的风险度量

9. **Omega比率与Ulcer Index**
   - 文件: 修改 `scripts/analysis/backtest_metrics.py`
   - 功能:
     - `calculate_omega_ratio(returns, threshold=0)`
     - `calculate_ulcer_index(equity_curve)`
   - 输出: 在JSON结果中添加 `omega` 和 `ulcer_index`

10. **盈亏比分布与肥尾检测**
    - 文件: `scripts/analysis/pnl_distribution.py`
    - 功能:
      - `analyze_pnl_distribution(trades)`
      - `detect_fat_tail_events(trades, threshold_pct=5.0)`
    - 输出: 分布直方图 + 极端单笔列表

---

## 实施建议

### 立即行动（本周内）

1. **创建评估工具目录结构**
   ```
   scripts/evaluation/
   ├── __init__.py
   ├── dynamic_slippage.py      # Phase 1
   ├── funding_rate.py           # Phase 1
   ├── ic_analysis.py            # Phase 2
   ├── factor_orthogonality.py   # Phase 2
   ├── extreme_events.py         # Phase 3
   ├── parameter_plateau.py      # Phase 3
   └── advanced_metrics.py       # Phase 4
   ```

2. **修改现有工具**
   - `scripts/analysis/backtest_metrics.py` - 添加回撤恢复时间、Omega、Ulcer Index
   - `scripts/analysis/stress_test.py` - 集成动态滑点模型

3. **下载必要数据**
   - OKX历史资金费率数据（2020-至今）
   - 极端事件期间的高频数据（用于滑点估算）

### 分阶段验证

每个Phase完成后，用**同一个回测结果**跑新旧评估工具对比：

```bash
# 旧工具（当前）
uv run python scripts/analysis/backtest_metrics.py --zip <path>

# 新工具（Phase 1完成后）
uv run python scripts/evaluation/enhanced_metrics.py --zip <path> --include-funding --dynamic-slippage

# 对比差异
uv run python scripts/evaluation/compare_old_vs_new.py --old <old_json> --new <new_json>
```

### 文档同步

每个新工具必须包含：
1. **Docstring** - 函数功能、参数、返回值、示例
2. **README** - 工具用途、使用方法、输出解释
3. **测试用例** - 至少1个单元测试（`tests/evaluation/`）

---

## 风险提示

### 数据依赖风险

- **资金费率数据**: OKX API限流，需分批下载，预计耗时1-2小时
- **极端事件数据**: 部分交易所在极端行情时API不稳定，可能缺失数据

### 计算性能风险

- **IC衰减曲线**: 需要逐笔计算前向收益，大数据集（>10万笔交易）可能耗时>10分钟
- **参数平原测试**: 双参数扫描需要N×M次回测，建议先用小数据集验证

### 过度拟合风险

- **不要为了"通过测试"而调参**: 极端行情测试的目的是发现问题，不是优化参数
- **样本外验证仍是王道**: 所有新指标都必须在样本外数据上验证

---

## 附录：关键公式速查

### 动态滑点
```python
slippage = base_slippage * np.clip(current_atr / avg_atr, 1.0, 5.0)
```

### 换手率调整IC
```python
IC_adj = IC - 2 * transaction_cost * daily_turnover
```

### Omega比率
```python
omega = sum(max(r - threshold, 0) for r in returns) / sum(max(threshold - r, 0) for r in returns)
```

### Ulcer Index
```python
ulcer = sqrt(mean((drawdown_pct ** 2)))
```

### 回撤恢复时间
```python
recovery_duration = first_index_where(equity >= previous_high) - drawdown_start_index
```

---

**文档版本**: v1.0  
**创建日期**: 2026-01-16  
**维护者**: Claude (Serena)  
**下次更新**: Phase 1完成后
