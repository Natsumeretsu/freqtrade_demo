<#
.SYNOPSIS
  写入 Claude Code 的 settings.json（含 env）

.DESCRIPTION
  目标文件默认是：C:\Users\<用户名>\.claude\settings.json
  脚本会写入以下结构（并尽量复用已存在的 Token/BaseUrl 作为默认值）：

  {
    "env": {
      "ANTHROPIC_AUTH_TOKEN": "...",
      "ANTHROPIC_BASE_URL": "https://www.right.codes/claude",
      "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1"
    },
    "permissions": { "allow": [], "deny": [] },
    "alwaysThinkingEnabled": true
  }

  说明：
  - 默认不会在控制台打印 Token，避免泄露；需要打印时请显式使用 -RevealToken。
  - 默认会同时设置“用户级”环境变量（永久设置）；如需仅写入 settings.json，请使用 -NoSetEnvUser。
  - 会在脚本同目录维护 claude_profiles.local.json，用于保存/切换多个站点和 Token：
    Token 使用 DPAPI 加密（绑定当前 Windows 用户），适合本机多站点管理；仍建议不要提交到仓库。
  - 自动备份名称固定为 backup / backup_2 / backup_3...（具体站点信息以 profile 内字段为准）。

.PARAMETER AnthropicAuthToken
  API 密钥（优先级：参数 > 环境变量 ANTHROPIC_AUTH_TOKEN > settings.json 现有值 > 交互输入）。

.PARAMETER AnthropicBaseUrl
  Base URL（优先级：参数 > 环境变量 ANTHROPIC_BASE_URL > settings.json 现有值 > 默认值）。

.PARAMETER SettingsPath
  自定义 settings.json 路径（默认：$env:USERPROFILE\.claude\settings.json）。

.PARAMETER ProfilesPath
  profile 存储文件路径（默认：脚本同目录 ./claude_profiles.local.json）。

.PARAMETER ProfileName
  保存/更新到哪个 profile 名称：
  - 未指定时，会根据 BaseUrl 自动生成名称
  - 同一站点存在多个 Token 时，会自动追加后缀（_2/_3/...）避免覆盖

.PARAMETER UseProfile
  使用指定 profile（从 ProfilesPath 读取 BaseUrl/Token），并应用到 settings.json + 用户级环境变量。

.PARAMETER ListProfiles
  列出 ProfilesPath 内的全部 profile，然后退出（不修改 settings/env）。

.PARAMETER NoBackupCurrent
  不自动备份“当前已生效”的 BaseUrl/Token（默认会先备份再切换，便于回滚）。

.PARAMETER SetEnvUser
  （可选）显式开启写入用户级环境变量（默认已开启）。

.PARAMETER NoSetEnvUser
  只写入 settings.json，不写入用户级环境变量。

.PARAMETER PrintPowerShell
  输出 PowerShell 环境变量设置命令（默认隐藏 Token）。

.PARAMETER PrintLinux
  输出 Linux/macOS 的 export 命令（默认隐藏 Token）。

.PARAMETER RevealToken
  与 -PrintPowerShell / -PrintLinux 配合使用：允许输出明文 Token（谨慎）。

.EXAMPLE
  # 交互式输入 Token，并写入默认路径
  .\scripts\mcp\setup_claude_settings.ps1

.EXAMPLE
  # 通过参数指定 Token/BaseUrl
  .\scripts\mcp\setup_claude_settings.ps1 -AnthropicAuthToken "你的API密钥" -AnthropicBaseUrl "https://www.right.codes/claude"

.EXAMPLE
  # 仅生成环境变量命令（不打印 Token）
  .\scripts\mcp\setup_claude_settings.ps1 -PrintPowerShell -PrintLinux

.EXAMPLE
  # 写入 settings.json 后，同时设置用户级环境变量
  .\scripts\mcp\setup_claude_settings.ps1 -SetEnvUser

.EXAMPLE
  # 保存为自定义 profile 名称（方便多站点/多 Token 管理）
  .\scripts\mcp\setup_claude_settings.ps1 -ProfileName "rightcodes_main" -AnthropicBaseUrl "https://www.right.codes/claude"

.EXAMPLE
  # 列出已保存的 profiles（仅查看，不改动配置）
  .\scripts\mcp\setup_claude_settings.ps1 -ListProfiles

