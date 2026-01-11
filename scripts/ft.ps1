<#
.SYNOPSIS
    Freqtrade command wrapper

.DESCRIPTION
    Run freqtrade via uv, auto-set userdir to repo root.
    All arguments are passed through to freqtrade.

.EXAMPLE
    .\ft.ps1 backtesting --config config.json
    .\ft.ps1 download-data --pairs BTC/USDT
#>
[CmdletBinding()]
param(
  [Parameter(ValueFromRemainingArguments = $true)]
  [string[]]$FreqtradeArgs
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

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
    $argsList += @("--userdir", ".")
  }

  if ($FreqtradeArgs.Count -gt 1) {
    $argsList += $FreqtradeArgs[1..($FreqtradeArgs.Count - 1)]
  }
}

Write-Host ""
Write-Host "Running: uv $($argsList -join ' ')"
Write-Host ""

& uv @argsList
