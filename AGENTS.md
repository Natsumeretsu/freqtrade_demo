# freqtrade_demo - AGENTS 指南

本文件用于给 Codex/自动化助手提供仓库级工作约束与最佳实践（适用于整个仓库目录树）。

## 语言规范（强制）

- 只允许使用**简体中文**回复（包含解释/分析/结论/命令说明等）。
- 代码注释与文档优先使用中文（必要时保留关键英文术语）。

## 环境与工具约束（重要）

- 本机为 Windows 环境，默认使用 **Windows PowerShell 5.1**。
- 统一使用 `uv` 管理虚拟环境，虚拟环境放在：`./.venv/`。
- 命令行优先显式调用虚拟环境内可执行文件，并带上 userdir：
  - `& "./.venv/Scripts/freqtrade.exe" --userdir "." ...`
- 路径处理：命令里优先使用双引号包裹路径，尽量使用正斜杠 `/`。

## 仓库结构与约定

- 仓库根目录即 Freqtrade userdir（策略/超参/笔记本/文档）。
- `strategies_ref_docs/`：策略参考文档（Git 子模块）。
- `requirements.txt`：Freqtrade 依赖锁定（固定到 Git commit，避免版本漂移）。
- 安全：`config*.json` 默认忽略，避免误提交密钥；提交前务必 `git status` 复核。

## 危险操作确认（强制）

执行以下操作前必须获得用户明确确认：

- 删除文件/目录、批量改动、移动关键目录
- 覆盖历史：`git push --force` / orphan 重置等
- 修改系统配置/权限/环境变量
