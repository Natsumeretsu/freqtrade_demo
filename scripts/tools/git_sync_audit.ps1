<#
.SYNOPSIS
  Git 同步自检（避免把缓存/数据/本地配置提交到仓库）

.DESCRIPTION
  这个脚本只做审计与建议输出：
  - 列出“已被 Git 跟踪，但按当前策略不应同步”的路径（例如 data/、config*.json、.claude/settings.local.json）
  - 列出“未跟踪，但建议纳入 Git 同步”的权威层目录（例如 docs/、.serena/memories/、scripts/tools/）
  - 提醒可能导致跨设备差异的 Git 配置（如 core.autocrlf）

  注意：脚本默认不会执行 git rm / git add 等修改操作，只会输出建议命令。

.PARAMETER LargeFileMB
  输出“疑似大文件”的阈值（MB）。默认 25。

.EXAMPLE
  ./scripts/tools/git_sync_audit.ps1

.EXAMPLE
  ./scripts/tools/git_sync_audit.ps1 -LargeFileMB 50
#>
[CmdletBinding()]
param(
  [int]$LargeFileMB = 25
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

function Test-Command {
  param([string]$Name)
  return [bool](Get-Command $Name -ErrorAction SilentlyContinue)
}

if (-not (Test-Command "git")) {
  throw "git not found. 请先安装 Git 并确保 git 在 PATH 中可用。"
}

$repoRoot = (git rev-parse --show-toplevel 2>$null)
if (-not $repoRoot) {
  throw "当前目录不在 Git 仓库内。请在仓库根目录或其子目录执行该脚本。"
}

Set-Location $repoRoot
Write-Host ""
Write-Host "Repo root: $repoRoot"
Write-Host ""

# --- Git 配置提示（跨设备一致性） ---
$autoCrlf = (git config --get core.autocrlf 2>$null)
if ($autoCrlf) {
  if ($autoCrlf -ne "false") {
    Write-Warning "检测到 core.autocrlf=$autoCrlf。为减少跨设备换行差异，建议设置为 false（并依赖 .gitattributes 统一 eol=lf）。"
    Write-Host "建议命令：git config core.autocrlf false"
    Write-Host ""
  }
}

# --- 工作区状态摘要 ---
$statusLines = @(git status --porcelain=v1)
$untracked = @($statusLines | Where-Object { $_.StartsWith("?? ") })
$modified = @($statusLines | Where-Object { -not $_.StartsWith("?? ") })

Write-Host "工作区摘要："
Write-Host "  Modified/Deleted: $($modified.Count)"
Write-Host "  Untracked:        $($untracked.Count)"
Write-Host ""

# --- 规则：哪些路径不应该被 Git 跟踪（但可能历史上已经被跟踪） ---
$shouldNotTrackPrefixes = @(
  "01_freqtrade/data/",
  "01_freqtrade/logs/",
  "01_freqtrade/backtest_results/",
  "01_freqtrade/hyperopt_results/",
  "01_freqtrade/plot/",
  "01_freqtrade/models/",
  "02_qlib_research/qlib_data/",
  "02_qlib_research/models/",
  "artifacts/",
  "temp/",
  ".vibe/",
  "in-memoria-vectors.db/",
  "lancedb/"
)

$shouldNotTrackExact = @(
  ".claude/settings.local.json",
  "scripts/mcp/claude_profiles.local.json"
)

# 根目录运行配置：config*.json（只匹配仓库根目录，允许同步）
function Is-RootConfigJson {
  param([string]$Path)
  if ($Path -match "/") { return $false }
  if ($Path -notmatch "^config.*\.json$") { return $false }
  return $Path -notmatch "\.(local|secrets|private)\.json$"
}

# 根目录密钥覆盖配置：config*.{local|secrets|private}.json（只匹配仓库根目录，不应同步）
function Is-RootConfigSecretJson {
  param([string]$Path)
  if ($Path -match "/") { return $false }
  return $Path -match "^config.*\.(local|secrets|private)\.json$"
}

$trackedFiles = @(git ls-files)

$trackedShouldNotTrack = @()
foreach ($path in $trackedFiles) {
  $normalized = $path -replace "\\", "/"

  if ($shouldNotTrackExact -contains $normalized) {
    $trackedShouldNotTrack += $normalized
    continue
  }

  if (Is-RootConfigSecretJson $normalized) {
    $trackedShouldNotTrack += $normalized
    continue
  }

  foreach ($prefix in $shouldNotTrackPrefixes) {
    if ($normalized.StartsWith($prefix)) {
      $trackedShouldNotTrack += $normalized
      break
    }
  }
}

$trackedShouldNotTrack = @($trackedShouldNotTrack | Sort-Object -Unique)

if ($trackedShouldNotTrack.Count -gt 0) {
  Write-Host "发现“已跟踪但按策略不应同步”的路径："
  $trackedShouldNotTrack | ForEach-Object { Write-Host "  - $_" }
  Write-Host ""
  Write-Host "建议（仅输出，不自动执行）："

  if ($trackedShouldNotTrack | Where-Object { $_.StartsWith("01_freqtrade/data/") }) {
    Write-Host "  git rm --cached -r -- 01_freqtrade/data/"
  }

  if ($trackedShouldNotTrack -contains ".claude/settings.local.json") {
    Write-Host "  git rm --cached -- .claude/settings.local.json"
  }

  $rootSecretConfigs = @($trackedShouldNotTrack | Where-Object { Is-RootConfigSecretJson $_ })
  if ($rootSecretConfigs.Count -gt 0) {
    Write-Host "  git rm --cached -- $($rootSecretConfigs -join ' ')"
  }

  Write-Host ""
} else {
  Write-Host "未发现明显“已跟踪但按策略不应同步”的路径。"
  Write-Host ""
}

# --- 规则：哪些路径通常应该纳入 Git（但当前未跟踪） ---
$recommendedTrackPrefixes = @(
  "docs/",
  ".serena/memories/",
  "04_shared/config/",
  "04_shared/configs/",
  "01_freqtrade/strategies/",
  "scripts/tools/",
  "scripts/lib/",
  "scripts/mcp/"
)

$recommendedTrackExact = @(
  "in-memoria.db"
)

$untrackedRecommended = @()
foreach ($line in $untracked) {
  $p = $line.Substring(3).Trim()
  $p = $p -replace "\\", "/"

  if ($recommendedTrackExact -contains $p) {
    $untrackedRecommended += $p
    continue
  }

  if (Is-RootConfigJson $p) {
    $untrackedRecommended += $p
    continue
  }

  foreach ($prefix in $recommendedTrackPrefixes) {
    if ($p.StartsWith($prefix)) {
      $untrackedRecommended += $p
      break
    }
  }
}

$untrackedRecommended = @($untrackedRecommended | Sort-Object -Unique)

if ($untrackedRecommended.Count -gt 0) {
  Write-Host "发现“未跟踪但建议纳入 Git 同步”的权威层路径："
  $untrackedRecommended | ForEach-Object { Write-Host "  - $_" }
  Write-Host ""
  Write-Host "建议（仅输出，不自动执行）："
  Write-Host "  git add -- $($untrackedRecommended -join ' ')"
  Write-Host ""
}

# --- 大文件提示（仅对已跟踪文件统计） ---
$largeThresholdBytes = [int64]$LargeFileMB * 1024 * 1024
$largeTracked = @()
foreach ($path in $trackedFiles) {
  $fsPath = Join-Path $repoRoot $path
  if (-not (Test-Path $fsPath)) { continue }
  $item = Get-Item $fsPath -ErrorAction SilentlyContinue
  if (-not $item) { continue }
  if ($item.PSIsContainer) { continue }
  if ($item.Length -ge $largeThresholdBytes) {
    $largeTracked += [pscustomobject]@{
      Path = ($path -replace "\\", "/")
      SizeMB = [math]::Round($item.Length / 1MB, 1)
    }
  }
}

if ($largeTracked.Count -gt 0) {
  Write-Host "疑似大文件（已跟踪，>= $LargeFileMB MB）："
  $largeTracked |
    Sort-Object SizeMB -Descending |
    Select-Object -First 20 |
    ForEach-Object { Write-Host "  - $($_.Path) ($($_.SizeMB) MB)" }
  Write-Host ""
  Write-Host "提示：若这些是缓存/产物，优先取消跟踪并加入 .gitignore；若必须版本化，考虑 Git LFS。"
  Write-Host ""
}

function Test-ConfigSecrets {
  param([string]$ConfigPath)

  try {
    $raw = Get-Content -Raw -Encoding UTF8 $ConfigPath
    $cfg = $raw | ConvertFrom-Json -ErrorAction Stop
  } catch {
    Write-Warning "无法解析 JSON：$ConfigPath（已跳过密钥检查）"
    return
  }

  $warnings = @()
  try {
    if ($cfg.exchange) {
      if ($cfg.exchange.key -and $cfg.exchange.key.ToString().Trim().Length -gt 0) { $warnings += "exchange.key" }
      if ($cfg.exchange.secret -and $cfg.exchange.secret.ToString().Trim().Length -gt 0) { $warnings += "exchange.secret" }
      if ($cfg.exchange.password -and $cfg.exchange.password.ToString().Trim().Length -gt 0) { $warnings += "exchange.password" }
    }
  } catch { }

  try {
    if ($cfg.telegram) {
      if ($cfg.telegram.token -and $cfg.telegram.token.ToString().Trim().Length -gt 0) { $warnings += "telegram.token" }
    }
  } catch { }

  if ($warnings.Count -gt 0) {
    Write-Warning "检测到可能的密钥字段非空（请勿提交）：$($warnings -join ', ') -> $ConfigPath"
  }
}

$rootConfigFiles = @(
  Get-ChildItem -Path $repoRoot -File -Filter "config*.json" -ErrorAction SilentlyContinue |
    Where-Object { Is-RootConfigJson $_.Name } |
    Select-Object -ExpandProperty FullName
)

if ($rootConfigFiles.Count -gt 0) {
  Write-Host "根目录 config*.json 密钥自检（不输出值，仅告警）："
  foreach ($cfgPath in $rootConfigFiles) {
    Test-ConfigSecrets $cfgPath
  }
  Write-Host ""
}

Write-Host "完成。"







