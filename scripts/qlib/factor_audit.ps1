<#
.SYNOPSIS
  短周期因子体检（15m/1h）：IC/分位收益/成本后收益/换手/30&60天滚动稳定性

.DESCRIPTION
  封装 uv + UTF-8 + PYTHONPATH，循环跑多个 timeframe。

.EXAMPLE
  ./scripts/qlib/factor_audit.ps1 -SymbolsYaml "04_shared/config/symbols.yaml" -FeatureSet "ml_core"

  ./scripts/qlib/factor_audit.ps1 `
    -Timeframes "15m","1h" `
    -SymbolsYaml "04_shared/config/symbols_research_okx_futures_top40.yaml" `
    -FeatureSet "cta_core" `
    -Horizons 1,4 `
    -Fee 0.0006 `
    -RollingDays 30,60
#>
[CmdletBinding()]
param(
  [string[]]$Timeframes = @("15m", "1h"),
  [string]$Exchange = "",
  [string]$SymbolsYaml = "",
  [string[]]$Pairs = @(),
  [string]$FeatureSet = "ml_core",
  [string]$StrategyParams = "",
  [string[]]$Vars = @(),
  [int[]]$Horizons = @(1, 4),
  [int]$Quantiles = 5,
  [double]$Fee = 0.0006,
  [double]$Slippage = 0.0,
  [int[]]$RollingDays = @(30, 60),
  [double]$MinRollMedian = 0.0,
  [double]$MinRollP10 = -0.15,
  [double]$MinIcIr = 0.0,
  [double]$MinTopAlphaBtcNet = 0.0,
  [string]$OutDir = "",
  [string]$RunId = "",
  [switch]$ExportSeries
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Test-Command {
  param([Parameter(Mandatory = $true)][string]$Name)
  return [bool](Get-Command $Name -ErrorAction SilentlyContinue)
}

if (-not (Test-Command "uv")) {
  throw "uv not found. Please install uv first, then re-run this script."
}

# PowerShell 5.1 默认输出编码可能导致 UTF-8 中文乱码，这里强制为 UTF-8
try {
  [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
  $OutputEncoding = [System.Text.Encoding]::UTF8
} catch {
  # ignore
}

# 统一 UTF-8（避免中文 Windows 默认编码导致子进程读文件异常）
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "../..")).Path
Set-Location $repoRoot

# 确保 Python 可导入 03_integration/trading_system
$integrationRoot = (Join-Path $repoRoot "03_integration")
if (Test-Path $integrationRoot) {
  if ([string]::IsNullOrWhiteSpace($env:PYTHONPATH)) {
    $env:PYTHONPATH = $integrationRoot
  } else {
    if ($env:PYTHONPATH -notmatch [regex]::Escape($integrationRoot)) {
      $env:PYTHONPATH = "$integrationRoot;$($env:PYTHONPATH)"
    }
  }
}

if ($Timeframes.Count -le 0) {
  throw "Timeframes 不能为空"
}

foreach ($tf in $Timeframes) {
  $tf2 = [string]$tf
  if ([string]::IsNullOrWhiteSpace($tf2)) { continue }

  Write-Host ""
  Write-Host ("=== 因子体检：{0} ===" -f $tf2)

  $args = @(
    "run","python","-X","utf8","scripts/qlib/factor_audit.py",
    "--timeframe",$tf2,
    "--feature-set",$FeatureSet,
    "--quantiles","$Quantiles",
    "--fee","$Fee",
    "--slippage","$Slippage"
  )

  $args += @("--min-roll-median","$MinRollMedian")
  $args += @("--min-roll-p10","$MinRollP10")
  $args += @("--min-ic-ir","$MinIcIr")
  $args += @("--min-top-alpha-btc-net","$MinTopAlphaBtcNet")

  if ($Horizons.Count -gt 0) {
    $args += @("--horizons")
    $args += ($Horizons | ForEach-Object { "$_" })
  }
  if ($RollingDays.Count -gt 0) {
    $args += @("--rolling-days")
    $args += ($RollingDays | ForEach-Object { "$_" })
  }
  if (-not [string]::IsNullOrWhiteSpace($Exchange)) {
    $args += @("--exchange",$Exchange)
  }
  if (-not [string]::IsNullOrWhiteSpace($SymbolsYaml)) {
    $args += @("--symbols-yaml",$SymbolsYaml)
  }
  if ($Pairs.Count -gt 0) {
    $args += @("--pairs")
    $args += $Pairs
  }
  if (-not [string]::IsNullOrWhiteSpace($StrategyParams)) {
    $args += @("--strategy-params",$StrategyParams)
  }
  foreach ($v in $Vars) {
    $vv = [string]$v
    if (-not [string]::IsNullOrWhiteSpace($vv)) {
      $args += @("--var",$vv)
    }
  }
  if (-not [string]::IsNullOrWhiteSpace($OutDir)) {
    $args += @("--outdir",$OutDir)
  }
  if (-not [string]::IsNullOrWhiteSpace($RunId)) {
    $args += @("--run-id",$RunId)
  }
  if ($ExportSeries) {
    $args += @("--export-series")
  }

  & uv @args
  if ($LASTEXITCODE -ne 0) {
    throw "factor_audit.py 失败（timeframe=$tf2 exit=$LASTEXITCODE）"
  }
}

Write-Host ""
Write-Host "Done."
