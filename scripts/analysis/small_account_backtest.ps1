<#
.SYNOPSIS
    小资金（10 USDT）回测一键脚本

.DESCRIPTION
    目标：把“能否在小资金约束下跑通回测”变成一个可重复的动作。

    这个脚本会：
    1) 自动计算/校验 stake_amount，避免常见硬错误：
       - 可用余额（dry_run_wallet * tradable_balance_ratio） < stake_amount * max_open_trades
    2) 统一封装 backtesting 参数（export/caching/output 目录）
    3) 可选生成：
       - 逐交易对报表（pair_report.py）
       - 压力测试（stress_test.py）

.EXAMPLE
    ./scripts/analysis/small_account_backtest.ps1

    ./scripts/analysis/small_account_backtest.ps1 `
      -Strategy "SmallAccountTrendFilteredV1" `
      -Pairs "BTC/USDT" `
      -Timerange "20250101-20251231" `
      -PairReport `
      -StressTest
#>
[CmdletBinding()]
param(
  [string]$Config = "configs/small_account/config_small_spot_base.json",
  [string]$Strategy = "SmallAccountTrendFilteredV1",
  [string[]]$Pairs = @("BTC/USDT"),
  [string]$Timeframe = "4h",
  [string]$Timerange = "20250101-20251231",

  # 交易模式最终以 config 内的 trading_mode 为准（backtesting 子命令不支持 --trading-mode 参数）
  [ValidateSet("spot", "futures")]
  [string]$TradingMode = "spot",

  [double]$DryRunWallet = 10,
  [int]$MaxOpenTrades = 1,
  [double]$Fee = 0.0006,

  # 资金约束：默认从 config 读取；读取失败则回退到 0.95
  [double]$TradableBalanceRatio = -1,

  # stake_amount：默认自动计算（比理论上限略小，避免浮点误差）
  # - 不传则不覆盖 config 的 stake_amount（推荐用 unlimited 让仓位随资金变化）
  # - 传入正数则强制覆盖（可能更贴近“固定下单金额”的假设，但要注意小资金会在亏损后出现“余额不足无法再开仓”）
  [double]$StakeAmount = -1,

  # 输出目录（位于 backtest_results/ 下）
  [string]$RunId = "",

  [switch]$PairReport,
  [switch]$StressTest,

  [int]$StressSimulations = 5000,
  [double]$StressSlippage = 0.0
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

# 加载公共模块（复用 Test-Command 等）
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

# 统一在 UTF-8 模式下运行（避免中文 Windows 默认编码导致子命令读文件失败）
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "../..")).Path
Set-Location $repoRoot

if (-not (Test-Path $Config)) {
  throw "未找到配置文件：$Config"
}

Write-Host ""
Write-Host "=== 小资金回测参数 ==="
Write-Host "- config: $Config"
Write-Host "- strategy: $Strategy"
Write-Host "- trading_mode: $TradingMode"
Write-Host "- timeframe: $Timeframe"
Write-Host "- timerange: $Timerange"
Write-Host "- pairs: $($Pairs -join ', ')"
Write-Host "- dry_run_wallet: $DryRunWallet"
Write-Host "- max_open_trades: $MaxOpenTrades"
Write-Host "- fee: $Fee"

# 读取配置（用于拿 exchange.name 和 tradable_balance_ratio 默认值）
$cfg = Get-Content -Raw -Encoding UTF8 $Config | ConvertFrom-Json
$exchangeName = ""
try {
  $exchangeName = [string]$cfg.exchange.name
} catch {
  $exchangeName = ""
}

try {
  $cfgMode = [string]$cfg.trading_mode
  if (-not [string]::IsNullOrWhiteSpace($cfgMode)) {
    $TradingMode = $cfgMode
  }
} catch {
  # ignore
}

if ($TradableBalanceRatio -le 0) {
  try {
    $TradableBalanceRatio = [double]$cfg.tradable_balance_ratio
  } catch {
    $TradableBalanceRatio = 0.95
  }
}

if ($MaxOpenTrades -le 0) {
  throw "max_open_trades 必须为正整数"
}
if ($DryRunWallet -le 0) {
  throw "dry_run_wallet 必须为正数"
}
if ($TradableBalanceRatio -le 0 -or $TradableBalanceRatio -gt 1) {
  throw "tradable_balance_ratio 必须在 (0, 1] 区间内"
}

$maxTradable = [double]($DryRunWallet * $TradableBalanceRatio)

if ($StakeAmount -gt 0) {
  $stakeTotal = [double]($StakeAmount * $MaxOpenTrades)
  if ($stakeTotal -gt ($maxTradable + 1e-8)) {
    throw ("资金约束不满足：stake_amount*max_open_trades={0} > dry_run_wallet*tradable_balance_ratio={1}。" -f $stakeTotal, $maxTradable)
  }
}

Write-Host "- tradable_balance_ratio: $TradableBalanceRatio"
if ($StakeAmount -gt 0) {
  Write-Host "- stake_amount(override): $StakeAmount"
} else {
  Write-Host "- stake_amount(override): (未覆盖，使用 config 内配置)"
}

# 输出目录：必须先创建，否则 Freqtrade 可能回退到默认 backtest_results/
$ts = Get-Date -Format "yyyy-MM-dd_HH-mm-ss"
$safeStrategy = ($Strategy -replace "[^0-9A-Za-z._-]", "_")
$runName = if ([string]::IsNullOrWhiteSpace($RunId)) { "small10_${TradingMode}_${safeStrategy}_${Timeframe}_${ts}" } else { $RunId }
$runDir = Join-Path "backtest_results" $runName
New-Item -ItemType Directory -Force -Path $runDir | Out-Null

# 若需要覆盖 tradable_balance_ratio，则在本次 runDir 内生成临时 config，避免污染基准配置文件
$configToUse = $Config
if ($PSBoundParameters.ContainsKey('TradableBalanceRatio') -and $TradableBalanceRatio -gt 0) {
  try {
    $cfg.tradable_balance_ratio = [double]$TradableBalanceRatio
    $overrideCfgPath = Join-Path $runDir "config_override.json"
    $cfg | ConvertTo-Json -Depth 100 | Set-Content -Encoding UTF8 -Path $overrideCfgPath
    $configToUse = $overrideCfgPath
  } catch {
    throw "生成 config_override.json 失败：$($_.Exception.Message)"
  }
}

$ftScript = Join-Path $repoRoot "scripts/ft.ps1"
if (-not (Test-Path $ftScript)) {
  throw "未找到脚本：$ftScript"
}

$ftArgs = @(
  "backtesting",
  "--config", $configToUse,
  "--strategy", $Strategy,
  "--timeframe", $Timeframe,
  "--timerange", $Timerange,
  "--dry-run-wallet", "$DryRunWallet",
  "--max-open-trades", "$MaxOpenTrades",
  "--fee", "$Fee",
  "--export", "trades",
  "--cache", "none",
  "--backtest-directory", $runDir
)

if ($StakeAmount -gt 0) {
  $ftArgs += @("--stake-amount", "$StakeAmount")
}

if ($Pairs.Count -gt 0) {
  $ftArgs += @("--pairs")
  $ftArgs += $Pairs
}

Write-Host ""
Write-Host "=== 运行回测 ==="
& $ftScript @ftArgs
if ($LASTEXITCODE -ne 0) {
  throw "回测失败（exit=$LASTEXITCODE）。请检查上方日志输出。"
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

  # 兜底：如果 .last_result.json 不在 runDir，则去 backtest_results 根目录找
  $fallbackLast = Join-Path "backtest_results" ".last_result.json"
  if (Test-Path $fallbackLast) {
    $last = Get-Content -Raw -Encoding UTF8 $fallbackLast | ConvertFrom-Json
    $name = [string]$last.latest_backtest
    if (-not [string]::IsNullOrWhiteSpace($name)) {
      $p = Join-Path "backtest_results" $name
      if (Test-Path $p) {
        return (Resolve-Path $p).Path
      }
    }
  }

  # 最后兜底：按时间找最新 zip
  $latest = Get-ChildItem -Path $PreferredDir -Filter "*.zip" -File -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 1
  if ($latest) {
    return $latest.FullName
  }

  throw "无法定位回测输出 zip（请检查 backtest_results/ 目录）。"
}

$zipPath = Resolve-LatestBacktestZip -PreferredDir $runDir
Write-Host ""
Write-Host "回测输出：$zipPath"

if ($PairReport) {
  if ([string]::IsNullOrWhiteSpace($exchangeName)) {
    Write-Host "跳过逐交易对报表：无法从 config 解析 exchange.name"
  } else {
    $datadir = ("data/{0}" -f $exchangeName)
    Write-Host ""
    Write-Host "=== 逐交易对报表 ==="
    uv run python -X utf8 "scripts/analysis/pair_report.py" --zip $zipPath --datadir $datadir --timeframe $Timeframe --trading-mode $TradingMode
    if ($LASTEXITCODE -ne 0) {
      throw "逐交易对报表生成失败（exit=$LASTEXITCODE）。"
    }
  }
}

if ($StressTest) {
  Write-Host ""
  Write-Host "=== 压力测试（蒙特卡洛）==="
  uv run python -X utf8 "scripts/analysis/stress_test.py" --zip $zipPath --simulations $StressSimulations --slippage $StressSlippage
  if ($LASTEXITCODE -ne 0) {
    throw "压力测试失败（exit=$LASTEXITCODE）。"
  }
}
