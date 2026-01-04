[CmdletBinding()]
param(
  [switch]$SkipSubmodules,
  [switch]$SkipPythonInstall
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

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

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $repoRoot

Write-Host "📌 仓库根目录: $repoRoot"

if (-not $SkipSubmodules -and (Test-Path ".gitmodules")) {
  Write-Host "🔄 初始化/更新子模块..."
  git submodule update --init --recursive
}

$pythonVersion = Get-PinnedPythonVersion ".python-version"

if (-not $SkipPythonInstall) {
  Write-Host "🐍 确保 Python $pythonVersion 可用(uv)..."
  uv python install $pythonVersion
}

Write-Host "📦 同步依赖(uv.lock, frozen)..."
uv sync --frozen

Write-Host "✅ 完成。示例：uv run freqtrade --version"
