<#
.SYNOPSIS
    更新市场仪表盘（下载数据 + 生成图表）

.DESCRIPTION
    先下载最新 K 线数据，再调用 dashboard.py 生成市场仪表盘 HTML。
    适合 Dry Run / Live 前的周期性监控。

.EXAMPLE
    .\update_dashboard.ps1 -Config "configs/config_moonshot.json" -Days 10
#>
[CmdletBinding()]
param(
  # 使用的配置文件：用于读取 exchange.pair_whitelist，并提供 download-data 的交易所配置
  [string]$Config = "configs/config_moonshot.json",

  # userdir（本仓库根目录默认就是 userdir）
  [string]$UserDir = ".",

  # 下载更新的 timeframe（必须包含仪表盘要用的 timeframe，例如 1h）
  [string[]]$Timeframes = @("1h"),

  # 仅刷新最近 N 天（实盘同步更新建议 3-30 天；历史已完整时无需再回填更早数据）
  [int]$Days = 10,

  # 现货/杠杆/合约
  [ValidateSet("spot", "margin", "futures")]
  [string]$TradingMode = "spot",

  # 仪表盘参数（会透传给 scripts/market_dashboard.py）
  [string]$TimeframeForDashboard = "1h",
  [string]$Resample = "1D",
  [int]$MinPairs = 1,
  [ValidateSet("rebalanced", "bh")]
  [string]$Benchmark = "rebalanced",
  [ValidateSet("pair", "global")]
  [string]$Anchor = "pair",
  [string]$HeatmapResample = "1W",

  # 输出文件
  [string]$Out = "plot/market_dashboard.html"
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

# 加载公共模块
$mcpCommon = Join-Path $PSScriptRoot "../lib/common.ps1"
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

# 统一 UTF-8，避免中文 Windows 默认 GBK 导致输出/解析异常
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "../..")).Path
Set-Location $repoRoot

$cfgPath = Resolve-Path $Config
$cfg = Get-Content -Path $cfgPath -Raw -Encoding UTF8 | ConvertFrom-Json

if (-not $cfg.exchange -or -not $cfg.exchange.pair_whitelist) {
  throw "配置文件缺少 exchange.pair_whitelist：$Config"
}

$pairs = @()
foreach ($p in $cfg.exchange.pair_whitelist) {
  if ([string]::IsNullOrWhiteSpace($p)) { continue }
  $pairs += [string]$p
}

if ($pairs.Count -eq 0) {
  throw "pair_whitelist 为空：$Config"
}

Write-Host ""
Write-Host "=== 1) 更新本地历史数据（增量） ==="
& "$PSScriptRoot/download.ps1" `
  -Pairs $pairs `
  -Timeframes $Timeframes `
  -Config $Config `
  -UserDir $UserDir `
  -Days $Days `
  -TradingMode $TradingMode `
  -DataFormatOhlcv "feather"

Write-Host ""
Write-Host "=== 2) 生成市场仪表盘（全历史 -> 最新） ==="

$argsList = @(
  "run",
  "python",
  "-X",
  "utf8",
  "scripts/market_dashboard.py",
  "--config", $Config,
  "--datadir", "data/okx",
  "--timeframe", $TimeframeForDashboard,
  "--resample", $Resample,
  "--min-pairs", "$MinPairs",
  "--benchmark", $Benchmark,
  "--anchor", $Anchor,
  "--heatmap-resample", $HeatmapResample,
  "--out", $Out
)

Write-Host ""
Write-Host "运行命令："
Write-Host ("uv " + ($argsList -join " "))
Write-Host ""

& uv @argsList

Write-Host ""
Write-Host "完成：$Out"
Write-Host "提示：你可以用 Windows 任务计划程序每 1h/4h/1d 调用本脚本，实现实盘周期同步更新。"
