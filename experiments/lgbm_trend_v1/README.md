# 实验：lgbm_trend_v1

## 0) 概览

- `identifier`：`lgbm_trend_v1`
- 配置：`configs/freqai/lgbm_trend_v1.json`
- 策略：`strategies/freqai_lgbm_trend_strategy.py`（`FreqaiLGBMTrendStrategy`）
- 模型：`LightGBMRegressor`

## 1) 复现命令（建议先跑通流程）

1) 下载数据（示例：BTC/USDT + 1h）：

```powershell
./scripts/ft.ps1 download-data --config "configs/freqai/lgbm_trend_v1.json" --pairs "BTC/USDT" --timeframes "1h" --days 120
```

2) 快速回测（14 天窗口）：

```powershell
$end = (Get-Date).ToString('yyyyMMdd')
$start = (Get-Date).AddDays(-14).ToString('yyyyMMdd')

./scripts/ft.ps1 backtesting --config "configs/freqai/lgbm_trend_v1.json" --strategy "FreqaiLGBMTrendStrategy" --freqaimodel "LightGBMRegressor" --timeframe "1h" --timerange "$start-$end" --pairs "BTC/USDT"
```

## 2) 备注

- FreqAI 训练/预测产物会自动写入 `models/<identifier>/`（默认被 git 忽略）。
- 策略当前的预测目标列为 `&s_close_mean`（未来 `label_period_candles` 根K线的均值收益率）。
- 默认入场阈值为 `1.5%`（给手续费/滑点留缓冲），并带有“盈利时预测转弱就走”的 `custom_exit()` 智能退出。
