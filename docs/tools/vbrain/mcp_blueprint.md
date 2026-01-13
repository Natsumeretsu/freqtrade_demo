# vbrain MCP（婴儿版）蓝图：把工作流打包成一个 MCP Server

更新日期：2026-01-11

目标：让其它 LLM/客户端只需安装一个 “vbrain MCP”，即可在任意仓库中落地同样的闭环习惯；随后每个仓库的 vbrain 会在日常开发中逐步进化成长。

注意：本仓库当前是“控制平面 + 脚本化工作流”，并已提供婴儿版 vbrain MCP Server（`scripts/tools/vbrain_mcp_server.py`）。该文档用于固化后续演进方向与接口形态（例如：更强的进度通知、打包分发等）。

---

## 1) 设计原则（单人 vibe coding 友好）

- **每仓库一份大脑**：状态落在仓库内（例如 `in-memoria.db`），跨设备用 Git 同步。
- **可重建缓存不提交**：向量库/feed 缓存等默认落在 `.vibe/` 并 gitignore。
- **核心闭环只消费 feed**：vbrain 不负责采集；采集应由独立能力承担（例如 `vharvest`）。

---

## 2) vbrain MCP 需要暴露哪些工具？

建议以“高层动作”封装现有脚本（而不是把细节暴露给 LLM）：

### 2.1 索引/预热类（vbrain core）

- `vbrain.preheat(rebuild_docs: bool, ingest_sources: bool, only_new_sources: bool)`
  - 典型动作：索引 `docs`（可选重建）+ 可选索引外部材料
- `vbrain.ingest_project_docs(rebuild: bool, pattern: str, limit: int)`
  - 对应：`scripts/tools/local_rag_ingest_project_docs.py`
- `vbrain.ingest_sources(only_new: bool, ids: str, limit: int)`
  - 对应：`scripts/tools/local_rag_ingest_sources.py`
- `vbrain.status()`
  - 输出：是否存在 `in-memoria.db`、local-rag DB 大小/文档数、sources 缓存条目数等

### 2.2 非目标：采集能力

vbrain MCP 不承载采集能力；采集应由独立能力提供（例如 `vharvest`），其产物（feed）再由 vbrain ingest。

---

## 3) 实现路径（建议）

推荐实现一个轻量 Python MCP Server（尽量 stdlib + 少量稳定依赖），核心能力是：

- 读取 `docs/tools/vbrain/manifest.json`，定位脚本入口与路径布局
- 通过 `subprocess` 调用仓库内脚本，并将 stdout/stderr 摘要化回传
- 对“需要人工介入”的操作，提供明确状态码（例如 `blocked` / `needs_human` / `ok`）

这样 vbrain MCP 本身不需要直接“再去调用其它 MCP”，而是复用已验证的脚本化流程（脚本内部按需调用索引/记忆相关能力）。

---

## 4) 迁移到其它仓库（让婴儿 vbrain 复制即用）

最低可移植集合（建议）：

- `docs/tools/vbrain/`（控制平面：README + manifest + blueprint）
- `scripts/tools/vbrain.py`（统一入口）
- `scripts/tools/local_rag_ingest_project_docs.py`
- `scripts/tools/local_rag_ingest_sources.py`
- `.serena/memories/vbrain_workflow.md`（闭环 SOP）

采集与来源登记属于独立能力（例如 `vharvest`），按需带走即可。
