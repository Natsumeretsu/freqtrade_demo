# vbrain（vibe brain）控制平面（本仓库实现）

更新日期：2026-01-11

`vbrain` 是一个**抽象设计**：把多个 MCP 组合成“项目大脑”，并用一套稳定的闭环流程让它在日常开发中持续进化。

本目录是 vbrain 的**控制平面**（Control Plane）：统一放置清单/索引/规范与未来 MCP 化的蓝图；不搬动实际数据与缓存，避免破坏现有工具默认路径与安全边界。

---

## 1) vbrain 集合了哪些 MCP？

### vbrain core（核心闭环，建议必装）

- `in_memoria`：主脑（代码库画像、跨会话套路/决策记忆、语义检索与文件路由）
- `local_rag`：资料索引加速器（显式 ingest → 高质量语义召回 + 关键词 boost）
- `serena`：代码符号级检索/编辑（用于把结论稳定落地到代码与文档；不把它当知识引擎）

### 输入层（feed，由独立能力提供）

vbrain **不负责采集**。它只消费“已经落盘的 feed”，并将其 ingest 为可检索输入。

- 采集层控制平面：`vharvest/README.md`

---

## 2) vbrain 的工作流程是什么？

vbrain 的核心闭环是：

1. Retrieve：检索对照（`local_rag` / `in_memoria` / 既有文档）
2. Distill：提炼为可执行结论（参数/边界/命令/反例/证据）
3. Backfill：回灌到权威知识层（`project_docs/` + `.serena/memories/`）
4. Memory：把“套路/决策/坑点”写入 `in_memoria`
5. Index：同步索引（按需 ingest `project_docs` 与外部材料）

权威 SOP 见：`.serena/memories/vbrain_workflow.md`。

---

## 3) vbrain 与 MCP 的区别

- **MCP**：协议 + 服务器（提供一组“工具调用”能力，职责单一、可替换）。
- **vbrain**：架构与工作流（编排多个 MCP + 规定“写到哪里/如何去重/如何进化”）。

简单说：MCP 是“器官”，vbrain 是“神经系统 + 行为习惯”。

---

## 4) 数据与目录（不集中搬家，只做统一索引）

vbrain 的数据平面（Data Plane）仍按职责落地：

- `in-memoria.db`：主脑 DB（建议随 Git 同步）
- `.serena/memories/`：流程/约定/关键结论（可读、可维护）
- `project_docs/`：权威知识库（可引用、可持续迭代）
- `.vibe/`：可重建缓存（例如 local-rag 向量库、feed 缓存；默认 gitignore）

---

## 5) 统一入口（推荐）

统一入口脚本：`scripts/tools/vbrain.py`

常用：

- 预热/同步索引（推荐跨设备迁移后跑一次）：
  - `python -X utf8 scripts/tools/vbrain.py preheat --rebuild-docs`
- 仅索引结论层：
  - `python -X utf8 scripts/tools/vbrain.py ingest-docs -- --rebuild`
- 仅索引 feed（可选）：
  - `python -X utf8 scripts/tools/vbrain.py ingest-sources -- --only-new`

如果你使用 Codex CLI，并已运行 `./scripts/mcp/setup_codex.ps1` 初始化 MCP，那么会额外注册一个 `vbrain` MCP Server，你可以在对话中直接调用 `vbrain.status` / `vbrain.preheat` 等高层工具。

---

## 6) 为 MCP 化做准备

本目录提供 vbrain MCP 的“婴儿版”实现与蓝图（让其它 LLM 只需安装一个 MCP）：

- `vbrain/manifest.json`：可机器读取的清单（组件、路径、脚本入口）
- `scripts/tools/vbrain_mcp_server.py`：婴儿版 MCP Server（对外暴露高层工具，内部复用 `scripts/tools/vbrain.py`）
- `vbrain/mcp_blueprint.md`：后续演进蓝图（例如：打包为可分发的 MCP / 增强进度通知等）
