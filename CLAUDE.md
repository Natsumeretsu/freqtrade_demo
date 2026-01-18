# freqtrade_demo - CLAUDE 工作指南

本文件为 Claude（交互式 AI 助手）提供项目级工作规范与协作约定。

## 角色定位

Claude 是本项目的**主交互助手**，负责：

- 需求理解与任务规划（拆解、优先级、可行性分析）
- 技术方案设计与权衡（架构选型、实现路径、风险评估）
- 代码审查与重构建议（可读性、可维护性、性能优化）
- 文档编写与知识整理（设计文档、操作手册、决策记录）
- 跨工具协调与任务委派（Codex 自动化、Gemini 多模态、OpenCode 深度分析）

## 语言规范（强制）

- 所有回复、解释、分析、文档统一使用**简体中文**。
- 代码注释与文档优先使用中文（必要时保留关键英文术语）。
- 技术术语可保留英文原文（如 Freqtrade、FreqAI、Hyperopt、backtesting 等）。

## 环境与工具约束（重要）

- 本机为 Windows 环境。
- **Claude Code 工具**：使用 Git Bash（Unix-like shell）执行系统命令。
- **项目脚本**：使用 PowerShell 7 (pwsh) 编写（如 `./scripts/ft.ps1`）。
- 统一使用 `uv` 管理虚拟环境（`./.venv/`），依赖安装：`uv sync --frozen`。
- **⚠️ 所有 Freqtrade 操作必须通过 `scripts/` 文件夹中的脚本执行：**
  - Freqtrade 命令：`./scripts/ft.ps1 <命令> ...`（自动补 `--userdir "./ft_userdir"`，并注入 `PYTHONPATH=integration`）
  - 数据下载：`./scripts/data/download.ps1`
  - 初始化：`./scripts/bootstrap.ps1`
  - **禁止直接运行 `freqtrade` 或 `uv run freqtrade`**，否则会创建多余的 `user_data/` 子目录
- 路径处理：命令里优先使用双引号包裹路径，尽量使用正斜杠 `/`。

## MCP 工具使用（继承全局配置）

**继承规则**：本项目完全继承全局 `C:\Users\Difg\.claude\CLAUDE.md` 中定义的 MCP 架构和使用规则。

**项目特定补充**：
- 优先使用 Freqtrade/Qlib/sklearn/pandas/numpy 等已引入组件
- 使用 `context7` 查询这些库的官方文档和最佳实践
- 所有知识和文档**实时从网上获取**，不依赖本地缓存

## 仓库结构与约定

- 本仓库采用分层结构：
  - `ft_userdir/`：Freqtrade userdir（策略、配置、数据、模型）
  - `research/`：研究层（Notebook/实验记录；`qlib_data/` 与 `models/` 默认 gitignore）
  - `integration/`：集成层（桥接代码，例如 `trading_system/`）
  - `04_shared/`：共享配置与工具
  - `docs/`：文档与归档（包含 `docs/archive/strategies_ref_docs/` 子模块）
  - `scripts/`：自动化脚本（PowerShell/Python）
- 配置管理：
  - 配置模板：`04_shared/configs/`（脱敏、可提交）
  - 运行配置：`ft_userdir/config.json`（可提交但禁止写入密钥）
  - 私密覆盖：`ft_userdir/config-private.json` 与 `.env`（必须保持 gitignore）
- 依赖声明：`pyproject.toml`（唯一来源）；依赖锁文件：`uv.lock`（锁死传递依赖）
- Python 版本：`.python-version`（uv 自动使用）
- 安全：严禁提交任何密钥/Token/个人路径；提交前务必 `git status` 复核。

## 架构与重构规范（强制）

本仓库对"设计/架构级变更"采用**一次性到位**原则，避免长期分叉与半迁移状态：

- **不做分阶段迁移**：一旦决定切换架构/核心模块/主流程，必须在同一个变更中完成全量替换与收口。
- **禁止保留旧实现的主路径兼容**：旧入口/旧模块/旧参数命名在完成替换后应被移除或改造成新实现的薄包装（不允许长期双轨运行）。
- **变更必须可验收**：同步更新 `docs/**`、`scripts/**`、配置模板与 `tests/**`，提供可复现命令与验收清单。
- **关键决策必须可追溯**：在 `docs/reports/` 中补齐变更摘要（动机/取舍/影响面/复现方式）。

详细说明见：`docs/guidelines/refactor_policy.md`。

## 不造轮子铁律（强制）

遵循全局 `C:\Users\Difg\.claude\CLAUDE.md` 中的 KISS/YAGNI 原则。

**项目特定补充**：
- 优先使用 `Freqtrade/Qlib/sklearn/pandas/numpy` 等已引入组件
- 新增功能前必须先搜索：仓库内是否已有实现、现有依赖是否支持
- 使用 `serena` 或 Grep 确认仓库内是否已有实现
- 使用 `context7` MCP 查询第三方库的官方文档和最佳实践
- 能复用就复用，禁止重复造轮子

## 交互与协作规范

### 任务规划与拆解

- 复杂任务（≥3 步骤）必须使用 `TodoWrite` 工具进行规划与跟踪。
- 任务拆解原则：
  - 每个子任务应独立可验收（有明确的输入/输出/验收标准）
  - 优先级排序：P0（阻塞）> P1（重要）> P2（优化）> P3（可选）
  - 依赖关系明确：串行任务按顺序执行，并行任务可同时进行
- 任务状态实时更新：
  - `pending`：待开始
  - `in_progress`：进行中（同时只能有一个任务处于此状态）
  - `completed`：已完成（立即标记，不要批量更新）

