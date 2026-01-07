[CmdletBinding()]
param(
  # 交易对（支持正则，例如 ".*/USDT"）
  [string[]]$Pairs = @("BTC/USDT"),

  # K线周期（建议至少包含训练/回测用到的周期）
  [string[]]$Timeframes = @("1h"),

  # 配置文件（仓库根目录默认就是 userdir）
  [string]$Config = "config.json",
  [string]$UserDir = ".",

  # 下载范围：二选一
  [int]$Days = 0,
  [string]$Timerange = "",

  # 现货/杠杆/合约
  [ValidateSet("spot", "margin", "futures")]
  [string]$TradingMode = "spot",

  # 回填更早数据：配合 -Timerange "YYYYMMDD-YYYYMMDD"
  [switch]$Prepend,

  # 危险：清空并重下（会删除已有数据）
  [switch]$Erase,

  # 其它可选参数
  [int]$NewPairsDays = 0,
  [switch]$IncludeInactivePairs,
  [switch]$NoParallelDownload,

  [ValidateSet("json", "jsongz", "feather", "parquet")]
  [string]$DataFormatOhlcv = "feather"
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

# 统一在 UTF-8 模式下运行，避免中文 Windows 默认 GBK 导致部分子命令读取文件时报 UnicodeDecodeError
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"

if ($Days -gt 0 -and -not [string]::IsNullOrWhiteSpace($Timerange)) {
  throw "参数冲突：-Days 与 -Timerange 只能二选一。"
}

if ($Erase) {
  Write-Host ""
  Write-Host "⚠️ 危险操作检测！"
  Write-Host "操作类型：清空并重下数据（--erase）"
  Write-Host "影响范围：当前 exchange/pairs/timeframes 对应的数据文件"
  Write-Host "风险评估：会删除本地历史数据，且需要重新下载（耗时/耗流量）"
  Write-Host ""
  $confirm = Read-Host "请确认是否继续？输入 '确认' 继续"
  if ($confirm -ne "确认") {
    throw "已取消。"
  }
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $repoRoot

$argsList = @(
  "run",
  "python",
  "-X",
  "utf8",
  "-m",
  "freqtrade",
  "download-data",
  "--userdir", $UserDir,
  "--config", $Config,
  "--trading-mode", $TradingMode,
  "--data-format-ohlcv", $DataFormatOhlcv
)

if ($Pairs.Count -gt 0) {
  $argsList += @("--pairs")
  $argsList += $Pairs
}

if ($Timeframes.Count -gt 0) {
  $argsList += @("--timeframes")
  $argsList += $Timeframes
}

if ($Days -gt 0) {
  $argsList += @("--days", "$Days")
}
elseif (-not [string]::IsNullOrWhiteSpace($Timerange)) {
  $argsList += @("--timerange", $Timerange)
}

if ($NewPairsDays -gt 0) {
  $argsList += @("--new-pairs-days", "$NewPairsDays")
}
if ($IncludeInactivePairs) {
  $argsList += @("--include-inactive-pairs")
}
if ($NoParallelDownload) {
  $argsList += @("--no-parallel-download")
}
if ($Prepend) {
  $argsList += @("--prepend")
}
if ($Erase) {
  $argsList += @("--erase")
}

Write-Host ""
Write-Host "运行命令："
Write-Host ("uv " + ($argsList -join " "))
Write-Host ""

& uv @argsList
