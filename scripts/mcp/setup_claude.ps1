<#
.SYNOPSIS
    一键配置 Claude Code CLI 的 MCP servers

.DESCRIPTION
    为 Claude Code 配置常用 MCP：Serena / Context7 / MarkItDown /
    Playwright / Chrome DevTools / Wolfram / GitHub。

.PARAMETER Force
    覆盖已存在的同名 MCP server 配置

.PARAMETER Scope
    配置作用域：user / local / project

.EXAMPLE
    .\setup_claude.ps1
    .\setup_claude.ps1 -WhatIf
    .\setup_claude.ps1 -Force
#>
[CmdletBinding(SupportsShouldProcess = $true, ConfirmImpact = "Low")]
param(
  [switch]$Force,

  [ValidateSet("user", "local", "project")]
  [string]$Scope = "user",

  [ValidateSet("auto", "paclet", "python", "skip")]
  [string]$WolframMode = "python",

  [string]$WolframMcpScriptPath,
  [string]$WolframMcpRepoUrl = "https://github.com/Natsumeretsu/Wolfram-MCP.git",
  [string]$WolframMcpRepoDir,
  [string]$WolframInstallationDirectory,
  [switch]$BootstrapWolframPython
)

# 加载公共模块
. (Join-Path $PSScriptRoot "common.ps1")

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "../..")).Path
Push-Location $repoRoot

