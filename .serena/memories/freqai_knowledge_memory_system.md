# 知识/记忆进化系统（vibe coding 项目大脑为主，可选人类知识库）

更新日期：2026-01-10

本记忆用于固化：在本仓库（以及未来其它仓库）如何构建一个“可进化的大脑”，覆盖：

- 跨会话记忆（任务/决策/上下文）
- 代码库画像（结构/入口/模式/文件路由/语义检索）
- 资料索引加速（文档/网页/PDF 的语义召回 + 关键词 boost）

同时明确 Serena 的职责边界：Serena 专注符号级代码检索/编辑与固化“流程/约定/关键结论”，不把它当知识引擎使用。

---

## 1) 两种模式（按你的真实诉求选）

### A) vibe coding「项目大脑」（本项目默认）

适用：单人开发、跨设备 Git 同步、无需人类审计 diff，只求“机器可用、越用越懂你”。

推荐组合：

- 主脑：`pi22by7/In-Memoria`（MCP：代码画像 + 工作上下文 + 语义检索 + 文件路由）
- 资料索引加速器：`shinpr/mcp-local-rag`（MCP：显式 ingest → 高质量召回 + keyword boost）
- 资料抓取/转写：`markitdown`（URL/文件 → Markdown，便于落盘与 ingest）

落地关键点：

- In-Memoria 默认会在仓库根目录生成 `in-memoria.db`（建议随 Git 同步，用于跨设备“同一个大脑”）。
- `mcp-local-rag` 的向量库建议只 ingest `project_docs/`（我们自己写的摘要/结论）；索引层在 `.vibe/local-rag/lancedb/`，默认 gitignore 忽略，跨设备用脚本预热重建即可（重建时有进度条）。模型缓存（`CACHE_DIR`）默认放在设备级目录 `~/.codex/cache/local-rag/models/`（可通过 `CODEX_HOME` 改变），并可用 `MODEL_NAME` 切换嵌入模型（切换需重建 DB）。
- “进化闭环”的关键不是存很多资料，而是把你确认过的**决策/套路/坑点**写回 In-Memoria（`contribute_insights`）。

### B) 人类可读「知识库」（可选）

适用：你希望把资料沉淀成可读可审计的 Markdown 笔记（长期维护/可迁移/可引用）。

推荐：

- `entanglr/zettelkasten-mcp`：Markdown 为 source-of-truth，SQLite 仅索引层，可删可重建。

说明：这个模式依旧有价值，但它服务的目标更偏“人类知识管理”，不是你这次明确的 vibe coding 工作流主诉求。

---

## 2) 对 Serena 的定位（边界与用法）

- Serena 的主业不是“知识库/记忆引擎”，而是“代码符号检索/编辑”的工作流。
- `.serena/memories/*` 适合固化：
  - 抓取/登记/回灌的流程规范（Policy）
  - 项目环境与工具约定（Ops）
  - 关键决策与原则（Index/Methodology）
- 真正的“可进化大脑”交给 In-Memoria；“资料召回加速”交给 Local RAG。

---

## 3) awesome-mcp-servers（Knowledge & Memory）筛选结论（与你的诉求对齐版）

来源：`https://github.com/punkpeye/awesome-mcp-servers#-knowledge--memory`

- 强烈匹配（vibe coding 项目大脑）：
  - `pi22by7/In-Memoria`：跨会话记忆 + 代码画像 + 文件路由 + 工作上下文（适配 Codex CLI）。
- 强烈匹配（资料索引加速器）：
  - `shinpr/mcp-local-rag`：本地运行、LanceDB 文件型向量库、工具包含 ingest/search/list/status；适合作为“资料召回层”。
- 可选补充（通用记忆库）：
  - `agentic-mcp-tools/memora`：SQLite 记忆库 + 标签/查询/导入导出/图谱可视化；更像“通用记忆仓库”，可作为二号记忆，但会引入“记忆分流”。
- 不建议（主要是云端或外部托管）：
  - `mem0ai/mem0-mcp`、`ragieai/ragie-mcp-server`、`graphlit-mcp-server`、`pinecone-io/assistant-mcp` 等：依赖 API Key/外部存储，不满足“每仓库一份大脑、随 Git 同步”的主目标。
- 维护状态风险：
  - `modelcontextprotocol/server-memory` 指向 archived 仓库子路径，当前不可用，不建议。

---

## 4) 本仓库落地映射（已做/应做）

- MCP 一键配置脚本（Codex）：`./scripts/mcp/setup_codex.ps1`
  - 默认服务器列表定义在：`./scripts/lib/common.ps1`（新增 `in_memoria` 与 `local_rag`）
- vibe coding 工作流文档：`project_docs/setup/vibe_brain_workflow.md`
- vbrain 默认闭环 SOP（让“不说也会做”）：`.serena/memories/vbrain_workflow.md`
- Local RAG 缓存目录说明：`.vibe/README.md`（本仓库默认忽略 `.vibe/local-rag/`，需要时用脚本预热重建）
- 资料侧权威入口（仍然建议保留）：
  - `project_docs/knowledge/source_registry.md`（来源登记）
  - `project_docs/knowledge/index.md`（索引）

---

## 5) 注意事项（单人也建议考虑）

- Git 同步 DB 的现实成本：仓库体积会增长；建议避免把可重建的大向量库缓存提交到远端。
- 外部网页资料：若 ingest 外部全文，向量库中会存放正文片段；默认忽略 `.vibe/local-rag/` 可以避免把第三方内容同步进仓库。
- 你明确不会多设备并行写同一 DB：这会显著降低二进制冲突风险，是这种工作流成立的关键前提。

---

## 6) 浏览器采集层（Browser Automation，面向“高保真输入”）

结论：
- 本项目无需为了抓网页额外引入新 MCP：继续以 `microsoft/playwright-mcp`（脚本使用 `@playwright/mcp`）作为浏览器渲染抓取主力，配合 `markitdown` 做静态/直连转写即可。
- 采集质量的关键在“产物更完整 + 元数据更规范”，而不是“换一个抓取 MCP”。

本仓库采集产物约定（默认落盘到 `.vibe/knowledge/sources/S-xxx/`，并由 `.gitignore` 忽略）：
- 静态抓取（markitdown）：`markitdown.md` + `meta.json`
- 浏览器抓取（Playwright）：`playwright_snapshot.md` + `playwright_dom.html` + `playwright_network.json` + `meta_playwright.json`（可选 `screenshot.png`）

行为边界（强制）：
- 遇到验证码/登录墙/订阅墙：只记录 `blocked` 与原因，不提供绕过方案；如你有合法访问权限，需要人工介入后再采集。

人工介入（合法访问前提）：
- 运行 `python -X utf8 scripts/tools/vharvest.py fetch-playwright -- --interactive`（默认 `--interactive-mode deferred` 不阻塞其它条目），按提示在浏览器窗口完成验证/登录；脚本会自动等待并在检测到页面可访问后继续抓取。
- 如仍受阻，可选择导出 HTML/PDF，脚本会离线转写为 `manual_markitdown.md`（同目录生成 `manual_meta.json`），作为后续提炼输入。

入口脚本：
- `scripts/tools/vharvest.py`（推荐入口）
- `scripts/tools/source_registry_fetch_sources.py`（实现细节）
- `scripts/tools/source_registry_fetch_sources_playwright.py`（实现细节）

选型说明文档：
- `project_docs/knowledge/mcp_browser_automation_landscape.md`

