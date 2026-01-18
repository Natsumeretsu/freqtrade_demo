# docs/ 目录结构分析报告

更新日期：2026-01-17

## 1. 概览

**总文件数**：5953 个 markdown 文件

**目录结构**：
```
docs/
├── archive/          5885 files (212MB) - 归档文档
│   └── strategies_ref_docs/  5808 files (Git 子模块)
├── evaluation/       15 files - 策略评估与分析
├── factors/          2 files - 因子分类与研究
├── guidelines/       2 files - 规范与指南
├── knowledge/        22 files - 知识库与参考资料
├── remp_research/    6 files - 研究笔记
├── reports/          13 files - 变更摘要与技术报告
├── setup/            1 file - 环境配置
└── tools/            0 files - 工具文档（已清空）
```

---

## 2. 各目录详细分析

### 2.1 archive/ (5885 files)

**定位**：归档文档，包含历史策略参考和设计文档

**子目录**：
- `strategies_ref_docs/` (5808 files, Git 子模块)：Freqtrade 策略参考文档
- 其他归档文档 (77 files)

**问题**：
- ✅ 结构清晰，Git 子模块管理得当
- ⚠️ 需要确认 77 个非子模块文件的分类是否合理

**建议**：
- 保持现状，定期审查归档内容

---

### 2.2 evaluation/ (15 files)

**定位**：策略评估、回测分析、参数优化

**文件列表**：
1. `academic_factors_ic_analysis_2026-01-16.md` - 学术因子 IC 分析
2. `factor_quality_analysis_2026-01-16.md` - 因子质量分析
3. `factor_quality_deep_analysis_2026-01-16.md` - 因子质量深度分析
4. `factor_reselection_analysis_2026-01-16.md` - 因子重选分析
5. `gap_analysis.md` - 差距分析
6. `p0_2_risk_warning_design.md` - P0 风险预警设计
7. `p0_fix_verification_report_2026-01-16.md` - P0 修复验证报告
8. `p0_improvements_backtest_results_2026-01-16.md` - P0 改进回测结果
9. `p0_improvements_summary_2026-01-16.md` - P0 改进总结
10. `parameter_optimization_comparison_2026-01-16.md` - 参数优化对比
11. `parameter_optimization_failure_analysis_plan_b.md` - 参数优化失败分析
12. `strategy_fix_proposal_SmallAccountFuturesTimingExecV1.md` - 策略修复方案
13. `strategy_fix_proposal_v2.md` - 策略修复方案 v2
14. `strategy_optimization_verification_report_2026-01-16.md` - 策略优化验证报告
15. `tools_usage_guide.md` - 工具使用指南

**问题**：
- ⚠️ 文件命名不统一（有的带日期，有的不带）
- ⚠️ 部分文件可能已过时（如 `gap_analysis.md` 无日期）
- ⚠️ `tools_usage_guide.md` 可能应该移到 `guidelines/` 或 `setup/`

**建议**：
- 统一命名规范：`<主题>_<日期>.md`
- 定期归档过时的评估报告到 `archive/evaluation/`
- 考虑将 `tools_usage_guide.md` 移到更合适的位置

---

### 2.3 factors/ (2 files)

**定位**：因子分类与研究

**文件列表**：
1. `time_series_factors_classification.md` - 时间序列因子分类
2. `time_series_factors_part2.md` - 时间序列因子（第二部分）

**问题**：
- ⚠️ 文件命名不统一（part2 应该是 part_2 或 _part2）
- ⚠️ 文件数量较少，可能应该合并到 `knowledge/` 目录

**建议**：
- 考虑将这 2 个文件移到 `knowledge/` 目录
- 或者扩充 `factors/` 目录内容，使其成为独立的因子研究目录

---

### 2.4 guidelines/ (2 files)

**定位**：规范与指南

**文件列表**：
1. `backtest_reporting_standard.md` - 回测报告标准
2. `refactor_policy.md` - 重构规范

**问题**：
- ✅ 结构清晰，文件命名规范
- ⚠️ 文件数量较少，可能需要补充更多规范文档

**建议**：
- 补充更多规范文档（如代码风格、提交规范、文档编写规范等）
- 考虑将 `evaluation/tools_usage_guide.md` 移到此目录

---

### 2.5 knowledge/ (22 files)

**定位**：知识库与参考资料

**文件分类**：