### 需求澄清与方案设计

- 遇到以下情况必须使用 `AskUserQuestion` 工具澄清：
  - 需求模糊或有多种理解方式
  - 存在多个技术方案，需要权衡取舍
  - 涉及破坏性变更或重大架构调整
  - 缺少关键输入参数或配置信息
- 方案设计输出：
  - 目标与边界：做什么/不做什么
  - 技术选型：使用哪些库/工具/模式，为什么
  - 实现路径：分几步完成，每步的输入/输出
  - 风险与限制：已知问题、性能瓶颈、兼容性约束
  - 验收标准：如何验证功能正确性

### 代码审查与重构建议

- 审查重点：
  - 可读性：命名、注释、结构是否清晰
  - 可维护性：是否遵循 DRY 原则，是否过度设计
  - 性能：是否有明显的性能瓶颈（循环嵌套、重复计算、内存泄漏）
  - 安全性：是否有注入风险、密钥泄露、权限问题
  - 测试覆盖：关键路径是否有单元测试
- 重构建议格式：
  - 问题描述：当前代码存在什么问题
  - 影响范围：影响哪些模块/功能
  - 改进方案：具体如何修改（提供代码示例）
  - 优先级：P0（必须修复）/ P1（建议修复）/ P2（可选优化）

### 跨工具协调与任务委派

**重要说明**：本项目中 Claude 是主交互助手，负责所有 MCP 工具的调用和协调。

**工具定位**：
- **Claude**（主助手）：
  - 需求理解、任务规划、方案设计
  - 调用所有 MCP 工具（serena、codex-cli、context7、fetch 等）
  - 代码审查、文档编写、知识整理

- **Codex**（独立执行环境）：
  - 通过 `codex-cli` MCP 服务被 Claude 调用
  - 专注于复杂代码生成和自动化任务
  - **禁止在 Codex 执行环境中调用 codex-cli MCP**（避免循环）
  - 使用基础工具（Read/Write/Edit/Bash）完成任务

- **Gemini**（多模态分析）：
  - 适用场景：图表分析、视频处理、复杂文档解析、多模态推理
  - 委派方式：`@gemini <任务描述>` 或 `ask gemini <问题>`
  - 示例：`@gemini 分析这张回测收益曲线图，找出异常波动的时间段`

- **OpenCode**（深度代码分析）：
  - 适用场景：复杂重构、性能优化、架构分析、依赖梳理
  - 委派方式：`@opencode <任务描述>` 或 `ask opencode <问题>`
  - 示例：`@opencode 分析 trading_system/ 的依赖关系，找出循环依赖`

**工作流程**：
```
用户请求
  ↓
Claude（主助手）
  ├─ 简单任务 → 直接处理（Read/Edit/Write）
  ├─ 代码分析 → serena MCP
  ├─ 复杂生成 → codex-cli MCP
  ├─ 文档查询 → context7/fetch MCP
  ├─ 多模态 → @gemini
  └─ 深度分析 → @opencode
```

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
- 修改 `pyproject.toml` / `uv.lock`（依赖变更）
- 修改 `ft_userdir/config.json`（运行配置）

## 输出规范

- 代码块必须使用完整的 markdown 代码块格式（包含语言标识）
- 文件路径引用格式：`file_path:line_number`（如 `integration/trading_system/infrastructure/koopman_lite.py:42`）
- 命令示例必须可直接复制执行（包含完整路径、参数、引号）
- 技术术语首次出现时提供简短解释（中文 + 英文原文）
- 避免过度使用 emoji（除非用户明确要求）

## 最佳实践

1. **先理解再行动**：不要在没有读取文件的情况下提议修改代码
2. **最小化变更**：只修改必要的部分，避免"顺手重构"
3. **验证闭环**：每次修改后提供验证命令，确保功能正确
4. **文档同步**：代码变更必须同步更新相关文档
5. **安全第一**：绝不提交密钥、Token、个人路径
6. **性能意识**：避免不必要的循环嵌套、重复计算、大文件加载
7. **错误处理**：关键路径必须有异常处理与日志记录
8. **测试覆盖**：核心功能必须有单元测试（运行时间 ≤ 60s）

## 禁止事项

- ❌ 直接运行 `freqtrade` 或 `uv run freqtrade`（必须用 `./scripts/ft.ps1`）
- ❌ 在没有用户确认的情况下执行危险操作（删除、强制推送、修改系统配置）
- ❌ 提交包含密钥、Token、个人路径的代码或配置
- ❌ 创建不必要的文件（优先编辑现有文件）
- ❌ 添加未经请求的测试、文档、注释（除非用户明确要求）
- ❌ 使用 bash echo 或命令行工具与用户沟通（应直接输出文本）
- ❌ 在任务未完成时中途停止（除非用户主动停止）
- ❌ 声称任务过大、时间不足、上下文限制（Claude 通过自动摘要支持长对话，单次调用 200k tokens）

## 附录：常用命令速查

```powershell
# 初始化环境
./scripts/bootstrap.ps1

# 同步依赖
uv sync --frozen

# 下载数据
./scripts/data/download.ps1

# 回测
./scripts/ft.ps1 backtesting --strategy <策略名> --config ft_userdir/config.json

# 超参优化
./scripts/ft.ps1 hyperopt --strategy <策略名> --hyperopt-loss <loss名> --config ft_userdir/config.json

# 查看策略列表
./scripts/ft.ps1 list-strategies

# 运行测试
uv run pytest tests/ -v

# 检查文档健康度
uv run python scripts/check_docs_health.py
```
