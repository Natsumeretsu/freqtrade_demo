<#
.SYNOPSIS
    一键配置 Codex CLI 的 MCP servers

.DESCRIPTION
    为 Codex CLI 配置常用 MCP：Serena / Context7 / MarkItDown /
    Playwright / Chrome DevTools / Wolfram。

.PARAMETER Force
    覆盖已存在的同名 MCP server 配置

.EXAMPLE
    .\setup_codex.ps1
    .\setup_codex.ps1 -WhatIf
    .\setup_codex.ps1 -Force
#>
[CmdletBinding(SupportsShouldProcess = $true, ConfirmImpact = "Low")]
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

# 加载公共模块
. (Join-Path $PSScriptRoot "common.ps1")

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "../..")).Path
Push-Location $repoRoot

try {
  Write-Host "开始初始化 Codex MCP..."

  Require-Command -Name "codex" -InstallHint "请先安装 Codex CLI"
  Require-Command -Name "npx" -InstallHint "请先安装 Node.js"
  Require-Command -Name "uvx" -InstallHint "请先安装 uv"

  # Codex 专用函数
  function Test-CodexMcpServerExists {
    param([string]$Name)
    & codex mcp get $Name --json *> $null
    return ($LASTEXITCODE -eq 0)
  }

  function Invoke-CodexMcpRemove {
    param([string]$Name)
    & codex mcp remove $Name | Out-Host
    if ($LASTEXITCODE -ne 0) { throw "codex mcp remove 失败：$Name" }
  }

  function Invoke-CodexMcpAdd {
    param([string]$Name, [string]$Command, [string[]]$Args, [string[]]$Env = @())
    $cmdArgs = @("mcp", "add")
    foreach ($pair in $Env) { $cmdArgs += @("--env", $pair) }
    $cmdArgs += @($Name, "--", $Command) + $Args
    & codex @cmdArgs | Out-Host
    if ($LASTEXITCODE -ne 0) { throw "codex mcp add 失败：$Name" }
  }

  # MCP 服务器列表
  $servers = @(
    @{ Name = "context7"; Command = "cmd"; Args = @("/c", "npx", "-y", "@upstash/context7-mcp@1.0.31"); Note = "Context7" },
    @{ Name = "chrome_devtools_mcp"; Command = "cmd"; Args = @("/c", "npx", "-y", "chrome-devtools-mcp@0.12.1"); Note = "Chrome DevTools" },
    @{ Name = "markitdown"; Command = "uvx"; Args = @("markitdown-mcp==0.0.1a4"); Note = "MarkItDown" },
    @{ Name = "playwright_mcp"; Command = "cmd"; Args = @("/c", "npx", "-y", "@playwright/mcp@latest"); Note = "Playwright" },
    @{ Name = "serena"; Command = "uvx"; Args = @("--from", "git+https://github.com/oraios/serena", "serena", "start-mcp-server", "--project-from-cwd"); Note = "Serena" }
  )

  # Wolfram 配置
  $codexHome = Get-DefaultCodexHome
  $resolvedWolframMode = $WolframMode

  if ($resolvedWolframMode -eq "auto") {
    if (-not [string]::IsNullOrWhiteSpace($WolframMcpScriptPath)) {
      $resolvedWolframMode = "python"
    } else {
      $repoDir = Get-DefaultWolframMcpRepoDir -CodexHome $codexHome -OverrideDir $WolframMcpRepoDir
      $candidate = $null
      if ($repoDir) {
        $candidatePath = Join-Path $repoDir "wolfram_mcp_server.py"
        if (Test-Path $candidatePath) { $candidate = $candidatePath }
      }
      if ($candidate) {
        $WolframMcpScriptPath = $candidate
        $resolvedWolframMode = "python"
      } else {
        $installDir = $WolframInstallationDirectory
        if (!$installDir) { $installDir = $env:WOLFRAM_INSTALLATION_DIRECTORY }
        if (!$installDir) { $installDir = Find-WolframInstallationDirectory }
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
    if (!$installDir) { $installDir = $env:WOLFRAM_INSTALLATION_DIRECTORY }
    if (!$installDir) { $installDir = Find-WolframInstallationDirectory }
    $wsCmd = Resolve-WolframScriptCommand -InstallDir $installDir
    if ($wsCmd) {
      $wolframEnv = @()
      if ($installDir) { $wolframEnv += "WOLFRAM_INSTALLATION_DIRECTORY=$installDir" }
      $servers += @{
        Name = "wolfram"; Command = $wsCmd
        Args = @("-code", 'Needs["RickHennigan`MCPServer`"];LaunchMCPServer[]')
        Env = $wolframEnv; Note = "Wolfram (Paclet)"
      }
    }
  }

  # Wolfram python 模式
  if ($resolvedWolframMode -eq "python") {
    $repoDir = Get-DefaultWolframMcpRepoDir -CodexHome $codexHome -OverrideDir $WolframMcpRepoDir
    if (!$WolframMcpScriptPath -and $repoDir) {
      Ensure-WolframMcpRepo -RepoDir $repoDir -RepoUrl $WolframMcpRepoUrl
      $WolframMcpScriptPath = Join-Path $repoDir "wolfram_mcp_server.py"
    }
    if ($WolframMcpScriptPath -and (Test-Path $WolframMcpScriptPath)) {
      $wolframScript = (Resolve-Path $WolframMcpScriptPath).Path
      $wolframProjectRoot = Split-Path $wolframScript -Parent
      $venvPython = Resolve-WolframMcpPython -RepoDir $wolframProjectRoot
      if ($BootstrapWolframPython -or !$venvPython) {
        Invoke-UvSync -ProjectRoot $wolframProjectRoot
        $venvPython = Resolve-WolframMcpPython -RepoDir $wolframProjectRoot
      }
      if ($venvPython) {
        $wolframEnv = @("PYTHONUTF8=1", "PYTHONIOENCODING=utf-8")
        $installDir = Find-WolframInstallationDirectory
        if ($installDir) { $wolframEnv += "WOLFRAM_INSTALLATION_DIRECTORY=$installDir" }
        $wsCmd = Resolve-WolframScriptCommand -InstallDir $installDir
        if ($wsCmd -and $wsCmd -ne "wolframscript") { $wolframEnv += "WOLFRAMSCRIPT_PATH=$wsCmd" }
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

    if (Test-CodexMcpServerExists -Name $name) {
      if ($Force) {
        Write-Host ("重建：{0}" -f $name)
        Invoke-CodexMcpRemove -Name $name
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
    Invoke-CodexMcpAdd -Name $name -Command $cmd -Args $server.Args -Env $envPairs
    $stats.Added++
  }

  # 输出统计
  Write-Host ""
  Write-Host ("统计：添加 {0}，跳过 {1}，未找到 {2}" -f $stats.Added, $stats.Skipped, $stats.NotFound)
  Write-Host "完成。运行 codex mcp list 查看结果。"

} finally {
  Pop-Location
}
