<#
.SYNOPSIS
    Freqtrade command wrapper

.DESCRIPTION
    Run freqtrade via uv, auto-set userdir to ./01_freqtrade.
    All arguments are passed through to freqtrade.

.EXAMPLE
    .\ft.ps1 backtesting --config 01_freqtrade/config.json
    .\ft.ps1 download-data --pairs BTC/USDT
#>
[CmdletBinding()]
param(
  [Parameter(ValueFromRemainingArguments = $true)]
  [string[]]$FreqtradeArgs
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

# 兼容：当脚本被不带参数调用（或只用了 PowerShell 的通用参数）时，这里可能是 $null
if ($null -eq $FreqtradeArgs) {
  $FreqtradeArgs = @()
}

# Load common module
$mcpCommon = Join-Path $PSScriptRoot "lib/common.ps1"
if (Test-Path $mcpCommon) {
  . $mcpCommon
} else {
  function Test-Command {
    param([string]$Name)
    return [bool](Get-Command $Name -ErrorAction SilentlyContinue)
  }
}

if (-not (Test-Command "uv")) {
  throw "uv not found. Please install uv first, then re-run this script."
}

# Force UTF-8 mode to avoid GBK encoding issues on Chinese Windows
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $repoRoot

# 确保策略侧可导入 03_integration/trading_system（集成层代码）
$integrationRoot = (Join-Path $repoRoot "03_integration")
if (Test-Path $integrationRoot) {
  if ([string]::IsNullOrWhiteSpace($env:PYTHONPATH)) {
    $env:PYTHONPATH = $integrationRoot
  } else {
    # Windows 上 PYTHONPATH 分隔符为 ';'
    if ($env:PYTHONPATH -notmatch [regex]::Escape($integrationRoot)) {
      $env:PYTHONPATH = "$integrationRoot;$($env:PYTHONPATH)"
    }
  }
}

$argsList = @(
  "run",
  "python",
  "-X",
  "utf8",
  "-m",
  "freqtrade"
)

$hasUserdir = $false
for ($i = 0; $i -lt $FreqtradeArgs.Count; $i++) {
  if ($FreqtradeArgs[$i] -in @("--userdir", "--user-data-dir")) {
    $hasUserdir = $true
    break
  }
}

if ($FreqtradeArgs.Count -eq 0) {
  # Allow running without args: .\scripts\ft.ps1 (e.g. just --help)
}
elseif ($FreqtradeArgs[0].StartsWith("-")) {
  # e.g. .\scripts\ft.ps1 --help / -V
  $argsList += $FreqtradeArgs
}
else {
  # Freqtrade's --userdir is a subcommand arg, must come after command
  $argsList += $FreqtradeArgs[0]
  if (-not $hasUserdir) {
    $argsList += @("--userdir", "./01_freqtrade")
  }

  if ($FreqtradeArgs.Count -gt 1) {
    $argsList += $FreqtradeArgs[1..($FreqtradeArgs.Count - 1)]
  }
}

Write-Host ""
Write-Host "Running: uv $($argsList -join ' ')"
Write-Host ""

& uv @argsList
