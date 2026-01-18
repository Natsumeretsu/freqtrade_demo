# 项目文档索引

更新日期：2026-01-17

欢迎来到 freqtrade_demo 项目文档中心。本索引帮助你快速找到所需文档。

---

## 快速导航

### 核心文档
- [知识库](knowledge/index.md) - 策略、因子、工具知识沉淀
- [规范指南](guidelines/) - 代码、文档、Git 提交规范
- [架构文档](architecture/) - 系统架构与目录结构说明

### 报告与分析
- [技术报告](reports/) - 变更摘要、技术债务、架构分析
- [评估报告](evaluation/) - 策略评估、回测分析、参数优化

### 研究与配置
- [研究笔记](research/) - 探索性研究、文献调研
- [环境配置](setup/) - 开发环境、MCP 配置

---

## 文档分类

### 按类型分类

**规范类**（长期稳定）：
- `guidelines/` - 项目规范与指南
  - 代码风格指南
  - Git 提交规范
  - 文档编写规范
  - 回测报告标准
  - 归档策略

**知识类**（定期更新）：
- `knowledge/` - 可复用的项目知识
  - `strategies/` - 交易策略知识
  - `factors/` - 因子模型知识
  - `tools/` - 工程化工具知识

**架构类**（长期稳定）：
- `architecture/` - 系统架构文档
  - 目录结构说明
  - MCP 集成架构

**报告类**（定期更新）：
- `reports/` - 技术报告与分析
- `evaluation/` - 策略评估报告

**研究类**（临时性）：
- `research/` - 探索性研究笔记

---

## 按更新频率分类

| 频率 | 目录 | 说明 |
|------|------|------|
| 长期稳定 | guidelines/, architecture/ | 基础规范，很少变动 |
| 定期更新 | knowledge/, reports/ | 持续积累，定期补充 |
| 临时性 | research/, evaluation/ | 阶段性产出，完成后归档 |

---

## 文档目录详解

### knowledge/ - 知识库
**用途**：沉淀可复用的项目知识

**子目录**：
- `strategies/` - 交易策略相关知识（7 个文档）
- `factors/` - 因子模型相关知识（10 个文档）
- `tools/` - 工程化工具相关知识（4 个文档）

**核心文档**：
- [知识结构索引](knowledge/index.md)
- [来源登记清单](knowledge/source_registry.md)

---

### guidelines/ - 规范指南
**用途**：项目开发规范与最佳实践

**文档列表**：
- [代码风格指南](guidelines/code_style_guide.md)
- [Git 提交规范](guidelines/git_commit_conventions.md)
- [文档编写规范](guidelines/documentation_writing_guide.md)
- [文档命名规范](guidelines/document_naming_conventions.md)
- [回测报告标准](guidelines/backtest_reporting_standard.md)
- [归档策略](guidelines/archive_policy.md)
- [重构规范](guidelines/refactor_policy.md)
- [工具使用指南](guidelines/tools_usage_guide.md)

---

### architecture/ - 架构文档
**用途**：系统架构与设计说明

**文档列表**：
- [目录结构说明](architecture/directory_structure.md) - 4层架构、各目录用途、临时文件管理规范

**规划中**：
- MCP 集成架构文档（mcp_integration.md）
- 数据流向图（data_flow.md）

---

### reports/ - 技术报告
**用途**：技术分析、变更摘要、架构评审

**核心报告**：
- [项目结构分析](reports/project_structure_analysis_2026-01-17.md) - 根目录清理、临时文件管理
- [文档结构分析](reports/docs_structure_analysis_2026-01-17.md) - 文档组织优化
- [Markdown 文档管理建议](reports/markdown_documentation_management_recommendations_2026-01-17.md) - MkDocs 推荐方案

**变更摘要**（按日期）：
- [2026-01-15](reports/change_summary_2026-01-15.md)
- [2026-01-14](reports/change_summary_2026-01-14.md)
- [2026-01-13](reports/change_summary_2026-01-13.md)
- [2026-01-12](reports/change_summary_2026-01-12.md)

**技术评审**：
- [技术债务评审](reports/tech_debt_review_2026-01-15_v1.0.md)
- [加密货币交易框架评审](reports/crypto_trading_framework_review_2026-01-15_v1.0.md)
- [本地向量数据库评审](reports/local_vector_db_review_2026-01-15_v1.0.md)
- [量化交易全栈指南](reports/quant_trading_full_stack_guide_2026-01-15_v1.0.md)

