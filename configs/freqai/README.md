# FreqAI 配置（configs/freqai/）

本目录用于存放 FreqAI 相关的示例/实验配置。

- `lgbm_trend_v1.json`：示例配置（对应 `freqai.identifier: lgbm_trend_v1`）

## 0) 快速验证（回测流程跑通）

```powershell
$end = (Get-Date).ToString('yyyyMMdd')
$start = (Get-Date).AddDays(-14).ToString('yyyyMMdd')

./scripts/ft.ps1 backtesting --config "configs/freqai/lgbm_trend_v1.json" --strategy "FreqaiLGBMTrendStrategy" --freqaimodel "LightGBMRegressor" --timeframe "1h" --timerange "$start-$end" --pairs "BTC/USDT"
```
