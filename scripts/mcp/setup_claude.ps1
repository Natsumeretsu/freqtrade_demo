<#
.SYNOPSIS
    一键配置 Claude Code CLI 的 MCP servers

.DESCRIPTION
    为 Claude Code 配置常用 MCP：Serena / Context7 / MarkItDown /
    Playwright / Chrome DevTools / Wolfram / In-Memoria / Local RAG / GitHub。

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
  [switch]$BootstrapWolframPython,
  [string]$LocalRagModelCacheDir,
  [string]$LocalRagModelName
)

# 加载公共模块
. (Join-Path $PSScriptRoot "../lib/common.ps1")

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "../..")).Path
Push-Location $repoRoot

try {
  Write-Host "开始初始化 Claude MCP..."
  Write-Host ("Scope: {0}" -f $Scope)

  # Windows 下 npm 安装的 claude 通常同时提供 claude.ps1 与 claude.cmd。
  # PowerShell 默认优先解析 .ps1，但它会把后续参数当作脚本参数解析，导致无法正确透传 `-y` 等下游参数。
  # 因此这里强制优先使用 claude.cmd，避免参数透传问题。
  $claudeExe = $null
  $claudeCmd = Get-Command "claude.cmd" -ErrorAction SilentlyContinue
  if ($claudeCmd) {
    $claudeExe = $claudeCmd.Source
  } else {
    $claudeExe = (Get-Command "claude" -ErrorAction Stop).Source
  }

  if (-not $claudeExe) {
    throw "未找到命令：claude。请先安装 Claude Code CLI"
  }

  Require-Command -Name "npx" -InstallHint "请先安装 Node.js"
  $hasUvx = Test-Command "uvx"
  if (-not $hasUvx) {
    Write-Warning "未找到 uvx：将跳过 MarkItDown/Serena（uvx 相关）MCP。"
  }

  # Claude 专用函数
  function Test-ClaudeMcpServerExists {
    param([string]$Name)
    try {
      & $claudeExe mcp get $Name *> $null
      return ($LASTEXITCODE -eq 0)
    } catch {
      return $false
    }
  }

  function Invoke-ClaudeMcpRemove {
    param([string]$Name, [string]$Scope)
    & $claudeExe mcp remove --scope $Scope $Name | Out-Host
    if ($LASTEXITCODE -ne 0) { throw "claude mcp remove 失败：$Name" }
  }

  function Invoke-ClaudeMcpAddStdio {
    param([string]$Name, [string]$Command, [string[]]$CommandArgs, [string[]]$EnvPairs, [string]$Scope)

    # 注意：必须插入 `--`，否则 claude.cmd 会把 `-y` 之类的参数当作自身 option 解析。
    $cmdArgs = @("mcp", "add", "--scope", $Scope, "--transport", "stdio", $Name)
    foreach ($pair in ($EnvPairs | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })) {
      $cmdArgs += @("--env", $pair)
    }
    $cmdArgs += @("--", $Command) + $CommandArgs

    & $claudeExe @cmdArgs | Out-Host
    if ($LASTEXITCODE -ne 0) { throw "claude mcp add(stdio) 失败：$Name" }
  }

  function Invoke-ClaudeMcpAddHttp {
    param([string]$Name, [string]$Url, [string]$Scope, [string[]]$Headers = @())
    $cmdArgs = @("mcp", "add", "--scope", $Scope, "--transport", "http", $Name, $Url)
    foreach ($h in $Headers) { $cmdArgs += @("--header", $h) }
    & $claudeExe @cmdArgs | Out-Host
    if ($LASTEXITCODE -ne 0) { throw "claude mcp add(http) 失败：$Name" }
  }

  # MCP 服务器列表（从 common.ps1 获取）
  $servers = @(Get-DefaultMcpServers -LocalRagCacheDir $LocalRagModelCacheDir -LocalRagModelName $LocalRagModelName)
  if (-not $hasUvx) {
    $servers = @($servers | Where-Object { $_.Command -ne "uvx" })
  }

  # Wolfram MCP 配置（从 common.ps1 获取）
  $wolframConfig = $null
  try {
    $wolframConfig = Get-WolframMcpConfig -Mode $WolframMode -ScriptPath $WolframMcpScriptPath `
      -RepoUrl $WolframMcpRepoUrl -RepoDir $WolframMcpRepoDir -InstallDir $WolframInstallationDirectory `
      -Bootstrap:$BootstrapWolframPython
  } catch {
    Write-Warning ("Wolfram MCP 配置失败，将跳过：{0}" -f $_.Exception.Message)
    $wolframConfig = $null
  }
  if ($wolframConfig) { $servers += $wolframConfig }

  # 统计计数器
  $stats = @{ Added = 0; Skipped = 0; NotFound = 0; Failed = 0 }

  # 主循环
  foreach ($server in $servers) {
    $name = $server.Name
    $cmd = $server.Command

    try {
      if (-not (Get-Command $cmd -EA SilentlyContinue) -and -not (Test-Path $cmd)) {
        Write-Host ("跳过：{0}（未找到 {1}）" -f $name, $cmd)
        $stats.NotFound++
        continue
      }

      $exists = Test-ClaudeMcpServerExists -Name $name
      if ($exists -and -not $Force) {
        Write-Host ("跳过：{0}（已存在）" -f $name)
        $stats.Skipped++
        continue
      }

      if ($exists -and $Force) {
        Write-Host ("重建：{0}" -f $name)
        if ($PSCmdlet.ShouldProcess($name, "claude mcp remove")) {
          Invoke-ClaudeMcpRemove -Name $name -Scope $Scope
        }
      } else {
        Write-Host ("添加：{0}" -f $name)
      }

      $envPairs = @()
      if ($server.ContainsKey("Env")) { $envPairs = [string[]]$server.Env }

      if ($PSCmdlet.ShouldProcess($name, "claude mcp add(stdio)")) {
        Invoke-ClaudeMcpAddStdio -Name $name -Scope $Scope -EnvPairs $envPairs -Command $cmd -CommandArgs @([string[]]$server.Args)
      }
      $stats.Added++
    } catch {
      $stats.Failed++
      Write-Warning ("配置失败：{0} - {1}" -f $name, $_.Exception.Message)
      continue
    }
  }

  # GitHub MCP (HTTP)
  $githubName = "github"
  $githubUrl = "https://api.githubcopilot.com/mcp/"
  $githubHeader = 'Authorization: Bearer ${GITHUB_MCP_PAT}'

  if (Test-ClaudeMcpServerExists -Name $githubName) {
    if ($Force) {
      Write-Host ("重建：{0}" -f $githubName)
      if ($PSCmdlet.ShouldProcess($githubName, "claude mcp remove")) {
        Invoke-ClaudeMcpRemove -Name $githubName -Scope $Scope
      }
    } else {
      Write-Host ("跳过：{0}（已存在）" -f $githubName)
      $stats.Skipped++
      $githubName = ""
    }
  } else {
    Write-Host ("添加：{0}" -f $githubName)
  }

  $needsRestart = $false
  if (-not [string]::IsNullOrWhiteSpace($githubName)) {
    # 检测 PAT - 分别检查进程级别和系统/用户级别
    $patProcess = $env:GITHUB_MCP_PAT
    $patMachine = [Environment]::GetEnvironmentVariable('GITHUB_MCP_PAT', 'Machine')
    $patUser = [Environment]::GetEnvironmentVariable('GITHUB_MCP_PAT', 'User')
    $pat = if ($patProcess) { $patProcess } elseif ($patMachine) { $patMachine } else { $patUser }

    if (-not $pat) {
      Write-Host ("跳过：{0}（未检测到 GITHUB_MCP_PAT 环境变量）" -f $githubName)
      Write-Host "  提示：请在系统环境变量中设置 GITHUB_MCP_PAT" -ForegroundColor Yellow
      $stats.NotFound++
    } else {
      try {
        if ($PSCmdlet.ShouldProcess($githubName, "claude mcp add (http)")) {
          Invoke-ClaudeMcpAddHttp -Name $githubName -Url $githubUrl -Scope $Scope -Headers @($githubHeader)
        }
        $stats.Added++
      } catch {
        $stats.Failed++
        Write-Warning ("配置失败：{0} - {1}" -f $githubName, $_.Exception.Message)
      }
      # 检查是否需要重启：PAT 存在于系统/用户级别但当前进程没有
      if (-not $patProcess -and ($patMachine -or $patUser)) {
        $needsRestart = $true
      }
    }
  }

  # 输出统计
  Write-Host ""
  Write-Host ("统计：添加 {0}，跳过 {1}，未找到 {2}，失败 {3}" -f $stats.Added, $stats.Skipped, $stats.NotFound, $stats.Failed)
  if ($WhatIfPreference) {
    Write-Host "（WhatIf 预览：未写入任何配置）"
  }
  if ($needsRestart) {
    Write-Host ""
    Write-Host "注意：GITHUB_MCP_PAT 环境变量已在系统级别设置，但当前进程尚未读取。" -ForegroundColor Yellow
    Write-Host "请重启 VSCode/终端后，GitHub MCP 才能正常连接。" -ForegroundColor Yellow
  }
  Write-Host "完成。运行 claude mcp list 查看结果。"

} finally {
  Pop-Location
}