**策略分析**：
- [SmallAccountSpotTrendFilteredV1 基准测试](reports/small_account_benchmark_SmallAccountSpotTrendFilteredV1_4h_2026-01-12.md)
- [SmallAccountSpotTrendFilteredV1 风险痛点](reports/risk_pain_points_SmallAccountSpotTrendFilteredV1_4h_2026-01-12.md)
- [SmallAccountFuturesTrendV1 改进计划](reports/plan_SmallAccountFuturesTrendV1_2026-01-13.md)
- [择时预测改进计划](reports/improvement_plan_timing_prediction_2026-01-15.md)

**其它**：
- [no-wheel 审计](reports/no_wheel_audit_2026-01-14.md)

---

### evaluation/ - 评估报告
**用途**：策略评估、回测分析、参数优化

**策略修复与优化**：
- [SmallAccountFuturesTimingExecV1 修复方案](evaluation/strategy_fix_proposal_SmallAccountFuturesTimingExecV1_2026-01-16.md)
- [策略修复方案 v2](evaluation/strategy_fix_proposal_v2_2026-01-16.md)
- [P0 修复验证报告](evaluation/p0_fix_verification_report_2026-01-16.md)
- [P0 改进摘要](evaluation/p0_improvements_summary_2026-01-16.md)
- [P0 改进回测结果](evaluation/p0_improvements_backtest_results_2026-01-16.md)
- [策略优化验证报告](evaluation/strategy_optimization_verification_report_2026-01-16.md)

**因子分析**：
- [学术因子 IC 分析](evaluation/academic_factors_ic_analysis_2026-01-16.md)
- [因子质量分析](evaluation/factor_quality_analysis_2026-01-16.md)
- [因子质量深度分析](evaluation/factor_quality_deep_analysis_2026-01-16.md)
- [因子重选分析](evaluation/factor_reselection_analysis_2026-01-16.md)

**参数优化**：
- [参数优化对比](evaluation/parameter_optimization_comparison_2026-01-16.md)
- [参数优化失败分析 Plan B](evaluation/parameter_optimization_failure_analysis_plan_b_2026-01-16.md)

**其它**：
- [差距分析](evaluation/gap_analysis_2026-01-16.md)
- [P0.2 风险警告设计](evaluation/p0_2_risk_warning_design_2026-01-16.md)

---

### research/ - 研究笔记
**用途**：探索性研究、文献调研

**因子研究**（2026-01-13）：
- [CTA 因子系列加密货币研究](research/cta_factors_series_crypto_research_2026-01-13.md)
- [华泰 CTA 因子加密货币研究](research/huatai_cta_factors_crypto_research_2026-01-13.md)
- [Qlib 因子库加密货币研究](research/qlib_factor_library_crypto_research_2026-01-13.md)
- [Qlib-Freqtrade 因子研究](research/qlib_freqtrade_factors_research_2026-01-13.md)

**策略研究**（2026-01-13）：
- [行业因子策略分离研究](research/industry_factor_strategy_separation_research_2026-01-13.md)
- [行业因子策略分离研究 Part 2](research/industry_factor_strategy_separation_research_part2_2026-01-13.md)

---

### setup/ - 环境配置
**用途**：开发环境配置、工具设置

**文档列表**：
- [Claude MCP 同步指南](setup/claude_mcp_sync.md) - Codex CLI 配置、MCP 服务器设置

**规划中**：
- 新设备对接流程（new_device_onboarding.md）
- Git 同步策略（git_sync_policy.md）

---

### archive/ - 归档文档
**用途**：过时文档、历史参考

**说明**：
- 包含已过时但有参考价值的文档
- 定期归档（每月第一周）
- 归档标准见 [归档策略](guidelines/archive_policy.md)

**子目录**：
- `freqtrade_docs/` - Freqtrade 官方文档离线版
- `strategies_ref_docs/` - 策略参考库（Git 子模块）
- `other_doc/` - 其它参考文档

---

## 源代码文档

以下是项目源代码目录中的 README 文档，提供各模块的使用说明：

