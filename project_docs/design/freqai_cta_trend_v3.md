# FreqaiCTATrendV3 策略唯一基底文档（单币对期货 CTA 多/空 + TB 多分类）

更新日期：2026-01-10

本文档是策略类 `FreqaiCTATrendV3` 的**唯一基底**与**权威指导文件**。

- 策略代码：`strategies/FreqaiCTATrendV3.py`
- 推荐配置：`configs/freqai/cta_trend_btc_1h_v3.json`
- 赛道选型参考：`project_docs/design/crypto_futures_strategy_options.md`

---

## 1. 策略定位与适用边界

- 周期：`1h`
- 方向：多/空双向（`can_short = True`）
- 核心思想：用 ATR 动态三重障碍生成三分类标签（`long/short/neutral`），并用分类器输出的概率列驱动入场；出场仍用相同的 Triple Barrier 约束持仓生命周期，避免“训练目标与执行逻辑不一致”。
- **推荐单币对**：`BTC/USDT:USDT`
  - 流动性深、滑点更可控，更适合 CTA 这类趋势捕捉与资金承载逻辑。
  - 单币对能让模型专注学习更稳定的微观结构，减少跨币对分布漂移带来的噪声。

---

## 2. 端到端逻辑（训练 → 预测 → 交易）

### 2.1 目标/标签（FreqAI Target）

- 目标列：`&s-direction`（字符串标签 `"neutral"` / `"short"` / `"long"`）
- 预测窗口：`freqai.feature_parameters.label_period_candles`（同时用于时间障碍对齐）
- 标签含义：
  - `long`：未来窗口内，做多先触达 TP（且未先触达 SL）
  - `short`：未来窗口内，做空先触达 TP（且未先触达 SL）
  - `neutral`：其余（超时/震荡/双向噪声）
- 类别名显式声明：策略设置 `self.freqai.class_names = ["neutral", "short", "long"]`，推理阶段输出概率列名为 `neutral` / `short` / `long`。

### 2.2 入场（CTA 双向）

入场由四层组成：预测就绪 + 波动率过滤 + 趋势/体制过滤 + 概率优势。

- `do_predict == 1`
- `atr_pct` 在区间内（避免极端波动噪声段）
- 趋势/体制过滤：
  - 多单：`uptrend == True` 且 `regime_4h_4h >= 0`
  - 空单：`downtrend == True` 且 `regime_4h_4h <= 0`
- 概率优势：
  - 多单：`long > enter_prob` 且 `long > short + prob_margin`
  - 空单：`short > enter_prob` 且 `short > long + prob_margin`

### 2.3 出场与止损（Triple Barrier 一致口径）

- 入场 ATR 持久化：`order_filled()` 写入 `trade.set_custom_data("entry_atr", ...)`
- 止盈（Upper Barrier）：以入场 ATR 定价（价格距离），触达即退出
- 信号反转/衰减：在已有一定盈利后，若优势方向显著反转或跌破 `exit_prob`，则提前退出
- 时间障碍（Vertical Barrier）：严格对齐 `label_period_candles * timeframe`，超时则按最小利润阈值清理
- 止损（Lower Barrier）：使用 `stoploss_from_absolute(..., leverage=trade.leverage)` 返回 futures 风险口径

---

## 3. 风险提示与调参优先级

- 空头侧风险（短挤压/资金费率）更明显：建议先用较低杠杆（例如 2~3），并优先把 `prob_margin` 调高以减少“方向摇摆”入场。
- 调参顺序建议：
  1) `enter_prob / prob_margin / min_atr_pct`（先稳定信号质量与交易频率）
  2) `profit_mult / stop_mult`（再调盈亏结构）
  3) `label_period_candles`（最后调趋势尺度）

---

## 4. 回测命令（本仓库约定）

```powershell
./scripts/ft.ps1 backtesting `
  --config "configs/freqai/cta_trend_btc_1h_v3.json" `
  --strategy "FreqaiCTATrendV3" `
  --timerange 20240101-20260101 `
  --export trades `
  --no-color
```

回测结果汇报标准见：`project_docs/guidelines/backtest_reporting_standard.md`。

---

## 5. 参考来源（MCP 摘要/登记）

- 统一来源登记：`project_docs/knowledge/source_registry.md`
- 关键条目：S-502（FreqAI 配置/分类器类名）、S-504（Running FreqAI）、S-505（LightGBM 不平衡与概率）、S-601（TB+Meta-Labeling）、S-401/S-402（永续/强平与杠杆风险）

---

## 6. 变更记录

- 2026-01-10：建立策略级唯一基底文档（本文件）。
