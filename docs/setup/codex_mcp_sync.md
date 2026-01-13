# Codex MCP 同步与一键初始化

本文面向团队/多电脑场景：在新电脑上快速把常用 MCP（vbrain core：Serena / Context7 / Wolfram / In-Memoria / Local RAG；采集层依赖：MarkItDown / Playwright / Chrome DevTools）配置到 Codex CLI 的用户配置 `~/.codex/config.toml`。

本仓库已提供一键脚本：`./scripts/mcp/setup_codex.ps1`。

## 🎯 推荐的 vibe coding「项目大脑」工作流

如果你希望每个仓库都有自己可进化的“大脑”（跨会话记忆 + 代码库画像 + 资料索引加速），建议按本文档完成 MCP 初始化后，再阅读并采用：

- `docs/setup/vibe_brain_workflow.md`
- （可选）采集层控制平面：`docs/tools/vharvest/README.md`

> 说明：本仓库额外提供 `vbrain` MCP（`scripts/tools/vbrain_mcp_server.py`），它不是替代其它 MCP 的“超级工具”，而是把闭环工作流打包成统一入口，降低日常摩擦。

## 为什么不建议直接复制 `~/.codex/config.toml`

- 配置里常包含**绝对路径**（不同电脑盘符/安装位置不同）。
- 配置里可能包含 **Token/API Key**（不应进仓库、也不应随意分发）。
- 一键脚本可按需探测依赖、统一参数、减少“改路径/改环境变量”的人工步骤。

## Serena 的同步策略（项目内 `.serena/`）

- 本仓库已包含 `.serena/project.yml` 与 `.serena/memories/`，建议随 Git 跨设备同步。
- `.serena/cache/` 与 `.serena/logs/` 属于本机缓存/日志，默认已忽略（不建议同步）。
- Serena MCP 默认使用 `--project-from-cwd` 自动识别项目，因此建议在目标项目目录内启动 Codex CLI。

## 一键初始化（Windows PowerShell 7）

前置要求：

- 已安装 `codex`（Codex CLI）
- 如需自动拉取/更新 Wolfram-MCP（Python 模式推荐）：已安装 `git`
- 已安装 `node`（含 `npx`）
- 如需使用 MarkItDown / Serena：建议安装 `uv`（含 `uvx`；若缺少 `uvx`，脚本会跳过这两个 MCP）
- 如需使用 In-Memoria / Local RAG：确保 Node.js 版本满足其要求（通常建议 Node.js 18+）
- 如需使用浏览器相关 MCP：安装 Chrome/Chromium（Playwright 相关依赖按需安装；若无法安装系统 Chrome，可用下方“无管理员修复方案”）
- 如需使用 Wolfram MCP：安装 Wolfram Engine/Mathematica（含 `wolframscript`）

说明：

- 脚本会自动探测并补齐缺失的 MCP server（不存在则添加，已存在则跳过）；单个 server 配置失败会告警并继续处理其它 server。
- 若缺少 `uvx`，脚本会跳过 MarkItDown / Serena（不自动安装）。

在仓库根目录执行：

```powershell
pwsh -ExecutionPolicy Bypass -File "./scripts/mcp/setup_codex.ps1"
```

> **注意**：需要 PowerShell 7 (`pwsh`)。Windows 内置的 PowerShell 5.1 (`powershell.exe`) 对 UTF-8 无 BOM 文件支持不佳。安装方式：`winget install Microsoft.PowerShell`

只预览（不改本机配置）：

```powershell
./scripts/mcp/setup_codex.ps1 -WhatIf
```

覆盖已有同名 MCP server（危险性：会重写你本机对应 server 配置）：

```powershell
./scripts/mcp/setup_codex.ps1 -Force
```

## 一键体检（推荐）

初始化完成后，建议先跑一次体检脚本，确认 MCP 版本对齐、Chrome 可用、Local RAG/In-Memoria 路径正确：

```powershell
powershell -ExecutionPolicy Bypass -File "./scripts/mcp/doctor.ps1"
```

深度检查（包含 Chrome/Local RAG/In-Memoria 缓存大小统计）：

```powershell
powershell -ExecutionPolicy Bypass -File "./scripts/mcp/doctor.ps1" -Deep
```

## Chrome 缺失的无管理员修复方案（推荐）

适用场景：系统无法安装 Google Chrome（权限受限/企业策略等），导致 `playwright_mcp` / `chrome_devtools_mcp` 找不到 `chrome.exe`。

推荐直接运行脚本（会下载 Playwright Chromium 并复制到用户级 Chrome 路径）：

```powershell
./scripts/tools/fix_chrome_for_mcp.ps1
```

做法：使用 Playwright 下载的 Chromium（含 “Google Chrome for Testing” 可执行文件），复制到本机可探测的用户级路径：`%LOCALAPPDATA%/Google/Chrome/Application/chrome.exe`。

```powershell
# 1) 下载 Playwright Chromium（写入到 %LOCALAPPDATA%/ms-playwright/）
npx playwright install chromium

# 2) 复制到用户级 Chrome 路径（供 MCP 自动探测）
$chromiumRoot = Get-ChildItem -Path \"$env:LOCALAPPDATA/ms-playwright\" -Directory -Filter \"chromium-*\" |
  Sort-Object -Property Name -Descending |
  Select-Object -First 1

if (-not $chromiumRoot) { throw \"未找到 Playwright Chromium 安装目录\" }

$src = Join-Path $chromiumRoot.FullName \"chrome-win64\"
$dst = \"$env:LOCALAPPDATA/Google/Chrome/Application\"

New-Item -ItemType Directory -Force -Path $dst | Out-Null
Copy-Item -Path (Join-Path $src '*') -Destination $dst -Recurse -Force
```

## 脚本参数说明

- `-LocalRagModelCacheDir <dir>`：指定 Local RAG 的嵌入模型缓存目录（写入 `CACHE_DIR`）。  
  默认使用设备级目录：`~/.codex/cache/local-rag/models/`（推荐；避免把模型缓存放进仓库）。
- `-LocalRagModelName <name>`：指定 Local RAG 的嵌入模型（写入 `MODEL_NAME`）。  
  切换模型会改变向量维度，必须配合重建向量库（见 `docs/setup/vibe_brain_workflow.md`）。
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
./scripts/mcp/setup_codex.ps1 -WolframMode python -WolframMcpRepoDir "C:/Users/Difg/.codex/tools/Wolfram-MCP" -WolframMcpRepoUrl "https://github.com/Natsumeretsu/Wolfram-MCP.git"
```

### 方案 B：Paclet 模式（可选）

优点：

- 不需要额外同步一个 Python 项目
- 依赖更少，跨设备更直观

缺点：

- 需要在 Wolfram 侧安装 MCPServer Paclet（具体安装方式取决于你使用的 Paclet 来源/渠道）

使用方式（示例）：

```powershell
./scripts/mcp/setup_codex.ps1 -WolframMode paclet
```

如果你的 `wolframscript` 不在 PATH，可显式传安装目录：

```powershell
./scripts/mcp/setup_codex.ps1 -WolframMode paclet -WolframInstallationDirectory "C:/Program Files/Wolfram Research/Wolfram Engine/14.3"
```

## 安全提醒

- 不要把各类 Token/API Key、生产环境地址写进仓库。
- 如需在多台电脑间同步敏感配置，建议用系统密钥链/密码管理器/企业机密管理服务分发，再通过环境变量注入。
