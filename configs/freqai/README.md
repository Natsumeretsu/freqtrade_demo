# FreqAI 配置（`configs/freqai/`）

本目录用于存放 FreqAI 相关的示例/实验配置（回测、训练、实盘均可复用）。

## 回归（收益率回归）

- `lgbm_trend_v1.json`：回归示例（`freqai.identifier: lgbm_trend_v1`），目标列为 `&s_close_mean`（未来 `label_period_candles` 根K线的均值收益率）。
- `lgbm_trend_v1_eval.json`：评估用配置（`purge_old_models: false`，避免频繁清理模型目录；identifier 用于实验隔离）。
- `lgbm_trend_v2_eval.json`：评估用配置（更长预测窗口/训练窗口的探索版）。

快速回测（跑通流程）：

```powershell
$end = (Get-Date).ToString('yyyyMMdd')
$start = (Get-Date).AddDays(-14).ToString('yyyyMMdd')

./scripts/ft.ps1 backtesting --config "configs/freqai/lgbm_trend_v1.json" --strategy "FreqaiLGBMTrendStrategy" --freqaimodel "LightGBMRegressor" --timeframe "1h" --timeframe-detail "5m" --timerange "$start-$end" --pairs "BTC/USDT"
```

扫参（跨多个窗口对比阈值稳健性）：

```powershell
uv run python "scripts/sweep_freqai_params.py" --configs "configs/freqai/lgbm_trend_v1_eval.json" --pairs "BTC/USDT" --timeframe-detail "5m" --fee 0.0015
```

可选：同时扫入“熊市/暴跌免疫”的入场过滤参数（按需添加）：

- `--buy-use-ema-long-slope-filters` / `--buy-ema-long-slope-lookbacks`
- `--buy-use-max-atr-pct-filters` / `--buy-max-atr-pcts`
- `--buy-use-adx-filters` / `--buy-adx-periods` / `--buy-adx-mins`

## 分类（方向分类）

- `lgbm_classifier_trend_v1.json`：二分类示例（`freqai.identifier: lgbm_cls_trend_v1`），目标列为 `&s_up_or_down`（`up` / `down`），并使用 `up` 概率做入场/出场阈值。
- `lgbm_classifier_trend_v1_eval.json`：评估用配置（`purge_old_models: false`）。

快速回测（跑通流程）：

```powershell
$end = (Get-Date).ToString('yyyyMMdd')
$start = (Get-Date).AddDays(-14).ToString('yyyyMMdd')

./scripts/ft.ps1 backtesting --config "configs/freqai/lgbm_classifier_trend_v1.json" --strategy "FreqaiLGBMClassifierTrendStrategy" --freqaimodel "LightGBMClassifier" --timeframe "1h" --timeframe-detail "5m" --timerange "$start-$end" --pairs "BTC/USDT"
```
