# FreqaiTripleBarrierV3 策略唯一基底文档（TB 二分类 + 纯 ML 入场）

更新日期：2026-01-10

本文档是策略类 `FreqaiTripleBarrierV3` 的**唯一基底**与**权威指导文件**。

- 策略代码：`01_freqtrade/strategies_archive/FreqaiTripleBarrierV3.py`
- 推荐配置：`04_shared/configs/archive/freqai/triple_barrier_1h_v3.json`

---

## 1. 策略定位与适用边界

- 周期：`1h`
- 方向：仅做多（`can_short = False`）
- 核心思想：用 ATR 动态三重障碍生成二分类标签（`win/lose`），并直接用分类器输出的 `win` 概率驱动入场；出场严格使用 Triple Barrier，保证训练目标与执行逻辑一致。
- 适用标的：主流合约（BTC/ETH）这类高流动性市场；不适合延迟敏感型高频。

---

## 2. 端到端逻辑（训练 → 预测 → 交易）

### 2.1 目标/标签（FreqAI Target）

- 目标列：`&s-win`（字符串标签 `"lose"` / `"win"`）
- 预测窗口：`freqai.feature_parameters.label_period_candles`（单一真相）
- 障碍定义（以 `close` 作为入场价）：
  - 上障碍（TP）：`close + profit_mult * ATR`
  - 下障碍（SL）：`close - stop_mult * ATR`
  - 垂直障碍：未来 `N=label_period_candles` 根 K 线
- 同一根 K 线同时触达上下障碍时：优先判定为 `"lose"`（更保守）
- 类别名显式声明：策略设置 `self.freqai.class_names = ["lose", "win"]`，推理阶段输出概率列名为 `lose` / `win`。

### 2.2 入场（纯 ML）

入场由三层组成：预测就绪 + 波动率过滤 + 体制过滤 + `win` 概率阈值。

- `do_predict == 1`
- `atr_pct` 在区间内（避免极端噪声段）
- 趋势/体制过滤：
  - `uptrend`（1h：`close > ema_200`）
  - `regime_4h_4h >= 0`（4h 体制不处于明确熊市；若本地缺少 4h 数据，该过滤会自动退化）
- `win > enter_win_prob` 才允许入场

### 2.3 出场与止损（Triple Barrier 一致口径）

- 入场 ATR 持久化：`order_filled()` 在入场单成交后写入 `trade.set_custom_data("entry_atr", ...)`，保证回测/实盘一致。
- 止盈（Upper Barrier）：以**入场 ATR** 定价（价格距离），触达即退出。
- 时间障碍（Vertical Barrier）：持仓超过 `label_period_candles` 对齐的时间窗口后，按最小利润阈值清理“僵尸单”。
- 止损（Lower Barrier）：用 `stoploss_from_absolute(sl_rate, current_rate, leverage=trade.leverage)` 返回 **futures 风险口径** 的止损百分比（已考虑杠杆）。

---

## 3. 参数调优建议（优先级）

1) 先稳定交易次数/回撤：`enter_win_prob`、`min_atr_pct/max_atr_pct`、`min_profit_at_timeout`。  
2) 再调盈亏结构：`profit_mult`、`stop_mult`（建议先固定 `stop_mult`，再调 TP）。  
3) 最后调窗口：`label_period_candles`（越长越“慢”，但更可能降低超时占比）。

---

## 4. 回测命令（本仓库约定）

> 说明：不要直接运行 `freqtrade`，统一通过 `./scripts/ft.ps1`。

```powershell
./scripts/ft.ps1 backtesting `
  --config "04_shared/configs/archive/freqai/triple_barrier_1h_v3.json" `
  --strategy-path "01_freqtrade/strategies_archive" `
  --strategy "FreqaiTripleBarrierV3" `
  --timerange 20240101-20260101 `
  --export trades `
  --no-color
```

回测结果汇报标准见：`docs/guidelines/backtest_reporting_standard.md`。

---

## 5. 参考来源（MCP 摘要/登记）

- 统一来源登记：`docs/knowledge/source_registry.md`
- 关键条目：S-502（FreqAI 配置/分类器类名）、S-505（LightGBM 不平衡与概率）、S-601/S-602（TB 与 Meta-Labeling 开源实现）、S-701（向量化的性能/内存约束）

---

## 6. 变更记录

- 2026-01-10：建立策略级唯一基底文档（本文件）。
