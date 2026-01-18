# 评估工具使用指南

更新日期：2026-01-17


本文档提供完整的策略评估工具使用说明，帮助你系统地分析回测结果的真实性和因子质量。

## 目录

1. [工具概览](#工具概览)
2. [快速开始](#快速开始)
3. [工具详细说明](#工具详细说明)
4. [完整评估流程](#完整评估流程)
5. [常见问题](#常见问题)

---

## 工具概览

所有评估工具位于 `scripts/evaluation/` 目录，分为三类：

### Phase 1 - P0 工具（关键，必须使用）

| 工具 | 用途 | 输入 |
|------|------|------|
| `quick_diagnosis.py` | 快速诊断回测结果 | 回测 zip 文件 |
| `dynamic_slippage.py` | 基于 ATR 的动态滑点分析 | 回测 zip + OHLCV 数据 |
| `funding_rate_analysis.py` | 期货资金费率成本估算 | 回测 zip 文件 |
| `extreme_event_stress_test.py` | 极端事件压力测试 | 回测 zip 文件 |
| `parameter_plateau_test.py` | 参数稳定性测试 | 策略 + 配置 + 时间范围 |

### Phase 1 - P1 工具（重要，建议使用）

| 工具 | 用途 | 输入 |
|------|------|------|
| `ic_decay_analysis.py` | IC 衰减曲线分析 | 因子数据 + OHLCV 数据 |
| `turnover_adjusted_ic.py` | 换手率调整 IC 计算 | 因子 + 信号 + 收益率数据 |
| `factor_orthogonality_check.py` | 因子正交性检查 | 因子数据 |

### Phase 2 - P2 工具（可选，锦上添花）

| 工具 | 用途 | 输入 |
|------|------|------|
| `omega_ratio.py` | Omega 比率计算 | 回测 zip 文件 |
| `ulcer_index.py` | Ulcer Index 计算 | 回测 zip 文件 |

---

## 快速开始

### 最小评估流程（5 分钟）

如果时间有限，至少运行快速诊断：

```powershell
# 1. 运行回测
./scripts/ft.ps1 backtesting `
    --strategy YourStrategy `
    --config your_config.json `
    --timerange 20250101-20260116

# 2. 快速诊断
uv run python -X utf8 scripts/evaluation/quick_diagnosis.py `
    --zip "01_freqtrade/user_data/backtest_results/backtest-result-<timestamp>.zip"
```

**关键指标**：
- 盈亏比 ≥ 1.5
- 黑天鹅事件 < 5 笔
- 最大单笔亏损 ≤ -8%

---

## 工具详细说明

### 1. quick_diagnosis.py - 快速诊断

**用途**：揭示回测结果的真实性，识别"高胜率陷阱"。

**使用方法**：
```powershell
uv run python -X utf8 scripts/evaluation/quick_diagnosis.py `
    --zip "path/to/backtest-result.zip" `
    --base-slippage 0.0005
```

**参数说明**：
- `--zip`: 回测结果 zip 文件路径（必需）
- `--strategy`: 策略名（可选，多策略时需要）
- `--base-slippage`: 基础滑点（默认 0.05%）

**输出解读**：

```
【盈亏比分析】
  盈利笔数: 167
  亏损笔数: 16
  平均盈利: 1.815%
  平均亏损: 19.015%
  盈亏比: 0.095  ← 关键指标！应 ≥ 1.5
  
  [!] 警告：检测到'高胜率陷阱'！
      胜率 91.3% 但盈亏比仅 0.10
```

**判断标准**：
- 盈亏比 < 1.0: 策略不可持续
- 盈亏比 1.0-1.5: 勉强可用
- 盈亏比 ≥ 1.5: 健康策略

---

### 2. dynamic_slippage.py - 动态滑点分析

**用途**：基于 ATR 计算真实滑点成本。

**使用方法**：
```powershell
uv run python scripts/evaluation/dynamic_slippage.py `
    --zip "path/to/backtest-result.zip" `
    --data-dir "01_freqtrade/user_data/data/okx"
```

**关键输出**：成本增加百分比，如果 > 50% 说明真实成本严重侵蚀收益。

---

### 3. funding_rate_analysis.py - 资金费率分析

**用途**：估算期货持仓的资金费率成本（每 8 小时结算）。

**使用方法**：
```powershell
uv run python scripts/evaluation/funding_rate_analysis.py `
    --zip "path/to/backtest-result.zip"
```

---

## 完整评估流程

### 阶段 1：基础诊断（必做）

```powershell
# 运行快速诊断
uv run python -X utf8 scripts/evaluation/quick_diagnosis.py --zip <your-zip>
```

**验收标准**：
- ✅ 盈亏比 ≥ 1.5
- ✅ 黑天鹅事件 < 5 笔
- ✅ 总收益 > 0%

### 阶段 2：成本验证（必做）

```powershell
# 动态滑点
uv run python scripts/evaluation/dynamic_slippage.py --zip <zip> --data-dir <data>

# 资金费率
uv run python scripts/evaluation/funding_rate_analysis.py --zip <zip>
```

### 阶段 3：因子分析（建议）

需要准备因子数据文件（CSV 格式）。

---

## 常见问题

**Q: 工具需要什么格式的输入数据？**

A: 
- 回测结果：Freqtrade 标准 zip 格式
- 因子数据：CSV，包含 date, pair, factor_value 列
- OHLCV 数据：Feather 格式（Freqtrade 标准）

**Q: 如何判断策略是否可以实盘？**

A: 必须满足：
1. 盈亏比 ≥ 1.5
2. 扣除真实成本后仍盈利
3. 极端事件压力测试得分 ≥ 60
4. 参数稳定性得分 ≥ 60

---

**文档版本**：v1.0  
**创建日期**：2026-01-16  
**作者**：Claude (Sonnet 4.5)