### Freqtrade 相关
- [自定义 FreqAI 模型说明](../01_freqtrade/archive/freqaimodels/README.md) - FreqAI 自定义预测模型开发指南

### Qlib 研究相关
- [实验记录目录说明](../02_qlib_research/experiments/README.md) - 实验记录规范与目录结构
- [lgbm_trend_v1 实验](../02_qlib_research/experiments/lgbm_trend_v1/README.md) - LightGBM 趋势预测实验详细记录

### 配置相关
- [配置模板说明](../04_shared/configs/README.md) - 配置文件使用指南
- [FreqAI 配置说明](../04_shared/configs/archive/freqai/README.md) - FreqAI 配置示例与使用方法

### 项目配置文件
- [项目 README](../README.md) - 项目总体说明与快速开始
- [Claude Code 配置](../CLAUDE.md) - Claude Code 工作指南（独立配置文件）
- [自动化助手指南](../AGENTS.md) - 自动化助手配置（独立配置文件）

---

## 文档使用指南

### 如何查找文档

**按任务类型查找**：
- 学习项目规范 → `guidelines/`
- 了解系统架构 → `architecture/`
- 查看技术分析 → `reports/`
- 查看策略评估 → `evaluation/`
- 学习策略/因子知识 → `knowledge/`
- 查看研究笔记 → `research/`
- 配置开发环境 → `setup/`

**按更新频率查找**：
- 长期稳定文档 → `guidelines/`, `architecture/`
- 定期更新文档 → `knowledge/`, `reports/`
- 临时性文档 → `research/`, `evaluation/`

**使用搜索**（推荐）：
- 使用 IDE 全局搜索（Ctrl+Shift+F）
- 使用 `grep` 命令搜索关键词
- 未来：使用 MkDocs 内置搜索功能

### 文档命名规范

所有文档遵循统一命名规范：
- 格式：`<主题>_<日期>.md` 或 `<主题>_<日期>_<版本>.md`
- 日期格式：`YYYY-MM-DD`（ISO 8601）
- 示例：`project_structure_analysis_2026-01-17.md`

详见：[文档命名规范](guidelines/document_naming_conventions.md)

---

## 文档维护

### 创建新文档

**步骤**：
1. 确定文档类型和目标目录
2. 使用规范的命名格式
3. 添加文档元数据（更新日期、版本、状态）
4. 遵循 [文档编写规范](guidelines/documentation_writing_guide.md)
5. 更新相关索引文件

**元数据格式**：
```markdown
# 文档标题

更新日期：YYYY-MM-DD
[可选] 版本：v1.0
[可选] 状态：草稿/已完成/已归档
```

### 更新现有文档

**原则**：
- 小改动：直接修改，更新日期
- 大改动：创建新版本（v1.0 → v2.0）
- 过时内容：移动到 `archive/`

### 归档策略

**归档时机**（每月第一周）：
- 文档已过时（>6个月未更新）
- 内容已被新文档替代
- 仅作历史参考

**归档流程**：
1. 移动到 `docs/archive/`
2. 在原位置添加重定向说明
3. 更新索引文件

详见：[归档策略](guidelines/archive_policy.md)

---

## 未来改进计划

### P1 - 短期（1-2周内）

**引入文档搜索工具**：
- 推荐方案：MkDocs + Material 主题
- 优势：Python 生态、配置简单、内置搜索、支持中文
- 详见：[Markdown 文档管理建议](reports/markdown_documentation_management_recommendations_2026-01-17.md)

**建立文档审查机制**：
- 创建文档审查清单
- 定期检查文档质量
- 确保链接有效性

### P2 - 长期优化

**文档自动化工具**：
- 使用 pre-commit hooks 自动检查文档质量
- 自动生成文档索引
- 自动检测过时文档

**文档变更日志**：
- 创建 `docs/CHANGELOG.md` 记录重要文档变更
- 追踪文档演进历史

---

## 相关资源

- [项目 README](../README.md) - 项目总体说明
- [Claude 工作指南](../CLAUDE.md) - Claude Code 使用规范
- [自动化助手指南](../AGENTS.md) - 自动化工作流
- [目录结构说明](architecture/directory_structure.md) - 完整的项目结构

---

**文档版本**：v1.0
**创建日期**：2026-01-17
**维护者**：项目团队
**最后更新**：2026-01-17
