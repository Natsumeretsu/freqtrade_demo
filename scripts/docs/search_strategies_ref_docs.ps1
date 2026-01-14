<#
.SYNOPSIS
  在离线策略参考库（docs/archive/strategies_ref_docs）中搜索关键词

.DESCRIPTION
  - 默认使用 ripgrep（rg），速度最快
  - 若未安装 rg，则回退到 Select-String（会慢很多）
  - 统一 UTF-8 输出，避免中文 Windows 控制台乱码

.EXAMPLE
  ./scripts/docs/search_strategies_ref_docs.ps1 -Query "momentum"
  ./scripts/docs/search_strategies_ref_docs.ps1 -Query "EMA(" -Regex
  ./scripts/docs/search_strategies_ref_docs.ps1 -Query "1-2-3" -FixedString
#>
[CmdletBinding()]
param(
  [Parameter(Mandatory = $true)][string]$Query,
  [string]$Root = "docs/archive/strategies_ref_docs",
  [switch]$IgnoreCase,
  [switch]$FixedString,
  [switch]$Regex
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

try {
  [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
  $OutputEncoding = [System.Text.Encoding]::UTF8
} catch {
  # ignore
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "../..")).Path
Set-Location $repoRoot

$rootPath = (Resolve-Path $Root -ErrorAction Stop).Path

function Test-Command {
  param([Parameter(Mandatory = $true)][string]$Name)
  return [bool](Get-Command $Name -ErrorAction SilentlyContinue)
}

if (Test-Command "rg") {
  $args = @("-n", "--no-heading", "--color", "never")
  if ($IgnoreCase) { $args += "-i" }
  if ($FixedString) { $args += "-F" }
  if ($Regex) {
    # 默认就是 regex；显式开关仅用于表达意图
  }
  $args += @("--", $Query, $rootPath)
  & rg @args
  exit $LASTEXITCODE
}

Write-Warning "未找到 rg（ripgrep），将回退到 Select-String（速度较慢）。建议安装 rg。"

$pattern = $Query
if ($FixedString) {
  # Select-String 默认是 regex；固定字符串模式用 Regex.Escape
  $pattern = [regex]::Escape($pattern)
}

Get-ChildItem -Recurse -File -Filter "*.md" $rootPath |
  Select-String -Pattern $pattern -SimpleMatch:$FixedString -CaseSensitive:(-not $IgnoreCase) |
  ForEach-Object {
    "{0}:{1}:{2}" -f $_.Path, $_.LineNumber, $_.Line.TrimEnd()
  }

