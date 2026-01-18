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
│   ├── data/              # 历史数据
│   └── strategies/        # 策略文件
├── 03_integration/        # 集成层（因子计算与验证）
│   ├── simple_factors/    # 基础因子计算
│   ├── data_pipeline.py   # 数据预处理
│   └── factor_validator.py # 因子验证
├── 04_shared/             # 共享配置
│   └── configs/           # 配置模板
├── scripts/               # 自动化脚本
│   ├── ft.ps1             # Freqtrade 命令包装器
│   └── data/              # 数据下载脚本
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
# 下载 BTC/USDT 15分钟数据（2020-2021年）
./scripts/data/download.ps1 `
  -Pairs "BTC/USDT:USDT" `
  -Timeframes "15m" `
  -TradingMode "futures" `
  -Timerange "20200101-20211231"
```

---

## 📊 MVP 工作流程

### 阶段1：数据准备
- 使用 `scripts/data/download.ps1` 下载 OHLCV 数据
- 数据自动保存到 `01_freqtrade/data/okx/futures/`
- 验证数据完整性

### 阶段2：因子验证
- 在 `03_integration/` 中实现因子计算函数
- 使用 `factor_validator.py` 计算 IC、t 值
- 编写单元测试验证因子逻辑
- **验收标准**：IC > 0.05，t 值 > 2

### 阶段3：策略构建
- 将验证通过的因子集成到策略中
- 使用 `./scripts/ft.ps1 backtesting` 回测
- 目标：夏普 > 1.5

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

- [架构说明](docs/ARCHITECTURE.md) - 了解项目架构设计
- [因子文档](docs/FACTORS.md) - 查看因子库和验证结果
- [快速开始](docs/QUICKSTART.md) - 详细的入门指南

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

### 短期目标
- 验证 3-5 个候选因子
- 找到 1-2 个真正有效的因子（IC > 0.05）
- 构建最简单的 MVP 策略

### 中期目标
- 策略在样本外测试中夏普 > 1.5
- 小资金实盘验证（$1000）
- 确认实际滑点、成交率

### 长期目标
- 策略稳定盈利（月均收益 > 5%）
- 考虑扩展到其他币种
- 考虑工程化优化

---

**最后更新**：2026-01-18
