<#
.SYNOPSIS
    Freqtrade command wrapper

.DESCRIPTION
    Run freqtrade via uv, auto-set userdir to ./ft_userdir.
    All arguments are passed through to freqtrade.

.EXAMPLE
    .\ft.ps1 backtesting --config ft_userdir/config.json
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
  # 临时关闭 StrictMode 以避免 common.ps1 的 StrictMode 影响后续变量定义
  Set-StrictMode -Off
  . $mcpCommon
  Set-StrictMode -Version Latest
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

# 确保策略侧可导入 integration（集成层代码）
$integrationRoot = Join-Path $repoRoot "integration"
if (Test-Path $integrationRoot) {
  $integrationRootStr = $integrationRoot.ToString()
  if ([string]::IsNullOrWhiteSpace($env:PYTHONPATH)) {
    $env:PYTHONPATH = $integrationRootStr
  } else {
    # Windows 上 PYTHONPATH 分隔符为 ';'
    $escapedPath = [regex]::Escape($integrationRootStr)
    if ($env:PYTHONPATH -notmatch $escapedPath) {
      $env:PYTHONPATH = "$integrationRootStr;$($env:PYTHONPATH)"
    }
  }
}

# 优先使用本仓库的 venv Python 直接运行，避免 uv run 在 Windows 上因文件占用触发依赖重装失败（os error 32）。
# 若 .venv 不存在，再回退到 uv run。
$venvPython = Join-Path $repoRoot ".venv/Scripts/python.exe"
$useVenvPython = Test-Path $venvPython

if ($useVenvPython) {
  $cmd = $venvPython
  $argsList = @(
    "-X",
    "utf8",
    "-m",
    "freqtrade"
  )
} else {
  $cmd = "uv"
  $argsList = @(
    "run",
    "python",
    "-X",
    "utf8",
    "-m",
    "freqtrade"
  )
}

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
    $argsList += @("--userdir", "./ft_userdir")
  }

  if ($FreqtradeArgs.Count -gt 1) {
    $argsList += $FreqtradeArgs[1..($FreqtradeArgs.Count - 1)]
  }
}

Write-Host ""
Write-Host "Running: $cmd $($argsList -join ' ')"
Write-Host ""

& $cmd @argsList
