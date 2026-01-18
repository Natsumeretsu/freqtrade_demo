# freqtrade_demo

**更新日期**：2026-01-18

加密货币量化交易项目 - MVP 架构（回归量化交易本质）

---

## 📋 项目简介

本项目采用 **假设驱动 + 增量验证** 的量化研究方法，聚焦于发现真正有效的 alpha 因子，而非过早工程化。

**核心理念**：先找到真正有效的因子，再考虑工程化。

---

## 🏗️ 目录结构

```
freqtrade_demo/
├── 01_freqtrade/          # 执行层（Freqtrade 策略）
│   ├── config.json        # 运行配置
│   └── strategies/        # 策略文件
├── 02_qlib_research/      # 研究层（因子验证）
│   ├── data_pipeline/     # 数据下载与清洗
│   └── notebooks/         # Jupyter 研究笔记
├── 03_integration/        # 集成层（简化因子模块）
│   └── simple_factors/    # 基础因子计算
├── 04_shared/             # 共享配置
│   └── configs/           # 配置模板
├── scripts/               # 自动化脚本
└── docs/                  # 文档
```

---

## 🚀 快速开始

### 1. 环境初始化

```powershell
# 安装 Python 3.11 并同步依赖
uv python install "3.11"
uv sync --frozen

# 或使用一键初始化脚本
./scripts/bootstrap.ps1
```

### 2. 生成配置文件

```powershell
Copy-Item "04_shared/configs/config.example.json" "01_freqtrade/config.json"
Copy-Item "04_shared/configs/config-private.example.json" "01_freqtrade/config-private.json"
```

### 3. 下载数据

```powershell
# 下载 BTC/USDT 15分钟数据（最近90天）
cd 02_qlib_research/data_pipeline
python download.py --symbol BTC/USDT --timeframe 15m --days 90
```

---

## 📊 MVP 工作流程

### 阶段1：数据准备
- 下载 OHLCV 数据
- 数据清洗与质量检查
- 验证数据完整性

### 阶段2：因子验证
- 在 Jupyter Notebook 中研究因子
- 计算 IC（信息系数）、t 值
- 样本外测试验证稳定性
- **验收标准**：IC > 0.05，t 值 > 2

### 阶段3：策略构建
- 选择验证通过的因子
- 实现 SimpleMVPStrategy
- 回测验证（目标：夏普 > 1.5）

---

## 🔧 常用命令

### Freqtrade 操作

```powershell
# 查看可用策略
./scripts/ft.ps1 list-strategies

# 回测（示例）
./scripts/ft.ps1 backtesting --strategy SimpleMVPStrategy --config 01_freqtrade/config.json
```

**⚠️ 重要**：所有 Freqtrade 命令必须通过 `./scripts/ft.ps1` 执行，禁止直接运行 `freqtrade` 命令。

### 数据下载

```powershell
./scripts/data/download.ps1 `
  -Pairs "BTC/USDT:USDT" `
  -Timeframes "15m" `
  -TradingMode "futures" `
  -Timerange "20200101-"
```

---

## 📚 参考文档

- [重构总结](docs/REFACTOR_SUMMARY.md) - 了解项目重构动机与新架构
- [深度清理报告](docs/DEEP_CLEANUP_REPORT.md) - 查看清理统计
- [改进清单](docs/IMPROVEMENT_CHECKLIST.md) - 进一步改进建议

---

## ⚠️ 重要约定

### 禁止事项
- ❌ 不要过早优化（在因子验证通过之前）
- ❌ 不要重复造轮子（优先使用现有库）
- ❌ 不要跳过验证（每个因子必须通过统计检验）
- ❌ 不要过度工程化（保持代码简单）

### 必须遵守
- ✅ 假设驱动（每个因子都要有明确的盈利假设）
- ✅ 样本外测试（训练/验证/测试集严格分离）
- ✅ 记录失败（失败的因子也要记录原因）
- ✅ 增量验证（先单因子，再组合）

---

## 🎯 成果预期

### 短期目标（1个月）
- 验证 3-5 个候选因子
- 找到 1-2 个真正有效的因子（IC > 0.05）
- 构建最简单的 MVP 策略

### 中期目标（3个月）
- 策略在样本外测试中夏普 > 1.5
- 小资金实盘验证（$1000）
- 确认实际滑点、成交率

### 长期目标（6个月）
- 策略稳定盈利（月均收益 > 5%）
- 考虑扩展到其他币种
- 考虑工程化优化

---

**最后更新**：2026-01-18