.EXAMPLE
  # 切换到已保存的 profile
  .\scripts\mcp\setup_claude_settings.ps1 -UseProfile "rightcodes_main"
#>
[CmdletBinding(SupportsShouldProcess = $true, ConfirmImpact = "Medium")]
param(
  [string]$AnthropicAuthToken,
  [string]$AnthropicBaseUrl,
  [string]$SettingsPath,
  [string]$ProfilesPath,
  [string]$ProfileName,
  [string]$UseProfile,
  [switch]$ListProfiles,
  [switch]$NoBackupCurrent,
  [switch]$SetEnvUser,
  [switch]$NoSetEnvUser,
  [switch]$PrintPowerShell,
  [switch]$PrintLinux,
  [switch]$RevealToken
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Resolve-UserHomePath {
  $userHome = $env:USERPROFILE
  if (-not [string]::IsNullOrWhiteSpace($userHome)) {
    return $userHome
  }
  $homeEnv = $env:HOME
  if (-not [string]::IsNullOrWhiteSpace($homeEnv)) {
    return $homeEnv
  }
  if (-not [string]::IsNullOrWhiteSpace($HOME)) {
    return $HOME
  }
  throw "无法确定用户目录（USERPROFILE/HOME 均为空）。"
}

function ConvertFrom-SecureStringToPlainText {
  param(
    [Parameter(Mandatory = $true)]
    [Security.SecureString]$SecureString
  )
  $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($SecureString)
  try {
    return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
  } finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
  }
}

function Read-ClaudeSettingsJson {
  param([string]$Path)

  if (-not (Test-Path -LiteralPath $Path)) {
    return $null
  }
  try {
    $raw = Get-Content -LiteralPath $Path -Raw -ErrorAction Stop
    if ([string]::IsNullOrWhiteSpace($raw)) {
      return $null
    }
    return ($raw | ConvertFrom-Json -ErrorAction Stop)
  } catch {
    Write-Warning ("读取/解析失败，将覆盖写入：{0}。原因：{1}" -f $Path, $_.Exception.Message)
    return $null
  }
}

function Write-TextFileUtf8NoBom {
  param(
    [Parameter(Mandatory = $true)]
    [string]$Path,
    [Parameter(Mandatory = $true)]
    [string]$Content
  )
  $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
  [System.IO.File]::WriteAllText($Path, $Content, $utf8NoBom)
}

function ConvertTo-HashtableDeep {
  param([object]$InputObject)

  if ($null -eq $InputObject) { return $null }

  if ($InputObject -is [System.Collections.IDictionary]) {
    $result = @{}
    foreach ($key in $InputObject.Keys) {
      $result[$key] = ConvertTo-HashtableDeep -InputObject $InputObject[$key]
    }
    return $result
  }

  if ($InputObject -is [pscustomobject]) {
    $result = @{}
    foreach ($prop in $InputObject.PSObject.Properties) {
      $result[$prop.Name] = ConvertTo-HashtableDeep -InputObject $prop.Value
    }
    return $result
  }

  if (($InputObject -is [System.Collections.IEnumerable]) -and -not ($InputObject -is [string])) {
    $items = @()
    foreach ($item in $InputObject) {
      $items += ,(ConvertTo-HashtableDeep -InputObject $item)
    }
    return $items
  }

  return $InputObject
}

function New-ClaudeProfileStore {
  return @{
    version = 1
    active_profile = ""
    profiles = @{}
  }
}

function Get-DefaultProfilesPath {
  return (Join-Path $PSScriptRoot "claude_profiles.local.json")
}

function Read-ClaudeProfileStore {
  param([string]$Path)

  if (-not (Test-Path -LiteralPath $Path)) {
    return (New-ClaudeProfileStore)
  }

  try {
    $raw = Get-Content -LiteralPath $Path -Raw -ErrorAction Stop
    if ([string]::IsNullOrWhiteSpace($raw)) {
      return (New-ClaudeProfileStore)
    }
    $obj = $raw | ConvertFrom-Json -ErrorAction Stop
    $store = ConvertTo-HashtableDeep -InputObject $obj
    if (-not $store) { return (New-ClaudeProfileStore) }
    if (-not $store.ContainsKey("profiles") -or -not ($store["profiles"] -is [System.Collections.IDictionary])) {
      $store["profiles"] = @{}
    }
    if (-not $store.ContainsKey("active_profile")) { $store["active_profile"] = "" }
    if (-not $store.ContainsKey("version")) { $store["version"] = 1 }
    return $store
  } catch {
    Write-Warning ("读取/解析 profiles 失败，将重新创建：{0}。原因：{1}" -f $Path, $_.Exception.Message)
    return (New-ClaudeProfileStore)
  }
}

