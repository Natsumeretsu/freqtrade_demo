# MkDocs 本地预览启动脚本
# 用法: ./scripts/docs/serve.ps1

Write-Host "启动 MkDocs 本地预览服务器..." -ForegroundColor Green
Write-Host "访问地址: http://127.0.0.1:8000" -ForegroundColor Cyan
Write-Host "按 Ctrl+C 停止服务器" -ForegroundColor Yellow
Write-Host ""

Set-Location "$PSScriptRoot\..\.."
uv run mkdocs serve
