<#
.SYNOPSIS
  小资金（10 USDT）跨年份稳定性基准回测

.DESCRIPTION
  针对同一套策略与配置，在多个 timerange 上重复回测，并汇总关键指标到 CSV/Markdown：
  - 每个窗口都要看：收益、回撤、交易次数
  - 汇总更关注“最差窗口”，避免单窗口爆炸式乐观

  注意：
  - 本脚本的目标是“可验证、可迭代”，不承诺任何实盘收益。
  - 回测结果体积较大，默认写入 01_freqtrade/backtest_results/（已在 .gitignore 忽略）。

.EXAMPLE
  ./scripts/analysis/small_account_benchmark.ps1 -Strategy "SimpleTrendFollowV6" -Pairs "BTC/USDT"

  ./scripts/analysis/small_account_benchmark.ps1 `
    -Strategy "SmallAccountTrendHybridV1" `
    -Pairs @("BTC/USDT","ETH/USDT") `
    -Timeframe "4h" `
    -Timeranges @("20230101-20231231","20240101-20241231","20250101-20251231")
#>
[CmdletBinding()]
param(
  [string]$Config = "04_shared/configs/small_account/config_small_spot_base.json",
  [string]$Strategy = "SmallAccountTrendFilteredV1",
  [string[]]$Pairs = @("BTC/USDT"),
  [string]$Timeframe = "4h",
  [string[]]$Timeranges = @("20230101-20231231", "20240101-20241231", "20250101-20251231"),

  # 以 config 内 trading_mode 为准；这里仅作为默认值/兜底
  [ValidateSet("spot", "futures")]
  [string]$TradingMode = "spot",

  [double]$DryRunWallet = 10,
  [int]$MaxOpenTrades = 1,
  [double]$Fee = 0.0006,
  [double]$StakeAmount = -1,
  [double]$TradableBalanceRatio = -1,

  # 稳定性门槛（可按策略类型调整）
  [int]$MinTradesPerWindow = 5,
  [double]$MinProfitPctPerWindow = 0.0,
  [double]$MaxDrawdownPct = 20.0,

  [switch]$StressTest,
  [int]$StressSimulations = 2000,
  [double]$StressSlippage = 0.0,

  [string]$OutDir = "artifacts/benchmarks",
  [string]$RunId = ""
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

# 统一在 UTF-8 模式下运行（避免中文 Windows 默认编码导致子命令读文件失败）
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "../..")).Path
Set-Location $repoRoot

if (-not (Test-Path $Config)) {
  throw "未找到配置文件：$Config"
}

$safeStrategy = ($Strategy -replace "[^0-9A-Za-z._-]", "_")
$safeTf = ($Timeframe -replace "[^0-9A-Za-z._-]", "_")
$ts = Get-Date -Format "yyyy-MM-dd_HH-mm-ss"
$benchName = if ([string]::IsNullOrWhiteSpace($RunId)) { "bench_small10_${safeStrategy}_${safeTf}_${ts}" } else { $RunId }
$benchDir = Join-Path $OutDir $benchName
New-Item -ItemType Directory -Force -Path $benchDir | Out-Null

$backtestScript = Join-Path $repoRoot "scripts/analysis/small_account_backtest.ps1"
if (-not (Test-Path $backtestScript)) {
  throw "未找到脚本：$backtestScript"
}

$metricsScript = Join-Path $repoRoot "scripts/analysis/backtest_metrics.py"
if (-not (Test-Path $metricsScript)) {
  throw "未找到脚本：$metricsScript"
}

function Resolve-LatestBacktestZip {
  param([string]$PreferredDir)

  $lastFile = Join-Path $PreferredDir ".last_result.json"
  if (Test-Path $lastFile) {
    $last = Get-Content -Raw -Encoding UTF8 $lastFile | ConvertFrom-Json
    $name = [string]$last.latest_backtest
    if (-not [string]::IsNullOrWhiteSpace($name)) {
      $p = Join-Path $PreferredDir $name
      if (Test-Path $p) {
        return (Resolve-Path $p).Path
      }
    }
  }

  $fallbackLast = Join-Path "01_freqtrade/backtest_results" ".last_result.json"
  if (Test-Path $fallbackLast) {
    $last = Get-Content -Raw -Encoding UTF8 $fallbackLast | ConvertFrom-Json
    $name = [string]$last.latest_backtest
    if (-not [string]::IsNullOrWhiteSpace($name)) {
      $p = Join-Path "01_freqtrade/backtest_results" $name
      if (Test-Path $p) {
        return (Resolve-Path $p).Path
      }
    }
  }

  $latest = Get-ChildItem -Path $PreferredDir -Filter "*.zip" -File -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 1
  if ($latest) {
    return $latest.FullName
  }

  throw "无法定位回测输出 zip（请检查 01_freqtrade/backtest_results/ 目录）。"
}

Write-Host ""
Write-Host "=== 小资金基准回测（稳定性评估）==="
Write-Host "- config: $Config"
Write-Host "- strategy: $Strategy"
Write-Host "- timeframe: $Timeframe"
Write-Host "- pairs: $($Pairs -join ', ')"
Write-Host "- timeranges: $($Timeranges -join ', ')"
Write-Host "- output: $benchDir"

$rows = @()