function Write-ClaudeProfileStore {
  param(
    [Parameter(Mandatory = $true)]
    [hashtable]$Store,
    [Parameter(Mandatory = $true)]
    [string]$Path
  )

  $payload = [ordered]@{
    version = $Store["version"]
    active_profile = $Store["active_profile"]
    profiles = $Store["profiles"]
  }
  $json = $payload | ConvertTo-Json -Depth 20
  if (-not $json.EndsWith("`n")) { $json += "`n" }

  $dir = Split-Path -Parent $Path
  if (-not [string]::IsNullOrWhiteSpace($dir)) {
    New-Item -ItemType Directory -Force -Path $dir | Out-Null
  }
  Write-TextFileUtf8NoBom -Path $Path -Content $json
}

function Protect-AnthropicToken {
  param([string]$Token)
  $secure = ConvertTo-SecureString -String $Token -AsPlainText -Force
  return (ConvertFrom-SecureString -SecureString $secure)
}

function Unprotect-AnthropicToken {
  param([string]$ProtectedToken)
  if ([string]::IsNullOrWhiteSpace($ProtectedToken)) { return "" }
  $secure = ConvertTo-SecureString -String $ProtectedToken
  return (ConvertFrom-SecureStringToPlainText -SecureString $secure)
}

function Get-ProfileNameFromBaseUrl {
  param([string]$BaseUrl)

  if ([string]::IsNullOrWhiteSpace($BaseUrl)) { return "default" }

  $raw = $BaseUrl.Trim()
  try {
    $uri = [Uri]$raw
    $host = $uri.Host
    $path = $uri.AbsolutePath
    if (-not $uri.IsDefaultPort) {
      $host = "{0}_{1}" -f $host, $uri.Port
    }
    $raw = ($host + $path).Trim("/")
  } catch {
    # 非标准 URL：直接使用原始字符串做清洗
  }

  # 兜底：无论是否成功解析，都移除 scheme / query / fragment
  $raw = ($raw -replace "^[A-Za-z][A-Za-z0-9+.-]*://", "")
  $raw = ($raw -replace "[\\?#].*$", "").Trim("/")

  $name = ($raw -replace "[^A-Za-z0-9]+", "_").Trim("_")
  if ([string]::IsNullOrWhiteSpace($name)) { return "default" }
  return $name
}

function Get-UniqueProfileName {
  param(
    [Parameter(Mandatory = $true)]
    [hashtable]$Profiles,
    [Parameter(Mandatory = $true)]
    [string]$BaseName
  )

  if (-not $Profiles.ContainsKey($BaseName)) { return $BaseName }

  for ($i = 2; $i -lt 10000; $i++) {
    $candidate = "{0}_{1}" -f $BaseName, $i
    if (-not $Profiles.ContainsKey($candidate)) { return $candidate }
  }

  throw ("无法生成可用的 profile 名称：{0}" -f $BaseName)
}

function Write-ProfileList {
  param(
    [hashtable]$Store,
    [string]$Path
  )

  Write-Host ("Profiles 文件：{0}" -f $Path)

  $profiles = $Store["profiles"]
  if (-not $profiles -or $profiles.Keys.Count -eq 0) {
    Write-Host "暂无 profiles。"
    return
  }

  $active = [string]$Store["active_profile"]
  foreach ($name in ($profiles.Keys | Sort-Object)) {
    $p = $profiles[$name]
    $baseUrl = if ($p -and ($p -is [System.Collections.IDictionary]) -and $p.ContainsKey("anthropic_base_url")) { [string]$p["anthropic_base_url"] } else { "" }
    $mark = if ($name -eq $active) { "*" } else { " " }
    Write-Host ("{0} {1}  {2}" -f $mark, $name, $baseUrl)
  }
}

if ([string]::IsNullOrWhiteSpace($SettingsPath)) {
  $SettingsPath = Join-Path (Resolve-UserHomePath) ".claude/settings.json"
}

