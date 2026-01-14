# Vibe Coding「项目大脑」工作流（Codex CLI + In-Memoria + Local RAG）

更新日期：2026-01-13

新设备/第二台电脑对接建议先按：`docs/setup/new_device_onboarding.md` 跑通“最小验收”，再阅读本文进行 vbrain 深度配置与工作流固化。

目标：为**每个仓库**提供一个可进化的“项目大脑”，支持：

- 跨会话记忆（任务/决策/上下文）
- 代码库画像（结构、入口、模式、文件路由）
- 资料索引加速（文档/网页/PDF 语义召回 + 关键词 boost）

本仓库推荐组合（vbrain core）：

- `in_memoria`：主脑（代码画像 + 任务/决策记忆 + 语义检索）
- `local_rag`：资料检索加速器（显式 ingest → 高质量召回）
- `serena`：代码符号检索/编辑（不作为“知识库”，只固化流程/约定/关键结论）

同级能力（可选）：采集层（vharvest）

- `vharvest`：输入采集层控制平面（把外部网页/文件采集为本地 feed，供 vbrain ingest）
  - 入口：`docs/tools/vharvest/README.md`
  - 清单：`docs/tools/vharvest/manifest.json`

vbrain 控制平面（统一索引与后续 MCP 化准备）：

- 入口：`docs/tools/vbrain/README.md`
- 清单：`docs/tools/vbrain/manifest.json`
- 统一命令入口：`scripts/tools/vbrain.py`
- MCP Server（婴儿版，高层工具封装）：`scripts/tools/vbrain_mcp_server.py`

---

## 1) 一键安装（本仓库约定）

在仓库根目录运行：

```powershell
pwsh -ExecutionPolicy Bypass -File "./scripts/mcp/setup_codex.ps1"
```

安装完成后检查：

```powershell
codex mcp list
```

应能看到（至少）：`docs/tools/vbrain`、`in_memoria`、`local_rag`、`serena`。如你需要采集外部 feed，再按 `docs/tools/vharvest/README.md` 启用采集层依赖与脚本。

建议紧接着跑一次体检（版本对齐 + Chrome/缓存路径自检）：

```powershell
powershell -ExecutionPolicy Bypass -File "./scripts/mcp/doctor.ps1" -Deep
```

---

## 2) 目录与存储约定（每仓库一份大脑）

- In-Memoria：默认在项目根目录生成 `in-memoria.db`（建议随 Git 同步）。  
  你不需要读懂 DB，只要它能跨会话复用即可。
- Local RAG：向量库默认落在 `.vibe/local-rag/lancedb/`（可重建缓存，默认不提交）。  
  模型缓存默认在设备级目录 `~/.codex/cache/local-rag/models/`（可通过 `CODEX_HOME` 改变）。  
  跨设备同步时建议直接跑预热脚本重建（带进度条）：`python -X utf8 scripts/tools/vbrain.py preheat --rebuild-docs`（如不需要外部 feed 可加 `--skip-sources`）

`.vibe/` 目录说明见：`.vibe/README.md`。

---

## 3) 会话启动仪式（让大脑“进入状态”）

建议每次新会话先让 `in_memoria` 给出项目蓝图并判断是否需要学习：

1) 调用 `get_project_blueprint`（path 建议 `.`）
2) 如果提示需要学习：调用 `auto_learn_if_needed`

如果你更喜欢一次性离线预热，也可以在终端手动运行（可选）：

```powershell
npx -y "in-memoria@0.6.0" learn "."
```

---

## 4) 资料 ingest 与检索（Local RAG）

`local_rag` 是“资料索引加速器”，特点是：

- 你决定 ingest 什么，它就索引什么（避免无意义全量扫描）。
- 检索时先语义召回，再用关键词 boost 提升精确匹配（对 API、参数名、错误码很有用）。

### 4.1 索引本仓库文档（推荐）

把你关心的文档（例如策略基底、设计文档、回测标准）逐个 ingest：

- `docs/archive/design/*.md`
- `docs/guidelines/*.md`
- `docs/knowledge/source_registry.md`

你可以直接对 Codex 说：把某个文件 ingest 到 `local_rag`。

也可以用仓库内脚本批量 ingest（更省心）：

```powershell
python -X utf8 scripts/tools/vbrain.py ingest-docs -- --rebuild
```

如需切换嵌入模型（会改变向量维度，必须重建 DB）：

```powershell
python -X utf8 scripts/tools/vbrain.py ingest-docs -- --rebuild --model-name "Xenova/all-MiniLM-L6-v2"
```

如你希望“效果优先”地选择嵌入模型，建议先用本仓库的**查询回归集**做一次对比评估（不会破坏主 DB）：

```powershell
# 默认：只评估当前 local_rag 模型（更快，避免拉慢日常索引）
python -X utf8 scripts/tools/vbrain.py eval-embeddings

# 显式指定要对比的模型（逗号分隔）
python -X utf8 scripts/tools/vbrain.py eval-embeddings -- --models "Xenova/multilingual-e5-large,Xenova/multilingual-e5-base,Xenova/bge-m3,Xenova/all-MiniLM-L6-v2"
```

