<#
.SYNOPSIS
  归一化市场数据目录结构（兼容 Freqtrade 2026+）。

.DESCRIPTION
  某些历史数据布局会把现货(spot) OHLCV 文件保存到：
    data/<exchange>/spot/<PAIR>-<TF>.<ext>
  但当前版本 Freqtrade 对现货数据的默认读取路径是：
    data/<exchange>/<PAIR>-<TF>.<ext>

  本脚本会把 data/<exchange>/spot 下的文件复制/移动到 data/<exchange>/，
  以便 `freqtrade list-data/backtesting` 能正确识别现货数据。

  说明：
  - 只处理现货子目录 spot，不会触碰 futures 等目录。
  - 默认使用“复制”模式，避免误操作导致数据丢失。
  - data/ 目录已被 .gitignore 忽略，本脚本仅用于本地数据可用性修复。

.PARAMETER DataRoot
  数据根目录（默认：data）。

.PARAMETER Exchange
  交易所目录名（例如：okx）。为空则自动扫描 DataRoot 下所有包含 spot 子目录的交易所。

.PARAMETER Mode
  归一化方式：
  - copy：复制到目标目录（默认，安全）
  - move：移动到目标目录（更省空间）

.PARAMETER Extensions
  需要处理的扩展名列表（默认包含 feather/json/json.gz/parquet）。
#>
[CmdletBinding(SupportsShouldProcess)]
param(
  [string]$DataRoot = "data",
  [string]$Exchange = "",
  [ValidateSet("copy", "move")]
  [string]$Mode = "copy",
  [string[]]$Extensions = @("feather", "json", "json.gz", "parquet")
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Resolve-RepoRoot {
  # 脚本位于 scripts/data/，向上两级为仓库根目录
  return (Resolve-Path (Join-Path $PSScriptRoot "../..")).Path
}

function Get-ExchangeDirs {
  param(
    [string]$RepoRoot,
    [string]$DataRoot,
    [string]$Exchange
  )

  $dataRootPath = Join-Path $RepoRoot $DataRoot
  if (-not (Test-Path $dataRootPath)) {
    Write-Host "未找到数据目录：$dataRootPath"
    return @()
  }

  if (-not [string]::IsNullOrWhiteSpace($Exchange)) {
    $exchangePath = Join-Path $dataRootPath $Exchange
    if (-not (Test-Path $exchangePath)) {
      Write-Host "未找到交易所目录：$exchangePath"
      return @()
    }
    return @($exchangePath)
  }

  return @(Get-ChildItem -Path $dataRootPath -Directory | Select-Object -ExpandProperty FullName)
}

$repoRoot = Resolve-RepoRoot
$exchangeDirs = @(Get-ExchangeDirs -RepoRoot $repoRoot -DataRoot $DataRoot -Exchange $Exchange)

if ($exchangeDirs.Count -eq 0) {
  exit 0
}

$totalCopied = 0
$totalSkipped = 0
$totalFailed = 0

foreach ($exchangeDir in $exchangeDirs) {
  $spotDir = Join-Path $exchangeDir "spot"
  if (-not (Test-Path $spotDir)) {
    continue
  }

  $destDir = $exchangeDir
  Write-Host ""
  Write-Host "发现旧现货目录：$spotDir"
  Write-Host "目标目录：$destDir"
  Write-Host "模式：$Mode"

  $files = @()
  foreach ($ext in $Extensions) {
    $pattern = "*.$ext"
    $files += Get-ChildItem -Path $spotDir -File -Filter $pattern -ErrorAction SilentlyContinue
  }

  if ($files.Count -eq 0) {
    Write-Host "spot 目录下未找到可处理文件，跳过。"
    continue
  }

  foreach ($file in $files) {
    $destPath = Join-Path $destDir $file.Name

    if (Test-Path $destPath) {
      # 目标已存在：默认不覆盖，避免把新数据覆盖成旧数据或反之。
      $totalSkipped++
      continue
    }

    try {
      if ($Mode -eq "move") {
        if ($PSCmdlet.ShouldProcess($file.FullName, "Move-Item -> $destPath")) {
          Move-Item -Path $file.FullName -Destination $destPath
        }
      } else {
        if ($PSCmdlet.ShouldProcess($file.FullName, "Copy-Item -> $destPath")) {
          Copy-Item -Path $file.FullName -Destination $destPath
        }
      }
      $totalCopied++
    } catch {
      $totalFailed++
      Write-Host "处理失败：$($file.FullName)"
      Write-Host $_.Exception.Message
    }
  }
}

Write-Host ""
Write-Host "归一化完成：copied/moved=$totalCopied skipped=$totalSkipped failed=$totalFailed"


