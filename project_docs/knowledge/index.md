# 项目固有知识结构索引（持续迭代）

更新日期：2026-01-12

本目录用于沉淀“可复用的项目知识”，其目标是：

- 把外部资料（链接）转化为**可执行的工程结论**（参数、风险、边界、落地映射）。
- 让策略迭代不再依赖“记忆/口口相传”，而是依赖可追溯文档与来源登记。

---

## 1) 赛道与策略（从“方向”到“落地”）

- 赛道选型总览（网格 / 均值回归 / 套利）：`project_docs/design/crypto_futures_strategy_options.md`
- 交易策略深入分析（算法/理论/陷阱）：`project_docs/knowledge/crypto_exchange_strategy_deep_dive.md`
- 小账户到大账户实践指南（风险/成本/流程）：`project_docs/knowledge/small_account_10_to_10000_practice_guide.md`
- 策略唯一基底索引（策略类一对一）：`project_docs/freqai_core_strategy_guide.md`
- 策略模式基底（非策略类）：动量回调（趋势内回撤）`project_docs/design/momentum_pullback_strategy_v1.md`

---

## 2) 来源登记（可追溯）

- 来源清单与抓取状态：`project_docs/knowledge/source_registry.md`

---

## 3) 维护规则（简版）

1. 新增外部资料：先把 URL 登记到 `source_registry.md`，标注类别与用途。  
2. 使用采集层把外部资料落盘为 feed，记录抓取日期与状态（ok/403/robot/js-required）。  
   - 推荐用 `vharvest` 批量采集并落盘到本地缓存（默认 gitignore）：  
     `python -X utf8 scripts/tools/vharvest.py fetch -- --limit 5`
   - 可选：把抓取缓存 ingest 到 `local_rag`，提升“外部全文”的可检索性：  
     `python -X utf8 scripts/tools/vbrain.py ingest-sources -- --only-new`
3. 只沉淀“结论与可复用要点”，不要粘贴整篇原文（避免噪声与版权风险）。  
4. 将要点回灌到对应的设计文档/策略唯一基底文档，并在索引处挂载链接。
5. Git 同步策略（哪些应提交/不应提交）：`project_docs/setup/git_sync_policy.md`

---

## 4) AI 大脑（vibe coding，可选）

如果你使用 Codex CLI 做 vibe coding，并希望“跨会话记忆 + 资料语义检索加速”，参考：

- `project_docs/setup/vibe_brain_workflow.md`
- MCP 选型评估（Knowledge & Memory）：`project_docs/knowledge/mcp_knowledge_memory_landscape.md`
- MCP 选型评估（Browser Automation / 抓取采集层）：`project_docs/knowledge/mcp_browser_automation_landscape.md`
