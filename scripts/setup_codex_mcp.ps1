[CmdletBinding(SupportsShouldProcess = $true, ConfirmImpact = "Medium")]
param(
  [switch]$Force,

  [ValidateSet("auto", "paclet", "python", "skip")]
  [string]$WolframMode = "python",

  [string]$WolframMcpScriptPath,

  [string]$WolframMcpRepoUrl = "https://github.com/Natsumeretsu/Wolfram-MCP.git",

  [string]$WolframMcpRepoDir,

  [string]$WolframInstallationDirectory,

  [switch]$BootstrapWolframPython
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $repoRoot

$codexHome = $env:CODEX_HOME
if ([string]::IsNullOrWhiteSpace($codexHome)) {
  $userHome = $env:USERPROFILE
  if (-not [string]::IsNullOrWhiteSpace($userHome)) {
    $codexHome = Join-Path $userHome ".codex"
  }
}

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

function Test-McpServerExists {
  param(
    [Parameter(Mandatory = $true)]
    [string]$Name
  )

  & codex mcp get $Name --json *> $null
  return ($LASTEXITCODE -eq 0)
}

function Invoke-CodexMcpRemove {
  param(
    [Parameter(Mandatory = $true)]
    [string]$Name
  )

  if (-not $PSCmdlet.ShouldProcess($Name, "codex mcp remove")) {
    return
  }

  & codex mcp remove $Name | Out-Host
  if ($LASTEXITCODE -ne 0) {
    throw "codex mcp remove 失败：$Name"
  }
}

function Invoke-CodexMcpAdd {
  param(
    [Parameter(Mandatory = $true)]
    [string]$Name,

    [Parameter(Mandatory = $true)]
    [string]$Command,

    [Parameter(Mandatory = $true)]
    [string[]]$Args,

    [string[]]$Env = @()
  )

  $cmdArgs = @("mcp", "add")
  foreach ($pair in $Env) {
    $cmdArgs += @("--env", $pair)
  }

  $cmdArgs += @($Name, "--", $Command) + $Args

  if (-not $PSCmdlet.ShouldProcess($Name, ("codex {0}" -f ($cmdArgs -join " ")))) {
    return
  }

  & codex @cmdArgs | Out-Host
  if ($LASTEXITCODE -ne 0) {
    throw "codex mcp add 失败：$Name"
  }
}

function Invoke-UvSync {
  param(
    [Parameter(Mandatory = $true)]
    [string]$ProjectRoot
  )

  if (-not (Test-Command "uv")) {
    throw "未找到命令：uv。请先安装 uv（https://docs.astral.sh/uv/）"
  }

  if (-not $PSCmdlet.ShouldProcess($ProjectRoot, "初始化/同步 Python 依赖（uv）")) {
    return
  }

  Push-Location $ProjectRoot
  try {
    if (Test-Path "uv.lock") {
      & uv sync --frozen | Out-Host
      if ($LASTEXITCODE -ne 0) {
        throw ("uv sync --frozen 失败：{0}" -f $ProjectRoot)
      }

      return
    } elseif (Test-Path "pyproject.toml") {
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
        throw ("未找到虚拟环境 Python，可尝试删除并重建：{0}" -f (Join-Path $ProjectRoot $venvDir))
      }

      & uv pip install -r "requirements.txt" -p $pythonPath | Out-Host
      if ($LASTEXITCODE -ne 0) {
        throw ("uv pip install 失败：{0}" -f $ProjectRoot)
      }

      return
    }

    Write-Warning ("未找到 uv.lock / pyproject.toml / requirements.txt，跳过依赖初始化：{0}" -f $ProjectRoot)
  } finally {
    Pop-Location
  }
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

function Get-DefaultWolframMcpScriptCandidates {
  param(
    [Parameter(Mandatory = $true)]
    [string]$CodexHome,

    [string]$WolframMcpRepoDir
  )

  $repoDir = Get-DefaultWolframMcpRepoDir -CodexHome $CodexHome -OverrideDir $WolframMcpRepoDir
  if ([string]::IsNullOrWhiteSpace($repoDir)) {
    return @()
  }

  return @(
    (Join-Path $repoDir "wolfram_mcp_server.py")
  )
}

function Ensure-WolframMcpRepo {
  param(
    [Parameter(Mandatory = $true)]
    [string]$RepoDir,

    [Parameter(Mandatory = $true)]
    [string]$RepoUrl
  )

  if (-not (Test-Command "git")) {
    Write-Warning "未找到命令：git，无法自动克隆/更新 Wolfram-MCP（Python 模式）。你可以安装 Git，或手动克隆后用 -WolframMcpScriptPath 指定脚本路径。"
    return
  }

  if (Test-Path $RepoDir) {
    if (-not (Test-Path (Join-Path $RepoDir ".git"))) {
      Write-Warning ("Wolfram-MCP 目录已存在但不是 Git 仓库，跳过自动更新：{0}" -f $RepoDir)
      return
    }

    $dirty = & git -C $RepoDir status --porcelain
    if ($LASTEXITCODE -ne 0) {
      Write-Warning ("无法读取 Wolfram-MCP 仓库状态，跳过自动更新：{0}" -f $RepoDir)
      return
    }

    if (-not [string]::IsNullOrWhiteSpace($dirty)) {
      Write-Warning ("检测到 Wolfram-MCP 仓库存在本地改动，跳过自动更新：{0}" -f $RepoDir)
      return
    }

    if (-not $PSCmdlet.ShouldProcess($RepoDir, "更新 Wolfram-MCP 仓库（git pull --ff-only）")) {
      return
    }

    & git -C $RepoDir pull --ff-only | Out-Host
    if ($LASTEXITCODE -ne 0) {
      Write-Warning ("git pull --ff-only 失败，继续使用现有版本：{0}" -f $RepoDir)
    }

    return
  }

  $parent = Split-Path $RepoDir -Parent
  if (-not $PSCmdlet.ShouldProcess($RepoDir, ("克隆 Wolfram-MCP（{0}）" -f $RepoUrl))) {
    return
  }

  New-Item -ItemType Directory -Force -Path $parent | Out-Null
  & git clone $RepoUrl $RepoDir | Out-Host
  if ($LASTEXITCODE -ne 0) {
    Write-Warning ("git clone 失败：{0}" -f $RepoUrl)
  }
}

function Resolve-WolframMcpPythonCommand {
  param(
    [Parameter(Mandatory = $true)]
    [string]$ServerScriptPath
  )

  $rootDir = Split-Path $ServerScriptPath -Parent
  $pythonCandidates = @(
    (Join-Path $rootDir ".venv/Scripts/python.exe"),
    (Join-Path $rootDir ".venv/bin/python")
  )
  $venvPython = $pythonCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
  if ($venvPython) {
    return $venvPython
  }

  return "python"
}

function Resolve-WolframScriptCommand {
  param(
    [string]$InstallDir
  )

  if (Test-Command "wolframscript") {
    return "wolframscript"
  }

  if (-not [string]::IsNullOrWhiteSpace($InstallDir)) {
    $candidateExe = Join-Path $InstallDir "wolframscript.exe"
    if (Test-Path $candidateExe) {
      return $candidateExe
    }

    $candidateNoExe = Join-Path $InstallDir "wolframscript"
    if (Test-Path $candidateNoExe) {
      return $candidateNoExe
    }
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
    if (-not (Test-Path $base)) {
      continue
    }

    $dirs = Get-ChildItem -Path $base -Directory -ErrorAction SilentlyContinue
    foreach ($dir in $dirs) {
      $exe = Join-Path $dir.FullName "wolframscript.exe"
      if (Test-Path $exe) {
        $candidates += $dir.FullName
      }
    }
  }

  if ($candidates.Count -eq 0) {
    return $null
  }

  $best = $candidates | Sort-Object {
    $leaf = Split-Path $_ -Leaf
    try {
      [Version]$leaf
    } catch {
      [Version]"0.0"
    }
  } -Descending | Select-Object -First 1

  return $best
}

Write-Host "开始初始化 Codex MCP（仅影响本机 ~/.codex/config.toml）..."
Write-Host ("Repo root: {0}" -f $repoRoot)
if (-not [string]::IsNullOrWhiteSpace($codexHome)) {
  Write-Host ("Codex home: {0}" -f $codexHome)
}

Require-Command -Name "codex" -InstallHint "请先安装 Codex CLI：npm i -g @openai/codex"
Require-Command -Name "npx" -InstallHint "请先安装 Node.js（需包含 npx）"
Require-Command -Name "uvx" -InstallHint "请先安装 uv（需包含 uvx），并确保 uvx 在 PATH 中"

$servers = @(
  @{
    Name = "context7"
    Command = "npx"
    Args = @("-y", "@upstash/context7-mcp@1.0.31")
    Note = "Context7（技术文档）"
  },
  @{
    Name = "chrome_devtools_mcp"
    Command = "npx"
    Args = @("-y", "chrome-devtools-mcp@0.12.1")
    Note = "Chrome DevTools MCP"
  },
  @{
    Name = "markitdown"
    Command = "uvx"
    Args = @("markitdown-mcp==0.0.1a4")
    Note = "MarkItDown（文档/网页转 Markdown）"
  },
  @{
    Name = "playwright_mcp"
    Command = "npx"
    Args = @("-y", "@playwright/mcp@latest")
    Note = "Playwright MCP"
  }
)

$resolvedWolframMode = $WolframMode
if ($resolvedWolframMode -eq "auto") {
  if (-not [string]::IsNullOrWhiteSpace($WolframMcpScriptPath)) {
    $resolvedWolframMode = "python"
  } else {
    $candidate = Get-DefaultWolframMcpScriptCandidates -CodexHome $codexHome -WolframMcpRepoDir $WolframMcpRepoDir | Where-Object { Test-Path $_ } | Select-Object -First 1
    if (-not $candidate) {
      $repoDir = Get-DefaultWolframMcpRepoDir -CodexHome $codexHome -OverrideDir $WolframMcpRepoDir
      if (-not [string]::IsNullOrWhiteSpace($repoDir)) {
        Ensure-WolframMcpRepo -RepoDir $repoDir -RepoUrl $WolframMcpRepoUrl
        $candidate = Get-DefaultWolframMcpScriptCandidates -CodexHome $codexHome -WolframMcpRepoDir $repoDir | Where-Object { Test-Path $_ } | Select-Object -First 1
      }
    }
    if ($candidate) {
      $WolframMcpScriptPath = $candidate
      $resolvedWolframMode = "python"
    } else {
      $installDir = $WolframInstallationDirectory
      if ([string]::IsNullOrWhiteSpace($installDir)) {
        $installDir = $env:WOLFRAM_INSTALLATION_DIRECTORY
      }
      if ([string]::IsNullOrWhiteSpace($installDir)) {
        $installDir = Find-WolframInstallationDirectory
      }

      if (Resolve-WolframScriptCommand -InstallDir $installDir) {
        $resolvedWolframMode = "paclet"
      } else {
        $resolvedWolframMode = "skip"
      }
    }
  }
}

if ($resolvedWolframMode -eq "paclet") {
  $wolframEnv = @()

  $installDir = $WolframInstallationDirectory
  if ([string]::IsNullOrWhiteSpace($installDir)) {
    $installDir = $env:WOLFRAM_INSTALLATION_DIRECTORY
  }
  if ([string]::IsNullOrWhiteSpace($installDir)) {
    $installDir = Find-WolframInstallationDirectory
  }

  $wolframScriptCmd = Resolve-WolframScriptCommand -InstallDir $installDir
  if (-not $wolframScriptCmd) {
    Write-Warning "未找到 wolframscript（可通过 PATH 或 -WolframInstallationDirectory / 环境变量 WOLFRAM_INSTALLATION_DIRECTORY 指定安装目录）。跳过 Wolfram MCP（Paclet 模式）。"
  } else {
    if (-not [string]::IsNullOrWhiteSpace($installDir)) {
      $wolframEnv += "WOLFRAM_INSTALLATION_DIRECTORY=$installDir"
    }

    $servers += @{
      Name = "wolfram"
      Command = $wolframScriptCmd
      Args = @(
        "-code",
        'Needs["RickHennigan`MCPServer`"];LaunchMCPServer[]'
      )
      Env = $wolframEnv
      Note = "Wolfram MCP（wolframscript + MCPServer Paclet）"
    }
  }
} elseif ($resolvedWolframMode -eq "python") {
  if ([string]::IsNullOrWhiteSpace($WolframMcpScriptPath)) {
    $repoDir = Get-DefaultWolframMcpRepoDir -CodexHome $codexHome -OverrideDir $WolframMcpRepoDir
    if (-not [string]::IsNullOrWhiteSpace($repoDir)) {
      Ensure-WolframMcpRepo -RepoDir $repoDir -RepoUrl $WolframMcpRepoUrl
      $WolframMcpScriptPath = Join-Path $repoDir "wolfram_mcp_server.py"
    }
  }

  if ([string]::IsNullOrWhiteSpace($WolframMcpScriptPath)) {
    Write-Warning "未提供 -WolframMcpScriptPath，且无法解析默认 Wolfram-MCP 路径（~/.codex/tools/Wolfram-MCP），跳过 Wolfram MCP（Python 模式）。"
  } elseif (-not (Test-Path $WolframMcpScriptPath)) {
    Write-Warning ("指定的 Wolfram MCP 脚本不存在，跳过：{0}" -f $WolframMcpScriptPath)
  } else {
    $wolframScript = (Resolve-Path $WolframMcpScriptPath).Path
    $wolframProjectRoot = Split-Path $wolframScript -Parent

    $venvPython = @(
      (Join-Path $wolframProjectRoot ".venv/Scripts/python.exe"),
      (Join-Path $wolframProjectRoot ".venv/bin/python")
    ) | Where-Object { Test-Path $_ } | Select-Object -First 1

    if ($BootstrapWolframPython -or -not $venvPython) {
      Invoke-UvSync -ProjectRoot $wolframProjectRoot

      $venvPython = @(
        (Join-Path $wolframProjectRoot ".venv/Scripts/python.exe"),
        (Join-Path $wolframProjectRoot ".venv/bin/python")
      ) | Where-Object { Test-Path $_ } | Select-Object -First 1
    }

    if (-not $venvPython) {
      if ($WhatIfPreference) {
        Write-Host "WhatIf: 未实际创建 .venv，Wolfram MCP 将暂以系统 python 作为预览结果。"
        $venvPython = Resolve-WolframMcpPythonCommand -ServerScriptPath $wolframScript
      } else {
        throw ("Wolfram MCP（Python 模式）初始化失败：未找到 {0} 下的 .venv Python。" -f $wolframProjectRoot)
      }
    }

    $pythonCmd = $venvPython
    $wolframEnv = @(
      "PYTHONUTF8=1",
      "PYTHONIOENCODING=utf-8"
    )

    $installDir = $WolframInstallationDirectory
    if ([string]::IsNullOrWhiteSpace($installDir)) {
      $installDir = $env:WOLFRAM_INSTALLATION_DIRECTORY
    }
    if ([string]::IsNullOrWhiteSpace($installDir)) {
      $installDir = Find-WolframInstallationDirectory
    }
    if (-not [string]::IsNullOrWhiteSpace($installDir)) {
      $wolframEnv += "WOLFRAM_INSTALLATION_DIRECTORY=$installDir"
    }

    $wolframScriptPath = $null
    if (Test-Command "wolframscript") {
      $wolframScriptPath = (Get-Command "wolframscript").Source
    } elseif (-not [string]::IsNullOrWhiteSpace($installDir)) {
      $candidateExe = Join-Path $installDir "wolframscript.exe"
      if (Test-Path $candidateExe) {
        $wolframScriptPath = $candidateExe
      }
    }
    if (-not [string]::IsNullOrWhiteSpace($wolframScriptPath)) {
      $wolframEnv += "WOLFRAMSCRIPT_PATH=$wolframScriptPath"
      $wolframEnv += "WOLFRAM_SCRIPT_PATH=$wolframScriptPath"
    }

    $servers += @{
      Name = "wolfram"
      Command = $pythonCmd
      Args = @($wolframScript)
      Env = $wolframEnv
      Note = "Wolfram MCP（Python 服务端脚本）"
    }
  }
}

foreach ($server in $servers) {
  $name = $server.Name

  if (-not (Get-Command $server.Command -ErrorAction SilentlyContinue)) {
    Write-Host ("未找到命令，跳过：{0}（需要 {1}）。" -f $name, $server.Command)
    continue
  }


  if (Test-McpServerExists -Name $name) {
    if ($Force) {
      Write-Host ("已存在，按 -Force 重新创建：{0}（{1}）" -f $name, $server.Note)
      Invoke-CodexMcpRemove -Name $name
    } else {
      Write-Host ("已存在，跳过：{0}（{1}）。如需覆盖请加 -Force。" -f $name, $server.Note)
      continue
    }
  } else {
    Write-Host ("添加：{0}（{1}）" -f $name, $server.Note)
  }

  $envPairs = @()
  if ($server.ContainsKey("Env") -and $server.Env) {
    $envPairs = [string[]]$server.Env
  }

  Invoke-CodexMcpAdd -Name $name -Command $server.Command -Args $server.Args -Env $envPairs
}

Write-Host "完成。可运行：codex mcp list"
Write-Host "提示：首次使用 npx/uvx 可能会联网下载依赖，请自行评估与确认。"
