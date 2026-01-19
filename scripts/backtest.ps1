#!/usr/bin/env pwsh
<#
.SYNOPSIS
    批量回测脚本

.DESCRIPTION
    自动执行多个策略的回测，收集结果并生成对比报告

.PARAMETER Strategies
    策略名称列表（逗号分隔），如果不指定则回测所有策略

.PARAMETER Config
    配置文件路径，默认为 ft_userdir/config.json

.PARAMETER Timerange
    时间范围，格式：20200101-20201231

.PARAMETER OutputDir
    输出目录，默认为 docs/reports/backtest

.EXAMPLE
    ./scripts/backtest.ps1 -Strategies "SimpleMVPStrategy,ETHHighFreqStrategy"

.EXAMPLE
    ./scripts/backtest.ps1 -Timerange "20230101-20231231"
#>

param(
    [string]$Strategies = "",
    [string]$Config = "ft_userdir/config.json",
    [string]$Timerange = "",
    [string]$OutputDir = "docs/reports/backtest"
)

# 设置错误处理
$ErrorActionPreference = "Stop"

# 获取项目根目录
$ProjectRoot = Split-Path -Parent $PSScriptRoot

# 切换到项目根目录
Push-Location $ProjectRoot

try {
    Write-Host "=== 批量回测开始 ===" -ForegroundColor Green
    Write-Host ""

    # 获取策略列表
    if ($Strategies) {
        $StrategyList = $Strategies -split ","
    } else {
        Write-Host "获取所有可用策略..." -ForegroundColor Cyan
        $StrategyOutput = & ./scripts/ft.ps1 list-strategies --userdir "./ft_userdir" 2>&1
        $StrategyList = $StrategyOutput | Where-Object { $_ -match "^\s*-\s*(.+)$" } | ForEach-Object { $Matches[1].Trim() }
    }

    Write-Host "将回测以下策略：" -ForegroundColor Cyan
    $StrategyList | ForEach-Object { Write-Host "  - $_" }
    Write-Host ""

    # 创建输出目录
    $Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $ResultDir = Join-Path $OutputDir $Timestamp
    New-Item -ItemType Directory -Path $ResultDir -Force | Out-Null

    Write-Host "结果将保存到: $ResultDir" -ForegroundColor Cyan
    Write-Host ""

    # 批量执行回测
    $ResultFiles = @()
    $SuccessCount = 0
    $FailCount = 0

    foreach ($Strategy in $StrategyList) {
        Write-Host "[$($SuccessCount + $FailCount + 1)/$($StrategyList.Count)] 回测策略: $Strategy" -ForegroundColor Yellow

        $BacktestArgs = @(
            "backtesting",
            "--strategy", $Strategy,
            "--config", $Config,
            "--export", "trades",
            "--export-filename", "$ResultDir/$Strategy.json"
        )

        if ($Timerange) {
            $BacktestArgs += "--timerange", $Timerange
        }

        try {
            & ./scripts/ft.ps1 @BacktestArgs
            if ($LASTEXITCODE -eq 0) {
                Write-Host "  ✓ 回测成功" -ForegroundColor Green
                $ResultFiles += "$ResultDir/$Strategy.json"
                $SuccessCount++
            } else {
                Write-Host "  ✗ 回测失败 (退出码: $LASTEXITCODE)" -ForegroundColor Red
                $FailCount++
            }
        } catch {
            Write-Host "  ✗ 回测失败: $_" -ForegroundColor Red
            $FailCount++
        }

        Write-Host ""
    }

    Write-Host "=== 回测完成 ===" -ForegroundColor Green
    Write-Host "成功: $SuccessCount, 失败: $FailCount" -ForegroundColor Cyan
    Write-Host ""

    # 生成对比报告
    if ($ResultFiles.Count -gt 0) {
        Write-Host "生成对比报告..." -ForegroundColor Cyan
        $ReportScript = @"
import sys
from pathlib import Path
sys.path.insert(0, str(Path('$ProjectRoot').resolve()))

from scripts.lib.backtest_utils import compare_results, generate_markdown_report

result_files = [
$($ResultFiles | ForEach-Object { "    Path('$_')," })
]

df = compare_results(result_files)
if not df.empty:
    print(df.to_string())
    generate_markdown_report(df, Path('$ResultDir/report.md'))
    print('\n报告已生成: $ResultDir/report.md')
else:
    print('没有有效的回测结果')
"@

        $ReportScript | uv run python -
    }

} finally {
    Pop-Location
}
