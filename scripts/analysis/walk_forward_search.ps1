<#
.SYNOPSIS
  Walk-forward 邻域搜索（先训练集搜索，再验证集复测）

.DESCRIPTION
  - 目标：减少“只在训练期好看”的过拟合风险
  - 做法：
    1) 在 TrainTimerange 上做小范围参数邻域随机搜索（多损失函数）
    2) 从训练集 TopK（按多损失函数取并集）里挑候选
    3) 在 TestTimerange 上复测这些候选
    4) 输出候选点集与“是否存在无损改进”的结论（以验证集为准）

.EXAMPLE
  ./scripts/analysis/walk_forward_search.ps1 `
    -Strategy "SmallAccountTrendFilteredV1" `
    -Pairs "BTC/USDT" `
    -Timeframe "4h" `
    -TrainTimerange "20200101-20211231" `
    -TestTimerange "20220101-20221231" `
    -Trials 80 `
    -Seed 42
#>
[CmdletBinding()]
param(
  [string]$Strategy = "SmallAccountTrendFilteredV1",
  [string]$Config = "04_shared/configs/small_account/config_small_spot_base.json",
  [string[]]$Pairs = @("BTC/USDT"),
  [string]$Timeframe = "4h",

  [string]$TrainTimerange = "20200101-20211231",
  [string]$TestTimerange = "20220101-20221231",

  [double]$DryRunWallet = 10,
  [int]$MaxOpenTrades = 1,
  [double]$Fee = 0.0006,

  [int]$Trials = 80,
  [int]$Seed = 42,
  [int]$MinTradesTrain = 20,
  [int]$MinTradesTest = 8,

  # 每个损失函数挑选 TopK，最后取并集进入验证期复测
  [int]$TopK = 12,
  [string]$OutDir = "artifacts/walk_forward_search"
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

function Ensure-JsonProperty {
  param(
    [Parameter(Mandatory = $true)][object]$Obj,
    [Parameter(Mandatory = $true)][string]$Name,
    [Parameter(Mandatory = $true)][object]$Value
  )
  if ($null -eq $Obj.PSObject.Properties[$Name]) {
    $Obj | Add-Member -NotePropertyName $Name -NotePropertyValue $Value -Force
  } else {
    $Obj.$Name = $Value
  }
}

function Set-StrategyParam {
  param(
    [Parameter(Mandatory = $true)][object]$StrategyObj,
    [Parameter(Mandatory = $true)][string]$Key,
    [Parameter(Mandatory = $true)][object]$Value
  )

  if ($Key -like "sell_*") {
    Ensure-JsonProperty -Obj $StrategyObj.params.sell -Name $Key -Value $Value
  } else {
    Ensure-JsonProperty -Obj $StrategyObj.params.buy -Name $Key -Value $Value
  }
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

  $tradePenalty = 0.0
  if ($Trades -lt $MinTrades) {
    $tradePenalty = [double](($MinTrades - $Trades) * 10.0)
  }

  $ddPenalty = 0.0
  if ($MaxDdPct -gt 20.0) {
    $ddPenalty = [double](($MaxDdPct - 20.0) * 5.0)
  }

  $lossProfitFirst = (-1.0 * $ProfitPct) + $ddPenalty + $tradePenalty
  $lossDdFirst = ($MaxDdPct) - (0.25 * $ProfitPct) + $tradePenalty
  $lossBalanced = ($MaxDdPct) - (0.40 * $ProfitPct) + $ddPenalty + $tradePenalty

  return @{
    loss_profit_first = $lossProfitFirst
    loss_dd_first = $lossDdFirst
    loss_balanced = $lossBalanced
  }
}

function Build-Signature {
  param([hashtable]$Params)
  $keys = @($Params.Keys | Sort-Object)
  return ($keys | ForEach-Object { "{0}={1}" -f $_, $Params[$_] }) -join ";"
}

function Run-BacktestMetrics {
  param(
    [Parameter(Mandatory = $true)][string]$Timerange,
    [Parameter(Mandatory = $true)][string]$RunId
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

  return @{
    zip = [string]$m.zip
    profit_total_pct = [double]$m.profit_total_pct
    max_drawdown_pct = [double]$m.max_relative_drawdown_pct
    total_trades = [int]$m.total_trades
    sharpe = [double]$m.sharpe
    sortino = [double]$m.sortino
    calmar = [double]$m.calmar
    profit_factor = [double]$m.profit_factor
    market_change_pct = [double]$m.market_change_pct
  }
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
function Pick-One {
  param([object[]]$Choices)
  return $Choices[$rng.Next(0, $Choices.Count)]
}

$ts = Get-Date -Format "yyyy-MM-dd_HH-mm-ss"
$runRoot = Join-Path $OutDir ("wf_{0}_{1}_{2}" -f $Strategy, $Timeframe, $ts)
New-Item -ItemType Directory -Force -Path $runRoot | Out-Null

$origJson = Get-Content -Raw -Encoding UTF8 $paramFile
$baseObj = $origJson | ConvertFrom-Json
if ($null -eq $baseObj.params -or $null -eq $baseObj.params.buy -or $null -eq $baseObj.params.sell) {
  throw "参数文件结构异常（缺少 params.buy / params.sell）：$paramFile"
}

$seen = New-Object "System.Collections.Generic.HashSet[string]"
$trainRows = @()

try {
  # baseline（训练集）
  Write-Utf8NoBom -Path $paramFile -Content $origJson
  $baselineRunTrain = "wf_${Strategy}_${Timeframe}_${ts}_baseline_train"
  $trainBase = Run-BacktestMetrics -Timerange $TrainTimerange -RunId $baselineRunTrain
  $trainBaseLoss = Compute-Losses -ProfitPct $trainBase.profit_total_pct -MaxDdPct $trainBase.max_drawdown_pct -Trades $trainBase.total_trades -MinTrades $MinTradesTrain

  $baselineChosen = @{}
  foreach ($k in $space.Keys) {
    try {
      if ($k -like "sell_*") {
        $baselineChosen[$k] = $baseObj.params.sell.$k
      } else {
        $baselineChosen[$k] = $baseObj.params.buy.$k
      }
    } catch {
      $baselineChosen[$k] = $space[$k][0]
    }
  }
  $baselineSig = Build-Signature -Params $baselineChosen
  $null = $seen.Add($baselineSig)

  $baselineRow = [ordered]@{
    id = "baseline"
    signature = $baselineSig
    run_id_train = $baselineRunTrain
    train_timerange = $TrainTimerange
    train_profit_total_pct = [math]::Round([double]$trainBase.profit_total_pct, 6)
    train_max_drawdown_pct = [math]::Round([double]$trainBase.max_drawdown_pct, 6)
    train_total_trades = [int]$trainBase.total_trades
    train_sharpe = [math]::Round([double]$trainBase.sharpe, 6)
    train_sortino = [math]::Round([double]$trainBase.sortino, 6)
    train_calmar = [math]::Round([double]$trainBase.calmar, 6)
    train_profit_factor = [math]::Round([double]$trainBase.profit_factor, 6)
    train_zip = [string]$trainBase.zip
    train_loss_profit_first = [math]::Round([double]$trainBaseLoss.loss_profit_first, 6)
    train_loss_dd_first = [math]::Round([double]$trainBaseLoss.loss_dd_first, 6)
    train_loss_balanced = [math]::Round([double]$trainBaseLoss.loss_balanced, 6)
  }
  foreach ($k in $baselineChosen.Keys) {
    $baselineRow[$k] = $baselineChosen[$k]
  }
  $trainRows += [PSCustomObject]$baselineRow

  # 候选（训练集）
  $i = 0
  $attempt = 0
  $maxAttempts = [math]::Max([int]($Trials * 5), 100)
  while ($i -lt $Trials -and $attempt -lt $maxAttempts) {
    $attempt++

    $chosen = @{}
    foreach ($k in $space.Keys) {
      $chosen[$k] = Pick-One -Choices $space[$k]
    }

    # 约束：短 EMA 必须小于长 EMA
    if ([int]$chosen.buy_ema_short_len -ge [int]$chosen.buy_ema_long_len) {
      continue
    }

    $sig = Build-Signature -Params $chosen
    if ($seen.Contains($sig)) {
      continue
    }
    $null = $seen.Add($sig)

    $candObj = Clone-JsonObject -Obj $baseObj
    foreach ($k in $chosen.Keys) {
      Set-StrategyParam -StrategyObj $candObj -Key $k -Value $chosen[$k]
    }
    $candJson = $candObj | ConvertTo-Json -Depth 100
    Write-Utf8NoBom -Path $paramFile -Content $candJson

    $i++
    $runTrain = "wf_${Strategy}_${Timeframe}_${ts}_${i}_train"
    try {
      $mTrain = Run-BacktestMetrics -Timerange $TrainTimerange -RunId $runTrain
      $lossTrain = Compute-Losses -ProfitPct $mTrain.profit_total_pct -MaxDdPct $mTrain.max_drawdown_pct -Trades $mTrain.total_trades -MinTrades $MinTradesTrain

      $candRow = [ordered]@{
        id = ("cand_{0}" -f $i)
        signature = $sig
        run_id_train = $runTrain
        train_timerange = $TrainTimerange
        train_profit_total_pct = [math]::Round([double]$mTrain.profit_total_pct, 6)
        train_max_drawdown_pct = [math]::Round([double]$mTrain.max_drawdown_pct, 6)
        train_total_trades = [int]$mTrain.total_trades
        train_sharpe = [math]::Round([double]$mTrain.sharpe, 6)
        train_sortino = [math]::Round([double]$mTrain.sortino, 6)
        train_calmar = [math]::Round([double]$mTrain.calmar, 6)
        train_profit_factor = [math]::Round([double]$mTrain.profit_factor, 6)
        train_zip = [string]$mTrain.zip
        train_loss_profit_first = [math]::Round([double]$lossTrain.loss_profit_first, 6)
        train_loss_dd_first = [math]::Round([double]$lossTrain.loss_dd_first, 6)
        train_loss_balanced = [math]::Round([double]$lossTrain.loss_balanced, 6)
      }
      foreach ($k in $chosen.Keys) {
        $candRow[$k] = $chosen[$k]
      }
      $trainRows += [PSCustomObject]$candRow
    } catch {
      Write-Host "训练回测失败（$runTrain）：$($_.Exception.Message)"
    }
  }
}
finally {
  # 恢复原始参数文件
  Write-Utf8NoBom -Path $paramFile -Content $origJson
}

if ($trainRows.Count -eq 0) {
  throw "训练阶段未产生任何结果。"
}

$trainCsv = Join-Path $runRoot "train_candidates.csv"
$trainRows | Export-Csv -NoTypeInformation -Encoding UTF8 -Path $trainCsv

# 选择进入验证集复测的候选（多损失函数 TopK 取并集）
$validTrain = @($trainRows | Where-Object { [int]$_.train_total_trades -ge $MinTradesTrain })
if ($validTrain.Count -eq 0) {
  $validTrain = @($trainRows)
}

$pickedIds = New-Object "System.Collections.Generic.HashSet[string]"
foreach ($k in @("train_loss_profit_first", "train_loss_dd_first", "train_loss_balanced")) {
  foreach ($row in ($validTrain | Sort-Object -Property $k | Select-Object -First $TopK)) {
    $null = $pickedIds.Add([string]$row.id)
  }
}

# baseline 必须包含
$null = $pickedIds.Add("baseline")

$picked = @($trainRows | Where-Object { $pickedIds.Contains([string]$_.id) })

# 验证集复测
$wfRows = @()
$baselineTestRun = "wf_${Strategy}_${Timeframe}_${ts}_baseline_test"
Write-Utf8NoBom -Path $paramFile -Content $origJson
$mBaseTest = Run-BacktestMetrics -Timerange $TestTimerange -RunId $baselineTestRun

foreach ($row in $picked) {
  $id = [string]$row.id
  $chosen = @{}
  foreach ($k in $space.Keys) {
    $chosen[$k] = $row.$k
  }

  $jsonObj = Clone-JsonObject -Obj $baseObj
  foreach ($k in $chosen.Keys) {
    Set-StrategyParam -StrategyObj $jsonObj -Key $k -Value $chosen[$k]
  }
  $jsonText = $jsonObj | ConvertTo-Json -Depth 100
  Write-Utf8NoBom -Path $paramFile -Content $jsonText

  $runTest = if ($id -eq "baseline") { $baselineTestRun } else { "wf_${Strategy}_${Timeframe}_${ts}_${id}_test" }
  try {
    $mTest = if ($id -eq "baseline") { $mBaseTest } else { Run-BacktestMetrics -Timerange $TestTimerange -RunId $runTest }
    $lossTest = Compute-Losses -ProfitPct $mTest.profit_total_pct -MaxDdPct $mTest.max_drawdown_pct -Trades $mTest.total_trades -MinTrades $MinTradesTest

    $wfRow = [ordered]@{
      id = $id
      signature = [string]$row.signature

      train_timerange = [string]$TrainTimerange
      train_profit_total_pct = [double]$row.train_profit_total_pct
      train_max_drawdown_pct = [double]$row.train_max_drawdown_pct
      train_total_trades = [int]$row.train_total_trades
      train_zip = [string]$row.train_zip
      train_loss_balanced = [double]$row.train_loss_balanced

      test_timerange = [string]$TestTimerange
      test_profit_total_pct = [math]::Round([double]$mTest.profit_total_pct, 6)
      test_max_drawdown_pct = [math]::Round([double]$mTest.max_drawdown_pct, 6)
      test_total_trades = [int]$mTest.total_trades
      test_sharpe = [math]::Round([double]$mTest.sharpe, 6)
      test_sortino = [math]::Round([double]$mTest.sortino, 6)
      test_calmar = [math]::Round([double]$mTest.calmar, 6)
      test_profit_factor = [math]::Round([double]$mTest.profit_factor, 6)
      test_zip = [string]$mTest.zip
      test_loss_profit_first = [math]::Round([double]$lossTest.loss_profit_first, 6)
      test_loss_dd_first = [math]::Round([double]$lossTest.loss_dd_first, 6)
      test_loss_balanced = [math]::Round([double]$lossTest.loss_balanced, 6)
    }
    foreach ($k in $chosen.Keys) {
      $wfRow[$k] = $chosen[$k]
    }
    $wfRows += [PSCustomObject]$wfRow
  } catch {
    Write-Host "验证回测失败（$runTest）：$($_.Exception.Message)"
  }
}

# 恢复参数文件
Write-Utf8NoBom -Path $paramFile -Content $origJson

if ($wfRows.Count -eq 0) {
  throw "验证阶段未产生任何结果。"
}

$wfCsv = Join-Path $runRoot "walk_forward_results.csv"
$wfRows | Export-Csv -NoTypeInformation -Encoding UTF8 -Path $wfCsv

# 验证集结论：是否存在支配 baseline 的无损改进点（以验证集三目标为准）
$baselineRow = $wfRows | Where-Object { $_.id -eq "baseline" } | Select-Object -First 1
$baseProfit = [double]$baselineRow.test_profit_total_pct
$baseDd = [double]$baselineRow.test_max_drawdown_pct
$baseTrades = [int]$baselineRow.test_total_trades

$dominators = @(
  $wfRows | Where-Object {
    $_.id -ne "baseline" -and
    ([int]$_.test_total_trades -ge $MinTradesTest) -and
    ([double]$_.test_profit_total_pct -ge $baseProfit) -and
    ([double]$_.test_max_drawdown_pct -le $baseDd) -and
    ([int]$_.test_total_trades -ge $baseTrades)
  }
)

$positive2022 = @(
  $wfRows | Where-Object {
    ([double]$_.test_profit_total_pct -gt 0) -and ([int]$_.test_total_trades -ge $MinTradesTest)
  } | Sort-Object @{Expression="test_profit_total_pct"; Ascending=$false}
)

$md = @()
$md += "# Walk-forward 搜索报告"
$md += ""
$md += "- Strategy: $Strategy"
$md += "- Timeframe: $Timeframe"
$md += "- Pair(s): $($Pairs -join ', ')"
$md += "- TrainTimerange: $TrainTimerange"
$md += "- TestTimerange: $TestTimerange"
$md += "- Trials: $Trials (训练集随机采样，不含 baseline)"
$md += "- Seed: $Seed"
$md += "- TopK(per loss): $TopK"
$md += ""
$md += "## 产物"
$md += ""
$md += "- train_candidates: $trainCsv"
$md += "- walk_forward_results: $wfCsv"
$md += ""
$md += "## baseline（验证集）"
$md += ""
$md += ("- profit_total_pct={0}  max_drawdown_pct={1}  total_trades={2}" -f $baseProfit, $baseDd, $baseTrades)
$md += ""
$md += "## 无损改进结论（以验证集为准）"
$md += ""
if ($dominators.Count -gt 0) {
  $bestDom = $dominators |
    Sort-Object @{Expression="test_max_drawdown_pct"; Ascending=$true}, @{Expression="test_profit_total_pct"; Ascending=$false} |
    Select-Object -First 1
  $md += "存在：发现至少 1 个候选点在验证集三目标上支配 baseline（收益≥、回撤≤、交易数≥）。"
  $md += ""
  $md += ("- best_dominator: id={0} profit_total_pct={1} max_drawdown_pct={2} total_trades={3}" -f $bestDom.id, $bestDom.test_profit_total_pct, $bestDom.test_max_drawdown_pct, $bestDom.test_total_trades)
} else {
  $md += "未发现：在当前邻域与样本数下，没有出现明确的验证集三目标无损改进点。"
}

$md += ""
$md += "## 验证集盈利候选（profit>0）"
$md += ""
if ($positive2022.Count -gt 0) {
  foreach ($r in ($positive2022 | Select-Object -First 8)) {
    $md += ("- id={0} profit_total_pct={1} max_drawdown_pct={2} trades={3}" -f $r.id, $r.test_profit_total_pct, $r.test_max_drawdown_pct, $r.test_total_trades)
  }
} else {
  $md += "- （无）"
}

$mdPath = Join-Path $runRoot "report.md"
$md | Set-Content -Encoding UTF8 -Path $mdPath

Write-Host ""
Write-Host "=== 完成 ==="
Write-Host "- output: $runRoot"
Write-Host "- train_candidates: $trainCsv"
Write-Host "- walk_forward_results: $wfCsv"
Write-Host "- report: $mdPath"


