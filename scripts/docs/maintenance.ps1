# 文档维护统一入口脚本
# 用法: ./scripts/docs/maintenance.ps1 [选项]

param(
    [switch]$CheckMetadata,    # 检查元数据
    [switch]$CheckLinks,       # 检查链接
    [switch]$DetectOutdated,   # 检测过时文档
    [switch]$All               # 执行所有检查
)

$ProjectRoot = "$PSScriptRoot\..\.."

Write-Host "=== 文档维护工具 ===" -ForegroundColor Green
Write-Host ""

if ($All -or $CheckMetadata) {
    Write-Host "[1/3] 检查文档元数据..." -ForegroundColor Cyan
    python "$ProjectRoot/scripts/tools/check_doc_metadata.py"
    Write-Host ""
}

if ($All -or $CheckLinks) {
    Write-Host "[2/3] 检查文档链接..." -ForegroundColor Cyan
    python "$ProjectRoot/scripts/tools/check_doc_links.py"
    Write-Host ""
}

if ($All -or $DetectOutdated) {
    Write-Host "[3/3] 检测过时文档..." -ForegroundColor Cyan
    python "$ProjectRoot/scripts/tools/detect_outdated_docs.py"
    Write-Host ""
}

if (-not ($All -or $CheckMetadata -or $CheckLinks -or $DetectOutdated)) {
    Write-Host "用法示例:" -ForegroundColor Yellow
    Write-Host "  ./scripts/docs/maintenance.ps1 -All              # 执行所有检查"
    Write-Host "  ./scripts/docs/maintenance.ps1 -CheckMetadata    # 只检查元数据"
    Write-Host "  ./scripts/docs/maintenance.ps1 -CheckLinks       # 只检查链接"
    Write-Host "  ./scripts/docs/maintenance.ps1 -DetectOutdated   # 只检测过时文档"
}

Write-Host "完成！" -ForegroundColor Green