try {
  Write-Host "开始初始化 Claude MCP..."
  Write-Host ("Scope: {0}" -f $Scope)

  Require-Command -Name "claude" -InstallHint "请先安装 Claude Code CLI"
  Require-Command -Name "npx" -InstallHint "请先安装 Node.js"
  Require-Command -Name "uvx" -InstallHint "请先安装 uv"

  # Claude 专用函数
  function Test-ClaudeMcpServerExists {
    param([string]$Name)
    & claude mcp get $Name *> $null
    return ($LASTEXITCODE -eq 0)
  }

  function Invoke-ClaudeMcpRemove {
    param([string]$Name, [string]$Scope)
    & claude mcp remove --scope $Scope $Name | Out-Host
    if ($LASTEXITCODE -ne 0) { throw "claude mcp remove 失败：$Name" }
  }

  function Invoke-ClaudeMcpAddJson {
    param([string]$Name, [hashtable]$Payload, [string]$Scope)
    $json = ($Payload | ConvertTo-Json -Compress -Depth 20)
    & claude mcp add-json --scope $Scope $Name $json | Out-Host
    if ($LASTEXITCODE -ne 0) { throw "claude mcp add-json 失败：$Name" }
  }

  function Invoke-ClaudeMcpAddHttp {
    param([string]$Name, [string]$Url, [string]$Scope, [string[]]$Headers = @())
    $cmdArgs = @("mcp", "add", "--scope", $Scope, "--transport", "http", $Name, $Url)
    foreach ($h in $Headers) { $cmdArgs += @("--header", $h) }
    & claude @cmdArgs | Out-Host
    if ($LASTEXITCODE -ne 0) { throw "claude mcp add(http) 失败：$Name" }
  }

  # MCP 服务器列表 - Windows 上 npx 需要通过 cmd /c 包装
  $servers = @(
    @{ Name = "context7"; Command = "cmd"; Args = @("/c", "npx", "-y", "@upstash/context7-mcp@1.0.31"); Note = "Context7" },
    @{ Name = "chrome_devtools_mcp"; Command = "cmd"; Args = @("/c", "npx", "-y", "chrome-devtools-mcp@0.12.1"); Note = "Chrome DevTools" },
    @{ Name = "markitdown"; Command = "uvx"; Args = @("markitdown-mcp==0.0.1a4"); Note = "MarkItDown" },
    @{ Name = "playwright_mcp"; Command = "cmd"; Args = @("/c", "npx", "-y", "@playwright/mcp@latest"); Note = "Playwright" },
    @{ Name = "serena"; Command = "uvx"; Args = @("--from", "git+https://github.com/oraios/serena", "serena", "start-mcp-server", "--project-from-cwd"); Note = "Serena" }
  )

  # Wolfram MCP 配置
  $codexHome = Get-DefaultCodexHome
  $resolvedWolframMode = $WolframMode

  if ($resolvedWolframMode -eq "auto") {
    if (-not [string]::IsNullOrWhiteSpace($WolframMcpScriptPath)) {
      $resolvedWolframMode = "python"
    } else {
      $repoDir = Get-DefaultWolframMcpRepoDir -CodexHome $codexHome -OverrideDir $WolframMcpRepoDir
      $candidate = $null
      if (-not [string]::IsNullOrWhiteSpace($repoDir)) {
        $candidatePath = Join-Path $repoDir "wolfram_mcp_server.py"
        if (Test-Path $candidatePath) { $candidate = $candidatePath }
      }
      if ($candidate) {
        $WolframMcpScriptPath = $candidate
        $resolvedWolframMode = "python"
      } else {
        $installDir = $WolframInstallationDirectory
        if ([string]::IsNullOrWhiteSpace($installDir)) { $installDir = $env:WOLFRAM_INSTALLATION_DIRECTORY }
        if ([string]::IsNullOrWhiteSpace($installDir)) { $installDir = Find-WolframInstallationDirectory }
        if (Resolve-WolframScriptCommand -InstallDir $installDir) {
          $resolvedWolframMode = "paclet"
        } else {
          $resolvedWolframMode = "skip"
        }
      }
    }
  }

  # Wolfram paclet 模式
  if ($resolvedWolframMode -eq "paclet") {
    $installDir = $WolframInstallationDirectory
    if ([string]::IsNullOrWhiteSpace($installDir)) { $installDir = $env:WOLFRAM_INSTALLATION_DIRECTORY }
    if ([string]::IsNullOrWhiteSpace($installDir)) { $installDir = Find-WolframInstallationDirectory }
    $wolframScriptCmd = Resolve-WolframScriptCommand -InstallDir $installDir
    if ($wolframScriptCmd) {
      $wolframEnv = @()
      if (-not [string]::IsNullOrWhiteSpace($installDir)) {
        $wolframEnv += "WOLFRAM_INSTALLATION_DIRECTORY=$installDir"
      }
      $servers += @{
        Name = "wolfram"
        Command = $wolframScriptCmd
        Args = @("-code", 'Needs["RickHennigan`MCPServer`"];LaunchMCPServer[]')
        Env = $wolframEnv
        Note = "Wolfram (Paclet)"
      }
    }
  }

  # Wolfram python 模式
  if ($resolvedWolframMode -eq "python") {
    $repoDir = Get-DefaultWolframMcpRepoDir -CodexHome $codexHome -OverrideDir $WolframMcpRepoDir
    if ([string]::IsNullOrWhiteSpace($WolframMcpScriptPath) -and -not [string]::IsNullOrWhiteSpace($repoDir)) {
      Ensure-WolframMcpRepo -RepoDir $repoDir -RepoUrl $WolframMcpRepoUrl
      $WolframMcpScriptPath = Join-Path $repoDir "wolfram_mcp_server.py"
    }

    if (-not [string]::IsNullOrWhiteSpace($WolframMcpScriptPath) -and (Test-Path $WolframMcpScriptPath)) {
      $wolframScript = (Resolve-Path $WolframMcpScriptPath).Path
      $wolframProjectRoot = Split-Path $wolframScript -Parent
      $venvPython = Resolve-WolframMcpPython -RepoDir $wolframProjectRoot

      if ($BootstrapWolframPython -or -not $venvPython) {
        Invoke-UvSync -ProjectRoot $wolframProjectRoot
        $venvPython = Resolve-WolframMcpPython -RepoDir $wolframProjectRoot
      }

      if ($venvPython) {
        $wolframEnv = @("PYTHONUTF8=1", "PYTHONIOENCODING=utf-8")
        $installDir = Find-WolframInstallationDirectory
        if ($installDir) { $wolframEnv += "WOLFRAM_INSTALLATION_DIRECTORY=$installDir" }
        $wsCmd = Resolve-WolframScriptCommand -InstallDir $installDir
        if ($wsCmd -and $wsCmd -ne "wolframscript") {
          $wolframEnv += "WOLFRAMSCRIPT_PATH=$wsCmd"
        }
        $servers += @{
          Name = "wolfram"; Command = $venvPython
          Args = @($wolframScript); Env = $wolframEnv; Note = "Wolfram (Python)"
        }
      }
    }
  }

  # 统计计数器
  $stats = @{ Added = 0; Skipped = 0; NotFound = 0 }

  # 主循环
  foreach ($server in $servers) {
    $name = $server.Name
    $cmd = $server.Command

    if (-not (Get-Command $cmd -EA SilentlyContinue) -and -not (Test-Path $cmd)) {
      Write-Host ("跳过：{0}（未找到 {1}）" -f $name, $cmd)
      $stats.NotFound++
      continue
    }

    if (Test-ClaudeMcpServerExists -Name $name) {
      if ($Force) {
        Write-Host ("重建：{0}" -f $name)
        Invoke-ClaudeMcpRemove -Name $name -Scope $Scope
      } else {
        Write-Host ("跳过：{0}（已存在）" -f $name)
        $stats.Skipped++
        continue
      }
    } else {
      Write-Host ("添加：{0}" -f $name)
    }

    $envPairs = @()
    if ($server.ContainsKey("Env")) { $envPairs = [string[]]$server.Env }
    $payload = @{
      type = "stdio"
      command = (Convert-PathToPosix $cmd)
      args = @([string[]]$server.Args)
      env = (Convert-EnvPairsToHashtable -EnvPairs $envPairs)
    }
    Invoke-ClaudeMcpAddJson -Name $name -Payload $payload -Scope $Scope
    $stats.Added++
  }

  # GitHub MCP (HTTP)
  $githubName = "github"
  $githubUrl = "https://api.githubcopilot.com/mcp/"
  $githubHeader = 'Authorization: Bearer ${GITHUB_MCP_PAT}'

  if (Test-ClaudeMcpServerExists -Name $githubName) {
    if ($Force) {
      Write-Host ("重建：{0}" -f $githubName)
      Invoke-ClaudeMcpRemove -Name $githubName -Scope $Scope
    } else {
      Write-Host ("跳过：{0}（已存在）" -f $githubName)
      $stats.Skipped++
      $githubName = ""
    }
  } else {
    Write-Host ("添加：{0}" -f $githubName)
  }

  if (-not [string]::IsNullOrWhiteSpace($githubName)) {
    # 检测 PAT
    $pat = $env:GITHUB_MCP_PAT
    if (-not $pat) { $pat = [Environment]::GetEnvironmentVariable('GITHUB_MCP_PAT', 'Machine') }
    if (-not $pat) { $pat = [Environment]::GetEnvironmentVariable('GITHUB_MCP_PAT', 'User') }
    if (-not $pat) { Write-Warning "未检测到 GITHUB_MCP_PAT" }
    Invoke-ClaudeMcpAddHttp -Name $githubName -Url $githubUrl -Scope $Scope -Headers @($githubHeader)
    $stats.Added++
  }

  # 输出统计
  Write-Host ""
  Write-Host ("统计：添加 {0}，跳过 {1}，未找到 {2}" -f $stats.Added, $stats.Skipped, $stats.NotFound)
  Write-Host "完成。运行 claude mcp list 查看结果。"

} finally {
  Pop-Location
}
