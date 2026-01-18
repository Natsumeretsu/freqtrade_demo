# 快速开始指南

**预计时间**：5 分钟

---

## 🚀 三步上手

### 1. 环境初始化

```powershell
# 安装 Python 3.11 并同步依赖
uv python install "3.11"
uv sync --frozen

# 或使用一键初始化
./scripts/bootstrap.ps1
```

### 2. 配置文件

```powershell
# 复制配置模板
Copy-Item "04_shared/configs/config.example.json" "01_freqtrade/config.json"
Copy-Item "04_shared/configs/config-private.example.json" "01_freqtrade/config-private.json"

# 编辑 config-private.json，填入交易所 API 密钥（可选）
```

### 3. 验证安装

```powershell
# 查看可用策略
./scripts/ft.ps1 list-strategies

# 应该看到：
# - SimpleMVPStrategy
# - SmallAccountSpotReversionV1
# - SmallAccountSpotSma200TrendV1
# - SmallAccountSpotTrendHybridV1
# - base_strategy
```

---

## 📊 MVP 工作流程

### 阶段 1：数据准备

```powershell
# 下载 BTC/USDT 15分钟数据（最近90天）
cd 02_qlib_research/data_pipeline
python download.py --symbol BTC/USDT --timeframe 15m --days 90
```

### 阶段 2：因子验证

```powershell
# 在 Jupyter Notebook 中研究因子
cd 02_qlib_research/notebooks/factor_research
jupyter notebook 01_funding_rate_factor.ipynb
```

**验收标准**：
- IC（信息系数）> 0.05
- t 值 > 2
- 样本外测试稳定（IC 衰减 < 30%）

### 阶段 3：策略回测

```powershell
# 回测 MVP 策略
./scripts/ft.ps1 backtesting --strategy SimpleMVPStrategy --config 01_freqtrade/config.json
```

---

## 🔧 常用命令

```powershell
# 查看策略列表
./scripts/ft.ps1 list-strategies

# 下载数据
./scripts/data/download.ps1 -Pairs "BTC/USDT:USDT" -Timeframes "15m" -TradingMode "futures"

# 回测
./scripts/ft.ps1 backtesting --strategy <策略名> --config 01_freqtrade/config.json

# 超参优化
./scripts/ft.ps1 hyperopt --strategy <策略名> --hyperopt-loss SharpeHyperOptLoss
```

---

## ⚠️ 重要约定

1. **所有 Freqtrade 命令必须通过 `./scripts/ft.ps1` 执行**
2. **私密信息只放 `.env` 或 `config-private.json`**
3. **不要过早优化，先验证因子有效性**

---

## 📚 下一步

- 阅读 [架构文档](ARCHITECTURE.md) 了解项目结构
- 阅读 [因子验证指南](FACTORS.md) 学习如何验证因子
- 查看 [API 参考](API.md) 了解如何使用因子模块

---

**最后更新**：2026-01-18
