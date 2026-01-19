#!/usr/bin/env pwsh
<#
.SYNOPSIS
    数据版本管理工具

.DESCRIPTION
    管理历史数据的版本，支持快照、列表、恢复等操作

.PARAMETER Action
    操作类型：snapshot（创建快照）、list（列出版本）、restore（恢复版本）

.PARAMETER VersionId
    版本ID（用于 restore 操作）

.PARAMETER Description
    快照描述（用于 snapshot 操作）

.EXAMPLE
    ./scripts/data_version.ps1 -Action snapshot -Description "初始数据"

.EXAMPLE
    ./scripts/data_version.ps1 -Action list

.EXAMPLE
    ./scripts/data_version.ps1 -Action restore -VersionId "20260119_120000"
#>

param(
    [Parameter(Mandatory=$true)]
    [ValidateSet("snapshot", "list", "restore")]
    [string]$Action,

    [string]$VersionId = "",
    [string]$Description = ""
)

# 设置错误处理
$ErrorActionPreference = "Stop"

# 获取项目根目录
$ProjectRoot = Split-Path -Parent $PSScriptRoot

# 切换到项目根目录
Push-Location $ProjectRoot

try {
    switch ($Action) {
        "snapshot" {
            Write-Host "创建数据快照..." -ForegroundColor Cyan
            $Script = @"
import sys
from pathlib import Path
sys.path.insert(0, str(Path('$ProjectRoot').resolve()))

from scripts.lib.data_version_manager import DataVersionManager

manager = DataVersionManager()
version_id = manager.create_snapshot(description='$Description')
print(f'快照已创建: {version_id}')
"@
            $Script | uv run python -
        }

        "list" {
            Write-Host "版本列表:" -ForegroundColor Cyan
            $Script = @"
import sys
from pathlib import Path
sys.path.insert(0, str(Path('$ProjectRoot').resolve()))

from scripts.lib.data_version_manager import DataVersionManager

manager = DataVersionManager()
versions = manager.list_versions()

if not versions:
    print('没有版本记录')
else:
    for v in versions:
        print(f"\n版本ID: {v['version_id']}")
        print(f"时间: {v['timestamp']}")
        print(f"描述: {v['description']}")
        print(f"文件数: {v['file_count']}")
        if v.get('tags'):
            print(f"标签: {', '.join(v['tags'])}")
"@
            $Script | uv run python -
        }

        "restore" {
            if (-not $VersionId) {
                Write-Host "错误: 必须指定 -VersionId 参数" -ForegroundColor Red
                exit 1
            }

            Write-Host "恢复到版本: $VersionId" -ForegroundColor Yellow
            Write-Host "警告: 这将覆盖当前数据！" -ForegroundColor Red
            $Confirm = Read-Host "确认继续？(y/N)"

            if ($Confirm -ne "y") {
                Write-Host "已取消" -ForegroundColor Yellow
                exit 0
            }

            $Script = @"
import sys
from pathlib import Path
sys.path.insert(0, str(Path('$ProjectRoot').resolve()))

from scripts.lib.data_version_manager import DataVersionManager

manager = DataVersionManager()
success = manager.restore_version('$VersionId')

if success:
    print('恢复成功')
else:
    print('恢复失败: 版本不存在')
    sys.exit(1)
"@
            $Script | uv run python -
        }
    }

} finally {
    Pop-Location
}
