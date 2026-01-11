<#
.SYNOPSIS
    MCP 一键体检（Codex/Claude）

.DESCRIPTION
    目标：快速检查本机 MCP 的“可用性 + 版本对齐 + 关键路径”。
    该脚本只读，不会修改任何配置。

.PARAMETER Target
    检查目标：codex / claude / both

.PARAMETER Deep
    深度检查：额外检查 Chrome/Local RAG/In-Memoria 等关键文件与目录是否存在，并统计大小。

.PARAMETER ShowConfig
    打印 MCP 配置 JSON（用于排查）。

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File "./scripts/mcp/doctor.ps1"
    powershell -ExecutionPolicy Bypass -File "./scripts/mcp/doctor.ps1" -Deep
    powershell -ExecutionPolicy Bypass -File "./scripts/mcp/doctor.ps1" -Target both -Deep
#>
[CmdletBinding()]
param(
  [ValidateSet("codex", "claude", "both")]
  [string]$Target = "codex",
  [switch]$Deep,
  [switch]$ShowConfig
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

. (Join-Path $PSScriptRoot "../lib/common.ps1")

function Get-ExecutablePath {
  param([string]$Name)
  try {
    $cmd = Get-Command $Name -ErrorAction Stop
    return $cmd.Source
  } catch {
    return $null
  }
}

function Try-Run {
  param(
    [Parameter(Mandatory = $true)]
    [string]$Name,
    [Parameter(Mandatory = $true)]
    [scriptblock]$Block
  )
  try {
    return & $Block
  } catch {
    Write-Warning ("{0} 失败：{1}" -f $Name, $_.Exception.Message)
    return $null
  }
}

function Get-NpxPackageSpecFromArgs {
  param([object[]]$ArgList)
  if (-not $ArgList) {
    return $null
  }
  $i = 0
  while ($i -lt $ArgList.Count) {
    if ([string]$ArgList[$i] -ieq "npx") {
      break
    }
    $i++
  }
  if ($i -ge $ArgList.Count) {
    return $null
  }
  $j = $i + 1
  while ($j -lt $ArgList.Count) {
    $arg = [string]$ArgList[$j]
    if (-not $arg.StartsWith("-")) {
      return $arg
    }
    $j++
  }
  return $null
}

function Get-DirectoryStats {
  param([string]$Path)
  if (-not (Test-Path $Path)) {
    return $null
  }
  $files = Get-ChildItem -Path $Path -Recurse -File -Force -ErrorAction SilentlyContinue
  $sum = ($files | Measure-Object -Property Length -Sum).Sum
  return @{
    FileCount = $files.Count
    SizeBytes = [int64]$(if ($null -ne $sum) { $sum } else { 0 })
  }
}

function Format-Bytes {
  param([int64]$Bytes)
  if ($Bytes -lt 1024) { return ("{0} B" -f $Bytes) }
  if ($Bytes -lt 1024 * 1024) { return ("{0:n2} KB" -f ($Bytes / 1024)) }
  if ($Bytes -lt 1024 * 1024 * 1024) { return ("{0:n2} MB" -f ($Bytes / 1024 / 1024)) }
  return ("{0:n2} GB" -f ($Bytes / 1024 / 1024 / 1024))
}

function Find-ChromeExe {
  $candidates = @(
    (Join-Path $env:LOCALAPPDATA "Google/Chrome/Application/chrome.exe"),
    (Join-Path $env:ProgramFiles "Google/Chrome/Application/chrome.exe"),
    (Join-Path ${env:ProgramFiles(x86)} "Google/Chrome/Application/chrome.exe")
  ) | Where-Object { -not [string]::IsNullOrWhiteSpace($_) }

  foreach ($p in $candidates) {
    if (Test-Path $p) {
      return $p
    }
  }
  return $null
}

function Get-CodexMcpServers {
  $json = & codex mcp list --json
  if ($LASTEXITCODE -ne 0) { throw "codex mcp list 失败" }
  return ($json | ConvertFrom-Json)
}

function Get-CodexMcpServerByName {
  param([string]$Name)
  $json = & codex mcp get $Name --json
  if ($LASTEXITCODE -ne 0) { throw ("codex mcp get 失败：{0}" -f $Name) }
  return ($json | ConvertFrom-Json)
}

function Get-ClaudeMcpServers {
  $raw = & claude mcp list
  if ($LASTEXITCODE -ne 0) { throw "claude mcp list 失败" }
  return ($raw | Out-String)
}

function Get-ClaudePackageSpecFromLine {
  param([string]$Line)
  if ([string]::IsNullOrWhiteSpace($Line)) {
    return $null
  }
  $m = [regex]::Match($Line, "npx\s+-y\s+([^\s]+)")
  if ($m.Success) {
    return $m.Groups[1].Value
  }
  $m = [regex]::Match($Line, "(markitdown-mcp==[^\s]+)")
  if ($m.Success) {
    return $m.Groups[1].Value
  }
  return $null
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "../..")).Path
Push-Location $repoRoot

