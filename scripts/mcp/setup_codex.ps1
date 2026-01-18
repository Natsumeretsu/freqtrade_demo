<#
.SYNOPSIS
    一键配置 Codex CLI 的 MCP servers

.DESCRIPTION
    为 Codex CLI 配置常用 MCP：Serena / Context7 / MarkItDown /
    Playwright / Chrome DevTools / Wolfram / GitHub。

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
  [switch]$BootstrapWolframPython,
  [string]$LocalRagModelCacheDir,
  [string]$LocalRagModelName
)

# 加载公共模块
. (Join-Path $PSScriptRoot "../lib/common.ps1")

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "../..")).Path
Push-Location $repoRoot

try {
  Write-Host "开始初始化 Codex MCP..."

  Require-Command -Name "codex" -InstallHint "请先安装 Codex CLI"
  Require-Command -Name "npx" -InstallHint "请先安装 Node.js"
  $hasUvx = Test-Command "uvx"
  if (-not $hasUvx) {
    Write-Warning "未找到 uvx：将跳过 MarkItDown/Serena（uvx 相关）MCP。"
  }

  # Codex 专用函数
  function Test-CodexMcpServerExists {
    param([string]$Name)
    try {
      & codex mcp get $Name --json *> $null
      return ($LASTEXITCODE -eq 0)
    } catch {
      return $false
    }
  }

  function Invoke-CodexMcpRemove {
    param([string]$Name)
    & codex mcp remove $Name | Out-Host
    if ($LASTEXITCODE -ne 0) { throw "codex mcp remove 失败：$Name" }
  }

  function Invoke-CodexMcpAdd {
    param([string]$Name, [string]$Command, [string[]]$CommandArgs, [string[]]$Env = @())
    $cmdArgs = @("mcp", "add")
    foreach ($pair in $Env) { $cmdArgs += @("--env", $pair) }
    $cmdArgs += @($Name, "--", $Command) + $CommandArgs
    & codex @cmdArgs | Out-Host
    if ($LASTEXITCODE -ne 0) { throw "codex mcp add 失败：$Name" }
  }

  function Ensure-CodexMcpServerCwd {
    <#
    .SYNOPSIS
      为指定 MCP server 写入/更新 cwd（Codex CLI 目前的 `codex mcp add` 不支持直接设置 cwd）
    #>
    param(
      [Parameter(Mandatory = $true)][string]$Name,
      [Parameter(Mandatory = $true)][string]$CwdValue
    )

    $codexHome = Get-DefaultCodexHome
    if ([string]::IsNullOrWhiteSpace($codexHome)) {
      Write-Warning "未找到 CODEX_HOME 或默认 ~/.codex，跳过写入 cwd。"
      return
    }

    $configPath = Join-Path $codexHome "config.toml"
    if (-not (Test-Path $configPath)) {
      Write-Warning ("未找到 Codex 配置文件，跳过写入 cwd：{0}" -f $configPath)
      return
    }

    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    $lines = [System.IO.File]::ReadAllLines($configPath, $utf8NoBom)
    $header = "[mcp_servers.$Name]"
    $start = [Array]::IndexOf($lines, $header)
    if ($start -lt 0) {
      Write-Warning ("未找到 MCP server 段落，跳过写入 cwd：{0}" -f $header)
      return
    }

    # 仅在 server 段落内查找/插入（遇到下一个 `[` 段落头就停止）
    $end = $lines.Length
    for ($i = $start + 1; $i -lt $lines.Length; $i++) {
      if ($lines[$i] -match '^\[') {
        $end = $i
        break
      }
    }

    $cwdLine = ('cwd = "{0}"' -f $CwdValue)
    $updated = $false
    for ($i = $start + 1; $i -lt $end; $i++) {
      if ($lines[$i] -match '^\s*cwd\s*=') {
        if ($lines[$i] -ne $cwdLine) {
          $lines[$i] = $cwdLine
        }
        $updated = $true
        break
      }
    }

    if (-not $updated) {
      $list = New-Object System.Collections.Generic.List[string]
      $list.AddRange($lines[0..$start])
      $list.Add($cwdLine)
      if ($start + 1 -lt $lines.Length) {
        $list.AddRange($lines[($start + 1)..($lines.Length - 1)])
      }
      $lines = $list.ToArray()
    }

    [System.IO.File]::WriteAllLines($configPath, $lines, $utf8NoBom)
    Write-Host ("已写入 cwd：{0} -> {1}" -f $Name, $CwdValue)
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

      $exists = Test-CodexMcpServerExists -Name $name
      if ($exists -and -not $Force) {
        Write-Host ("跳过：{0}（已存在）" -f $name)
        $stats.Skipped++
        continue
      }

      if ($exists -and $Force) {
        Write-Host ("重建：{0}" -f $name)
        if ($PSCmdlet.ShouldProcess($name, "codex mcp remove")) {
          Invoke-CodexMcpRemove -Name $name
        }
      } else {
        Write-Host ("添加：{0}" -f $name)
      }

      $envPairs = @()
      if ($server.ContainsKey("Env")) { $envPairs = [string[]]$server.Env }
      if ($PSCmdlet.ShouldProcess($name, "codex mcp add")) {
        Invoke-CodexMcpAdd -Name $name -Command $cmd -CommandArgs $server.Args -Env $envPairs
      }
      $stats.Added++
    } catch {
      $stats.Failed++
      Write-Warning ("配置失败：{0} - {1}" -f $name, $_.Exception.Message)
      continue
    }
  }

  # 输出统计
  Write-Host ""
  Write-Host ("统计：添加 {0}，跳过 {1}，未找到 {2}，失败 {3}" -f $stats.Added, $stats.Skipped, $stats.NotFound, $stats.Failed)
  if ($WhatIfPreference) {
    Write-Host "（WhatIf 预览：未写入任何配置）"
  }
  Write-Host "完成。运行 codex mcp list 查看结果。"

} finally {
  Pop-Location
}
