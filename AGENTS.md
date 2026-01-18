# freqtrade_demo - AGENTS 指南

本文件用于给 Codex/自动化助手提供仓库级工作约束与最佳实践（适用于整个仓库目录树）。

---

## 继承规则

**本项目完全继承全局 `C:\Users\Difg\.codex\agents.md` 中定义的所有规则**，包括：
- 优先级栈
- Windows 环境规范
- 工作流程
- MCP 工具使用规则
- 代码编辑规则
- 质量标准
- 语言规范

---

## 项目特定约束

### 环境与工具

- 本机为 Windows 环境。
- **Codex 执行环境**：使用 Git Bash（Unix-like shell）执行系统命令。
- **项目脚本**：使用 PowerShell 7 (pwsh) 编写（如 `./scripts/ft.ps1`）。
- 统一使用 `uv` 管理虚拟环境，虚拟环境放在：`./.venv/`。
- 依赖安装统一使用 `uv sync --frozen`（以 `uv.lock` 为准）。

### Freqtrade 操作规范（强制）

**⚠️ 所有 Freqtrade 操作必须通过 `scripts/` 文件夹中的脚本执行：**

- Freqtrade 命令：`./scripts/ft.ps1 <命令> ...`（自动补 `--userdir "./ft_userdir"`，并注入 `PYTHONPATH=integration`）
- 数据下载：`./scripts/data/download.ps1`
- 初始化：`./scripts/bootstrap.ps1`
- **禁止直接运行 `freqtrade` 或 `uv run freqtrade`**，否则会创建多余的 `user_data/` 子目录
- 仅当 `scripts/` 中没有对应脚本时，才考虑运行底层命令

### 路径处理

- 命令里优先使用双引号包裹路径
- 尽量使用正斜杠 `/`

---

## 仓库结构

- `ft_userdir/`：Freqtrade userdir（策略、配置、数据、模型）
- `research/`：研究层（Notebook/实验记录）
- `integration/`：集成层（桥接代码，例如 `trading_system/`）
- `04_shared/`：共享配置与工具
- `docs/`：文档与归档
- `scripts/`：自动化脚本（PowerShell/Python）

---

## 架构与重构规范（强制）

本仓库对"设计/架构级变更"采用**一次性到位**原则：

- **不做分阶段迁移**：一旦决定切换架构/核心模块/主流程，必须在同一个变更中完成全量替换与收口。
- **禁止保留旧实现的主路径兼容**：旧入口/旧模块/旧参数命名在完成替换后应被移除或改造成新实现的薄包装。
- **变更必须可验收**：同步更新 `docs/**`、`scripts/**`、配置模板与 `tests/**`，提供可复现命令与验收清单。
- **关键决策必须可追溯**：在 `docs/reports/` 中补齐变更摘要（动机/取舍/影响面/复现方式）。

详细说明见：`docs/guidelines/refactor_policy.md`。

---

## 不造轮子铁律（强制）

遵循全局 `C:\Users\Difg\.codex\agents.md` 中的"不造轮子铁律"。

**项目特定补充**：
- 优先使用 `Freqtrade/Qlib/sklearn/pandas/numpy` 等已引入组件
- 使用 `context7` MCP 查询这些库的官方文档和最佳实践

---

## 提交规范（Conventional Commits）

- 提交信息格式：`type(scope): subject`
- `type` 推荐：`feat`、`fix`、`docs`、`refactor`、`perf`、`test`、`build`、`ci`、`chore`
- `scope` 用于标注影响范围（例如：`uv`、`bootstrap`、`docs`、`strategies`），可省略
- `subject` 使用英文动词原形（imperative），简短明确（建议 ≤ 72 字符），不要以句号结尾
- 破坏性变更：使用 `type(scope)!: ...` 或在正文/脚注中写 `BREAKING CHANGE: ...`

---

## 危险操作确认（强制）

执行以下操作前必须获得用户明确确认：

- 删除文件/目录、批量改动、移动关键目录
- 覆盖历史：`git push --force` / orphan 重置等
- 修改系统配置/权限/环境变量
