<#
.SYNOPSIS
    Freqtrade 命令包装器

.DESCRIPTION
    通过 uv run freqtrade 执行命令，自动设置 userdir 为仓库根目录。
    所有参数透传给 freqtrade。

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

function Test-Command {
  param([string]$Name)
  return [bool](Get-Command $Name -ErrorAction SilentlyContinue)
}

if (-not (Test-Command "uv")) {
  throw "uv not found. Please install uv first, then re-run this script."
}

# 统一在 UTF-8 模式下运行，避免中文 Windows 默认 GBK 导致策略扫描时报 UnicodeDecodeError
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
  # 允许直接运行：.\scripts\ft.ps1 （例如仅查看 --help）
}
elseif ($FreqtradeArgs[0].StartsWith("-")) {
  # 例如：.\scripts\ft.ps1 --help / -V
  $argsList += $FreqtradeArgs
}
else {
  # Freqtrade 的 --userdir 是子命令参数，必须放在 command 之后
  $argsList += $FreqtradeArgs[0]
  if (-not $hasUserdir) {
    $argsList += @("--userdir", ".")
  }

  if ($FreqtradeArgs.Count -gt 1) {
    $argsList += $FreqtradeArgs[1..($FreqtradeArgs.Count - 1)]
  }
}

Write-Host ""
Write-Host "运行命令："
Write-Host ("uv " + ($argsList -join " "))
Write-Host ""

& uv @argsList
