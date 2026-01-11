# FreqaiMetaLabel 策略唯一基底文档（v1，已被 v2 替代）

更新日期：2026-01-10

本文档是策略类 `FreqaiMetaLabel` 的**唯一基底**与**权威指导文件**。

> 重要结论：`FreqaiMetaLabel`（v1）在当前 freqtrade 版本下存在关键执行缺陷（入场 ATR 未正确持久化、止损语义不一致、窗口双源），不建议直接用于实盘。  
> 推荐优先使用已修复并对齐为分类器的 `FreqaiMetaLabelV2`（见：`project_docs/freqai_meta_label_v2.md`）。

- 策略代码：`strategies/FreqaiMetaLabel.py`
- 推荐配置：`configs/freqai/meta_label_1h_v1.json`

---

## 1. 策略定位

- 周期：`1h`
- 方向：仅做多
- 结构：基础信号（RSI/BB/ADX/ROC/EMA200）产生候选入场，FreqAI 输出列 `&s-win` 作为过滤阈值（Meta-Labeling）。
- 标签方法：基于 ATR 的动态三重障碍（TBM 思路），但 v1 实现存在一致性问题（见第 3 节）。

---

## 2. 2025 实证：v1 参数下的标签分布（本仓库本地数据）

数据：`data/okx/futures/*-1h-futures.feather`，区间：2025-01-01 ~ 2026-01-01。

以 v1 典型参数（`TP=2.0ATR`, `SL=2.0ATR`, horizon=6）统计：

- BTC：win≈0.180，lose≈0.199，timeout≈0.620，tie≈0.001
- ETH：win≈0.184，lose≈0.203，timeout≈0.612，tie≈0.001

含义：

- timeout 超过 60%，标签天然偏 0（强不平衡）。  
- 若继续用回归器拟合 0/1 + 固定阈值，容易出现“模型过度保守、交易稀疏”的行为模式。

---

## 3. v1 已知关键问题（必须先修复，否则策略行为与预期不一致）

### 3.1 入场 ATR 未可靠持久化（导致动态止损形同虚设）

现状：

- v1 在 `confirm_trade_entry()` 写入 `self.custom_trade_data = {"entry_atr": ...}`。\n- 但当前 freqtrade 并不会自动把 `custom_trade_data` 写入 Trade 的自定义数据表。\n- v1 在 `custom_stoploss()` 中把 `trade.custom_data` 当作 `dict` 读取也不成立（实际是关系表）。\n
结果：`entry_atr` 往往读不到，最终止损退化为固定硬止损 `stoploss`。

修复方向（原则级）：

- 在入场单成交后（`order_filled`）使用 `trade.set_custom_data("entry_atr", ...)` 落盘。\n- 在 `custom_stoploss` 使用 `trade.get_custom_data("entry_atr")` 读取。\n
> 参考实现：`strategies/FreqaiMetaLabelV2.py`

### 3.2 标签窗口双源（配置 vs 代码）导致训练语义漂移

- v1 配置 `meta_label_1h_v1.json` 的 `label_period_candles = 6`。\n- v1 策略内部硬编码 `prediction_period = 8`。\n
结果：训练/推理目标不一致，滚动训练时迁移性下降。

修复方向：

- 以配置 `label_period_candles` 为唯一真相，策略从 `self.freqai_info["feature_parameters"]["label_period_candles"]` 读取窗口。

### 3.3 同 K 线双触达的偏置

v1 实现默认先判 TP 再判 SL，会把同 K 线触达上下障碍的场景偏向 win。\n建议改为更保守的 tie 处理（例如 tie 统一归为 lose/neutral）。

---

## 4. 运行方式（仅用于回测验证）

> 说明：不要直接运行 `freqtrade`，统一通过 `./scripts/ft.ps1`。

```powershell
$end = (Get-Date).ToString('yyyyMMdd')
$start = (Get-Date).AddDays(-90).ToString('yyyyMMdd')

./scripts/ft.ps1 backtesting `
  --config "configs/freqai/meta_label_1h_v1.json" `
  --strategy "FreqaiMetaLabel" `
  --freqaimodel "LightGBMRegressor" `
  --timeframe "1h" `
  --timeframe-detail "5m" `
  --timerange "$start-$end" `
  --pairs "BTC/USDT:USDT" `
  --export trades `
  --no-color
```

回测报告规范见：`project_docs/guidelines/backtest_reporting_standard.md`。

---

## 5. 推荐迁移路径

- 直接迁移到 `FreqaiMetaLabelV2`：`project_docs/freqai_meta_label_v2.md`。\n- 若你坚持保留 v1，请先完成第 3 节的三项修复，并重新做 walk-forward 评估与成本敏感性分析。  
