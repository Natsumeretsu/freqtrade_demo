<#
.SYNOPSIS
    项目初始化脚本

.DESCRIPTION
    克隆仓库后的一键初始化：安装 Python 依赖、初始化子模块、配置 MCP 等。

.PARAMETER SetupClaude
    同时配置 Claude Code CLI 的 MCP servers

.PARAMETER SetupCodex
    同时配置 Codex CLI 的 MCP servers

.EXAMPLE
    .\bootstrap.ps1
    .\bootstrap.ps1 -SetupClaude
    .\bootstrap.ps1 -SetupCodex
    .\bootstrap.ps1 -SkipSubmodules -SetupClaude
#>
[CmdletBinding()]
param(
  [switch]$SkipSubmodules,
  [switch]$SkipPythonInstall,
  [switch]$SetupClaude,
  [switch]$SetupCodex
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

# 加载公共模块（复用 Test-Command 等函数）
$mcpCommon = Join-Path $PSScriptRoot "lib/common.ps1"
if (Test-Path $mcpCommon) {
  . $mcpCommon
} else {
  # 备用定义
  function Test-Command {
    param([string]$Name)
    return [bool](Get-Command $Name -ErrorAction SilentlyContinue)
  }
}

function Get-PinnedPythonVersion {
  param([string]$Path)

  if (-not (Test-Path $Path)) {
    return "3.11"
  }

  $version = (Get-Content $Path -Raw).Trim()
  if ([string]::IsNullOrWhiteSpace($version)) {
    return "3.11"
  }

  return $version
}

if (-not (Test-Command "uv")) {
  throw "uv not found. Please install uv first, then re-run this script."
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $repoRoot

Write-Host "Repo root: $repoRoot"

if (-not $SkipSubmodules -and (Test-Path ".gitmodules")) {
  if (Test-Command "git") {
    Write-Host "Init/update git submodules..."
    git submodule update --init --recursive
    if ($LASTEXITCODE -ne 0) {
      throw "git submodule update 失败"
    }
  }
  else {
    Write-Warning "git not found, skipped submodules init/update."
  }
}

$pythonVersion = Get-PinnedPythonVersion ".python-version"

if (-not $SkipPythonInstall) {
  Write-Host "Ensure Python $pythonVersion is available (uv)..."
  uv python install $pythonVersion
  if ($LASTEXITCODE -ne 0) {
    throw "uv python install 失败"
  }
}

Write-Host "Sync dependencies (uv.lock, frozen)..."
uv sync --frozen
if ($LASTEXITCODE -ne 0) {
  throw "uv sync --frozen 失败"
}

# MCP 配置
$mcpScriptDir = Join-Path $PSScriptRoot "mcp"

if ($SetupClaude) {
  $claudeScript = Join-Path $mcpScriptDir "setup_claude.ps1"
  if (Test-Path $claudeScript) {
    Write-Host ""
    Write-Host "Setting up Claude Code MCP..."
    & $claudeScript
  } else {
    Write-Warning "setup_claude.ps1 not found, skipped."
  }
}

if ($SetupCodex) {
  $codexScript = Join-Path $mcpScriptDir "setup_codex.ps1"
  if (Test-Path $codexScript) {
    Write-Host ""
    Write-Host "Setting up Codex MCP..."
    & $codexScript
  } else {
    Write-Warning "setup_codex.ps1 not found, skipped."
  }
}

Write-Host ""
Write-Host "Done. Example: uv run freqtrade --version"
