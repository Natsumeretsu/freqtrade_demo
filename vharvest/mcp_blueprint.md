# vharvest MCP（蓝图）：把采集层打包成一个 MCP Server

更新日期：2026-01-11

目标：把“来源登记 → 采集落盘 → 状态记录（ok/blocked/needs_human）”封装成一个独立 MCP（vharvest），与 vbrain 解耦。

---

## 1) 设计原则

- **采集与学习解耦**：vharvest 只负责 feed；vbrain 只负责 ingest/检索/提炼/回灌/记忆。
- **合规优先**：遇到验证码/登录墙/订阅墙不做绕过；仅允许合法人工介入，失败则 `blocked`。
- **可重建缓存**：采集产物默认落在 `.vibe/knowledge/sources/`，并保持可重建。

---

## 2) 建议暴露的工具（高层动作）

- `vharvest.fetch_markitdown(ids: str, limit: int, force: bool, update_registry: bool)`
  - 对应：`scripts/tools/source_registry_fetch_sources.py`
- `vharvest.fetch_playwright(ids: str, limit: int, interactive: bool, only_failed: bool, update_registry: bool)`
  - 对应：`scripts/tools/source_registry_fetch_sources_playwright.py`
- `vharvest.status()`
  - 输出：sources 缓存条目数、最近失败原因概览、interactive 队列是否存在等

---

## 3) 与 vbrain 的接口（输入契约）

vharvest 的输出是 feed（文件落盘 + 元信息），vbrain 只需要 ingest：

- `python -X utf8 scripts/tools/vbrain.py ingest-sources -- --only-new`

后续如需更强的“feed contract”（统一 JSON 结构、hash 去重、质量评分），应在采集层先完成标准化，再交给 vbrain 消费。

