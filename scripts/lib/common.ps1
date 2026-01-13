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
    $userHome = $env:HOME
  }
  if (
    [string]::IsNullOrWhiteSpace($userHome) -and
    (-not [string]::IsNullOrWhiteSpace($env:HOMEDRIVE)) -and
    (-not [string]::IsNullOrWhiteSpace($env:HOMEPATH))
  ) {
    $userHome = (Join-Path $env:HOMEDRIVE $env:HOMEPATH)
  }
  if ([string]::IsNullOrWhiteSpace($userHome)) { return $null }
  return (Join-Path $userHome ".codex")
}

function Get-DefaultLocalRagCacheDir {
  param([string]$OverrideDir)

  if (-not [string]::IsNullOrWhiteSpace($OverrideDir)) {
    return (Convert-PathToPosix $OverrideDir)
  }

  $codexHome = Get-DefaultCodexHome
  if (-not [string]::IsNullOrWhiteSpace($codexHome)) {
    return (Convert-PathToPosix (Join-Path $codexHome "cache/local-rag/models"))
  }

  if (-not [string]::IsNullOrWhiteSpace($env:LOCALAPPDATA)) {
    return (Convert-PathToPosix (Join-Path $env:LOCALAPPDATA "codex/cache/local-rag/models"))
  }

  return $null
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

function Initialize-WolframMcpRepo {
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

function Get-DefaultMcpServers {
  param(
    [string]$LocalRagCacheDir,
    [string]$LocalRagModelName
  )

  $defaultModelName = "Xenova/all-MiniLM-L6-v2"
  $modelName = $LocalRagModelName
  if ([string]::IsNullOrWhiteSpace($modelName)) {
    $modelName = $defaultModelName
  } else {
    $modelName = $modelName.Trim()
  }

  $cacheDir = Get-DefaultLocalRagCacheDir -OverrideDir $LocalRagCacheDir
  if ([string]::IsNullOrWhiteSpace($cacheDir)) {
    $cacheDir = ".vibe/local-rag/models"
  }

  $localRagEnv = @(
    "npm_config_cache=.vibe/npm-cache",
    "BASE_DIR=docs",
    "DB_PATH=.vibe/local-rag/lancedb",
    ("CACHE_DIR={0}" -f $cacheDir),
    ("MODEL_NAME={0}" -f $modelName),
    "RAG_HYBRID_WEIGHT=0.7",
    "RAG_GROUPING=similar"
  )

  return @(
    @{ Name = "context7"; Command = "cmd"; Args = @("/c", "npx", "-y", "@upstash/context7-mcp@2.1.0"); Env = @("npm_config_cache=.vibe/npm-cache"); Note = "Context7" },
    @{ Name = "chrome_devtools_mcp"; Command = "cmd"; Args = @("/c", "npx", "-y", "chrome-devtools-mcp@0.12.1"); Env = @("npm_config_cache=.vibe/npm-cache"); Note = "Chrome DevTools" },
    @{ Name = "in_memoria"; Command = "cmd"; Args = @("/c", "npx", "-y", "in-memoria@0.6.0", "server"); Env = @("npm_config_cache=.vibe/npm-cache"); Note = "In Memoria (项目大脑：代码画像/任务上下文/跨会话记忆)" },
    @{ Name = "local_rag"; Command = "cmd"; Args = @("/c", "npx", "-y", "mcp-local-rag@0.5.3"); Env = $localRagEnv; Note = "Local RAG (资料索引加速器：文档/网页/PDF 语义召回 + 关键词 boost)" },
    @{ Name = "vbrain"; Command = "python"; Args = @("-X", "utf8", "scripts/tools/vbrain_mcp_server.py"); Env = @("PYTHONUTF8=1", "PYTHONIOENCODING=utf-8"); Note = "vbrain (工作流编排：统一入口 + 闭环自动化)" },
    @{ Name = "markitdown"; Command = "uvx"; Args = @("--python", "3.11", "markitdown-mcp==0.0.1a4"); Note = "MarkItDown" },
    @{ Name = "playwright_mcp"; Command = "cmd"; Args = @("/c", "npx", "-y", "@playwright/mcp@0.0.55"); Env = @("npm_config_cache=.vibe/npm-cache"); Note = "Playwright" },
    @{ Name = "serena"; Command = "uvx"; Args = @("--from", "git+https://github.com/oraios/serena", "serena", "start-mcp-server", "--project-from-cwd", "--enable-web-dashboard", "false"); Note = "Serena" }
  )
}

function Get-WolframMcpConfig {
  param(
    [string]$Mode = "python",
    [string]$ScriptPath,
    [string]$RepoUrl = "https://github.com/Natsumeretsu/Wolfram-MCP.git",
    [string]$RepoDir,
    [string]$InstallDir,
    [switch]$Bootstrap
  )

  $codexHome = Get-DefaultCodexHome
  $resolvedMode = $Mode

  # auto 模式检测
  if ($resolvedMode -eq "auto") {
    if (-not [string]::IsNullOrWhiteSpace($ScriptPath)) {
      $resolvedMode = "python"
    } else {
      $repoDir = Get-DefaultWolframMcpRepoDir -CodexHome $codexHome -OverrideDir $RepoDir
      $candidate = $null
      if (-not [string]::IsNullOrWhiteSpace($repoDir)) {
        $candidatePath = Join-Path $repoDir "wolfram_mcp_server.py"
        if (Test-Path $candidatePath) { $candidate = $candidatePath }
      }
      if ($candidate) {
        $ScriptPath = $candidate
        $resolvedMode = "python"
      } else {
        $dir = $InstallDir
        if ([string]::IsNullOrWhiteSpace($dir)) { $dir = $env:WOLFRAM_INSTALLATION_DIRECTORY }
        if ([string]::IsNullOrWhiteSpace($dir)) { $dir = Find-WolframInstallationDirectory }
        if (Resolve-WolframScriptCommand -InstallDir $dir) {
          $resolvedMode = "paclet"
        } else {
          $resolvedMode = "skip"
        }
      }
    }
  }

  if ($resolvedMode -eq "skip") { return $null }

  # paclet 模式
  if ($resolvedMode -eq "paclet") {
    $dir = $InstallDir
    if ([string]::IsNullOrWhiteSpace($dir)) { $dir = $env:WOLFRAM_INSTALLATION_DIRECTORY }
    if ([string]::IsNullOrWhiteSpace($dir)) { $dir = Find-WolframInstallationDirectory }
    $wsCmd = Resolve-WolframScriptCommand -InstallDir $dir
    if (-not $wsCmd) { return $null }
    $env = @()
    if (-not [string]::IsNullOrWhiteSpace($dir)) { $env += "WOLFRAM_INSTALLATION_DIRECTORY=$dir" }
    return @{
      Name = "wolfram"; Command = $wsCmd
      Args = @("-code", 'Needs["RickHennigan`MCPServer`"];LaunchMCPServer[]')
      Env = $env; Note = "Wolfram (Paclet)"
    }
  }

  # python 模式
  if ($resolvedMode -eq "python") {
    $repoDir = Get-DefaultWolframMcpRepoDir -CodexHome $codexHome -OverrideDir $RepoDir
    if ([string]::IsNullOrWhiteSpace($ScriptPath) -and -not [string]::IsNullOrWhiteSpace($repoDir)) {
      Initialize-WolframMcpRepo -RepoDir $repoDir -RepoUrl $RepoUrl
      $ScriptPath = Join-Path $repoDir "wolfram_mcp_server.py"
    }
    if ([string]::IsNullOrWhiteSpace($ScriptPath) -or -not (Test-Path $ScriptPath)) { return $null }

    $script = (Resolve-Path $ScriptPath).Path
    $projectRoot = Split-Path $script -Parent
    $venvPython = Resolve-WolframMcpPython -RepoDir $projectRoot

    if ($Bootstrap -or -not $venvPython) {
      Invoke-UvSync -ProjectRoot $projectRoot
      $venvPython = Resolve-WolframMcpPython -RepoDir $projectRoot
    }
    if (-not $venvPython) { return $null }

    $env = @("PYTHONUTF8=1", "PYTHONIOENCODING=utf-8")
    $dir = Find-WolframInstallationDirectory
    if ($dir) { $env += "WOLFRAM_INSTALLATION_DIRECTORY=$dir" }
    $wsCmd = Resolve-WolframScriptCommand -InstallDir $dir
    if ($wsCmd -and $wsCmd -ne "wolframscript") { $env += "WOLFRAMSCRIPT_PATH=$wsCmd" }

    return @{
      Name = "wolfram"; Command = $venvPython
      Args = @($script); Env = $env; Note = "Wolfram (Python)"
    }
  }

  return $null
}
