# freqtrade_demo - AGENTS 指南

本文件用于给 Codex/自动化助手提供仓库级工作约束与最佳实践（适用于整个仓库目录树）。

## 语言规范（强制）

- 只允许使用**简体中文**回复（包含解释/分析/结论/命令说明等）。
- 代码注释与文档优先使用中文（必要时保留关键英文术语）。

## 环境与工具约束（重要）

- 本机为 Windows 环境，默认使用 **Windows PowerShell 5.1**。
- 统一使用 `uv` 管理虚拟环境，虚拟环境放在：`./.venv/`。
- 依赖安装统一使用 `uv sync --frozen`（以 `uv.lock` 为准）。
- 命令行优先使用 `uv run` 在项目环境中执行，并带上 userdir：
  - `uv run freqtrade <命令> --userdir "." ...`
- 可选：使用 `./scripts/bootstrap.ps1` 一键初始化（含子模块 + 依赖同步）。
- 路径处理：命令里优先使用双引号包裹路径，尽量使用正斜杠 `/`。

## MCP 工具优先策略（默认）

当任务明显属于以下场景时，默认优先调用对应 MCP 工具来获得可验证结果（除非用户明确要求不用工具）：

- `serena`：语义/符号级代码检索与编辑（适合快速定位定义/引用、精确修改）
- `wolfram`：数学/符号计算/作图/优化/极值（求导、积分、解方程、画图、极值/数值求解等）
- `context7`：第三方库/框架文档与 API 查询（先 `resolve-library-id` 再 `get-library-docs`）
- `github`：GitHub 仓库/代码/提交/Issue/PR/Actions（适合跨仓库检索、PR/Issue 自动化、CI/CD 分析等）
- `markitdown`：网页/文件转 Markdown，提取正文用于总结/对照
- `playwright_mcp`：需要可复现的网页交互/抓取（登录、点击、下载、表单、滚动、截图等）
- `chrome_devtools_mcp`：更底层的浏览器调试/网络请求/性能分析（Network/Console/Trace）

执行约定：

- 工具运行前若缺关键输入（URL、文件路径、变量范围/约束等），先提问补齐，不要凭空猜测。
- 代码导航/精确编辑优先 `serena`；仅做纯文本检索时再用 `rg`。
- 网页自动化优先 `playwright_mcp`；只有需要更底层的 Network/性能数据时再用 `chrome_devtools_mcp`。

## 仓库结构与约定

- 仓库根目录即 Freqtrade userdir（策略/超参/笔记本/文档）。
- `strategies_ref_docs/`：策略参考文档（Git 子模块）。
- `pyproject.toml`：依赖声明（唯一来源）。
- `uv.lock`：依赖锁文件（锁死传递依赖）。
- `.python-version`：固定 Python 版本（uv 自动使用）。
- 安全：`config*.json` 默认忽略，避免误提交密钥；提交前务必 `git status` 复核。

## 提交规范（Conventional Commits）

- 提交信息格式：`type(scope): subject`
- `type` 推荐：`feat`、`fix`、`docs`、`refactor`、`perf`、`test`、`build`、`ci`、`chore`
- `scope` 用于标注影响范围（例如：`uv`、`bootstrap`、`docs`、`strategies`），可省略
- `subject` 使用英文动词原形（imperative），简短明确（建议 ≤ 72 字符），不要以句号结尾
- 破坏性变更：使用 `type(scope)!: ...` 或在正文/脚注中写 `BREAKING CHANGE: ...`

## 危险操作确认（强制）

执行以下操作前必须获得用户明确确认：

- 删除文件/目录、批量改动、移动关键目录
- 覆盖历史：`git push --force` / orphan 重置等
- 修改系统配置/权限/环境变量
