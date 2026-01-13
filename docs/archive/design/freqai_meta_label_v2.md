# FreqaiMetaLabelV2 策略唯一基底文档（Meta-Labeling + 动态 Triple Barrier）

更新日期：2026-01-10

本文档是策略类 `FreqaiMetaLabelV2` 的**唯一基底**与**权威指导文件**。

- 策略代码：`01_freqtrade/strategies_archive/FreqaiMetaLabelV2.py`
- 推荐配置：`04_shared/configs/archive/freqai/meta_label_1h_v2.json`

---

## 1. 策略定位与适用边界

- 周期：`1h`（偏趋势/波段）
- 方向：仅做多（`can_short = False`）
- 核心思想：用基础信号生成“候选入场”，再用 FreqAI 分类器判断该候选是否具备“先触达止盈障碍”的概率优势（Meta-Labeling）。
- 适用市场：主流高流动性合约标的（例如 BTC/ETH），更依赖**体制过滤 + 成本建模 + 滚动训练**，不适合延迟敏感型高频。

---

## 2. 端到端逻辑（训练 → 预测 → 交易）

### 2.1 目标/标签（FreqAI Target）

- 目标列：`&s-win`（分类标签，取值为字符串 `"lose"` / `"win"`）
- 预测窗口：从配置读取 `freqai.feature_parameters.label_period_candles`（单一真相）
- 动态三重障碍（基于 ATR）：
  - 上障碍（TP）：`entry + profit_atr_mult * ATR`
  - 下障碍（SL）：`entry - loss_atr_mult * ATR`
  - 垂直障碍（Time）：`label_period_candles` 根 K 线
- 同一根 K 线触达上下障碍时：优先判定为 `"lose"`（更保守，避免标签系统性偏乐观）。
- 类别名显式声明：策略会设置 `self.freqai.class_names = ["lose", "win"]`，确保推理阶段输出概率列名为 `lose` / `win`。

### 2.2 特征工程（Feature Engineering）

策略使用 `feature_engineering_*` 三段式特征：

- 多周期扩展特征：RSI / ROC / BB 位置 / NATR / ADX / MFI（统一归一化/去极值）
- 基础特征：收益率变化、成交量比、价格区间位置、波动率体制（NATR 相对均值）
- 时间特征：星期/小时（捕捉周期性）

### 2.3 入场（Meta-Labeling）

入场 = 基础信号（高召回） + ML 过滤（高精度）：

- 基础信号（放宽过滤以增加样本）：
  - RSI 区间过滤（`buy_rsi_min/buy_rsi_max`）
  - 站上布林带中轨（`close > bb_mid`）
  - ADX 趋势过滤（`adx > buy_adx`）
  - 动量为正（`roc > 0`）
  - 牛市体制过滤（`close > ema_200`）
- ML 过滤（分类器概率）：
  - `do_predict == 1`
  - `win` 概率列存在且 `win > ml_threshold`

### 2.4 出场与风控

- 出场信号：策略 `populate_exit_trend` 默认不主动给出离场信号（`exit_* = 0`）。
- ROI：仍启用 `minimal_roi`（分段 ROI）作为“上层获利退出”机制。
- 止损：启用 `custom_stoploss`，核心是“以入场 ATR 固定距离（相对开仓价）”，并换算为“相对当前价”的返回值：
  - 入场 ATR 由 `order_filled()` 在**入场单成交后**写入 `trade.set_custom_data("entry_atr", ...)`
  - 止损返回值使用 `stoploss_from_open()` 换算，且 ATR 止损**不允许比硬止损更宽**（以开仓价口径裁剪）
  - 期货/杠杆口径：ATR 计算的是“价格距离”，在 futures 下需要乘以 `trade.leverage` 换算为“本次交易风险”，否则会出现止损被系统性放大/收紧的问题

---

## 3. 2025 实证：标签分布与类不平衡（本仓库本地数据）

数据：`01_freqtrade/data/okx/futures/*-1h-futures.feather`，区间：2025-01-01 ~ 2026-01-01。

以 v2 默认参数（`label_period_candles=12`, `TP=2.5ATR`, `SL=1.5ATR`）统计：

- BTC：win≈0.217，lose≈0.445，timeout≈0.336，tie≈0.001
- ETH：win≈0.217，lose≈0.462，timeout≈0.320，tie≈0.002

含义：

- horizon 拉长后 timeout 下降，但 SL 更紧会显著提高 lose 占比（仍是强不平衡）。  
- 因此配置侧建议用 `is_unbalance: true`（或 `class_weight: balanced`）做代价敏感学习，但**不要同时启用**两者。

---

## 4. 参数调优建议（先顺序，后数值）

### 4.1 先调“交易次数稳定性”，再调“单笔收益”

- 如果交易次数断崖式减少：优先检查 `ml_threshold` 与 `win` 概率分布是否塌缩；其次检查基础信号是否过严。
- 如果超时占比过高：降低 TP 倍数或缩短 `label_period_candles`（但会增加噪声/扫损概率）。
- 如果 lose 占比过高：放宽 SL 倍数或增加波动率过滤（避免高噪声段）。

### 4.2 配置侧建议

- `model_training_parameters.is_unbalance: true` 与 `class_weight` 二选一（推荐保留 `is_unbalance: true`）。
- `objective: binary`、`metric: auc` 可作为基线；建议额外关注 PR-AUC / Precision@K（更贴近交易）。

---

## 5. 常见问题排查

- 入场条件一直不触发：
  - 检查是否存在 `win` 概率列（分类器需要 `class_names` 与标签一致）。
  - 检查 `do_predict` 是否为 1（FreqAI 未就绪时会为 0）。
- 动态止损未按 ATR 工作：
  - 检查 `trade.get_custom_data("entry_atr")` 是否存在（需入场单真实成交后写入）。
  - 检查 `stoploss` 与 `loss_atr_mult` 的组合是否导致“硬止损裁剪始终更紧”。  

---

## 6. 回测命令（本仓库约定）

> 说明：不要直接运行 `freqtrade`，统一通过 `./scripts/ft.ps1`。

```powershell
$end = (Get-Date).ToString('yyyyMMdd')
$start = (Get-Date).AddDays(-90).ToString('yyyyMMdd')

./scripts/ft.ps1 backtesting `
  --config "04_shared/configs/archive/freqai/meta_label_1h_v2.json" `
  --strategy-path "01_freqtrade/strategies_archive" `
  --strategy "FreqaiMetaLabelV2" `
  --freqaimodel "LightGBMClassifier" `
  --timeframe "1h" `
  --timeframe-detail "5m" `
  --timerange "$start-$end" `
  --pairs "BTC/USDT:USDT" `
  --export trades `
  --no-color
```

回测报告规范见：`docs/guidelines/backtest_reporting_standard.md`。

---

## 7. 变更记录

- 2026-01-10：将 `label_period_candles` 作为唯一窗口来源；修复入场 ATR 的 Trade 自定义数据持久化；修复 `custom_stoploss` 返回值语义（开仓价口径 → 当前价口径换算）；显式声明分类器类别名（输出 `win` 概率列）。  
- 2026-01-10：修复 futures 杠杆下 ATR 止损口径（价格距离 → 风险距离），避免止损系统性偏紧。  
