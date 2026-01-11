# FreqaiVolatilityGridV1 策略唯一基底文档（波动率预测门控 + 网格风格均值回归）

更新日期：2026-01-10

本文档是策略类 `FreqaiVolatilityGridV1` 的**唯一基底**与**权威指导文件**。

- 策略代码：`strategies/FreqaiVolatilityGridV1.py`
- 推荐配置：`configs/freqai/volatility_grid_btc_1h_v1.json`

---

## 1. 策略定位与适用边界

- 周期：`1h`
- 方向：仅做多（`can_short = False`）
- 核心思想：不预测方向，而是预测未来一段时间的“实现波动率”（回归目标）。当预测波动率较低时，执行“均值回归/网格风格”的挂单入场；当预测波动率走高时，停止开仓并更保守地退出持仓。
- 适用标的：主流高流动性合约（优先 BTC），用于探索“横盘/低波动”赛道的可行性。

---

## 2. 端到端逻辑（训练 → 预测 → 交易）

### 2.1 目标/标签（FreqAI Target）

- 目标列：`&s-volatility`（回归目标，未来 N 根的实现波动率）
- 预测窗口：`freqai.feature_parameters.label_period_candles`
- 计算方式：对未来 `N` 根的 `log_return` 标准差做滚动估计（只使用历史可得的 `close` 构造，不引入未来函数）。

### 2.2 入场（低波动门控 + 均值回归）

入场条件（做多）：

- `do_predict == 1`
- bull 体制过滤：`close > ema_200`（避免熊市“接飞刀”）
- 技术触发：`close < bb_lower` 且 `rsi < 35`
- 波动率门控：预测值 `&s-volatility <= vol_enter_max`

下单价格（maker 风格）：

- `custom_entry_price()` 将买单挂在“更深一档”的位置：`min(bb_lower, close) * (1 - maker_premium)`

### 2.3 出场与止损

出场路径：

- 均值回归退出：`close >= bb_middle` 或 `custom_exit_price()` 挂在 `bb_middle * (1 - maker_premium)` 附近
- 风险退出：预测波动率走高（`&s-volatility >= vol_exit_min`）且已有盈利时，提前退出
- 时间止损：持仓超过 `max_trade_age` 仍未回归则退出（或仅在达到 `min_profit_to_extend` 后延长）

止损：

- 使用入场 ATR 计算止损价格距离：`sl_rate = open_rate - entry_atr * stop_atr_mult`
- 使用 `stoploss_from_absolute(sl_rate, current_rate, leverage=trade.leverage)` 返回 futures 风险口径

---

## 3. 参数调优建议（原型阶段）

1) 先调门控（是否交易）：`vol_enter_max`、`vol_exit_min`、`bull_regime` 条件。  
2) 再调执行（挂单深度与均值回归速度）：`maker_premium`、`bb_period/bb_dev`。  
3) 最后调窗口：`label_period_candles` 与 `max_trade_age` 的组合。

---

## 4. 回测命令（本仓库约定）

```powershell
./scripts/ft.ps1 backtesting `
  --config "configs/freqai/volatility_grid_btc_1h_v1.json" `
  --strategy "FreqaiVolatilityGridV1" `
  --timerange 20240101-20260101 `
  --export trades `
  --no-color
```

回测结果汇报标准见：`project_docs/guidelines/backtest_reporting_standard.md`。

---

## 5. 变更记录

- 2026-01-10：建立策略级唯一基底文档（本文件）。
