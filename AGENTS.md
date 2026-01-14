# freqtrade_demo - AGENTS 指南

本文件用于给 Codex/自动化助手提供仓库级工作约束与最佳实践（适用于整个仓库目录树）。

## 语言规范（强制）

- 只允许使用**简体中文**回复（包含解释/分析/结论/命令说明等）。
- 代码注释与文档优先使用中文（必要时保留关键英文术语）。

## 环境与工具约束（重要）

- 本机为 Windows 环境，默认使用 **Windows PowerShell 5.1**。
- 统一使用 `uv` 管理虚拟环境，虚拟环境放在：`./.venv/`。
- 依赖安装统一使用 `uv sync --frozen`（以 `uv.lock` 为准）。
- **⚠️ 所有操作必须通过 `scripts/` 文件夹中的脚本执行：**
  - Freqtrade 命令：`./scripts/ft.ps1 <命令> ...`（自动补 `--userdir "./01_freqtrade"`，并注入 `PYTHONPATH=03_integration` 供策略侧导入桥接代码）
  - 数据下载：`./scripts/data/download.ps1`
  - 初始化：`./scripts/bootstrap.ps1`
  - **禁止直接运行 `freqtrade` 或 `uv run freqtrade`**，否则会创建多余的 `user_data/` 子目录
  - 仅当 `scripts/` 中没有对应脚本时，才考虑运行底层命令
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

- 本仓库采用分层结构，Freqtrade `userdir` 位于：`01_freqtrade/`。
- 配置模板：`04_shared/configs/`（脱敏、可提交）；运行配置：`01_freqtrade/config.json`（可提交但禁止写入密钥）；私密覆盖：`01_freqtrade/config-private.json` 与 `.env`（必须保持 gitignore）。
- 研究层：`02_qlib_research/`（Notebook/实验记录；`qlib_data/` 与 `models/` 默认 gitignore）。
- 集成层：`03_integration/`（桥接代码，例如 `trading_system/`）。
- 参考资料/归档：`docs/archive/`（包含 `docs/archive/strategies_ref_docs/` 子模块）。
- `pyproject.toml`：依赖声明（唯一来源）。
- `uv.lock`：依赖锁文件（锁死传递依赖）。
- `.python-version`：固定 Python 版本（uv 自动使用）。
- 安全：严禁提交任何密钥/Token/个人路径；提交前务必 `git status` 复核。

## 架构与重构规范（强制）

本仓库对“设计/架构级变更”采用**一次性到位**原则，避免长期分叉与半迁移状态导致的不可控复杂度：

- **不做分阶段迁移**：一旦决定切换架构/核心模块/主流程，必须在同一个变更中完成全量替换与收口。
- **禁止保留旧实现的主路径兼容**：旧入口/旧模块/旧参数命名在完成替换后应被移除或改造成新实现的薄包装（不允许长期双轨运行）。
- **变更必须可验收**：同步更新 `docs/**`、`scripts/**`、配置模板与 `tests/**`，提供可复现命令与验收清单。
- **关键决策必须可追溯**：在 `docs/reports/` 中补齐变更摘要（动机/取舍/影响面/复现方式）。

对应更详细说明见：`docs/guidelines/refactor_policy.md`。

## 不造轮子铁律（强制）

> 能不造轮子就不要造轮子。  
> 能不造轮子就不要造轮子。  
> 能不造轮子就不要造轮子。

“人生苦短，我用 Python。”但更重要的是：**把时间用在顶层设计与验证闭环上，而不是重复发明、重复维护。**

执行要求（写代码前必须满足）：

- **先搜再写**：新增任何功能/脚本/模块前，必须完成替代方案检索：
  - 仓库内检索：用 `rg` 确认是否已有实现/相近工具；
  - 现有依赖优先：优先使用 `Freqtrade/Qlib/sklearn/pandas/numpy` 等已引入组件；
  - 文档检索：优先用 Context7 查第三方库的现成能力与最佳实践。
- **能复用就复用**：能通过组合现有库/现有模块实现的，禁止写“自定义框架/自定义协议/自定义算法”来替代。
- **必须造轮子时先申请**：若确认“现成方案不可用”，必须先把原因与需求写清楚并向仓库维护者（你）确认，确认后才允许落地：
  - 需求与边界：做什么/不做什么（避免无限膨胀）；
  - 替代方案清单：尝试过哪些库/模块/方案，为什么不行；
  - 维护成本评估：后续谁维护、如何测试、如何回归、性能/边界如何保证；
  - 交付物：最小实现 + 单元测试（≤60s）+ 文档 + 可复现命令。

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
