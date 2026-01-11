<#
.SYNOPSIS
    检查 GITHUB_MCP_PAT 环境变量状态

.DESCRIPTION
    检查 GITHUB_MCP_PAT 在不同级别（进程/用户/系统）的设置情况，
    帮助诊断 GitHub MCP 连接问题。

.EXAMPLE
    .\check_pat.ps1
#>

$processPat = $env:GITHUB_MCP_PAT
$userPat = [Environment]::GetEnvironmentVariable('GITHUB_MCP_PAT', 'User')
$machinePat = [Environment]::GetEnvironmentVariable('GITHUB_MCP_PAT', 'Machine')

Write-Host "GITHUB_MCP_PAT 环境变量检查："
Write-Host ""

if ($processPat) {
  Write-Host "[进程] 已设置，长度: $($processPat.Length)" -ForegroundColor Green
} else {
  Write-Host "[进程] 未设置" -ForegroundColor Yellow
}

if ($userPat) {
  Write-Host "[用户] 已设置，长度: $($userPat.Length)" -ForegroundColor Green
} else {
  Write-Host "[用户] 未设置" -ForegroundColor Gray
}

if ($machinePat) {
  Write-Host "[系统] 已设置，长度: $($machinePat.Length)" -ForegroundColor Green
} else {
  Write-Host "[系统] 未设置" -ForegroundColor Gray
}

Write-Host ""
if (-not $processPat -and ($userPat -or $machinePat)) {
  Write-Host "提示：环境变量已在用户/系统级别设置，但当前进程未读取。" -ForegroundColor Yellow
  Write-Host "请重启 VSCode/终端后重试。" -ForegroundColor Yellow
} elseif (-not $processPat -and -not $userPat -and -not $machinePat) {
  Write-Host "提示：未检测到 GITHUB_MCP_PAT，请先设置环境变量。" -ForegroundColor Red
}