try {
  Write-Host ("MCP 体检开始（repo={0}）" -f $repoRoot)

  $psVersion = $PSVersionTable.PSVersion.ToString()
  Write-Host ("PowerShell: {0}" -f $psVersion)

  $pwshPath = Get-ExecutablePath "pwsh"
  if ([string]::IsNullOrWhiteSpace($pwshPath)) {
    Write-Host "提示：未检测到 PowerShell 7（pwsh）。部分脚本在 pwsh 下的 UTF-8 体验更好，但不是硬要求。"
  } else {
    Write-Host ("pwsh: {0}" -f $pwshPath)
  }

  $codexHome = Get-DefaultCodexHome
  if (-not [string]::IsNullOrWhiteSpace($codexHome)) {
    Write-Host ("CODEX_HOME: {0}" -f (Convert-PathToPosix $codexHome))
  }

  $nodePath = Get-ExecutablePath "node"
  $npxPath = Get-ExecutablePath "npx"
  $uvxPath = Get-ExecutablePath "uvx"
  Write-Host ("node: {0}" -f $(if ($nodePath) { $nodePath } else { "未安装" }))
  Write-Host ("npx: {0}" -f $(if ($npxPath) { $npxPath } else { "未安装" }))
  Write-Host ("uvx: {0}" -f $(if ($uvxPath) { $uvxPath } else { "未安装" }))

  $expected = @(Get-DefaultMcpServers)
  $expectedByName = @{}
  foreach ($s in $expected) {
    $expectedByName[$s.Name] = $s
  }

  if ($Target -in @("codex", "both")) {
    Write-Host ""
    Write-Host "=== Codex MCP ==="

    if (-not (Test-Command "codex")) {
      Write-Warning "未找到 codex CLI，跳过 Codex MCP 检查。"
    } else {
      $codexServers = Get-CodexMcpServers
      $codexByName = @{}
      foreach ($s in $codexServers) {
        $codexByName[$s.name] = $s
      }

      $missing = @()
      $versionMismatch = @()

      foreach ($name in ($expectedByName.Keys | Sort-Object)) {
        if (-not $codexByName.ContainsKey($name)) {
          $missing += $name
          continue
        }

        $expectedArgs = [object[]]$expectedByName[$name].Args
        $expectedPkg = Get-NpxPackageSpecFromArgs -ArgList $expectedArgs

        $actualArgs = [object[]]$codexByName[$name].transport.args
        $actualPkg = Get-NpxPackageSpecFromArgs -ArgList $actualArgs

        if (-not [string]::IsNullOrWhiteSpace($expectedPkg) -and -not [string]::IsNullOrWhiteSpace($actualPkg)) {
          if ($expectedPkg -ne $actualPkg) {
            $versionMismatch += ("{0}: {1} -> {2}" -f $name, $actualPkg, $expectedPkg)
          }
        }
      }

      if ($missing.Count -eq 0) {
        Write-Host ("已配置预期 MCP：{0} 项" -f $expectedByName.Keys.Count)
      } else {
        Write-Warning ("缺失 MCP：{0}" -f ($missing -join ", "))
      }

      if ($versionMismatch.Count -gt 0) {
        Write-Warning "检测到版本不一致："
        foreach ($m in $versionMismatch) {
          Write-Warning ("  {0}" -f $m)
        }
        Write-Host "建议：运行 ./scripts/mcp/setup_codex.ps1 -Force 进行对齐。"
      } else {
        Write-Host "版本对齐：未发现不一致。"
      }

      if ($ShowConfig) {
        foreach ($name in ($expectedByName.Keys | Sort-Object)) {
          if ($codexByName.ContainsKey($name)) {
            $cfg = Get-CodexMcpServerByName -Name $name
            Write-Host ""
            Write-Host ("--- codex mcp get {0} --json ---" -f $name)
            Write-Host ($cfg | ConvertTo-Json -Depth 10)
          }
        }
      }

      if ($Deep) {
        Write-Host ""
        Write-Host "=== 深度检查（路径/缓存）==="

        $chromeExe = Find-ChromeExe
        if ($chromeExe) {
          Write-Host ("chrome.exe: {0}" -f (Convert-PathToPosix $chromeExe))
        } else {
          Write-Warning "未找到 chrome.exe（Playwright/Chrome DevTools 可能不可用）。"
          Write-Host "建议：运行 ./scripts/tools/fix_chrome_for_mcp.ps1"
        }

        $inMemoriaDb = Join-Path $repoRoot "in-memoria.db"
        if (Test-Path $inMemoriaDb) {
          $size = (Get-Item $inMemoriaDb).Length
          Write-Host ("in-memoria.db: {0}（{1}）" -f (Convert-PathToPosix $inMemoriaDb), (Format-Bytes $size))
        } else {
          Write-Warning "未找到 in-memoria.db（首次使用可忽略；跑过学习后会生成）。"
        }

        $localRagDb = Join-Path $repoRoot ".vibe/local-rag/lancedb"
        $dbStats = Get-DirectoryStats -Path $localRagDb
        if ($dbStats) {
          Write-Host ("Local RAG DB: {0}（{1} 文件，{2}）" -f (Convert-PathToPosix $localRagDb), $dbStats.FileCount, (Format-Bytes $dbStats.SizeBytes))
        } else {
          Write-Warning "未找到 Local RAG DB（可运行 python -X utf8 scripts/tools/local_rag_ingest_project_docs.py --rebuild 生成）。"
        }

        $serenaProject = Join-Path $repoRoot ".serena/project.yml"
        if (Test-Path $serenaProject) {
          Write-Host (".serena/project.yml: {0}" -f (Convert-PathToPosix $serenaProject))
        } else {
          Write-Warning "未找到 .serena/project.yml（Serena 项目配置可能未初始化）。"
        }

        $localRag = $codexByName["local_rag"]
        if ($localRag -and $localRag.transport -and $localRag.transport.env) {
          $cacheDir = $localRag.transport.env.CACHE_DIR
          $modelName = $localRag.transport.env.MODEL_NAME
          if (-not [string]::IsNullOrWhiteSpace($cacheDir)) {
            $cacheStats = Get-DirectoryStats -Path $cacheDir
            if ($cacheStats) {
              Write-Host ("Local RAG CACHE_DIR: {0}（{1} 文件，{2}）" -f $cacheDir, $cacheStats.FileCount, (Format-Bytes $cacheStats.SizeBytes))
            } else {
              Write-Host ("Local RAG CACHE_DIR: {0}（目录不存在，首次运行会自动下载/生成）" -f $cacheDir)
            }
          }
          $repoModelsDir = Join-Path $repoRoot ".vibe/local-rag/models"
          $repoModelsStats = Get-DirectoryStats -Path $repoModelsDir
          if ($repoModelsStats -and $repoModelsStats.FileCount -gt 0) {
            $repoModelsPosix = Convert-PathToPosix $repoModelsDir
            Write-Host ("Repo Local RAG models: {0}（{1} 文件，{2}）" -f $repoModelsPosix, $repoModelsStats.FileCount, (Format-Bytes $repoModelsStats.SizeBytes))
            if (-not [string]::IsNullOrWhiteSpace($cacheDir)) {
              $a = $cacheDir.TrimEnd("/")
              $b = $repoModelsPosix.TrimEnd("/")
              if ($a -ne $b) {
                Write-Warning ("检测到仓库内仍有旧的 Local RAG 模型缓存：{0}（当前 CACHE_DIR={1}）。如需释放空间可手动删除该目录（不影响代码/文档）。" -f $repoModelsPosix, $cacheDir)
              }
            }
          }
          if (-not [string]::IsNullOrWhiteSpace($modelName)) {
            Write-Host ("Local RAG MODEL_NAME: {0}" -f $modelName)
          }
        }
      }
    }
  }

  if ($Target -in @("claude", "both")) {
    Write-Host ""
    Write-Host "=== Claude MCP ==="

    if (-not (Test-Command "claude")) {
      Write-Warning "未找到 claude CLI，跳过 Claude MCP 检查。"
    } else {
      $list = Try-Run -Name "claude mcp list" -Block { Get-ClaudeMcpServers }
      if (-not $list) {
        Write-Warning "claude mcp list 失败，跳过后续检查。"
      } else {
        Write-Host "claude mcp list："
        Write-Host $list.TrimEnd()

        $claudeByName = @{}
        foreach ($line in ($list -split "`r?`n")) {
          $m = [regex]::Match($line, "^([A-Za-z0-9_]+):\s+")
          if ($m.Success) {
            $claudeByName[$m.Groups[1].Value] = $line
          }
        }

        $missing = @()
        $versionMismatch = @()

        foreach ($name in ($expectedByName.Keys | Sort-Object)) {
          if (-not $claudeByName.ContainsKey($name)) {
            $missing += $name
            continue
          }

          $expectedArgs = [object[]]$expectedByName[$name].Args
          $expectedPkg = Get-NpxPackageSpecFromArgs -ArgList $expectedArgs
          if ([string]::IsNullOrWhiteSpace($expectedPkg)) {
            continue
          }

          $actualLine = [string]$claudeByName[$name]
          $actualPkg = Get-ClaudePackageSpecFromLine -Line $actualLine
          if ([string]::IsNullOrWhiteSpace($actualPkg)) {
            continue
          }

          if ($expectedPkg -ne $actualPkg) {
            $versionMismatch += ("{0}: {1} -> {2}" -f $name, $actualPkg, $expectedPkg)
          }
        }

        if ($missing.Count -gt 0) {
          Write-Warning ("Claude 缺失 MCP：{0}" -f ($missing -join ", "))
        }

        if ($versionMismatch.Count -gt 0) {
          Write-Warning "Claude 检测到版本不一致："
          foreach ($m in $versionMismatch) {
            Write-Warning ("  {0}" -f $m)
          }
          Write-Host "建议：运行 ./scripts/mcp/setup_claude.ps1 -Force 进行对齐。"
        }
      }
    }
  }

  Write-Host ""
  Write-Host "体检完成。"
} finally {
  Pop-Location
}

