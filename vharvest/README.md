# vharvest（vibe harvest）采集层控制平面

更新日期：2026-01-11

`vharvest` 是 vbrain 体系中的**采集层（输入系统）**：负责把网页/文件等外部信息获取为可复用的本地“feed”，并记录访问与合规状态（ok / blocked / needs_human）。

> 职责边界：vharvest **只负责输入获取与落盘**；vbrain **只负责 ingest/feed→检索→提炼→回灌→记忆→索引/巩固**。两者解耦，便于跨项目复用与维护。

---

## 1) vharvest 产物（feed）是什么？

vharvest 的输出是**可被 vbrain 消费的本地材料**，默认落盘在：

- `.vibe/knowledge/sources/S-xxx/`

常见文件（示例）：

- `markitdown.md`：静态页面/文件转换后的 Markdown
- `playwright_dom.html`：浏览器渲染后的 DOM（利于后续正文清洗与完整性校验）
- `playwright_snapshot.md`：可读快照（兜底，但噪声可能更大）
- `playwright_network.json`：关键网络请求记录（用于定位加载与阻断原因）
- `meta.json` / `meta_playwright.json`：抓取元信息（时间、状态、URL、失败原因等）

这些产物属于**可重建缓存/证据层**，默认不作为“权威结论”；权威结论应写入 `project_docs/` 与 `.serena/memories/`。

---

## 2) 合规与人工介入（强制）

vharvest 默认遵循：

- 不提供任何“绕过”方案：验证码/登录墙/订阅墙等只允许**合法访问 + 人工介入**；否则标记为 `blocked` 并记录原因。
- 允许交互式采集：当你确认拥有合法访问权限时，可用 `--interactive` 让脚本暂停并提示你在浏览器窗口完成登录/验证，然后恢复抓取。

---

## 3) 推荐流程（来源登记 → 采集 → 供 vbrain ingest）

1) 在 `project_docs/knowledge/source_registry.md` 登记 URL（分配 `S-xxx`）
2) 批量采集并落盘（静态优先）：
   - `python -X utf8 scripts/tools/vharvest.py fetch -- --limit 5`
3) 对 `js-required` / `blocked` 的条目，使用浏览器渲染采集：
   - `python -X utf8 scripts/tools/vharvest.py fetch-playwright -- --only-failed --limit 10`
   - 需要人工介入时追加：`--interactive`
4) 交给 vbrain ingest（让资料可被语义检索召回）：
   - `python -X utf8 scripts/tools/vbrain.py ingest-sources -- --only-new`

---

## 4) 与 vbrain 的关系

- vharvest 负责“感觉输入”（把世界变成 feed）
- vbrain 负责“学习与记忆”（把 feed 变成可复用结论与跨会话套路）

vbrain 控制平面见：`vbrain/README.md`。
