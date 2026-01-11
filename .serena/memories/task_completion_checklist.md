# 任务完成检查清单（建议）

## ⚠️ 开始任何任务前（必须）
- **先读 README.md** 了解项目结构
- **先读 suggested_commands memory** 了解命令使用规则
- 如任务涉及“知识获取/决策/工作流”：按 `vbrain_workflow` 先检索对照，再落地与回灌。
- 禁止直接运行底层命令（如 `freqtrade`、`uv run freqtrade`），必须通过 `scripts/` 脚本执行

## 环境/依赖
- 依赖同步：`uv sync --frozen`
- 若遇到 Windows 文件占用导致清理失败（例如 VSCode 占用包目录）：`uv sync --frozen --inexact`

## 策略/超参相关改动
- 基础导入检查：`uv run python -m compileall "strategies" "hyperopts"`
- 策略可见性/加载检查：`./scripts/ft.ps1 list-strategies`
- 行为验证（按需，可能较慢）：使用对应配置跑一次 `backtesting`。

## 脚本相关改动（scripts/）
- 基础运行检查：`uv run python -m compileall "scripts"`

## 文档相关改动（freqtrade_book/ / freqtrade_docs/）
- 必跑自检：`uv run python "scripts/check_docs_health.py"`
- 如涉及配置示例：可加跑 `uv run python "scripts/check_docs_health.py" --check-config-examples`（需要依赖已安装）。

## vbrain 闭环（默认：有新增知识/决策时执行）
- 先对照检索：`local_rag`（外部全文/证据）+ `in_memoria`（历史套路/坑点）+ `project_docs/.serena`（既有权威结论）。
- 再回灌提炼：把“可执行结论”写回 `project_docs/` 或 `.serena/memories/`（避免只存原文）。
- 再写入套路记忆：把“决策/套路/坑点”写进 `in_memoria`（作为跨会话习惯库）。
- 再同步索引（按需）：`python -X utf8 scripts/tools/vbrain.py ingest-docs`；外部来源可用 `python -X utf8 scripts/tools/vbrain.py ingest-sources -- --only-new`。
- 推荐统一入口：`python -X utf8 scripts/tools/vbrain.py preheat --rebuild-docs`（跨设备迁移后尤其有用）。

## 通用安全复核
- 确认未引入/提交 `config.json` 等敏感文件与密钥。
- `git status` 确认变更范围符合预期。
