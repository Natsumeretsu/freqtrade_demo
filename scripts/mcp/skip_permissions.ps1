<#
.SYNOPSIS
    以免授权模式启动 Claude Code

.DESCRIPTION
    包装 claude --dangerously-skip-permissions，减少执行动作时的授权打断。
    所有参数会透传给 claude CLI。

.EXAMPLE
    .\skip_permissions.ps1
    .\skip_permissions.ps1 mcp list
#>
[CmdletBinding()]
param(
  [Parameter(ValueFromRemainingArguments = $true)]
  [string[]]$Arguments
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$claudeCmd = Get-Command "claude" -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $claudeCmd) {
  throw "未找到命令：claude。请先安装 Claude Code（claude CLI），并确保 claude 在 PATH 中。"
}

& $claudeCmd.Source "--dangerously-skip-permissions" @Arguments
exit $LASTEXITCODE