说明：
- 回归集默认在 `docs/tools/vbrain/local_rag_eval_cases.json`，可按你“常问的问题”持续追加。
- 评估默认使用 `.vibe/local-rag/model_dbs/<model_slug>/` 存放向量库，不影响 `.vibe/local-rag/lancedb/`。
- 每次评估会输出报告到 `artifacts/local_rag_eval/<timestamp>/report.json`，便于追溯。

#### 4.1.1 嵌入模型选型结论（2026-01-13，可跨设备复用）

结论（中文为主，效果优先）：`Xenova/multilingual-e5-large`（最佳） > `Xenova/multilingual-e5-base`（次选） > `Xenova/bge-m3`（再次） > `Xenova/all-MiniLM-L6-v2`（默认/速度优先）。

基于本仓库回归集（`docs/tools/vbrain/local_rag_eval_cases.json`，Top5）的一次评估结果参考：

- `Xenova/all-MiniLM-L6-v2`：hit@5≈40%（快，但效果一般）
- `Xenova/multilingual-e5-base`：hit@5≈80%，mrr@5≈0.713（效果强且相对更快）
- `Xenova/multilingual-e5-large`：hit@5≈80%，mrr@5≈0.800（更强但 ingest 更慢）
- `Xenova/bge-m3`：中等；ingest 很慢

重建速度抽样（本机，`docs` 前 5 个 `.md`，`--mode build --build rebuild`）：

- `Xenova/all-MiniLM-L6-v2`：≈5.3s（≈1.06s/文件，最快）
- `Xenova/multilingual-e5-base`：≈37.8s（≈7.56s/文件）
- `Xenova/bge-m3`：≈78.3s（≈15.66s/文件）
- `Xenova/multilingual-e5-large`：≈80.4s（≈16.07s/文件，最慢）

落地建议（兼顾体验与效果）：

- 日常主索引：保持 `Xenova/all-MiniLM-L6-v2`，配合 `--only-changed` 做增量 ingest（默认开启）。
- 质量优先：用 `Xenova/multilingual-e5-large` 单独构建“可选索引”（或离线重建），再用 `--build update` 增量维护；避免把主索引的 ingest 体验拖慢。

复现命令（跨设备可直接跑；首次运行可能包含模型下载，建议至少跑两次看稳定速度）：

```powershell
# 评估效果（回归集 hit@k / mrr@k）
python -X utf8 scripts/tools/vbrain.py eval-embeddings -- --models "Xenova/multilingual-e5-large,Xenova/multilingual-e5-base,Xenova/bge-m3,Xenova/all-MiniLM-L6-v2"

# 对比重建速度（仅构建索引 + 统计耗时；用 file-limit 快速抽样）
python -X utf8 scripts/tools/vbrain.py eval-embeddings -- --mode build --build rebuild --file-limit 50 --models "Xenova/multilingual-e5-large,Xenova/multilingual-e5-base,Xenova/bge-m3,Xenova/all-MiniLM-L6-v2"
```

### 4.2 外部资料 feed（可选：由 vharvest 负责）

本节不属于 vbrain core：只有当你需要把“外部原文”纳入可检索输入时才需要做。

约定：采集层（vharvest）负责把外部资料落盘为本地 feed（默认 `.vibe/knowledge/sources/S-xxx/`），vbrain 只负责 ingest 与检索召回。

推荐流程（可复现 + 可追溯）：

1) 先把 URL 登记到 `docs/knowledge/source_registry.md`（分配 S-xxx）。
2) 按 `docs/tools/vharvest/README.md` 执行采集并落盘（必要时人工介入完成合法访问）。
3) （可选）把 feed ingest 到 `local_rag`，让“外部全文”也能被语义检索召回：  
   `python -X utf8 scripts/tools/vbrain.py ingest-sources -- --only-new`

建议优先坚持本仓库的“来源登记 → 提炼要点 → 回灌文档”流程，把**可复用结论**写进仓库文档；feed 原文只作为证据层缓存存在即可。

---

## 5) “进化”的关键：把决策/套路写回 In-Memoria

你想要的大脑自我进化，核心不在“存很多资料”，而在于：把**你做过的决策与有效套路**沉淀为可检索的 insight。

建议在每次完成一个阶段任务后，让 Codex 调用 `contribute_insights` 记录：

- `type`：例如 `decision` / `pattern` / `pitfall` / `workflow`
- `content`：建议结构化字段：`context`、`decision`、`rationale`、`tradeoffs`、`files`、`commands`、`links_or_S_ids`
- `confidence`：0~1（越接近 1 表示你越确定这条经验稳定可靠）
- `sourceAgent`：固定写 `codex` 或你的昵称，便于追踪

这样下次你只要描述目标，`in_memoria` 就能预测实现路径并路由到正确文件，同时带上你过去确认过的套路与坑点。

你也可以先把本仓库的关键工作流/坑点种子写入 In-Memoria（可选）：

```powershell
python -X utf8 scripts/tools/in_memoria_seed_vibe_insights.py
```