**A. 索引与规范 (4 files)**：
- `index.md` - 知识结构索引
- `source_registry.md` - 外部来源登记
- `project_naming_conventions.md` - 项目命名规范
- `factor_ablation_checklist_smallaccount_futures.md` - 因子消融检查清单

**B. 策略与交易 (3 files)**：
- `crypto_exchange_strategy_deep_dive.md` - 加密交易策略深入分析
- `small_account_10_to_10000_practice_guide.md` - 小账户实践指南
- `candlestick_pinbar_playbook.md` - K线与 Pinbar 战法

**C. 技术指标 (2 files)**：
- `ema_macd_vegas_playbook.md` - EMA/MACD/Vegas 隧道
- `crypto_liquidity_microstructure_playbook.md` - 流动性微观结构

**D. 因子模型 (7 files)**：
- `crypto_risk_factors_engineering_playbook.md` - 风险因子工程化
- `crypto_pricing_five_factor_models_playbook.md` - 五因子定价模型
- `crypto_factor_model_implementation_playbook.md` - 因子模型实现
- `crypto_factor_model_ecosystem_survey.md` - 因子模型生态综述
- `crypto_price_forecasting_models_playbook.md` - 价格预测模型
- `causal_factor_identification_crypto_playbook.md` - 因果特征识别
- `factor_single_vs_multi_timing.md` - 单因子 vs 多因子

**E. 工程与工具 (4 files)**：
- `freqtrade_qlib_engineering_workflow.md` - Freqtrade + Qlib 工程化
- `crypto_information_theory_signal_system_playbook.md` - 信息论与信号系统
- `mcp_browser_automation_landscape.md` - MCP 浏览器自动化选型
- `mcp_knowledge_memory_landscape.md` - MCP 知识管理选型

**F. 业界实践 (2 files)**：
- `industry_best_practices_support_analysis.md` - 业界最佳实践支撑分析
- `industry_best_practices_improvement_space.md` - 业界最佳实践改进空间

**问题**：
- ✅ 文件命名规范统一（使用下划线分隔）
- ✅ 内容分类清晰
- ⚠️ 文件数量较多（22 个），可能需要进一步细分子目录

**建议**：
- 考虑创建子目录：`knowledge/strategies/`、`knowledge/factors/`、`knowledge/tools/`
- 保持 `index.md` 和 `source_registry.md` 在根目录

---

### 2.6 remp_research/ (6 files)

**定位**：研究笔记（临时性、探索性）

**文件列表**：
1. `qlib结合freqtrade研究alpha因子与风险因子.md`
2. `qlib自带哪些因子？因子库？怎么使用和研究？针对加密市场.md`
3. `聚焦华泰期货的CTA 量化策略因子系列，与加密货币市场的应用要点与不足.md`
4. `业界实现深度调查：因子与策略分离、依赖倒置的设计与实践.md`
5. `业界实现深度调查：因子与策略分离、依赖倒置的设计与实践2.md`
6. `总共有CTA量化策略因子系列（一）到（七）全部获取聚焦，与加密货币市场的应用要点与不足.md`

**问题**：
- ⚠️ 文件命名不规范（使用中文、问号、过长）
- ⚠️ 文件名过于描述性，不便于引用
- ⚠️ 部分文件可能已提炼完成，应该移到 `knowledge/` 或归档

**建议**：
- 重命名为规范格式：`<主题>_research_<日期>.md`
- 定期审查：提炼完成的移到 `knowledge/`，过时的归档到 `archive/research/`
- 考虑将此目录重命名为 `research/` 或 `drafts/`

---

### 2.7 reports/ (14 files)

**定位**：变更摘要与技术报告

**文件分类**：

**A. 变更摘要 (4 files)**：
- `change_summary_2026-01-12.md`
- `change_summary_2026-01-13.md`
- `change_summary_2026-01-14.md`
- `change_summary_2026-01-15.md`

**B. 技术报告 (10 files)**：
- `crypto_trading_framework_review_2026-01-15_v1.0.md`
- `improvement_plan_timing_prediction_2026-01-15.md`
- `local_vector_db_review_2026-01-15_v1.0.md`
- `no_wheel_audit_2026-01-14.md`
- `plan_SmallAccountFuturesTrendV1_2026-01-13.md`
- `quant_trading_full_stack_guide_2026-01-15_v1.0.md`
- `risk_pain_points_SmallAccountSpotTrendFilteredV1_4h_2026-01-12.md`
- `small_account_benchmark_SmallAccountSpotTrendFilteredV1_4h_2026-01-12.md`
- `tech_debt_review_2026-01-15_v1.0.md`
- `docs_structure_analysis_2026-01-17.md` (本文档)

