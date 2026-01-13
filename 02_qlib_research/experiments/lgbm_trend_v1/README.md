# 实验：lgbm_trend_v1

## 0) 概览

- `identifier`：`lgbm_trend_v1`
- 配置：`04_shared/configs/archive/freqai/lgbm_trend_v1.json`
- 策略：`01_freqtrade/strategies_archive/FreqaiLGBMTrendStrategy.py`（`FreqaiLGBMTrendStrategy`）
- 模型：`LightGBMRegressor`

## 1) 复现命令（建议先跑通流程）

1) 下载数据（示例：BTC/USDT + 1h）：

```powershell
./scripts/ft.ps1 download-data --config "04_shared/configs/archive/freqai/lgbm_trend_v1.json" --pairs "BTC/USDT" --timeframes "1h" --days 120
```

2) 快速回测（14 天窗口）：

```powershell
$end = (Get-Date).ToString('yyyyMMdd')
$start = (Get-Date).AddDays(-14).ToString('yyyyMMdd')

./scripts/ft.ps1 backtesting --config "04_shared/configs/archive/freqai/lgbm_trend_v1.json" --strategy-path "01_freqtrade/strategies_archive" --strategy "FreqaiLGBMTrendStrategy" --freqaimodel "LightGBMRegressor" --timeframe "1h" --timeframe-detail "5m" --timerange "$start-$end" --pairs "BTC/USDT"
```

3) 三窗口扫参（更关注稳健性而非单窗口爆炸）：

```powershell
uv run python "scripts/archive/freqai/param_sweep.py" --configs "04_shared/configs/archive/freqai/lgbm_trend_v1_eval.json" --pairs "BTC/USDT" --timeframe-detail "5m" --fee 0.0015
```

输出会写到 `01_freqtrade/backtest_results/sweeps/<run_id>/`，包含：

- `results.csv`：每次回测的明细指标（含 zip / log 路径）
- `ranking.csv`：对 `buy_pred_threshold` / `sell_smart_exit_pred_threshold` 的跨窗口汇总排序（稳健性导向）

如需优先提升“熊市/暴跌窗口”的抗性，可额外把入场过滤参数也纳入扫参（按需添加）：

- `--buy-use-ema-long-slope-filters` / `--buy-ema-long-slope-lookbacks`：EMA 长周期斜率过滤（避免下跌趋势中“反弹诱多”）
- `--buy-use-max-atr-pct-filters` / `--buy-max-atr-pcts`：波动率上限过滤（极端波动期禁入）
- `--buy-use-adx-filters` / `--buy-adx-periods` / `--buy-adx-mins`：趋势强度过滤（可选）

## 2) 备注

- FreqAI 训练/预测产物会自动写入 `01_freqtrade/models/<identifier>/`（默认被 git 忽略）。
- 为了更真实地回测止损/追踪止损，建议在有 `5m` 数据时加上 `--timeframe-detail "5m"`（否则请移除该参数）。
- 策略当前的预测目标列为 `&s_close_mean`（未来 `label_period_candles` 根K线的均值收益率）。
- 配置已启用 `DI_threshold`（异常点过滤）：当特征与训练分布差异过大时，`do_predict` 会被降为 `0/-1`，策略只在 `do_predict == 1` 时允许开仓/出场信号生效。
- 默认入场阈值为 `1.2%`（多窗口扫参后更稳健，给手续费/滑点留缓冲），可通过同名参数文件 `01_freqtrade/strategies_archive/FreqaiLGBMTrendStrategy.json` 覆盖（优先级：config > 参数文件 > 默认值）。
- 策略已内置 `protections`（Cooldown + StoplossGuard），用于抑制极端行情下的“连环亏损”（可按需再调参/替换为配置级 protections）。
- `custom_exit()` 包含两层逻辑：盈利单“预测转弱就走”；亏损/持平单在持仓时间超过预测窗口后，若预测仍转弱则退出，避免长时间拖单回撤。
