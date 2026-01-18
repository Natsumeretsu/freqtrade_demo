# 快速参考：Freqtrade + Qlib（本仓库约定）

本文件只回答三件事：**入口脚本是什么、常用命令怎么跑、产物会落到哪里**。

---

## 1) 入口脚本（必须）

- Freqtrade 命令入口：`./scripts/ft.ps1 <命令> ...`（自动 `--userdir "./01_freqtrade"`）
- 数据下载入口：`./scripts/data/download.ps1`
- 小资金回测入口：`./scripts/analysis/small_account_backtest.ps1`
- Qlib 工程流水线入口：`./scripts/qlib/pipeline.ps1`

---

## 2) 常用命令（PowerShell）

### 2.1 初始化运行配置（推荐）

```powershell
Copy-Item "04_shared/configs/config.example.json" "01_freqtrade/config.json"
Copy-Item "04_shared/configs/config-private.example.json" "01_freqtrade/config-private.json"

./scripts/ft.ps1 show-config --config "01_freqtrade/config.json" --config "01_freqtrade/config-private.json"
```

### 2.2 查看策略是否被正确识别

```powershell
./scripts/ft.ps1 list-strategies --config "01_freqtrade/config.json"
```

### 2.3 下载数据（示例：OKX 永续，4h + 1d）

```powershell
./scripts/data/download.ps1 `
  -Pairs "BTC/USDT:USDT" `
  -Timeframes "4h","1d" `
  -TradingMode "futures" `
  -Timerange "20200101-"
```

### 2.4 回测（示例：小资金合约趋势策略）

```powershell
./scripts/analysis/small_account_backtest.ps1 `
  -Config "04_shared/configs/small_account/config_small_futures_base.json" `
  -Strategy "SmallAccountFuturesTrendV1" `
  -Pairs "BTC/USDT:USDT" `
  -Timeframe "4h" `
  -TradingMode "futures" `
  -Timerange "20200101-20251231"
```

### 2.5 研究层：一键转换 + 训练（Qlib 风格）

```powershell
./scripts/qlib/pipeline.ps1 -Timeframe "4h" -ModelVersion "v1"
```

---

## 3) 默认输出位置（你应该去哪里找产物）

- 市场数据：`01_freqtrade/data/<exchange>/...`
- 回测产物：`01_freqtrade/backtest_results/`
- 报表/图：`01_freqtrade/plot/`
- Qlib 数据：`02_qlib_research/qlib_data/`
- Qlib 模型：`02_qlib_research/models/qlib/`

