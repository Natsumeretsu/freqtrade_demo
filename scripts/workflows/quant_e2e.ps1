<#
.SYNOPSIS
  端到端一键编排（不造轮子版）：下载数据 → Qlib 转换/训练 → 因子体检 → 回测基准报告

.DESCRIPTION
  本脚本只做“编排/收口”，不实现任何新算法。
  统一入口的目的：
  - 让“数据下载 → 研究训练 → 体检审计 → 回测报告”变成一个可复现动作
  - 统一参数口径（pairs/timeframe/trading_mode/fee 等），避免每次手动拼命令导致漂移
  - 默认不执行任何危险操作（不会 erase / 不会改基准配置），产物写入 artifacts 与 backtest_results（gitignore）

  复用的既有脚本：
  - scripts/data/download.ps1
  - scripts/qlib/pipeline.ps1
  - scripts/qlib/factor_audit.ps1
  - scripts/analysis/small_account_benchmark.ps1

.EXAMPLE
  # 默认闭环：Qlib + 因子体检 + 基准回测（不下载数据）
  ./scripts/workflows/quant_e2e.ps1

  # 全量闭环：包含下载（建议先用 -WhatIf 看将执行的命令）
  ./scripts/workflows/quant_e2e.ps1 -All -Download -DownloadDays 120 -TradingMode "futures" -Pairs "BTC/USDT:USDT"

  # 指定研究/回测周期与策略（示例：15m 择时执行器）
  ./scripts/workflows/quant_e2e.ps1 -All -Download `
    -TradingMode "futures" `
    -Pairs "BTC/USDT:USDT" `
    -Timeframe "15m" `
    -DownloadDays 120 `
    -BacktestConfig "04_shared/configs/small_account/config_small_futures_timing_15m.json" `
    -Strategy "SmallAccountFuturesTimingExecV1" `
    -BacktestTimerange "20251215-20260114"
#>
[CmdletBinding(SupportsShouldProcess = $true)]
param(
  # === 执行步骤 ===
  [switch]$All,
  [switch]$Download,
  [switch]$Qlib,
  [switch]$Audit,
  [switch]$Benchmark,

  # === 通用参数（尽量统一口径）===
  [string[]]$Pairs = @(),
  [string]$Timeframe = "4h",

  [ValidateSet("spot", "margin", "futures")]
  [string]$TradingMode = "spot",

  # 费用口径：factor_audit 与 backtest 统一使用同一个 fee（避免“研究/执行口径漂移”）
  [double]$Fee = 0.0006,

  # === 下载数据（scripts/data/download.ps1）===
  [string[]]$DownloadTimeframes = @(),
  [int]$DownloadDays = 0,
  [string]$DownloadTimerange = "",
  [string]$DownloadConfig = "01_freqtrade/config.json",
  [string]$UserDir = "./01_freqtrade",

  # 危险：清空并重下（会触发 scripts/data/download.ps1 内的二次确认）
  [switch]$DownloadErase,
  [switch]$DownloadPrepend,

  # === Qlib 流水线（scripts/qlib/pipeline.ps1）===
  [string]$Exchange = "",
  [string]$SymbolsYaml = "",
  [string]$ModelVersion = "",
  [string]$FeatureSet = "",
  [switch]$SkipConvert,

  # === 因子体检（scripts/qlib/factor_audit.ps1）===
  [string]$AuditFeatureSet = "ml_core",
  [string[]]$AuditTimeframes = @(),
  [int[]]$AuditRollingDays = @(30, 60),
  [double]$AuditSlippage = 0.0,

  # === 回测基准（scripts/analysis/small_account_benchmark.ps1）===
  [string]$BacktestConfig = "04_shared/configs/small_account/config_small_spot_base.json",
  [string]$Strategy = "SmallAccountSpotTrendFilteredV1",
  [string]$BacktestTimerange = "20250101-20251231",
  [string[]]$BenchmarkTimeranges = @(),
  [double]$DryRunWallet = 10,
  [int]$MaxOpenTrades = 1,
  [double]$StakeAmount = -1,
  [double]$TradableBalanceRatio = -1,
  [string]$BenchmarkOutDir = "artifacts/benchmarks",
  [string]$RunId = ""
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Test-Command {
  param([Parameter(Mandatory = $true)][string]$Name)
  return [bool](Get-Command $Name -ErrorAction SilentlyContinue)
}

# 优先复用 common.ps1 的 Test-Command/路径工具（若存在）
$common = Join-Path $PSScriptRoot "../lib/common.ps1"
if (Test-Path $common) {
  . $common
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

# 统一在 UTF-8 模式下运行（避免中文 Windows 默认编码导致子命令读文件失败）
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "../..")).Path
Set-Location $repoRoot

# 确保 Python 可导入 03_integration/trading_system（用于读取 pairs 默认值）
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

function Resolve-Pairs {
  if ($Pairs.Count -gt 0) { return $Pairs }

  if (-not [string]::IsNullOrWhiteSpace($SymbolsYaml)) {
    try {
      $symPath = (Resolve-Path $SymbolsYaml).Path
      $pairsJson = & uv run python -X utf8 -c "import json, yaml; p=yaml.safe_load(open(r'$symPath', encoding='utf-8')) or {}; print(json.dumps(p.get('pairs', []), ensure_ascii=False))"
      return @((ConvertFrom-Json -InputObject $pairsJson) | ForEach-Object { [string]$_ })
    } catch {
      throw "无法从 -SymbolsYaml 读取 pairs：$SymbolsYaml"
    }
  }

  try {
    $pairsJson = & uv run python -X utf8 -c "import json; from trading_system.infrastructure.config_loader import get_config; print(json.dumps(get_config().pairs(), ensure_ascii=False))"
    $resolved = @((ConvertFrom-Json -InputObject $pairsJson) | ForEach-Object { [string]$_ })
    return $resolved
  } catch {
    return @()
  }
}

$hasExplicitStep =
  $PSBoundParameters.ContainsKey("All") -or
  $PSBoundParameters.ContainsKey("Download") -or
  $PSBoundParameters.ContainsKey("Qlib") -or
  $PSBoundParameters.ContainsKey("Audit") -or
  $PSBoundParameters.ContainsKey("Benchmark")

$runDownload = $Download
$runQlib = $All -or $Qlib
$runAudit = $All -or $Audit
$runBenchmark = $All -or $Benchmark

if (-not $hasExplicitStep) {
  # 默认闭环：研究/体检/回测（不默认下载，避免误触发大规模网络操作）
  $runQlib = $true
  $runAudit = $true
  $runBenchmark = $true
}

Write-Host ""
Write-Host "=== 端到端编排参数（统一口径）==="
Write-Host "- steps: download=$runDownload qlib=$runQlib audit=$runAudit benchmark=$runBenchmark"
Write-Host "- trading_mode: $TradingMode"
Write-Host "- timeframe: $Timeframe"
Write-Host "- fee: $Fee"

$resolvedPairs = Resolve-Pairs
if ($resolvedPairs.Count -gt 0) {
  Write-Host "- pairs: $($resolvedPairs -join ', ')"
} else {
  Write-Host "- pairs: (未解析到，将依赖各子脚本自身默认/配置)"
}

if ($runDownload) {
  if (($DownloadDays -le 0) -and [string]::IsNullOrWhiteSpace($DownloadTimerange)) {
    throw "下载数据需要指定 -DownloadDays 或 -DownloadTimerange。"
  }

  $downloadScript = Join-Path $repoRoot "scripts/data/download.ps1"
  if (-not (Test-Path $downloadScript)) {
    throw "未找到脚本：$downloadScript"
  }

  $tfs = if ($DownloadTimeframes.Count -gt 0) { $DownloadTimeframes } else { @($Timeframe) }

  $dlMode = if ($TradingMode -eq "futures") { "futures" } else { "spot" }
  $dlParams = @{
    Timeframes = $tfs
    TradingMode = $dlMode
    Config = $DownloadConfig
    UserDir = $UserDir
  }
  if ($resolvedPairs.Count -gt 0) {
    $dlParams.Pairs = $resolvedPairs
  }
  if ($DownloadDays -gt 0) { $dlParams.Days = $DownloadDays }
  if (-not [string]::IsNullOrWhiteSpace($DownloadTimerange)) { $dlParams.Timerange = $DownloadTimerange }
  if ($DownloadPrepend) { $dlParams.Prepend = $true }
  if ($DownloadErase) { $dlParams.Erase = $true }

  Write-Host ""
  Write-Host "=== 0) 下载历史数据 ==="
  Write-Host "- timeframes: $($tfs -join ', ')"
  if ($PSCmdlet.ShouldProcess("download data", "scripts/data/download.ps1")) {
    & $downloadScript @dlParams
  }
}

if ($runQlib) {
  $qlibScript = Join-Path $repoRoot "scripts/qlib/pipeline.ps1"
  if (-not (Test-Path $qlibScript)) {
    throw "未找到脚本：$qlibScript"
  }

  $qlibParams = @{
    Timeframe = $Timeframe
    Exchange = $Exchange
    SymbolsYaml = $SymbolsYaml
    ModelVersion = $ModelVersion
    FeatureSet = $FeatureSet
  }
  if ($resolvedPairs.Count -gt 0) {
    $qlibParams.Pairs = $resolvedPairs
  }
  if ($SkipConvert) {
    $qlibParams.SkipConvert = $true
  }

  Write-Host ""
  Write-Host "=== 1) Qlib 转换 + 训练（研究层闭环）==="
  if ($PSCmdlet.ShouldProcess("qlib pipeline", "scripts/qlib/pipeline.ps1")) {
    & $qlibScript @qlibParams
  }
}

if ($runAudit) {
  $auditScript = Join-Path $repoRoot "scripts/qlib/factor_audit.ps1"
  if (-not (Test-Path $auditScript)) {
    throw "未找到脚本：$auditScript"
  }

  $auditTfs = if ($AuditTimeframes.Count -gt 0) { $AuditTimeframes } else { @($Timeframe) }

  $auditParams = @{
    Timeframes = $auditTfs
    Exchange = $Exchange
    SymbolsYaml = $SymbolsYaml
    FeatureSet = $AuditFeatureSet
    Fee = $Fee
    Slippage = $AuditSlippage
    RollingDays = $AuditRollingDays
  }
  if ($resolvedPairs.Count -gt 0) {
    $auditParams.Pairs = $resolvedPairs
  }

  Write-Host ""
  Write-Host "=== 2) 因子体检（研究口径自检）==="
  Write-Host "- timeframes: $($auditTfs -join ', ')"
  if ($PSCmdlet.ShouldProcess("factor audit", "scripts/qlib/factor_audit.ps1")) {
    & $auditScript @auditParams
  }
}

if ($runBenchmark) {
  $benchScript = Join-Path $repoRoot "scripts/analysis/small_account_benchmark.ps1"
  if (-not (Test-Path $benchScript)) {
    throw "未找到脚本：$benchScript"
  }
  if (-not (Test-Path $BacktestConfig)) {
    throw "未找到回测配置文件：$BacktestConfig"
  }

  $benchTrs = if ($BenchmarkTimeranges.Count -gt 0) { $BenchmarkTimeranges } else { @($BacktestTimerange) }

  # small_account_* 脚本仅支持 spot/futures（margin 按 spot 处理）
  $btMode = if ($TradingMode -eq "futures") { "futures" } else { "spot" }

  $benchParams = @{
    Config = $BacktestConfig
    Strategy = $Strategy
    Timeframe = $Timeframe
    TradingMode = $btMode
    Timeranges = $benchTrs
    DryRunWallet = $DryRunWallet
    MaxOpenTrades = $MaxOpenTrades
    Fee = $Fee
    OutDir = $BenchmarkOutDir
    RunId = $RunId
  }
  if ($resolvedPairs.Count -gt 0) {
    $benchParams.Pairs = $resolvedPairs
  }
  if ($StakeAmount -gt 0) {
    $benchParams.StakeAmount = $StakeAmount
  }
  if ($TradableBalanceRatio -gt 0) {
    $benchParams.TradableBalanceRatio = $TradableBalanceRatio
  }

  Write-Host ""
  Write-Host "=== 3) 回测基准（稳定性报告）==="
  Write-Host "- timeranges: $($benchTrs -join ', ')"
  if ($PSCmdlet.ShouldProcess("benchmark backtest", "scripts/analysis/small_account_benchmark.ps1")) {
    & $benchScript @benchParams
  }
}

Write-Host ""
Write-Host "=== Done ==="
Write-Host "提示："
Write-Host "- 如需先看将执行的命令：加 -WhatIf"
Write-Host "- Qlib 入口与口径说明：docs/knowledge/freqtrade_qlib_engineering_workflow.md"
Write-Host "- 全栈生态补充指南：docs/reports/quant_trading_full_stack_guide_2026-01-15_v1.0.md"

