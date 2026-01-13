<#
.SYNOPSIS
  小范围参数邻域 + 多损失函数搜索（输出候选集与帕累托前沿）

.DESCRIPTION
  - 面向 SmallAccountTrendFilteredV1 这类以参数 JSON 为权威口径的策略：
    通过临时改写 01_freqtrade/strategies/<Strategy>.json，重复运行回测，抽取关键指标，
    生成候选点集（收益-回撤-交易数）并计算帕累托非支配集合。

  - 这是轻量邻域搜索，不是完整 hyperopt：
    1) 搜索空间小（围绕当前参数的邻域）
    2) 通过多种损失函数（不同权重）挑选 Top-N 候选
    3) 通过帕累托支配关系判断是否存在无损改进

.EXAMPLE
  ./scripts/analysis/pareto_neighborhood_search.ps1 `
    -Timerange "20200101-20251231" `
    -Trials 30 `
    -Seed 42
#>
[CmdletBinding()]
param(
  [string]$Strategy = "SmallAccountTrendFilteredV1",
  [string]$Config = "04_shared/configs/small_account/config_small_spot_base.json",
  [string[]]$Pairs = @("BTC/USDT"),
  [string]$Timeframe = "4h",
  [string]$Timerange = "20200101-20251231",

  [double]$DryRunWallet = 10,
  [int]$MaxOpenTrades = 1,
  [double]$Fee = 0.0006,

  [int]$Trials = 30,
  [int]$Seed = 42,
  [int]$MinTrades = 20,

  [string]$OutDir = "artifacts/pareto_search",
  [int]$TopK = 12
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

$paramFile = Join-Path "01_freqtrade/strategies" ("{0}.json" -f $Strategy)
if (-not (Test-Path $paramFile)) {
  throw "未找到策略参数文件：$paramFile"
}

$backtestScript = Join-Path $repoRoot "scripts/analysis/small_account_backtest.ps1"
if (-not (Test-Path $backtestScript)) {
  throw "未找到脚本：$backtestScript"
}

$metricsScript = Join-Path $repoRoot "scripts/analysis/backtest_metrics.py"
if (-not (Test-Path $metricsScript)) {
  throw "未找到脚本：$metricsScript"
}

function Write-Utf8NoBom {
  param(
    [Parameter(Mandatory = $true)][string]$Path,
    [Parameter(Mandatory = $true)][string]$Content
  )

  $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
  [System.IO.File]::WriteAllText($Path, $Content, $utf8NoBom)
}

function Clone-JsonObject {
  param([object]$Obj)
  return ($Obj | ConvertTo-Json -Depth 100 | ConvertFrom-Json)
}

function Resolve-LatestBacktestZip {
  param([string]$RunId)

  $runDir = Join-Path "01_freqtrade/backtest_results" $RunId
  $lastFile = Join-Path $runDir ".last_result.json"
  if (Test-Path $lastFile) {
    $last = Get-Content -Raw -Encoding UTF8 $lastFile | ConvertFrom-Json
    $name = [string]$last.latest_backtest
    if (-not [string]::IsNullOrWhiteSpace($name)) {
      $p = Join-Path $runDir $name
      if (Test-Path $p) {
        return (Resolve-Path $p).Path
      }
    }
  }

  $latest = Get-ChildItem -Path $runDir -Filter "*.zip" -File -ErrorAction SilentlyContinue |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1
  if ($latest) {
    return $latest.FullName
  }

  throw "无法定位回测输出 zip（RunId=$RunId）"
}

function Compute-Losses {
  param(
    [double]$ProfitPct,
    [double]$MaxDdPct,
    [int]$Trades,
    [int]$MinTrades
  )

  # 统一约束：避免 0 交易/超低交易 的假前沿点
  $tradePenalty = 0.0
  if ($Trades -lt $MinTrades) {
    $tradePenalty = [double](($MinTrades - $Trades) * 10.0)
  }

  # 超过 20% 回撤的惩罚（可按需调权重）
  $ddPenalty = 0.0
  if ($MaxDdPct -gt 20.0) {
    $ddPenalty = [double](($MaxDdPct - 20.0) * 5.0)
  }

  # 多损失函数：同一批候选点用不同偏好排序挑选 TopK
  $lossProfitFirst = (-1.0 * $ProfitPct) + $ddPenalty + $tradePenalty
  $lossDdFirst = ($MaxDdPct) - (0.25 * $ProfitPct) + $tradePenalty
  $lossBalanced = ($MaxDdPct) - (0.40 * $ProfitPct) + $ddPenalty + $tradePenalty

  return @{
    loss_profit_first = $lossProfitFirst
    loss_dd_first = $lossDdFirst
    loss_balanced = $lossBalanced
  }
}

function Is-Dominated {
  param(
    [object]$A,
    [object]$B
  )

  $bBetterOrEqualProfit = ([double]$B.profit_total_pct -ge [double]$A.profit_total_pct)
  $bBetterOrEqualTrades = ([int]$B.total_trades -ge [int]$A.total_trades)
  $bBetterOrEqualDd = ([double]$B.max_drawdown_pct -le [double]$A.max_drawdown_pct)

  if (-not ($bBetterOrEqualProfit -and $bBetterOrEqualTrades -and $bBetterOrEqualDd)) {
    return $false
  }

  $bStrict =
    ([double]$B.profit_total_pct -gt [double]$A.profit_total_pct) -or
    ([int]$B.total_trades -gt [int]$A.total_trades) -or
    ([double]$B.max_drawdown_pct -lt [double]$A.max_drawdown_pct)

  return $bStrict
}

$ts = Get-Date -Format "yyyy-MM-dd_HH-mm-ss"
$runRoot = Join-Path $OutDir ("pareto_{0}_{1}_{2}" -f $Strategy, $Timeframe, $ts)
New-Item -ItemType Directory -Force -Path $runRoot | Out-Null

$origJson = Get-Content -Raw -Encoding UTF8 $paramFile
$baseObj = $origJson | ConvertFrom-Json

if ($null -eq $baseObj.params -or $null -eq $baseObj.params.buy -or $null -eq $baseObj.params.sell) {
  throw "参数文件结构异常（缺少 params.buy / params.sell）：$paramFile"
}

# 邻域空间：围绕当前参数做小范围扰动（包含当前值）
$space = @{
  buy_ema_short_len = @(15, 20, 25)
  buy_ema_long_len = @(140, 160, 180)
  buy_adx = @(16, 20, 24)
  buy_ema_slope_lookback = @(4, 6, 8)
  buy_ema_long_min_slope = @(0.0, 0.005, 0.010)
  buy_max_ema_short_offset = @(0.04, 0.06, 0.08)
  buy_bull_ema_long_offset = @(0.06, 0.08, 0.10)
  buy_min_ema_spread = @(0.0, 0.005, 0.010)
  sell_ema_slope_lookback = @(16, 24, 32)
  sell_stop_atr_mult = @(3.0, 4.0, 5.0)
  sell_stop_min_loss = @(0.02, 0.03, 0.04)
  sell_bear_max_loss = @(0.05, 0.06, 0.07)

  # 风险开关因子（新增）
  buy_use_macro_trend_filter = @($false, $true)
  buy_macro_sma_period = @(150, 200, 250)
  buy_macro_sma_slope_lookback = @(10, 20, 40)
  buy_macro_sma_min_slope = @(0.0, 0.001, 0.003, 0.005)
  buy_use_atr_pct_max_filter = @($false, $true)
  buy_atr_pct_max = @(0.06, 0.08, 0.10, 0.12)
  buy_use_volume_ratio_filter = @($false, $true)
  buy_volume_ratio_lookback = @(24, 72, 144)
  buy_volume_ratio_min = @(0.7, 0.8, 0.9, 1.0)

  # 风险预算折扣（软风险开关）：不改信号，只改仓位
  buy_use_macro_trend_stake_scale = @($false, $true)
  buy_macro_stake_scale_floor = @(0.15, 0.25, 0.35)
  buy_use_atr_pct_stake_scale = @($false, $true)
  buy_atr_pct_soft_start = @(0.04, 0.06, 0.08)
  buy_atr_pct_soft_end = @(0.10, 0.12, 0.14)
  buy_atr_pct_soft_floor = @(0.15, 0.25, 0.35)
  buy_use_volume_ratio_stake_scale = @($false, $true)
  buy_volume_ratio_soft_min = @(0.6, 0.7, 0.8)
  buy_volume_ratio_soft_target = @(0.9, 1.0, 1.1)
  buy_volume_ratio_soft_floor = @(0.15, 0.25, 0.35)
}

$rng = New-Object System.Random($Seed)
$seen = New-Object "System.Collections.Generic.HashSet[string]"

function Pick-One {
  param([object[]]$Choices)
  return $Choices[$rng.Next(0, $Choices.Count)]
}

function Build-Signature {
  param([hashtable]$Params)
  $keys = @($Params.Keys | Sort-Object)
  return ($keys | ForEach-Object { "{0}={1}" -f $_, $Params[$_] }) -join ";"
}

$results = @()

function Run-BacktestAndCollect {
  param(
    [string]$Id,
    [string]$RunId,
    [hashtable]$Chosen
  )

  $btParams = @{
    Config = $Config
    Strategy = $Strategy
    Pairs = $Pairs
    Timeframe = $Timeframe
    Timerange = $Timerange
    DryRunWallet = $DryRunWallet
    MaxOpenTrades = $MaxOpenTrades
    Fee = $Fee
    RunId = $RunId
  }

  & $backtestScript @btParams | Out-Null
  if ($LASTEXITCODE -ne 0) {
    throw "回测失败（RunId=$RunId, exit=$LASTEXITCODE）"
  }

  $zipPath = Resolve-LatestBacktestZip -RunId $RunId
  $metricsJson = & uv run python -X utf8 $metricsScript --zip $zipPath --strategy $Strategy
  if ($LASTEXITCODE -ne 0) {
    throw "指标提取失败（RunId=$RunId, exit=$LASTEXITCODE）"
  }
  $m = $metricsJson | ConvertFrom-Json

  $profitPct = [double]$m.profit_total_pct
  $mddPct = [double]$m.max_relative_drawdown_pct
  $trades = [int]$m.total_trades

  $losses = Compute-Losses -ProfitPct $profitPct -MaxDdPct $mddPct -Trades $trades -MinTrades $MinTrades

  return [PSCustomObject]@{
    id = $Id
    run_id = $RunId
    timerange = $Timerange
    profit_total_pct = [math]::Round($profitPct, 6)
    max_drawdown_pct = [math]::Round($mddPct, 6)
    total_trades = $trades
    sharpe = [math]::Round([double]$m.sharpe, 6)
    sortino = [math]::Round([double]$m.sortino, 6)
    calmar = [math]::Round([double]$m.calmar, 6)
    profit_factor = [math]::Round([double]$m.profit_factor, 6)
    market_change_pct = [math]::Round([double]$m.market_change_pct, 6)
    zip = [string]$m.zip

    loss_profit_first = [math]::Round([double]$losses.loss_profit_first, 6)
    loss_dd_first = [math]::Round([double]$losses.loss_dd_first, 6)
    loss_balanced = [math]::Round([double]$losses.loss_balanced, 6)

    buy_ema_short_len = $Chosen.buy_ema_short_len
    buy_ema_long_len = $Chosen.buy_ema_long_len
    buy_adx = $Chosen.buy_adx
    buy_ema_slope_lookback = $Chosen.buy_ema_slope_lookback
    buy_ema_long_min_slope = $Chosen.buy_ema_long_min_slope
    buy_max_ema_short_offset = $Chosen.buy_max_ema_short_offset
    buy_bull_ema_long_offset = $Chosen.buy_bull_ema_long_offset
    buy_min_ema_spread = $Chosen.buy_min_ema_spread
    sell_ema_slope_lookback = $Chosen.sell_ema_slope_lookback
    sell_stop_atr_mult = $Chosen.sell_stop_atr_mult
    sell_stop_min_loss = $Chosen.sell_stop_min_loss
    sell_bear_max_loss = $Chosen.sell_bear_max_loss

    buy_use_macro_trend_filter = $Chosen.buy_use_macro_trend_filter
    buy_macro_sma_period = $Chosen.buy_macro_sma_period
    buy_macro_sma_slope_lookback = $Chosen.buy_macro_sma_slope_lookback
    buy_macro_sma_min_slope = $Chosen.buy_macro_sma_min_slope
    buy_use_atr_pct_max_filter = $Chosen.buy_use_atr_pct_max_filter
    buy_atr_pct_max = $Chosen.buy_atr_pct_max
    buy_use_volume_ratio_filter = $Chosen.buy_use_volume_ratio_filter
    buy_volume_ratio_lookback = $Chosen.buy_volume_ratio_lookback
    buy_volume_ratio_min = $Chosen.buy_volume_ratio_min

    buy_use_macro_trend_stake_scale = $Chosen.buy_use_macro_trend_stake_scale
    buy_macro_stake_scale_floor = $Chosen.buy_macro_stake_scale_floor
    buy_use_atr_pct_stake_scale = $Chosen.buy_use_atr_pct_stake_scale
    buy_atr_pct_soft_start = $Chosen.buy_atr_pct_soft_start
    buy_atr_pct_soft_end = $Chosen.buy_atr_pct_soft_end
    buy_atr_pct_soft_floor = $Chosen.buy_atr_pct_soft_floor
    buy_use_volume_ratio_stake_scale = $Chosen.buy_use_volume_ratio_stake_scale
    buy_volume_ratio_soft_min = $Chosen.buy_volume_ratio_soft_min
    buy_volume_ratio_soft_target = $Chosen.buy_volume_ratio_soft_target
    buy_volume_ratio_soft_floor = $Chosen.buy_volume_ratio_soft_floor
  }
}

try {
  # baseline（当前参数文件，不做扰动）
  $baselineRunId = "pareto_${Strategy}_${Timeframe}_${ts}_baseline"
  $baselineChosen = @{}
  foreach ($k in $space.Keys) {
    try {
      if ($k -like "sell_*") {
        $baselineChosen[$k] = $baseObj.params.sell.$k
      } else {
        $baselineChosen[$k] = $baseObj.params.buy.$k
      }
    } catch {
      # 如果 base 未包含该键（新增参数），就用当前 space 的默认候选（第一个）
      $baselineChosen[$k] = $space[$k][0]
    }
  }
  $results += Run-BacktestAndCollect -Id "baseline" -RunId $baselineRunId -Chosen $baselineChosen

  for ($i = 1; $i -le $Trials; $i++) {
    $chosen = @{}
    foreach ($k in $space.Keys) {
      $chosen[$k] = Pick-One -Choices $space[$k]
    }

    # 约束：短 EMA 必须小于长 EMA
    if ([int]$chosen.buy_ema_short_len -ge [int]$chosen.buy_ema_long_len) {
      continue
    }

    # 去重：避免重复跑同一组参数
    $sig = Build-Signature -Params $chosen
    if ($seen.Contains($sig)) {
      continue
    }
    $null = $seen.Add($sig)

    $candObj = Clone-JsonObject -Obj $baseObj
    foreach ($k in $chosen.Keys) {
      if ($k -like "sell_*") {
        $candObj.params.sell.$k = $chosen[$k]
      } else {
        $candObj.params.buy.$k = $chosen[$k]
      }
    }

    $candJson = $candObj | ConvertTo-Json -Depth 100
    Write-Utf8NoBom -Path $paramFile -Content $candJson

    $runId = "pareto_${Strategy}_${Timeframe}_${ts}_${i}"
    try {
      $results += Run-BacktestAndCollect -Id ("cand_{0}" -f $i) -RunId $runId -Chosen $chosen
    } catch {
      # 保底：单个候选失败不影响整轮搜索
      Write-Host "候选失败（$runId）：$($_.Exception.Message)"
    }
  }
}
finally {
  # 无论成功与否，都恢复原始参数文件
  Write-Utf8NoBom -Path $paramFile -Content $origJson
}

if ($results.Count -eq 0) {
  throw "未产生任何结果（可能所有候选都被约束过滤/执行失败）。"
}

$csvAll = Join-Path $runRoot "candidates.csv"
$results | Export-Csv -NoTypeInformation -Encoding UTF8 -Path $csvAll

# 过滤掉交易数过低的点再做帕累托（避免 0 交易点污染）
$valid = @($results | Where-Object { $_.total_trades -ge $MinTrades })

$pareto = @()
foreach ($a in $valid) {
  $dominated = $false
  foreach ($b in $valid) {
    if ($a -eq $b) { continue }
    if (Is-Dominated -A $a -B $b) {
      $dominated = $true
      break
    }
  }
  if (-not $dominated) {
    $pareto += $a
  }
}

$csvPareto = Join-Path $runRoot "pareto_front.csv"
$pareto | Export-Csv -NoTypeInformation -Encoding UTF8 -Path $csvPareto

function Export-Top {
  param(
    [string]$Name,
    [object[]]$Rows,
    [string]$Key
  )
  $out = Join-Path $runRoot ("top_{0}.csv" -f $Name)
  $Rows |
    Sort-Object -Property $Key |
    Select-Object -First $TopK |
    Export-Csv -NoTypeInformation -Encoding UTF8 -Path $out
}

Export-Top -Name "loss_profit_first" -Rows $valid -Key "loss_profit_first"
Export-Top -Name "loss_dd_first" -Rows $valid -Key "loss_dd_first"
Export-Top -Name "loss_balanced" -Rows $valid -Key "loss_balanced"

# 是否存在无损改进：在 (profit↑, trades↑, drawdown↓) 三目标上支配 baseline
$baseline = $results | Where-Object { $_.id -eq "baseline" } | Select-Object -First 1
$dominators = @()
foreach ($b in $valid) {
  if ($b.id -eq "baseline") { continue }
  if (Is-Dominated -A $baseline -B $b) {
    $dominators += $b
  }
}

$md = @()
$md += "# 参数邻域搜索报告（收益-回撤-交易数）"
$md += ""
$md += "- Strategy: $Strategy"
$md += "- Timeframe: $Timeframe"
$md += "- Pair(s): $($Pairs -join ', ')"
$md += "- Timerange: $Timerange"
$md += "- Trials: $Trials (含 baseline=1)"
$md += "- MinTrades(for pareto): $MinTrades"
$md += "- Seed: $Seed"
$md += ""
$md += "## 产物"
$md += ""
$md += "- candidates: $($csvAll)"
$md += "- pareto_front: $($csvPareto)"
$md += ""
$md += "## baseline"
$md += ""
$md += ("- profit_total_pct={0}  max_drawdown_pct={1}  total_trades={2}" -f $baseline.profit_total_pct, $baseline.max_drawdown_pct, $baseline.total_trades)
$md += ""
$md += "## 无损改进结论"
$md += ""
if ($dominators.Count -gt 0) {
  $bestDom = $dominators | Sort-Object @{Expression="max_drawdown_pct"; Ascending=$true}, @{Expression="profit_total_pct"; Ascending=$false} | Select-Object -First 1
  $md += "存在：发现至少 1 个候选点在三目标上支配 baseline（收益≥、回撤≤、交易数≥）。"
  $md += ""
  $md += ("- best_dominator: id={0} profit_total_pct={1} max_drawdown_pct={2} total_trades={3}" -f $bestDom.id, $bestDom.profit_total_pct, $bestDom.max_drawdown_pct, $bestDom.total_trades)
} else {
  $md += "未发现：在当前邻域与样本数下，没有出现明确的三目标无损改进点。"
  $md += ""
  $md += "建议：扩大 Trials 或放宽/调整约束（例如以 maxDD≤20% 为硬约束，改为双目标 profit↑ + trades↑），再做一轮。"
}

$mdPath = Join-Path $runRoot "report.md"
$md | Set-Content -Encoding UTF8 -Path $mdPath

Write-Host ""
Write-Host "=== 完成 ==="
Write-Host "- output: $runRoot"
Write-Host "- candidates: $csvAll"
Write-Host "- pareto: $csvPareto"
Write-Host "- report: $mdPath"
