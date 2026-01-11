# FreqaiTripleBarrierV2 策略唯一基底文档（回归预测 + Triple Barrier 出场）

更新日期：2026-01-10

本文档是策略类 `FreqaiTripleBarrierV2` 的**唯一基底**与**权威指导文件**。

- 策略代码：`strategies/FreqaiTripleBarrierV2.py`
- 推荐配置：`configs/freqai/triple_barrier_1h_v2.json`

---

## 1. 策略定位与适用边界

- 周期：`1h`（趋势/波段）
- 方向：仅做多（`can_short = False`）
- 核心思想：FreqAI 回归模型预测未来 N 根的收益率（`&s_close_pct`），入场用“强预测 + 体制过滤”，出场用“三重障碍”（动态止盈 + 时间止盈/止损 + 预测反转）。
- 特点：ROI 基本禁用（`minimal_roi = {"0": 100}`），策略主要依赖 `custom_exit` 与 `custom_stoploss` 管理离场与风险。

---

## 2. 端到端逻辑（训练 → 预测 → 交易）

### 2.1 目标/标签（FreqAI Target）

- 目标列：`&s_close_pct`（连续值回归目标）
- 预测窗口：从配置读取 `freqai.feature_parameters.label_period_candles`
- 定义：
  - `&s_close_pct = close.shift(-N) / close - 1`
- 含义：模型学习“未来 N 根收盘相对当前的百分比变化”（点对点回归，不是严格的 TBM 三类标签）。

### 2.2 指标与体制过滤

策略在 `populate_indicators` 里生成并合并以下关键变量：

- `atr` 与 `atr_pct = atr / close`（波动率尺度）
- `ema_50`、`ema_200`，并用 `close` 与 `ema_200` 判断 `uptrend/downtrend`
- informative 级别的 `4h` 体制 `regime_4h_4h`（通过 `merge_informative_pair` 合并）

> 运行前提：需要本地存在对应交易对的 `4h` 数据，否则 `regime_4h_4h` 可能缺失，体制过滤会退化。

### 2.3 入场

入场条件由三层组成：预测置信度 + 波动率过滤 + 体制过滤。

- 基础过滤（波动率与预测可用性）：
  - `do_predict == 1`
  - `atr_pct` 处于合理区间：`0.005 < atr_pct < max_atr_pct`
- 做多条件（long）：
  - `pred = &s_close_pct > pred_threshold_long`
  - `uptrend == True`（1h 方向）
  - `regime_4h_4h >= 0`（4h 不处于明确熊市）

### 2.4 出场（Triple Barrier）

策略在 `custom_exit` 实现三种离场路径：

1) **动态止盈（Upper Barrier）**  
   - 使用**入场 ATR** 定义止盈价格：`tp_rate = open_rate + entry_atr * profit_mult`  
   - `current_rate >= tp_rate` → `TB_TAKE_PROFIT`

2) **时间障碍（Vertical Barrier）**  
   - 持仓时间超过 `vertical_barrier_hours`：  
     - 若 `current_profit < min_profit_at_timeout` → `TB_TIME_EXIT`（清理“僵尸单”）  
     - 若 `current_profit > 0` → `TB_TIME_PROFIT`（时间止盈）

3) **信号反转（Signal Reversal）**  
   - 当 `do_predict == 1` 且已有一定利润（`current_profit > 0.01`）时：  
     - 若预测显著转负（`pred < -0.005`）→ `TB_SIGNAL_REVERSAL`

### 2.5 止损（Lower Barrier）

策略在 `custom_stoploss` 返回止损距离（futures 风险口径）：

- 使用**入场 ATR** 定义止损价格：`sl_rate = open_rate - entry_atr * stop_mult`
- 使用 `stoploss_from_absolute(sl_rate, current_rate, leverage=trade.leverage)` 换算为 **futures 需要的“本次交易风险%”**
- 并裁剪到区间 `[0.03, abs(stoploss)]`（默认：最紧 3%，最宽 8%）

注意：

- `entry_atr` 由 `order_filled()` 在入场单成交后使用 `trade.set_custom_data("entry_atr", ...)` 持久化，保证回测/实盘一致。
- Freqtrade 默认“止损只允许朝有利方向移动”（除非 `after_fill=True`），因此即使返回值变化也会受到该机制约束。

---

## 3. 参数调优建议（优先级顺序）

1) **先稳定交易次数与回撤**：调 `pred_threshold_long`、`max_atr_pct`、`vertical_barrier_hours`。\n2) **再调止盈/止损结构**：调 `profit_mult` 与 `stop_mult`（并确保与资金费率/手续费后仍有正期望）。\n3) **最后调模型侧窗口**：`label_period_candles` 影响目标尺度与噪声水平，建议配合 walk-forward 观察稳定性。

额外建议：

- `pred_threshold_long` 不应拍脑袋固定，建议用滚动分位数或基于回测期的目标分布做校准。\n- `max_atr_pct` 是“避开异常波动”的关键阀门，过大容易吃噪声，过小会错过趋势启动段。

---

## 4. 常见问题排查

- `regime_4h_4h` 列缺失：
  - 检查是否下载了 `4h` 数据；以及 `informative_pairs()` 是否返回了对应 pair 的 `4h`。\n- `do_predict` 长期为 0：
  - 说明 FreqAI 未训练完成或模型不可用；先确保配置 `identifier` 隔离且训练期足够。\n- 动态止盈/止损过于频繁触发：
  - 优先检查 `atr_pct` 的分布（是否过高）；其次检查 `profit_mult/stop_mult` 是否过小。

---

## 5. 回测命令（本仓库约定）

> 说明：不要直接运行 `freqtrade`，统一通过 `./scripts/ft.ps1`。

```powershell
$end = (Get-Date).ToString('yyyyMMdd')
$start = (Get-Date).AddDays(-90).ToString('yyyyMMdd')

./scripts/ft.ps1 backtesting `
  --config "configs/freqai/triple_barrier_1h_v2.json" `
  --strategy "FreqaiTripleBarrierV2" `
  --timeframe "1h" `
  --timeframe-detail "5m" `
  --timerange "$start-$end" `
  --pairs "BTC/USDT:USDT" `
  --export trades `
  --no-color
```

回测报告规范见：`project_docs/guidelines/backtest_reporting_standard.md`。

---

## 6. 变更记录

- 2026-01-10：建立策略级唯一基底文档（本文件）。  
- 2026-01-10：补全配置 `freqaimodel=LightGBMRegressor`；入场 ATR 落盘（`order_filled`）；修复 futures 杠杆下 Triple Barrier 的止盈/止损口径一致性。  