foreach ($tr in $Timeranges) {
  $safeTr = ($tr -replace "[^0-9A-Za-z._-]", "_")
  $caseId = "case_${safeTr}"
  $btRunId = "${benchName}_${caseId}"

  Write-Host ""
  Write-Host "=== 基准窗口：$tr ==="

  # 说明：数组 splatting 仅用于“位置参数”；这里用 Hashtable splatting 传命名参数，避免参数错位
  $btParams = @{
    Config = $Config
    Strategy = $Strategy
    Pairs = $Pairs
    Timeframe = $Timeframe
    Timerange = $tr
    TradingMode = $TradingMode
    DryRunWallet = $DryRunWallet
    MaxOpenTrades = $MaxOpenTrades
    Fee = $Fee
    RunId = $btRunId
  }

  if ($TradableBalanceRatio -gt 0) {
    $btParams.TradableBalanceRatio = $TradableBalanceRatio
  }
  if ($StakeAmount -gt 0) {
    $btParams.StakeAmount = $StakeAmount
  }
  if ($StressTest) {
    $btParams.StressTest = $true
    $btParams.StressSimulations = $StressSimulations
    $btParams.StressSlippage = $StressSlippage
  }

  & $backtestScript @btParams
  if ($LASTEXITCODE -ne 0) {
    throw "窗口回测失败（timerange=$tr, exit=$LASTEXITCODE）"
  }

  $runDir = Join-Path "01_freqtrade/backtest_results" $btRunId
  $zipPath = Resolve-LatestBacktestZip -PreferredDir $runDir

  $metricsJson = & uv run python -X utf8 $metricsScript --zip $zipPath --strategy $Strategy
  if ($LASTEXITCODE -ne 0) {
    throw "指标提取失败（timerange=$tr, exit=$LASTEXITCODE）"
  }

  $m = $metricsJson | ConvertFrom-Json
  $profitPct = [double]$m.profit_total_pct
  $mddPct = [double]$m.max_relative_drawdown_pct
  $trades = [int]$m.total_trades

  $passProfit = ($profitPct -gt $MinProfitPctPerWindow)
  $passMdd = ($mddPct -le $MaxDrawdownPct)
  $passTrades = ($trades -ge $MinTradesPerWindow)
  $passAll = ($passProfit -and $passMdd -and $passTrades)

  $rows += [PSCustomObject]@{
    timerange = $tr
    strategy = $m.strategy
    timeframe = $m.timeframe
    pairs = ($Pairs -join ",")
    total_trades = $trades
    profit_total_pct = [math]::Round($profitPct, 4)
    profit_total_abs = [math]::Round([double]$m.profit_total_abs, 8)
    max_drawdown_pct = [math]::Round($mddPct, 4)
    sharpe = [math]::Round([double]$m.sharpe, 4)
    sortino = [math]::Round([double]$m.sortino, 4)
    calmar = [math]::Round([double]$m.calmar, 4)
    profit_factor = [math]::Round([double]$m.profit_factor, 4)
    winrate_pct = [math]::Round([double]$m.winrate_pct, 2)
    market_change_pct = [math]::Round([double]$m.market_change_pct, 4)
    pass_profit = $passProfit
    pass_drawdown = $passMdd
    pass_trades = $passTrades
    pass = $passAll
    zip = $zipPath
  }
}

$csvPath = Join-Path $benchDir "summary.csv"
$rows | Export-Csv -NoTypeInformation -Encoding UTF8 -Path $csvPath

$worstProfit = ($rows | Measure-Object profit_total_pct -Minimum).Minimum
$bestProfit = ($rows | Measure-Object profit_total_pct -Maximum).Maximum
$avgProfit = ($rows | Measure-Object profit_total_pct -Average).Average
$maxMdd = ($rows | Measure-Object max_drawdown_pct -Maximum).Maximum
$minTrades = ($rows | Measure-Object total_trades -Minimum).Minimum
$failed = @($rows | Where-Object { -not $_.pass })
$allPass = ($failed.Count -eq 0)

$mdPath = Join-Path $benchDir "summary.md"
$lines = @()
$lines += "# 小资金基准回测汇总"
$lines += ""
$lines += "- 运行: $benchName"
$lines += "- 策略: $Strategy"
$lines += "- timeframe: $Timeframe"
$lines += "- pairs: $($Pairs -join ', ')"
$lines += "- timeranges: $($Timeranges -join ', ')"
$lines += ""
$lines += "## 门槛"
$lines += ""
$lines += "- 每窗口最少交易数: $MinTradesPerWindow"
$lines += "- 每窗口最低收益(%): > $MinProfitPctPerWindow"
$lines += "- 最大回撤上限(%): <= $MaxDrawdownPct"
$lines += ""
$lines += "## 汇总"
$lines += ""
$lines += "- 结论: " + $(if ($allPass) { "PASS（各窗口均达标）" } else { "FAIL（存在未达标窗口）" })
$lines += "- 最差窗口收益(%): $([math]::Round($worstProfit, 4))"
$lines += "- 最佳窗口收益(%): $([math]::Round($bestProfit, 4))"
$lines += "- 平均收益(%): $([math]::Round($avgProfit, 4))"
$lines += "- 最大回撤(%): $([math]::Round($maxMdd, 4))"
$lines += "- 最少交易数: $minTrades"
$lines += ""
$lines += "## 明细"
$lines += ""
$lines += "详见同目录 CSV：summary.csv"
$lines | Set-Content -Encoding UTF8 -Path $mdPath

Write-Host ""
Write-Host "=== 完成 ==="
Write-Host "- CSV: $csvPath"
Write-Host "- MD : $mdPath"
Write-Host "- PASS: $allPass"
