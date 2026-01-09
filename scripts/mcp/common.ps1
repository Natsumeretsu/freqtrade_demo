<#
.SYNOPSIS
    MCP 配置脚本公共模块

.DESCRIPTION
    提供 setup_claude.ps1 和 setup_codex.ps1 共用的工具函数，
    包括命令检测、MCP server 注册等。

.NOTES
    此文件不应直接执行，由其他脚本 dot-source 引用。
#>

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Require-Command {
  param(
    [Parameter(Mandatory = $true)]
    [string]$Name,

    [Parameter(Mandatory = $true)]
    [string]$InstallHint
  )

  if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
    throw "未找到命令：$Name。$InstallHint"
  }
}

function Test-Command {
  param(
    [Parameter(Mandatory = $true)]
    [string]$Name
  )

  return [bool](Get-Command $Name -ErrorAction SilentlyContinue)
}

function Convert-PathToPosix {
  param([string]$Path)
  if ([string]::IsNullOrWhiteSpace($Path)) {
    return $Path
  }
  return ($Path -replace "\\", "/")
}

function Convert-EnvPairsToHashtable {
  param([string[]]$EnvPairs)
  $envMap = @{}
  foreach ($pair in ($EnvPairs | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })) {
    $idx = $pair.IndexOf("=")
    if ($idx -le 0) {
      continue
    }
    $k = $pair.Substring(0, $idx).Trim()
    $v = $pair.Substring($idx + 1)
    if (-not [string]::IsNullOrWhiteSpace($k)) {
      $envMap[$k] = $v
    }
  }
  return $envMap
}

function Invoke-UvSync {
  param(
    [Parameter(Mandatory = $true)]
    [string]$ProjectRoot
  )

  if (-not (Test-Command "uv")) {
    throw "未找到命令：uv。请先安装 uv（https://docs.astral.sh/uv/）"
  }

  Push-Location $ProjectRoot
  try {
    if (Test-Path "uv.lock") {
      & uv sync --frozen | Out-Host
      if ($LASTEXITCODE -ne 0) {
        throw ("uv sync --frozen 失败：{0}" -f $ProjectRoot)
      }
      return
    }

    if (Test-Path "pyproject.toml") {
      & uv sync | Out-Host
      if ($LASTEXITCODE -ne 0) {
        throw ("uv sync 失败：{0}" -f $ProjectRoot)
      }
      return
    }

    if (Test-Path "requirements.txt") {
      $venvDir = ".venv"
      & uv venv $venvDir --allow-existing --no-project | Out-Host
      if ($LASTEXITCODE -ne 0) {
        throw ("uv venv 失败：{0}" -f $ProjectRoot)
      }

      $pythonCandidates = @(
        (Join-Path $venvDir "Scripts/python.exe"),
        (Join-Path $venvDir "bin/python")
      )
      $pythonPath = $pythonCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
      if (-not $pythonPath) {
        throw ("未找到虚拟环境 Python：{0}" -f (Join-Path $ProjectRoot $venvDir))
      }

      & uv pip install -r "requirements.txt" -p $pythonPath | Out-Host
      if ($LASTEXITCODE -ne 0) {
        throw ("uv pip install 失败：{0}" -f $ProjectRoot)
      }
      return
    }

    Write-Warning ("未找到 uv.lock / pyproject.toml / requirements.txt，跳过：{0}" -f $ProjectRoot)
  } finally {
    Pop-Location
  }
}

function Get-DefaultCodexHome {
  $codexHome = $env:CODEX_HOME
  if (-not [string]::IsNullOrWhiteSpace($codexHome)) {
    return $codexHome
  }
  $userHome = $env:USERPROFILE
  if ([string]::IsNullOrWhiteSpace($userHome)) {
    return $null
  }
  return (Join-Path $userHome ".codex")
}

function Get-DefaultWolframMcpRepoDir {
  param(
    [Parameter(Mandatory = $true)]
    [string]$CodexHome,
    [string]$OverrideDir
  )
  if (-not [string]::IsNullOrWhiteSpace($OverrideDir)) {
    return $OverrideDir
  }
  if ([string]::IsNullOrWhiteSpace($CodexHome)) {
    return $null
  }
  return (Join-Path $CodexHome "tools/Wolfram-MCP")
}

function Ensure-WolframMcpRepo {
  param(
    [Parameter(Mandatory = $true)]
    [string]$RepoDir,
    [Parameter(Mandatory = $true)]
    [string]$RepoUrl
  )

  if (Test-Path (Join-Path $RepoDir ".git")) {
    if (-not (Test-Command "git")) {
      Write-Warning "未找到 git，无法更新 Wolfram-MCP。"
      return
    }
    Push-Location $RepoDir
    try {
      $dirty = (& git status --porcelain) 2>$null
      if (-not [string]::IsNullOrWhiteSpace($dirty)) {
        Write-Warning ("Wolfram-MCP 有本地改动，跳过更新：{0}" -f $RepoDir)
        return
      }
      & git pull --ff-only | Out-Host
      if ($LASTEXITCODE -ne 0) {
        Write-Warning ("git pull 失败：{0}" -f $RepoDir)
      }
    } finally {
      Pop-Location
    }
    return
  }

  if (-not (Test-Command "git")) {
    Write-Warning "未找到 git，无法克隆 Wolfram-MCP。"
    return
  }

  $parent = Split-Path $RepoDir -Parent
  New-Item -ItemType Directory -Force -Path $parent | Out-Null
  & git clone $RepoUrl $RepoDir | Out-Host
  if ($LASTEXITCODE -ne 0) {
    Write-Warning ("git clone 失败：{0}" -f $RepoUrl)
  }
}

function Resolve-WolframScriptCommand {
  param([string]$InstallDir)

  if (Test-Command "wolframscript") {
    return "wolframscript"
  }
  if (-not [string]::IsNullOrWhiteSpace($InstallDir)) {
    $exe = Join-Path $InstallDir "wolframscript.exe"
    if (Test-Path $exe) { return $exe }
    $noExe = Join-Path $InstallDir "wolframscript"
    if (Test-Path $noExe) { return $noExe }
  }
  return $null
}

function Find-WolframInstallationDirectory {
  $programFiles = $env:ProgramFiles
  if ([string]::IsNullOrWhiteSpace($programFiles)) {
    return $null
  }

  $baseDirs = @(
    (Join-Path $programFiles "Wolfram Research/Wolfram Engine"),
    (Join-Path $programFiles "Wolfram Research/Mathematica")
  )

  $candidates = @()
  foreach ($base in $baseDirs) {
    if (-not (Test-Path $base)) { continue }
    $dirs = Get-ChildItem -Path $base -Directory -ErrorAction SilentlyContinue
    foreach ($dir in $dirs) {
      $exe = Join-Path $dir.FullName "wolframscript.exe"
      if (Test-Path $exe) {
        $candidates += $dir.FullName
      }
    }
  }

  if ($candidates.Count -eq 0) { return $null }

  $best = $candidates | Sort-Object {
    $leaf = Split-Path $_ -Leaf
    try { [Version]$leaf } catch { [Version]"0.0" }
  } -Descending | Select-Object -First 1

  return $best
}

function Resolve-WolframMcpPython {
  param(
    [Parameter(Mandatory = $true)]
    [string]$RepoDir
  )
  $candidates = @(
    (Join-Path $RepoDir ".venv/Scripts/python.exe"),
    (Join-Path $RepoDir ".venv/bin/python")
  )
  return $candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
}