**问题**：
- ✅ 文件命名规范统一（带日期）
- ✅ 内容分类清晰
- ⚠️ 部分历史报告包含已废弃的 vbrain 引用（已添加废弃说明）

**建议**：
- 保持现状，继续使用统一的命名规范
- 定期归档过时的报告到 `archive/reports/`

---

### 2.8 setup/ (1 file)

**定位**：环境配置与设置指南

**文件列表**：
- `claude_mcp_sync.md` - Claude MCP 同步配置

**问题**：
- ⚠️ 文件数量过少（仅 1 个）
- ⚠️ 可能需要补充更多环境配置文档

**建议**：
- 补充更多配置文档（如开发环境配置、依赖安装指南等）
- 考虑将 `evaluation/tools_usage_guide.md` 移到此目录

---

### 2.9 tools/ (0 files)

**定位**：工具文档（已清空）

**状态**：
- ✅ 已清空（vbrain 相关工具文档已删除）

**建议**：
- 如果未来有新的工具文档，可以使用此目录
- 或者考虑删除此空目录

---

## 3. 整体问题与建议

### 3.1 主要问题

**A. 命名规范不统一**：
- `remp_research/` 目录文件命名不规范（中文、问号、过长）
- `evaluation/` 部分文件缺少日期
- `factors/` 文件命名不一致（part2 vs part_2）

**B. 目录职责不清晰**：
- `factors/` 仅 2 个文件，可能应该合并到 `knowledge/`
- `tools/` 目录已清空，可以删除
- `remp_research/` 命名不直观（建议改为 `research/` 或 `drafts/`）

**C. 文件分类不合理**：
- `evaluation/tools_usage_guide.md` 应该移到 `guidelines/` 或 `setup/`
- `knowledge/` 目录文件过多（22 个），需要细分子目录

**D. 历史文档管理**：
- 部分过时文档未归档
- 历史报告包含已废弃的 vbrain 引用（已添加废弃说明）

---

### 3.2 整改建议（优先级排序）

**P0 - 立即执行**：

1. **删除空目录**：
   - 删除 `docs/tools/` 目录（已清空）

2. **移动错位文件**：
   - 将 `evaluation/tools_usage_guide.md` 移到 `guidelines/` 或 `setup/`

**P1 - 短期执行（1-2 周内）**：

3. **重命名 remp_research 目录**：
   - 将 `remp_research/` 重命名为 `research/`
   - 规范化目录内文件命名：`<主题>_research_<日期>.md`

4. **细分 knowledge 目录**：
   - 创建子目录：`knowledge/strategies/`、`knowledge/factors/`、`knowledge/tools/`
   - 按分类移动文件到对应子目录
   - 保持 `index.md` 和 `source_registry.md` 在根目录

5. **合并 factors 目录**：
   - 将 `factors/` 目录的 2 个文件移到 `knowledge/factors/`
   - 删除 `factors/` 目录

**P2 - 长期优化（按需执行）**：

6. **统一命名规范**：
   - 为所有评估文档添加日期：`<主题>_<日期>.md`
   - 规范化 research 目录文件命名

7. **定期归档**：
   - 建立归档机制：每月审查过时文档
   - 创建 `archive/evaluation/`、`archive/research/` 子目录
   - 移动过时文档到归档目录

8. **补充文档**：
   - 在 `guidelines/` 补充更多规范文档
   - 在 `setup/` 补充环境配置文档

---

## 4. 总结

**当前状态**：
- 总文件数：5953 个 markdown 文件
- 主要问题：命名规范不统一、目录职责不清晰、文件分类不合理
- 已完成清理：vbrain 相关工具文档已删除，历史报告已添加废弃说明

**下一步行动**：
1. 执行 P0 任务：删除空目录、移动错位文件
2. 执行 P1 任务：重命名目录、细分 knowledge、合并 factors
3. 建立长期维护机制：定期审查、归档过时文档

**预期收益**：
- 提升文档可维护性
- 降低查找成本
- 提高文档质量

---

**报告版本**：v1.0
**创建日期**：2026-01-17
**状态**：已完成
