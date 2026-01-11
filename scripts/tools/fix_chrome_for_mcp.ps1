<#
.SYNOPSIS
  修复 Chrome 缺失导致的 MCP 浏览器工具不可用（无需管理员权限）

.DESCRIPTION
  适用场景：
  - 系统无法安装 Google Chrome（权限受限/企业策略等）
  - `playwright_mcp` / `chrome_devtools_mcp` 等工具需要可探测的 `chrome.exe`

  方案：
  1) 使用 Playwright 下载 Chromium（写入 %LOCALAPPDATA%/ms-playwright/）
  2) 把包含 chrome.exe 的目录复制到用户级路径：
     %LOCALAPPDATA%/Google/Chrome/Application/chrome.exe

.EXAMPLE
  ./scripts/tools/fix_chrome_for_mcp.ps1
  ./scripts/tools/fix_chrome_for_mcp.ps1 -WhatIf
#>
[CmdletBinding(SupportsShouldProcess = $true, ConfirmImpact = "Low")]
param()

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Resolve-ChromeExeCandidates {
  $candidates = @()

  if ($env:LOCALAPPDATA) {
    $candidates += (Join-Path $env:LOCALAPPDATA "Google/Chrome/Application/chrome.exe")
  }
  if ($env:PROGRAMFILES) {
    $candidates += (Join-Path $env:PROGRAMFILES "Google/Chrome/Application/chrome.exe")
  }
  $programFilesX86 = ${env:ProgramFiles(x86)}
  if ($programFilesX86) {
    $candidates += (Join-Path $programFilesX86 "Google/Chrome/Application/chrome.exe")
  }

  return $candidates | Where-Object { -not [string]::IsNullOrWhiteSpace($_) } | Select-Object -Unique
}

$existing = Resolve-ChromeExeCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if ($existing) {
  Write-Host ("已检测到 Chrome：{0}" -f $existing)
  Write-Host "无需修复。"
  return
}

if (-not (Get-Command "npx" -ErrorAction SilentlyContinue)) {
  throw "未找到 npx。请先安装 Node.js（包含 npx）。"
}

Write-Host "未检测到可用的 chrome.exe，开始使用 Playwright 安装 Chromium..."

if ($WhatIfPreference) {
  $pwRootPreview = Join-Path $env:LOCALAPPDATA "ms-playwright"
  $dstDirPreview = Join-Path $env:LOCALAPPDATA "Google/Chrome/Application"
  $PSCmdlet.ShouldProcess("Playwright Chromium", "下载（npx playwright install chromium）") | Out-Null
  $PSCmdlet.ShouldProcess($dstDirPreview, "复制 Chromium 到用户级 Chrome 路径") | Out-Null
  Write-Host ("WhatIf 预览完成。下载目录：{0}" -f $pwRootPreview)
  return
}

if ($PSCmdlet.ShouldProcess("Playwright Chromium", "下载（npx playwright install chromium）")) {
  & npx playwright install chromium | Out-Host
  if ($LASTEXITCODE -ne 0) {
    throw "Playwright Chromium 下载失败（npx playwright install chromium）。"
  }
}

$pwRoot = Join-Path $env:LOCALAPPDATA "ms-playwright"
if (-not (Test-Path $pwRoot)) {
  throw ("未找到 Playwright 安装目录：{0}" -f $pwRoot)
}

$chromiumRoot = Get-ChildItem -Path $pwRoot -Directory -Filter "chromium-*" |
  Sort-Object -Property Name -Descending |
  Select-Object -First 1

if (-not $chromiumRoot) {
  throw ("未找到 Playwright Chromium 目录（chromium-*）：{0}" -f $pwRoot)
}

$chromeExe = Get-ChildItem -Path $chromiumRoot.FullName -Recurse -File -Filter "chrome.exe" |
  Select-Object -First 1

if (-not $chromeExe) {
  throw ("在 Playwright Chromium 目录中未找到 chrome.exe：{0}" -f $chromiumRoot.FullName)
}

$srcDir = Split-Path -Parent $chromeExe.FullName
$dstDir = Join-Path $env:LOCALAPPDATA "Google/Chrome/Application"

Write-Host ("源目录：{0}" -f $srcDir)
Write-Host ("目标目录：{0}" -f $dstDir)

if ($PSCmdlet.ShouldProcess($dstDir, "复制 Chromium 到用户级 Chrome 路径")) {
  New-Item -ItemType Directory -Force -Path $dstDir | Out-Null
  Copy-Item -Path (Join-Path $srcDir "*") -Destination $dstDir -Recurse -Force
}

$final = Join-Path $dstDir "chrome.exe"
if (-not (Test-Path $final)) {
  throw ("复制完成但仍未找到：{0}" -f $final)
}

Write-Host ("修复完成：{0}" -f $final)

