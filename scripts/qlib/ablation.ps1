<#
.SYNOPSIS
  因子消融：对多个特征集分别训练并汇总指标（Qlib 风格）

.DESCRIPTION
  目标：
  - 使用同一份研究数据集，对不同 feature_set（来自 04_shared/config/factors.yaml）分别训练模型
  - 汇总 base / calibrated 的验证集指标，输出 CSV/Markdown，便于做因子“加法/减法”决策

  注意：
  - 本脚本本身是封装器，但会调用 `scripts/qlib/train_model.py`（依赖真实 Qlib：pyqlib）。
  - 输出默认写入 artifacts/qlib_ablation/（建议不入库）。

.EXAMPLE
  ./scripts/qlib/ablation.ps1 -Pairs "BTC/USDT:USDT" -FeatureSets "cta_alpha","cta_risk","cta_core"

  ./scripts/qlib/ablation.ps1 -Timeframe "4h" -Threshold 0.0005 -ValidPct 0.2
#>
[CmdletBinding()]
param(
  [string]$Timeframe = "4h",
  [string]$Exchange = "",
  [string[]]$Pairs = @(),
  [string]$ModelVersion = "",
  [int]$Horizon = 1,
  [double]$Threshold = 0.0,
  [double]$ValidPct = 0.2,

  [string[]]$FeatureSets = @("cta_alpha", "cta_risk", "cta_core"),

  [string]$OutDir = "artifacts/qlib_ablation",
  [string]$RunId = "",

  [switch]$SkipConvert
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

# 确保 Python 可导入 03_integration/trading_system（供 -c 片段与策略侧复用）
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

if ([string]::IsNullOrWhiteSpace($ModelVersion)) {
  try {
    $ModelVersion = & uv run python -X utf8 -c "from trading_system.infrastructure.config_loader import get_config; print(get_config().model_version)"
    $ModelVersion = [string]$ModelVersion
    $ModelVersion = $ModelVersion.Trim()
  } catch {
    $ModelVersion = "v1"
  }
}

if ($Pairs.Count -le 0) {
  try {
    $pairsJson = & uv run python -X utf8 -c "import json; from trading_system.infrastructure.config_loader import get_config; print(json.dumps(get_config().pairs(), ensure_ascii=False))"
    $Pairs = @((ConvertFrom-Json -InputObject $pairsJson) | ForEach-Object { [string]$_ })
  } catch {
    throw "无法从 04_shared/config/symbols.yaml 读取 pairs，请用 -Pairs 显式传入。"
  }
}

if ($FeatureSets.Count -le 0) {
  throw "FeatureSets 不能为空。"
}

$ts = Get-Date -Format "yyyy-MM-dd_HH-mm-ss"
$runName = if ([string]::IsNullOrWhiteSpace($RunId)) { "ablation_${ModelVersion}_${Timeframe}_${ts}" } else { $RunId }
$runDir = (Join-Path $OutDir $runName)
New-Item -ItemType Directory -Force -Path $runDir | Out-Null

Write-Host ""
Write-Host "=== 因子消融参数 ==="
Write-Host "- timeframe: $Timeframe"
Write-Host "- exchange(override): $Exchange"
Write-Host "- pairs: $($Pairs -join ', ')"
Write-Host "- model_version(tag): $ModelVersion"
Write-Host "- horizon: $Horizon"
Write-Host "- threshold: $Threshold"
Write-Host "- valid_pct: $ValidPct"
Write-Host "- feature_sets: $($FeatureSets -join ', ')"
Write-Host "- output: $runDir"

if (-not $SkipConvert) {
  Write-Host ""
  Write-Host "=== 1) 转换数据（feather → pkl）==="
  $args = @("run","python","-X","utf8","scripts/qlib/convert_freqtrade_to_qlib.py","--timeframe",$Timeframe)
  if (-not [string]::IsNullOrWhiteSpace($Exchange)) {
    $args += @("--exchange",$Exchange)
  }
  & uv @args
  if ($LASTEXITCODE -ne 0) { throw "转换数据失败（exit=$LASTEXITCODE）。" }
}

Write-Host ""
Write-Host "=== 2) 逐特征集训练并汇总 ==="

$rows = @()

foreach ($pair in $Pairs) {
  $symbol = ""
  try {
    $symbol = & uv run python -X utf8 -c "from trading_system.domain.symbols import freqtrade_pair_to_symbol; print(freqtrade_pair_to_symbol(r'''$pair'''))"
    $symbol = [string]$symbol
    $symbol = $symbol.Trim()
  } catch {
    $symbol = ""
  }
  if ([string]::IsNullOrWhiteSpace($symbol)) {
    $symbol = ($pair -replace "[^0-9A-Za-z._-]", "_")
  }

  foreach ($fs in $FeatureSets) {
    $fsName = [string]$fs
    if ([string]::IsNullOrWhiteSpace($fsName)) { continue }

    Write-Host ""
    Write-Host ("--- train: {0} | feature_set={1} ---" -f $pair, $fsName)

    $out = Join-Path $runDir (Join-Path $fsName (Join-Path $Timeframe $symbol))
    New-Item -ItemType Directory -Force -Path $out | Out-Null

    $args = @(
      "run","python","-X","utf8","scripts/qlib/train_model.py",
      "--pair",$pair,
      "--timeframe",$Timeframe,
      "--model-version",$ModelVersion,
      "--horizon","$Horizon",
      "--threshold","$Threshold",
      "--valid-pct","$ValidPct",
      "--feature-set",$fsName,
      "--outdir",$out
    )
    if (-not [string]::IsNullOrWhiteSpace($Exchange)) {
      $args += @("--exchange",$Exchange)
    }
    & uv @args
    if ($LASTEXITCODE -ne 0) { throw "训练失败（pair=$pair feature_set=$fsName exit=$LASTEXITCODE）。" }

    $infoPath = Join-Path $out "model_info.json"
    if (-not (Test-Path $infoPath)) {
      throw "未找到训练输出：$infoPath"
    }
    $info = Get-Content -Raw -Encoding UTF8 $infoPath | ConvertFrom-Json

    $base = $info.metrics.base
    $cal = $info.metrics.calibrated

    $rows += [PSCustomObject]@{
      pair = $pair
      symbol = $info.symbol
      timeframe = $info.timeframe
      feature_set = $info.feature_spec.feature_set
      rows_train = $info.rows_train
      rows_valid = $info.rows_valid

      base_auc = $base.valid_auc
      base_brier = $base.valid_brier
      base_logloss = $base.valid_logloss
      base_accuracy = $base.valid_accuracy

      calibrated_auc = $cal.valid_auc
      calibrated_brier = $cal.valid_brier
      calibrated_logloss = $cal.valid_logloss
      calibrated_accuracy = $cal.valid_accuracy

      model_dir = $out
    }
  }
}

$csvPath = Join-Path $runDir "summary.csv"
$rows | Export-Csv -NoTypeInformation -Encoding UTF8 -Path $csvPath

$mdPath = Join-Path $runDir "summary.md"
$lines = @()
$lines += "# 因子消融汇总"
$lines += ""
$lines += "- run: $runName"
$lines += "- timeframe: $Timeframe"
$lines += "- pairs: $($Pairs -join ', ')"
$lines += "- feature_sets: $($FeatureSets -join ', ')"
$lines += ""
$lines += "输出明细见同目录：summary.csv"
$lines | Set-Content -Encoding UTF8 -Path $mdPath

Write-Host ""
Write-Host "=== 完成 ==="
Write-Host "- CSV: $csvPath"
Write-Host "- MD : $mdPath"
Write-Host "- Dir: $runDir"
