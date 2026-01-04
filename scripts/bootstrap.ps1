[CmdletBinding()]
param(
  [switch]$SkipSubmodules,
  [switch]$SkipPythonInstall
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

function Test-Command {
  param([string]$Name)

  return [bool](Get-Command $Name -ErrorAction SilentlyContinue)
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
  }
  else {
    Write-Warning "git not found, skipped submodules init/update."
  }
}

$pythonVersion = Get-PinnedPythonVersion ".python-version"

if (-not $SkipPythonInstall) {
  Write-Host "Ensure Python $pythonVersion is available (uv)..."
  uv python install $pythonVersion
}

Write-Host "Sync dependencies (uv.lock, frozen)..."
uv sync --frozen

Write-Host "Done. Example: uv run freqtrade --version"
