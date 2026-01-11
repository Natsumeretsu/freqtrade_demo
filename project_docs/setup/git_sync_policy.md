# Git 同步策略（freqtrade_demo）

更新日期：2026-01-12

本文用于回答三个问题：

1. 哪些文件/目录应该用 Git 同步（作为“权威源”）？
2. 哪些不应该同步（缓存/产物/敏感本地），并把规则固化到 `.gitignore`？
3. vbrain（AI 大脑）跨设备是否会不一致？如何把差异控制在可接受范围？

---

## 1) 三类资产（先定原则）

### 1.1 权威源（必须同步）

特点：不可从别处可靠重建；或重建成本高；或承载团队共识。

- 代码（策略/脚本/工具）
- 配置模板与策略参数（不含密钥）
- 文档（设计、知识库、流程）
- 记忆与索引（Serena memories、in-memoria 主脑 DB）

### 1.2 可再生成缓存/产物（不需要同步）

特点：可通过脚本/命令重建；体积大；变化频繁；会让 `git status` 常年脏。

- 市场数据下载产物（OHLCV、资金费率、指数/标记价等）
- 回测/超参/绘图产物（`backtest_results/`、`hyperopt_results/`、`plot/`）
- 训练产物与模型缓存（`models/` 等）
- 本地 RAG/采集缓存（`.vibe/` 下的向量库/抓取快照/浏览器 profile 等）
- 虚拟环境、缓存（`.venv/`、`__pycache__/`）

### 1.3 敏感本地配置（绝不同步）

特点：包含密钥/Token/个人路径/站点信息，或语义上就是“local”。

- `.env`（仓库根目录）
- `.claude/settings.local.json`
- `scripts/mcp/claude_profiles.local.json`
- `config*.local.json` / `config*.secrets.json` / `config*.private.json`（推荐用于存放密钥的本地覆盖配置）

---

## 2) 本仓库：建议同步清单（推荐纳入 Git）

### 2.1 根目录关键文件

- `AGENTS.md`
- `README.md`
- `.gitignore`、`.gitattributes`、`.gitmodules`
- `.python-version`、`pyproject.toml`、`uv.lock`
- `.env.example`（仅模板，不含密钥）
- `config*.json`（运行配置：允许同步，但必须保持 key/secret/password/token 为空；密钥放到 `.env` 或 `config*.local.json`）
- `in-memoria.db`（主脑 DB：跨设备一致性更重要，体积可控）

### 2.2 代码与配置

- `strategies/`：策略实现（Python）
- `configs/`：策略配置（不含密钥）
- `scripts/`：统一命令入口与工具链（`scripts/lib/`、`scripts/tools/` 必须同步）
- `hyperopts/`：Hyperopt loss / 目标函数（源码）
- `notebooks/`：可复现的分析笔记（如确有价值）

### 2.3 文档与知识层

- `project_docs/`：权威知识库（设计/知识/维护规则）
- `.serena/project.yml`、`.serena/memories/`：流程与记忆（可读、可维护）
- `vbrain/`、`vharvest/`：控制平面文档（清单/蓝图/入口说明）
- `freqtrade_docs/`、`freqtrade_book/`：离线文档（注意：`freqtrade_docs/raw_html/` 默认不提交）

---

## 3) vbrain 跨设备一致性（同步“结论层”，重建“加速层”）

建议把 vbrain 视为“三层结构”，并用不同的同步策略来控制一致性与成本：

- 结论层（必须同步）：`project_docs/` + `.serena/memories/`  
  这是你真正的“知识/结论”，两台设备一致性由 Git 保证。
- 主脑层（建议同步）：`in-memoria.db`  
  这是可写的结构化记忆（提炼洞见/索引状态等）。单用户双设备场景下，建议也随 Git 同步，避免两边大脑分叉。
- 检索加速层（默认不同步）：`.vibe/` + `in-memoria-vectors.db/` + `lancedb/`  
  这是可再生成的向量/缓存，允许每台设备独立重建。

不同设备重建会不会导致差异？

- 会：可能出现“召回/排序”层面的细微差异（依赖版本、浮点误差、索引构建细节等）。
- 不应：`project_docs/` 与 `.serena/memories/` 的文本结论不应出现差异（受 Git 约束）。

降低差异的做法：

- 统一 Python 与依赖：两台设备都执行 `uv sync --frozen`（以 `uv.lock` 为准）并使用 `.python-version`。
- 统一换行策略：建议设置 `git config core.autocrlf false`，并依赖 `.gitattributes` 统一 `eol=lf`。
- 每次切设备后预热检索：`python -X utf8 scripts/tools/vbrain.py preheat`

单用户双设备切换 SOP（无并发写入前提）：

- 切换设备前（设备 A）：先 `git pull`，再写入/更新结论层，最后提交并推送。
- 切到设备 B：`git pull` → `uv sync --frozen` → `python -X utf8 scripts/tools/vbrain.py preheat`

---

## 4) 本仓库：不需要同步清单（应忽略/不提交）

已固化到 `.gitignore`（如需查看规则以 `.gitignore` 为准）：

- `.venv/`
- `__pycache__/`
- `.serena/cache/`、`.serena/logs/`
- `.vibe/`（Local RAG 向量库、采集缓存、浏览器 profile、diagnostics 等）
- `logs/`、`backtest_results/`、`hyperopt_results/`、`plot/`
- `models/`（训练产物目录）
- `artifacts/`
- `temp/`（草稿/临时研究文件，建议把“成熟结论”迁入 `project_docs/`）
- `in-memoria-vectors.db/`、`lancedb/`（本地索引/向量缓存）

---

## 5) 市场数据 `data/` 的策略（重要）

现状：`data/` 往往体积大、更新频繁，会导致：

- 仓库体积膨胀（clone/pull 变慢）
- `git status` 常年出现大量变更
- 合并冲突与历史噪声（对策略迭代价值很低）

推荐策略：

- 默认不使用 Git 同步 `data/`（已在 `.gitignore` 忽略）。
- 需要数据时，通过脚本重新下载：
  - `./scripts/data/download.ps1 ...`
- 如果团队确实需要跨设备共享“固定快照数据”：
  - 优先放到独立存储（NAS/对象存储），或使用 Git LFS（仅对数据快照启用）。

---

## 6) 新设备/新克隆的最小复现流程（建议）

1. 初始化依赖：`./scripts/bootstrap.ps1`
2. 下载必要数据（按你的策略/回测范围）：`./scripts/data/download.ps1 ...`
3. 预热 vbrain（重建可检索索引）：`python -X utf8 scripts/tools/vbrain.py preheat`

---

## 7) 如果你想“立刻变干净”：取消跟踪已提交的大文件（可选）

说明：以下命令会把文件从 Git 跟踪中移除，但不会删除你本地的文件内容；需要你自行提交（commit）后才会对团队生效。

建议先运行一次自检脚本，确认有哪些路径仍在被跟踪：
- `./scripts/tools/git_sync_audit.ps1`

- 取消跟踪市场数据（推荐）：
  - `git rm --cached -r data/`
- 取消跟踪 Claude 本地设置（推荐）：
  - `git rm --cached .claude/settings.local.json`

如果你希望进一步把历史中的大文件彻底移除（减小仓库历史体积），需要另行讨论并使用 `git filter-repo` 等工具（属于高风险操作，不建议在未对齐共识前执行）。
