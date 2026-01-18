# Claude MCP 同步与一键初始化

更新日期：2026-01-17


本文面向团队/多电脑场景：在新电脑拉取本项目后，一键把常用 MCP（Serena / Context7 / MarkItDown / Playwright / Chrome DevTools / Wolfram / GitHub / In-Memoria / Local RAG）配置到 **Claude Code（`claude` CLI）**。

本仓库已提供一键脚本：`./scripts/mcp/setup_claude.ps1`。

## 为什么不建议直接复制 `~/.claude.json`

- 配置里常包含**绝对路径**（不同电脑盘符/安装位置不同）。
- 配置里可能包含 **Token/API Key**（不应进仓库、也不应随意分发）。
- 一键脚本可按需探测依赖、统一参数、减少“改路径/改环境变量”的人工步骤。

## 一键初始化（Windows PowerShell 7）

前置要求：

- 已安装 `claude`（Claude Code CLI）
- 已安装 `node`（需包含 `npx`）
- 已安装 `uv`（需包含 `uvx`）
- 如需自动拉取/更新 Wolfram-MCP（Python 模式推荐）：已安装 `git`
- 如需使用浏览器相关 MCP：安装 Chrome/Chromium（Playwright 相关依赖按需安装）
- 如需使用 Wolfram MCP：安装 Wolfram Engine/Mathematica（含 `wolframscript`）

在仓库根目录执行：

```powershell
pwsh -ExecutionPolicy Bypass -File "./scripts/mcp/setup_claude.ps1"
```

> **注意**：需要 PowerShell 7 (`pwsh`)。Windows 内置的 PowerShell 5.1 (`powershell.exe`) 对 UTF-8 无 BOM 文件支持不佳。安装方式：`winget install Microsoft.PowerShell`

只预览（不改本机配置）：

```powershell
./scripts/mcp/setup_claude.ps1 -WhatIf
```

覆盖已有同名 MCP server（危险性：会重写你本机对应 server 配置）：

```powershell
./scripts/mcp/setup_claude.ps1 -Force
```

执行完成后建议检查：

```powershell
claude mcp list
```

## 一键体检（推荐）

如果你同时使用 Codex CLI，建议直接在仓库根目录运行体检脚本（可同时检查 Codex/Claude）：

```powershell
powershell -ExecutionPolicy Bypass -File "./scripts/mcp/doctor.ps1" -Target both
```

深度检查（包含 Chrome/Local RAG/In-Memoria 缓存大小统计）：

```powershell
powershell -ExecutionPolicy Bypass -File "./scripts/mcp/doctor.ps1" -Target both -Deep
```

## 5. 使用免授权模式（可选）

Claude Code 支持通过启动参数开启 “Bypassing Permissions” 模式，减少每次执行动作时的授权打断：

```powershell
claude --dangerously-skip-permissions
```

注意事项：

- 启动时仍会有一次确认弹窗/提示，需要你确认（Yes）后才会进入该模式。
- 该模式会显著降低误操作风险控制，只建议在你**完全信任**当前项目与命令的情况下使用。

### 推荐方式：使用仓库内包装脚本（PowerShell）

本仓库提供了一个包装器脚本，会自动追加 `--dangerously-skip-permissions` 并透传所有参数：

```powershell
./scripts/mcp/skip_permissions.ps1
```

示例：

```powershell
./scripts/mcp/skip_permissions.ps1 mcp list
./scripts/mcp/skip_permissions.ps1 mcp get context7
```

### 永久生效：写入 PowerShell Profile（高级）

PowerShell 的 `Set-Alias` 不能带参数，想要“像 alias 一样”需要用函数。你可以把下面片段追加到 `$PROFILE`：

```powershell
$claudeExe = (Get-Command "claude" -CommandType Application).Source
function claude { & $claudeExe --dangerously-skip-permissions @args }
```

编辑 Profile：

```powershell
notepad $PROFILE
```

保存后重载：

```powershell
. $PROFILE
```

## 脚本参数说明

- `-Scope user|local|project`（默认：`user`）
  - `user`：写入 `~/.claude.json`（全局生效，推荐）
  - `local`：写入本机本地配置（仅当前机器）
  - `project`：写入当前项目的 project 配置（仅当前项目）
- `-LocalRagModelCacheDir <dir>`：指定 Local RAG 的嵌入模型缓存目录（写入 `CACHE_DIR`）。  
  默认使用设备级目录：`~/.codex/cache/local-rag/models/`（推荐；避免把模型缓存放进仓库）。
- `-LocalRagModelName <name>`：指定 Local RAG 的嵌入模型（写入 `MODEL_NAME`）。  
  切换模型会改变向量维度，必须配合重建向量库（见 `docs/setup/vibe_brain_workflow.md`）。
- `-WolframMode auto|paclet|python|skip`（默认：`python`）
  - `auto`：优先使用 Python 服务端脚本；若不可用再尝试 Paclet，否则跳过
  - `paclet`：使用 `wolframscript` + MCPServer Paclet 方式启动 Wolfram MCP
  - `python`：使用本地 `wolfram_mcp_server.py` 启动 Wolfram MCP（推荐）
  - `skip`：不配置 Wolfram MCP
- `-WolframMcpScriptPath <path>`：Python 模式下指定 `wolfram_mcp_server.py` 路径（建议用绝对路径）
- `-WolframMcpRepoUrl <url>`：Python 模式下 Wolfram-MCP 仓库地址（默认：`https://github.com/Natsumeretsu/Wolfram-MCP.git`）
- `-WolframMcpRepoDir <dir>`：Python 模式下 Wolfram-MCP 仓库目录（默认：`~/.codex/tools/Wolfram-MCP/`）
- `-BootstrapWolframPython`：Python 模式下强制（重新）初始化依赖并生成/更新 `.venv`（支持 `uv sync` 或 `requirements.txt`）
- `-WolframInstallationDirectory <dir>`：指定 Wolfram 安装目录（用于定位 `wolframscript`，并注入 `WOLFRAM_INSTALLATION_DIRECTORY` 环境变量）

## GitHub MCP（需要环境变量）

GitHub MCP 依赖环境变量 `GITHUB_MCP_PAT`（脚本会添加 server，但未配置该变量时健康检查会失败）。

PowerShell 临时设置（仅当前终端会话）：

```powershell
$env:GITHUB_MCP_PAT = "你的Token"
```

然后重新检查：

```powershell
claude mcp get github
```

## 安全提醒

- 不要把各类 Token/API Key、生产环境地址写进仓库。
- 多设备同步敏感配置建议走密码管理器/企业机密管理服务，再通过环境变量注入。
