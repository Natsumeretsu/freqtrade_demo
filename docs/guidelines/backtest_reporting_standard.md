# 回测输出标准（强制）

更新日期：2026-01-17


本仓库后续所有“策略回测结果”的汇报，统一遵循以下输出规范：

## 1) 样本窗口（必须覆盖完整周期）

- 默认使用当前数据目录中**最早 ~ 最新**的完整区间（覆盖上涨/下跌/震荡）。
- 若因研究目的需要拆分区间（Train/Val/Test 或分年），允许多次回测，但**每个区间都必须输出同样格式的报表**。

## 2) 输出格式（固定）

- **纵轴 = 交易对（行）**
- **横轴 = 指标（列）**
- 输出产物顺序：**HTML 优先，其次 CSV**
- 每份回测至少输出 1 份“逐交易对 vs Market change”的报表。

## 3) Market change 的口径（逐交易对）

- `market_change_pct` 由本地 OHLCV 数据计算：`close_end / close_start - 1`（%）。
- 计算区间使用回测结果 JSON 内的 `backtest_start/backtest_end`（已包含 `startup_candle_count` 的偏移），确保策略与市场对齐。

## 4) 推荐列（最少要包含）

- 策略：`trades`、`winrate_pct`、`profit_total_pct`、`profit_total_abs`、`max_drawdown_account_pct`
- 市场：`market_change_pct`
- 对比：`strategy_return_equal_alloc_pct`（等权分配口径的回报率）与 `alpha_equal_alloc_pct`

## 5) 标准命令（示例）

### A. 运行回测（Windows / PowerShell）

```powershell
./scripts/ft.ps1 backtesting `
  -c "04_shared/configs/small_account/config_small_spot_base.json" `
  --strategy "SmallAccountSpotTrendFilteredV1" `
  --timerange 20240101-20260101 `
  --export trades `
  --backtest-directory "01_freqtrade/backtest_results/fullcycle" `
  --no-color
```

运行完成后，会在 `--backtest-directory` 指定目录下写入 `.last_result.json`（记录最新 zip 名称）。

### B. 生成逐交易对报表（HTML + CSV）

```powershell
$last = (Get-Content -Raw "01_freqtrade/backtest_results/fullcycle/.last_result.json" | ConvertFrom-Json).latest_backtest
uv run python "scripts/analysis/pair_report.py" `
  --zip ("01_freqtrade/backtest_results/fullcycle/" + $last) `
  --datadir "01_freqtrade/data/okx" `
  --trading-mode futures
```

默认输出：
- `01_freqtrade/plot/<Strategy>_per_pair_report_<YYYYMMDD>_<YYYYMMDD>.html`
- `01_freqtrade/plot/<Strategy>_per_pair_report_<YYYYMMDD>_<YYYYMMDD>.csv`