$profilesPathResolved = $ProfilesPath
if ([string]::IsNullOrWhiteSpace($profilesPathResolved)) {
  $profilesPathResolved = Get-DefaultProfilesPath
}

$profileStore = Read-ClaudeProfileStore -Path $profilesPathResolved

if ($ListProfiles) {
  Write-ProfileList -Store $profileStore -Path $profilesPathResolved
  if ([string]::IsNullOrWhiteSpace($UseProfile)) {
    return
  }
}

$existing = Read-ClaudeSettingsJson -Path $SettingsPath
$existingEnv = if ($existing -and $existing.PSObject.Properties.Name -contains "env") { $existing.env } else { $null }

$userEnvBaseUrl = [Environment]::GetEnvironmentVariable("ANTHROPIC_BASE_URL", "User")
$userEnvToken = [Environment]::GetEnvironmentVariable("ANTHROPIC_AUTH_TOKEN", "User")

$settingsBaseUrl = if ($existingEnv) { [string]$existingEnv.ANTHROPIC_BASE_URL } else { "" }
$settingsToken = if ($existingEnv) { [string]$existingEnv.ANTHROPIC_AUTH_TOKEN } else { "" }

$currentBaseUrl = if (-not [string]::IsNullOrWhiteSpace($env:ANTHROPIC_BASE_URL)) { $env:ANTHROPIC_BASE_URL } elseif (-not [string]::IsNullOrWhiteSpace($userEnvBaseUrl)) { $userEnvBaseUrl } else { $settingsBaseUrl }
$currentToken = if (-not [string]::IsNullOrWhiteSpace($env:ANTHROPIC_AUTH_TOKEN)) { $env:ANTHROPIC_AUTH_TOKEN } elseif (-not [string]::IsNullOrWhiteSpace($userEnvToken)) { $userEnvToken } else { $settingsToken }

$resolvedBaseUrl = ""
$resolvedToken = ""
$resolvedProfileName = ""

if (-not [string]::IsNullOrWhiteSpace($UseProfile)) {
  $profiles = $profileStore["profiles"]
  if (-not $profiles.ContainsKey($UseProfile)) {
    throw ("未找到 profile：{0}。可用 -ListProfiles 查看。" -f $UseProfile)
  }
  $p = $profiles[$UseProfile]
  if (-not ($p -is [System.Collections.IDictionary])) {
    throw ("profile 格式异常：{0}" -f $UseProfile)
  }
  $resolvedBaseUrl = [string]$p["anthropic_base_url"]
  $resolvedToken = Unprotect-AnthropicToken -ProtectedToken ([string]$p["anthropic_auth_token_secure"])
  $resolvedProfileName = $UseProfile
} else {
  $resolvedBaseUrl = $AnthropicBaseUrl
  if ([string]::IsNullOrWhiteSpace($resolvedBaseUrl)) { $resolvedBaseUrl = $env:ANTHROPIC_BASE_URL }
  if ([string]::IsNullOrWhiteSpace($resolvedBaseUrl)) { $resolvedBaseUrl = $userEnvBaseUrl }
  if ([string]::IsNullOrWhiteSpace($resolvedBaseUrl)) { $resolvedBaseUrl = $settingsBaseUrl }
  if ([string]::IsNullOrWhiteSpace($resolvedBaseUrl)) { $resolvedBaseUrl = "https://www.right.codes/claude" }

  $resolvedToken = $AnthropicAuthToken
  if ([string]::IsNullOrWhiteSpace($resolvedToken)) { $resolvedToken = $env:ANTHROPIC_AUTH_TOKEN }
  if ([string]::IsNullOrWhiteSpace($resolvedToken)) { $resolvedToken = $userEnvToken }
  if ([string]::IsNullOrWhiteSpace($resolvedToken)) { $resolvedToken = $settingsToken }

  if ([string]::IsNullOrWhiteSpace($ProfileName)) {
    $resolvedProfileName = Get-ProfileNameFromBaseUrl -BaseUrl $resolvedBaseUrl
  } else {
    $resolvedProfileName = $ProfileName.Trim()
  }
}

if ([string]::IsNullOrWhiteSpace($resolvedToken)) {
  $secure = Read-Host "请输入 ANTHROPIC_AUTH_TOKEN（不会回显）" -AsSecureString
  $resolvedToken = ConvertFrom-SecureStringToPlainText -SecureString $secure
}

