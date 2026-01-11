# FreqAI 项目主干记忆入口（Index）

更新日期：2026-01-10

本记忆是本仓库 FreqAI/策略研发的**主入口**，用于把知识拆分为可维护的“主干模块”，避免所有内容堆在单一文件里。

---

## 0) 通用记忆（跨项目也适用）

- 项目概览：`project_overview`
- 常用命令（脚本入口/禁用底层命令）：`suggested_commands`
- 任务完成检查清单：`task_completion_checklist`
- vbrain 闭环工作流（默认执行）：`vbrain_workflow`
- 风格约定：`style_conventions`
- 回测汇报标准：`backtest_reporting_standard`

---

## 1) 主干记忆目录（请按类更新）

- 方法论（标签/门控/不平衡/性能）：`freqai_methodology`
- 工程与环境（命令约定/MCP/浏览器/回测输出）：`freqai_ops_environment`
- 来源流程（抓取→登记→回灌规则）：`freqai_sources_policy`
- 知识记忆系统（本地存储/检索/演进/MCP 选型）：`freqai_knowledge_memory_system`

> 策略级优化记录（单策略快照）：保留各自独立记忆（例如 `freqai_moonshot_optimization_2026-01-09`）。

---

## 2) 仓库内“权威入口”（优先查这里）

- 策略唯一基底索引：`project_docs/freqai_core_strategy_guide.md`
- 项目知识索引（文档侧入口）：`project_docs/knowledge/index.md`
- vbrain 控制平面（清单/索引/蓝图）：`vbrain/README.md`
- 外部来源登记表（唯一清单）：`project_docs/knowledge/source_registry.md`
- 回测汇报标准（强制）：`project_docs/guidelines/backtest_reporting_standard.md`
- MCP/环境一键初始化：`project_docs/setup/codex_mcp_sync.md`

---

## 3) 快照归档（仅留作里程碑，不再继续堆内容）

- `freqai_knowledge_system_2026-01-10`：已转为“快照归档”，最新主干以本 Index 为准。
- `freqai_moonshot_optimization_2026-01-09`：策略/赛道相关的阶段性重构记录（仅留档）。
