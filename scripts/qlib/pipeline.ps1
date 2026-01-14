<#
.SYNOPSIS
    Freqtrade → 研究数据 → 模型训练 一键流水线（Qlib 风格导出）

.DESCRIPTION
    目标：把“研究层数据+模型”构建变成可复现的一键动作：
    1) feather → pkl（02_qlib_research/qlib_data/<exchange>/<tf>/）
    2) 逐交易对训练并导出模型（02_qlib_research/models/qlib/<version>/<exchange>/<tf>/<symbol>/）

    注意：
    - 本脚本不依赖真实 Qlib，只遵循本仓库的工程化约定（trading_system + scripts/qlib）。
    - 默认交易对来自 04_shared/config/symbols.yaml（也可用 -Pairs 覆盖）。

.EXAMPLE
    ./scripts/qlib/pipeline.ps1
    ./scripts/qlib/pipeline.ps1 -Timeframe "4h" -ModelVersion "v2_cal"
    ./scripts/qlib/pipeline.ps1 -Pairs "BTC/USDT:USDT","ETH/USDT:USDT" -Threshold 0.0005
#>
[CmdletBinding()]
param(
  [string]$Timeframe = "4h",
  [string]$Exchange = "",
  [string]$SymbolsYaml = "",
  [string[]]$Pairs = @(),
  [string]$ModelVersion = "",
  [int]$Horizon = 1,
  [double]$Threshold = 0.0,
  [double]$ValidPct = 0.2,
  [string]$FeatureSet = "",

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
    # Windows 上 PYTHONPATH 分隔符为 ';'
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
  if (-not [string]::IsNullOrWhiteSpace($SymbolsYaml)) {
    try {
      $symPath = (Resolve-Path $SymbolsYaml).Path
      $pairsJson = & uv run python -X utf8 -c "import json, yaml; p=yaml.safe_load(open(r'$symPath', encoding='utf-8')) or {}; print(json.dumps(p.get('pairs', []), ensure_ascii=False))"
      $Pairs = @((ConvertFrom-Json -InputObject $pairsJson) | ForEach-Object { [string]$_ })
    } catch {
      throw "无法从 SymbolsYaml 读取 pairs：$SymbolsYaml"
    }
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

Write-Host ""
Write-Host "=== Qlib 工程流水线参数 ==="
Write-Host "- timeframe: $Timeframe"
Write-Host "- exchange(override): $Exchange"
Write-Host "- pairs: $($Pairs -join ', ')"
Write-Host "- model_version: $ModelVersion"
Write-Host "- horizon: $Horizon"
Write-Host "- threshold: $Threshold"
Write-Host "- valid_pct: $ValidPct"
Write-Host "- feature_set: $FeatureSet"

if (-not $SkipConvert) {
  Write-Host ""
  Write-Host "=== 1) 转换数据（feather → pkl）==="
  $args = @("run","python","-X","utf8","scripts/qlib/convert_freqtrade_to_qlib.py","--timeframe",$Timeframe,"--pairs")
  $args += $Pairs
  if (-not [string]::IsNullOrWhiteSpace($Exchange)) {
    $args += @("--exchange",$Exchange)
  }
  & uv @args
  if ($LASTEXITCODE -ne 0) { throw "转换数据失败（exit=$LASTEXITCODE）。" }
}

Write-Host ""
Write-Host "=== 2) 训练模型（逐交易对）==="
foreach ($pair in $Pairs) {
  Write-Host ""
  Write-Host ("--- train: {0} ---" -f $pair)
  $args = @(
    "run","python","-X","utf8","scripts/qlib/train_model.py",
    "--pair",$pair,
    "--timeframe",$Timeframe,
    "--model-version",$ModelVersion,
    "--horizon","$Horizon",
    "--threshold","$Threshold",
    "--valid-pct","$ValidPct"
  )
  if (-not [string]::IsNullOrWhiteSpace($Exchange)) {
    $args += @("--exchange",$Exchange)
  }
  if (-not [string]::IsNullOrWhiteSpace($FeatureSet)) {
    $args += @("--feature-set",$FeatureSet)
  }
  & uv @args
  if ($LASTEXITCODE -ne 0) { throw "训练失败（pair=$pair exit=$LASTEXITCODE）。" }
}

Write-Host ""
Write-Host "Done."