if ([string]::IsNullOrWhiteSpace($resolvedToken)) {
  throw "未提供 ANTHROPIC_AUTH_TOKEN。请通过 -AnthropicAuthToken 参数或交互输入提供。"
}

$profiles = $profileStore["profiles"]
$now = (Get-Date).ToString("yyyy-MM-ddTHH:mm:ssK")

# 先备份当前已生效的配置（避免切换后找不回）
if (-not $NoBackupCurrent) {
  if (-not [string]::IsNullOrWhiteSpace($currentBaseUrl) -and -not [string]::IsNullOrWhiteSpace($currentToken)) {
    $sameAsTarget = ($currentBaseUrl -eq $resolvedBaseUrl) -and ($currentToken -eq $resolvedToken)
    if (-not $sameAsTarget) {
      $backupBase = "backup"
      $backupName = Get-UniqueProfileName -Profiles $profiles -BaseName $backupBase
      $profiles[$backupName] = @{
        anthropic_base_url = $currentBaseUrl
        anthropic_auth_token_secure = (Protect-AnthropicToken -Token $currentToken)
        claude_code_disable_nonessential_traffic = "1"
        always_thinking_enabled = $true
        source = "auto_backup"
        created_at = $now
        updated_at = $now
        last_used_at = $now
      }
    }
  }
}

# 保存/更新目标 profile（同站点多 Token：默认不覆盖，自动追加后缀）
if ([string]::IsNullOrWhiteSpace($resolvedProfileName)) {
  $resolvedProfileName = Get-ProfileNameFromBaseUrl -BaseUrl $resolvedBaseUrl
}
if ([string]::IsNullOrWhiteSpace($resolvedProfileName)) {
  $resolvedProfileName = "default"
}

$explicitProfileName = -not [string]::IsNullOrWhiteSpace($ProfileName)
$finalProfileName = $resolvedProfileName
if ($profiles.ContainsKey($finalProfileName) -and -not $explicitProfileName -and [string]::IsNullOrWhiteSpace($UseProfile)) {
  $existingProfile = $profiles[$finalProfileName]
  if ($existingProfile -is [System.Collections.IDictionary]) {
    $existingBaseUrl = [string]$existingProfile["anthropic_base_url"]
    $existingToken = ""
    try {
      $existingToken = Unprotect-AnthropicToken -ProtectedToken ([string]$existingProfile["anthropic_auth_token_secure"])
    } catch {
      $existingToken = ""
    }
    if (-not ($existingBaseUrl -eq $resolvedBaseUrl -and $existingToken -eq $resolvedToken)) {
      $finalProfileName = Get-UniqueProfileName -Profiles $profiles -BaseName $finalProfileName
    }
  } else {
    $finalProfileName = Get-UniqueProfileName -Profiles $profiles -BaseName $finalProfileName
  }
}

if ([string]::IsNullOrWhiteSpace($UseProfile)) {
  $createdAt = $now
  if ($profiles.ContainsKey($finalProfileName)) {
    $ep = $profiles[$finalProfileName]
    if ($ep -is [System.Collections.IDictionary] -and $ep.ContainsKey("created_at")) {
      $createdAt = [string]$ep["created_at"]
    }
  }
  $profiles[$finalProfileName] = @{
    anthropic_base_url = $resolvedBaseUrl
    anthropic_auth_token_secure = (Protect-AnthropicToken -Token $resolvedToken)
    claude_code_disable_nonessential_traffic = "1"
    always_thinking_enabled = $true
    source = "manual"
    created_at = $createdAt
    updated_at = $now
    last_used_at = $now
  }
}

$profileStore["active_profile"] = $finalProfileName

if ($PSCmdlet.ShouldProcess($profilesPathResolved, "保存 Claude profiles")) {
  Write-ClaudeProfileStore -Store $profileStore -Path $profilesPathResolved
  Write-Host ("已保存 profiles：{0}" -f $profilesPathResolved)
  Write-Host ("当前 profile：{0}" -f $finalProfileName)
}

$targetSettings = [ordered]@{
  env = [ordered]@{
    ANTHROPIC_AUTH_TOKEN = $resolvedToken
    ANTHROPIC_BASE_URL = $resolvedBaseUrl
    CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC = "1"
  }
  permissions = [ordered]@{
    allow = @()
    deny = @()
  }
  alwaysThinkingEnabled = $true
}

