# 离线策略参考库（`strategies_ref_docs`）

本仓库通过 **git 子模块**引入策略参考库：`docs/archive/strategies_ref_docs/`。

它的定位是：**离线可用的“策略想法/实现思路语料库”**，用于快速对照、检索与提炼。

---

## 1) 克隆/更新（含子模块）

克隆时带上子模块：

```bash
git clone --recurse-submodules "<your_repo_url>"
git submodule update --init --recursive
```

你也可以在已有仓库里补齐子模块：

```bash
git submodule update --init --recursive
```

---

## 2) 离线全文搜索（推荐）

策略参考库的体量很大，**最推荐的离线用法是全文搜索**：

```powershell
rg -n "关键词" "docs/archive/strategies_ref_docs"
rg -n "EMA\\(|RSI|MACD|ATR" "docs/archive/strategies_ref_docs"
rg -n -i "breakout|pullback|mean reversion" "docs/archive/strategies_ref_docs"
```

如果你更喜欢“固定字符串”搜索（避免正则转义）：

```powershell
rg -n -F "1-2-3" "docs/archive/strategies_ref_docs"
```

---

## 3) 快速浏览标题（可选）

```powershell
rg -n \"^# \" \"docs/archive/strategies_ref_docs\" -g\"*.md\" | Select-Object -First 50
```

---

## 4) 不建议：全量 ingest 到 Local RAG

`docs/archive/strategies_ref_docs` 的 Markdown 文件数量非常多（数千级），**不建议默认全量 ingest 到 `local_rag`**（会导致向量库体积和索引时间不可控）。

如果你确实需要语义检索，建议从“小规模可控”开始（例如只 ingest 少量文件做验证）：

```powershell
python -X utf8 "scripts/tools/local_rag_ingest_project_docs.py" --base-dir "docs/archive/strategies_ref_docs" --limit 200
```

> 提示：`scripts/tools/local_rag_ingest_project_docs.py` 默认索引 `docs/` 并排除 `docs/archive/**`，这是为了避免把归档/海量文档塞进向量库。

---

## 5) 约定与排雷

- **权威路径**：只使用 `docs/archive/strategies_ref_docs/`（子模块）。根目录下误创建的 `strategies_ref_docs/` 已被 `.gitignore` 忽略。
- 参考库用于“提炼思路”，不等价于“可直接上线的策略代码”；落地前必须走本仓库的回测与风控闭环。

