# 项目固有知识结构索引（持续迭代）

更新日期：2026-01-17

本目录用于沉淀“可复用的项目知识”，其目标是：

- 把外部资料（链接）转化为**可执行的工程结论**（参数、风险、边界、落地映射）。
- 让策略迭代不再依赖“记忆/口口相传”，而是依赖可追溯文档与来源登记。

当前研究主线（重要）：

- 暂时只做**单交易对**的**时间序列预测/择时**（研究层验证 → 执行层落地）。
- “横截面多币因子模型”（SMB/NET/C-5 等）仅作为**风险语义/背景知识**与未来扩展，不作为近期落地目标。

---

## 1) 赛道与策略（从"方向"到"落地"）

- 赛道选型总览（网格 / 均值回归 / 套利）：`docs/archive/design/crypto_futures_strategy_options.md`
- 交易策略深入分析（算法/理论/陷阱）：`docs/knowledge/strategies/crypto_exchange_strategy_deep_dive.md`
- 小账户到大账户实践指南（风险/成本/流程）：`docs/knowledge/strategies/small_account_10_to_10000_practice_guide.md`
- EMA/MACD 形态与 Vegas 隧道（可程序化落地笔记）：`docs/knowledge/strategies/ema_macd_vegas_playbook.md`
- K线/Pin Bar（工程化落地笔记）：`docs/knowledge/strategies/candlestick_pinbar_playbook.md`
- 流动性/微观结构（工程化落地笔记）：`docs/knowledge/strategies/crypto_liquidity_microstructure_playbook.md`
- 业界成熟做法的正确性与支撑（本项目对标与验收）：`docs/knowledge/strategies/industry_best_practices_support_analysis.md`
- 业界成熟做法仍有提升空间（进阶方向与路线图）：`docs/knowledge/strategies/industry_best_practices_improvement_space.md`
- 策略唯一基底索引（已归档）：`docs/archive/freqai/freqai_core_strategy_guide.md`
- 策略模式基底（已归档）：动量回调（趋势内回撤）`docs/archive/design/momentum_pullback_strategy_v1.md`

---

## 2) 来源登记（可追溯）

- 来源清单与抓取状态：`docs/knowledge/source_registry.md`

---

## 3) 维护规则（简版）

1. 新增外部资料：先把 URL 登记到 `source_registry.md`，标注类别与用途。
2. 使用 MCP 工具实时获取外部资料：
   - 网页内容：使用 `fetch` 或 `playwright` MCP 工具
   - 官方文档：使用 `context7` MCP 工具
   - 搜索查询：使用 `duckduckgo` MCP 工具
3. 只沉淀"结论与可复用要点"，不要粘贴整篇原文（避免噪声与版权风险）。
4. 将要点回灌到对应的设计文档/策略唯一基底文档，并在索引处挂载链接。

---

## 4) 因子模型与研究

- 时间序列因子分类：`docs/knowledge/factors/time_series_factors_classification.md`
- 时间序列因子（第二部分）：`docs/knowledge/factors/time_series_factors_part2.md`
- 因子消融检查清单：`docs/knowledge/factors/factor_ablation_checklist_smallaccount_futures.md`
- 因果特征识别：`docs/knowledge/factors/causal_factor_identification_crypto_playbook.md`
- 因子模型生态综述：`docs/knowledge/factors/crypto_factor_model_ecosystem_survey.md`
- 因子模型实现：`docs/knowledge/factors/crypto_factor_model_implementation_playbook.md`
- 价格预测模型：`docs/knowledge/factors/crypto_price_forecasting_models_playbook.md`
- 五因子定价模型：`docs/knowledge/factors/crypto_pricing_five_factor_models_playbook.md`
- 风险因子工程化：`docs/knowledge/factors/crypto_risk_factors_engineering_playbook.md`
- 单因子 vs 多因子择时：`docs/knowledge/factors/factor_single_vs_multi_timing.md`

---

## 5) 工程化与工具

- Freqtrade + Qlib 工程化流程：`docs/knowledge/tools/freqtrade_qlib_engineering_workflow.md`
- 信息论与信号系统：`docs/knowledge/tools/crypto_information_theory_signal_system_playbook.md`
- MCP 选型评估（Knowledge & Memory）：`docs/knowledge/tools/mcp_knowledge_memory_landscape.md`
- MCP 选型评估（Browser Automation）：`docs/knowledge/tools/mcp_browser_automation_landscape.md`

---

## 6) 维护规则（简版）

1. 新增外部资料：先把 URL 登记到 `source_registry.md`，标注类别与用途。
2. 使用 MCP 工具实时获取外部资料：
   - 网页内容：使用 `fetch` 或 `playwright` MCP 工具
   - 官方文档：使用 `context7` MCP 工具
   - 搜索查询：使用 `duckduckgo` MCP 工具
3. 只沉淀"结论与可复用要点"，不要粘贴整篇原文（避免噪声与版权风险）。
4. 将要点回灌到对应的设计文档/策略唯一基底文档，并在索引处挂载链接。