$json = $targetSettings | ConvertTo-Json -Depth 20
if (-not $json.EndsWith("`n")) { $json += "`n" }

$settingsDir = Split-Path -Parent $SettingsPath
New-Item -ItemType Directory -Force -Path $settingsDir | Out-Null

if ($PSCmdlet.ShouldProcess($SettingsPath, "写入 Claude settings.json")) {
  Write-TextFileUtf8NoBom -Path $SettingsPath -Content $json
  Write-Host ("已写入：{0}" -f $SettingsPath)
  Write-Host ("ANTHROPIC_BASE_URL：{0}" -f $resolvedBaseUrl)
  Write-Host "ANTHROPIC_AUTH_TOKEN：已设置（已隐藏）"
}

if ($SetEnvUser -and $NoSetEnvUser) {
  throw "参数冲突：-SetEnvUser 与 -NoSetEnvUser 不能同时使用。"
}

$shouldSetEnvUser = $true
if ($NoSetEnvUser) { $shouldSetEnvUser = $false }

if ($shouldSetEnvUser) {
  if ($PSCmdlet.ShouldProcess("用户级环境变量", "写入 ANTHROPIC_*")) {
    [System.Environment]::SetEnvironmentVariable("ANTHROPIC_BASE_URL", $resolvedBaseUrl, [System.EnvironmentVariableTarget]::User)
    [System.Environment]::SetEnvironmentVariable("ANTHROPIC_AUTH_TOKEN", $resolvedToken, [System.EnvironmentVariableTarget]::User)
    [System.Environment]::SetEnvironmentVariable("CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC", "1", [System.EnvironmentVariableTarget]::User)
    Write-Host "已写入用户级环境变量（需要重启终端/编辑器后生效）。"
  }
}

function Get-MaskedToken {
  param([string]$Token, [switch]$Reveal)
  if ($Reveal) { return $Token }
  return "<你的API密钥>"
}

if ($PrintPowerShell) {
  $tokenForPrint = Get-MaskedToken -Token $resolvedToken -Reveal:$RevealToken
  Write-Host ""
  Write-Host "# PowerShell（临时：仅当前会话）"
  Write-Host ('$env:ANTHROPIC_BASE_URL = "{0}"' -f $resolvedBaseUrl)
  Write-Host ('$env:ANTHROPIC_AUTH_TOKEN = "{0}"' -f $tokenForPrint)
  Write-Host '$env:CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC = "1"'
  Write-Host ""
  Write-Host "# PowerShell（永久：用户级）"
  Write-Host ("[System.Environment]::SetEnvironmentVariable(""ANTHROPIC_BASE_URL"", ""{0}"", [System.EnvironmentVariableTarget]::User)" -f $resolvedBaseUrl)
  Write-Host ("[System.Environment]::SetEnvironmentVariable(""ANTHROPIC_AUTH_TOKEN"", ""{0}"", [System.EnvironmentVariableTarget]::User)" -f $tokenForPrint)
  Write-Host "[System.Environment]::SetEnvironmentVariable(""CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC"", ""1"", [System.EnvironmentVariableTarget]::User)"
}

if ($PrintLinux) {
  $tokenForPrint = Get-MaskedToken -Token $resolvedToken -Reveal:$RevealToken
  $rcFile = "~/.bashrc"
  Write-Host ""
  Write-Host "# Linux/macOS（临时：仅当前 shell）"
  Write-Host ("export ANTHROPIC_BASE_URL=""{0}""" -f $resolvedBaseUrl)
  Write-Host ("export ANTHROPIC_AUTH_TOKEN=""{0}""" -f $tokenForPrint)
  Write-Host "export CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=""1"""
  Write-Host ""
  Write-Host "# Linux/macOS（永久：写入 ~/.bashrc 或 ~/.zshrc 后 source 生效）"
  Write-Host ("echo 'export ANTHROPIC_BASE_URL=""{0}""' >> {1}" -f $resolvedBaseUrl, $rcFile)
  Write-Host ("echo 'export ANTHROPIC_AUTH_TOKEN=""{0}""' >> {1}" -f $tokenForPrint, $rcFile)
  Write-Host ("echo 'export CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=""1""' >> {0}" -f $rcFile)
  Write-Host ("# 如果你使用 zsh，请把 {0} 改成 ~/.zshrc" -f $rcFile)
}
