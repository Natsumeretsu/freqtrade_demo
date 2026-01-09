# Codex MCP 同步与一键初始化

本文面向团队/多电脑场景：在新电脑上快速把常用 MCP（Context7 / MarkItDown / Playwright / Chrome DevTools / Wolfram）配置到 Codex CLI 的用户配置 `~/.codex/config.toml`。

本仓库已提供一键脚本：`./scripts/setup_codex_mcp.ps1`。

## 为什么不建议直接复制 `~/.codex/config.toml`

- 配置里常包含**绝对路径**（不同电脑盘符/安装位置不同）。
- 配置里可能包含 **Token/API Key**（不应进仓库、也不应随意分发）。
- 一键脚本可按需探测依赖、统一参数、减少“改路径/改环境变量”的人工步骤。

## 一键初始化（Windows）

前置要求：

- 已安装 `codex`（Codex CLI）
- 如需自动拉取/更新 Wolfram-MCP（Python 模式推荐）：已安装 `git`
- 已安装 `node`（含 `npx`）
- 建议安装 `uv`（含 `uvx`；若未安装 `uvx`，脚本会尝试自动安装 uv，失败则跳过 MarkItDown MCP）
- 如需使用浏览器相关 MCP：安装 Chrome/Chromium（Playwright 相关依赖按需安装）
- 如需使用 Wolfram MCP：安装 Wolfram Engine/Mathematica（含 `wolframscript`）

说明：

- 脚本会自动探测并补齐缺失的 MCP server（不存在则添加，已存在则跳过）；单个 server 配置失败会告警并继续处理其它 server。
- 若缺少 `uvx`，脚本会优先尝试自动安装 uv（可能需要联网/系统权限确认）；若安装失败，会跳过 MarkItDown MCP。

在仓库根目录执行：

```powershell
powershell.exe -ExecutionPolicy Bypass -File "./scripts/setup_codex_mcp.ps1"
```

只预览（不改本机配置）：

```powershell
./scripts/setup_codex_mcp.ps1 -WhatIf
```

覆盖已有同名 MCP server（危险性：会重写你本机对应 server 配置）：

```powershell
./scripts/setup_codex_mcp.ps1 -Force
```

## 脚本参数说明

- `-WolframMode auto|paclet|python|skip`（默认：`python`）
  - `auto`：优先使用 Python 服务端脚本（默认 `~/.codex/tools/Wolfram-MCP/`，必要时会尝试拉取/更新仓库），若不可用再尝试 Paclet，否则跳过
  - `paclet`：使用 `wolframscript` + MCPServer Paclet 方式启动 Wolfram MCP
  - `python`：使用本地 `wolfram_mcp_server.py` 启动 Wolfram MCP
  - `skip`：不配置 Wolfram MCP
- `-WolframMcpScriptPath <path>`：Python 模式下指定 `wolfram_mcp_server.py` 路径（建议用绝对路径，或放在固定位置）
- `-WolframMcpRepoUrl <url>`：Python 模式下 Wolfram-MCP 仓库地址（默认：`https://github.com/Natsumeretsu/Wolfram-MCP.git`）
- `-WolframMcpRepoDir <dir>`：Python 模式下 Wolfram-MCP 仓库目录（默认：`~/.codex/tools/Wolfram-MCP/`）
- `-BootstrapWolframPython`：Python 模式下强制（重新）初始化依赖并生成/更新 `.venv`（优先 `uv sync`；若仅有 `requirements.txt` 则使用 `uv venv` + `uv pip install -r requirements.txt`）
- `-WolframInstallationDirectory <dir>`：指定 Wolfram 安装目录（用于定位 `wolframscript`，并注入 `WOLFRAM_INSTALLATION_DIRECTORY` 环境变量）

## Wolfram MCP 的同步策略（推荐：独立仓库 + 全局 tools）

结论建议：

- **默认/推荐**：使用 **Python 模式**，并把 Wolfram-MCP 作为**独立仓库**放在 `~/.codex/tools/Wolfram-MCP/`（不放进本仓库、不使用子模块），由该目录下的 `.venv` 独立运行
- **Paclet 模式**：作为可选替代（不想维护 Python 依赖或不需要自定义服务端时）

### 方案 A：Python 模式 + 独立仓库（默认/推荐）

默认约定：

- 仓库：`https://github.com/Natsumeretsu/Wolfram-MCP.git`
- 目录：`~/.codex/tools/Wolfram-MCP/`

脚本行为（Python 模式）：

- 若目录不存在：尝试 `git clone`
- 若目录存在且工作区干净：尝试 `git pull --ff-only`
- 若目录存在但有本地改动：跳过更新并继续使用当前版本

如需自定义：

```powershell
./scripts/setup_codex_mcp.ps1 -WolframMode python -WolframMcpRepoDir "C:/Users/Difg/.codex/tools/Wolfram-MCP" -WolframMcpRepoUrl "https://github.com/Natsumeretsu/Wolfram-MCP.git"
```

### 方案 B：Paclet 模式（可选）

优点：

- 不需要额外同步一个 Python 项目
- 依赖更少，跨设备更直观

缺点：

- 需要在 Wolfram 侧安装 MCPServer Paclet（具体安装方式取决于你使用的 Paclet 来源/渠道）

使用方式（示例）：

```powershell
./scripts/setup_codex_mcp.ps1 -WolframMode paclet
```

如果你的 `wolframscript` 不在 PATH，可显式传安装目录：

```powershell
./scripts/setup_codex_mcp.ps1 -WolframMode paclet -WolframInstallationDirectory "C:/Program Files/Wolfram Research/Wolfram Engine/14.3"
```

## 安全提醒

- 不要把各类 Token/API Key、生产环境地址写进仓库。
- 如需在多台电脑间同步敏感配置，建议用系统密钥链/密码管理器/企业机密管理服务分发，再通过环境变量注入。
