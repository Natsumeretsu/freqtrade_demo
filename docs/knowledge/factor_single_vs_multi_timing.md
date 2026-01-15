# 单因子 vs 多因子：择时视角（面向本仓库 / Freqtrade）

更新日期：2026-01-15

一句话概括：

- **单因子（择时）**：一次只改动/启用一个“过滤器或门槛”，看它对交易质量的**边际贡献**。
- **多因子（择时）**：把多个“过滤器或门槛”组合成一套准入规则与风险预算，让系统在更多体制下**更稳**。

本文目标：把“因子框架”落到本仓库可复现的工程动作上，避免把股票的横截面因子分析（IC、分位数组合）直接套到单币择时而产生误解。

---

## 0) 在本仓库里，“因子”指什么？

在 Freqtrade 策略里，你可以把“因子”粗分为三类（都属于“可量化特征/规则”）：

1) **触发类（Trigger）**：产生候选入场事件（例如 EMA 交叉、回踩再入）。
2) **准入类（Gate / Filter）**：决定“候选是否允许进入”（例如 ADX/斜率/价差/宏观/波动率/流动性门槛）。
3) **风险类（Budget / Scale）**：不改信号，只调仓位/杠杆（例如风险折扣、杠杆封顶、弱体制降档位）。

对 `SmallAccountFuturesTrendV1` 来说，策略结构天然就是“多因子门控 + 风险预算”，只是这些因子并不一定叫“因子”，而是以参数/开关的形式存在。

补充心智模型（可选）：如果你习惯用“流体二维平面”来直觉化市场，把“因子”理解为对“时间-价格密度场” ρ(t,p) 的不同观测/门控会更顺：趋势/动量更像密度峰移动，波动/流动性门槛更像梯度/空洞预警。P0（OHLCV-only）只能做弱代理；订单簿密度需要 P1 数据。参考：`docs/knowledge/crypto_liquidity_microstructure_playbook.md`。

---

## 1) 先分清两种“因子研究”：横截面 vs 择时

### 1.1 横截面（选股/选币）因子（你看到的 IC/分位数那套）

典型对象：同一时刻对一篮子资产排序（例如 top 20% 做多、bottom 20% 做空）。

- 常用指标：IC、分位数组合收益、换手率等。
- 关键假设：存在足够多的资产横截面，用来做排序/分层统计。

### 1.2 择时（单币/少币）因子（本仓库更常见）

典型对象：对单一交易对在时间序列上做“入场/出场/风控”决策。

- 更合适的验证：**消融对照（ablation）**、事件收益分布、止损占比、回撤路径、交易频率稳定性。
- 关键假设：你关心的是“什么时候进/什么时候不进”，而不是“同一时刻买谁”。

结论：你当然可以借鉴“因子”这套语言，但别强行把 IC/分位数组合当成择时策略的主要评估方法。

---

## 2) `SmallAccountFuturesTrendV1` 的“因子地图”（从代码到概念）

下面是把策略里已经存在的关键因子，按职责映射出来（便于你做单因子/多因子实验设计）：

### 2.1 触发层（Trigger）

- `cross_*`：短 EMA 与长 EMA 的交叉启动（趋势切换的“事件”）
- `reentry_*`：价格回踩短 EMA 再上/再下（趋势内回调后的再入）

### 2.2 准入层（Gate / Filter）

- 趋势确认：`buy_adx`、`buy_ema_slope_lookback`、`buy_ema_long_min_slope`、`buy_min_ema_spread`
- 价位约束：`buy_max_ema_short_offset`（避免离短 EMA 太远追涨杀跌）
- 动量确认：`macdhist` 的方向（正/负）
- 波动率：`buy_atr_pct_min`（波动不足不交易）；可选 `buy_use_atr_pct_max_filter + buy_atr_pct_max`
- 流动性：可选 `buy_use_volume_ratio_filter + buy_volume_ratio_*`
- 宏观体制（BTC/USDT 日线）：可选 `buy_use_macro_trend_filter`（硬门控）
- cross 专用 Gate（仅加严交叉触发，不影响 reentry）：`buy_use_cross_gate + buy_gate_cross_*`

### 2.3 风险预算层（Budget / Scale）

- 仓位档位：`buy_stake_frac_*` + `_pick_stake_fraction()`（按强弱体制分档位）
- 宏观软门控（不改信号，只降风险）：`buy_use_macro_trend_stake_scale + buy_macro_stake_scale_floor`
- 动态杠杆：`buy_leverage_*` + `_risk_multiplier()`
- 小账户杠杆护栏：`buy_use_account_leverage_cap + buy_account_*`（按账户规模封顶杠杆）
- 资金费率过滤（可选）：`buy_use_funding_rate_filter + buy_funding_rate_max`（缺数据则放行，不影响回测）

---

## 3) 单因子（择时）怎么做：用“消融对照”替代“IC”

单因子研究在择时场景里的核心思想是：**一次只动一个开关或一个门槛**，其余全部保持不变。

### 3.1 固定口径（强制）

建议固定以下参数后再做对照，否则结果不可比：

- config：`04_shared/configs/small_account/config_small_futures_base.json`
- pair：`BTC/USDT:USDT`
- timeframe：`4h`
- timerange：例如 `20200101-20251231`（或按年拆分）
- dry_run_wallet：10（小资金约束）
- max_open_trades：1
- fee：0.0006（先用保守口径）

关于 `timeframe` 的关键提醒（非常重要）：

- **K 线周期不是市场的“客观周期”**，而是你选择的采样间隔 Δt。换周期等价于换采样率，会改变你能“看见”的频率范围，高频结构还可能在下采样后产生**混叠（aliasing）**，看起来像低频“伪周期”。
- 因此不要用“试出来哪个周期最好”来证明因子有效性；在统计意义上，这更像是在调一个隐含超参数，虚假发现率会显著上升。
- 更稳健的做法是：先固定一个 `timeframe` 做单因子消融与组合叠加；然后做**跨尺度 sanity check**：保持“有效持仓时长”一致（`hold = horizon × timeframe`），换相邻周期复核边际效果是否还成立。示例：`4h×1 ≈ 1h×4 ≈ 15m×16`。

多尺度思路（可选，先理解再落地）：

- **优先做“同一采样率下的多窗口”**：相比频繁切换 `timeframe`，更稳健的做法是在同一根 K 线上用不同 lookback 提取特征（例如短/中/长窗口动量、波动、成交量强弱），相当于在同一采样率里做多尺度投影。
- **把 Hurst 当作体制标签而不是买卖点**：H>0.5 更像趋势/持久性，H<0.5 更像均值回归/反持久性；但 H 会随尺度变化（multiscaling），因此必须在多个窗口上滚动估计，并做样本外验证后再用于风险预算。
- **小波/EMD 更适合研究层**：把价格拆成“趋势/中频/高频/噪声”分量后分别建模，再按体制加权融合；工程上先从“可复现 + 成本敏感 + 样本外”三件事做起，不要一上来就追求复杂度。

回测入口统一用脚本（避免跑出多余 user_data 目录）：

```powershell
./scripts/analysis/small_account_backtest.ps1 -Config "04_shared/configs/small_account/config_small_futures_base.json" -Strategy "SmallAccountFuturesTrendV1" -Pairs "BTC/USDT:USDT" -Timeframe "4h" -TradingMode "futures" -Timerange "20200101-20251231"
```

### 3.2 评价指标（优先级建议）

择时策略更应关注“生存指标”：

1) 最大回撤（相对）是否下降？
2) `stop_loss` 占比是否下降（特别是 `cross_*`）？
3) 交易数是否在可接受范围内（避免 0 trades 或极低交易数的“回测幻觉”）？
4) 收益/风险指标（Sharpe/Calmar/Profit Factor）是否一致改善？

---

## 4) 多因子（择时）怎么做：从“能活”到“更稳”

多因子不是“堆更多指标”，而是把策略拆成两条线：

- **触发层适度放宽**：让候选事件出现（通常靠 `reentry` 提供频率）。
- **准入层选择性收紧**：只挡掉“明显差”的候选（例如弱交叉、弱动量）。

### 4.1 组合建议（本仓库经验口径）

- 先确保“基础门槛”稳定：`atr_pct_min`（波动不足不做）+ `not_too_far_*`（避免追价）
- 用 `cross gate` 专门修理“弱交叉噪声”，不要把 `reentry` 也一起勒死
- 宏观体制优先用“软门控”（仓位/杠杆折扣），硬门控容易导致 0 trades

### 4.2 过拟合警戒线

- 如果某个组合只在单一窗口（例如 2021）好看，而在 2022/2023 明显失效：先做 Walk-forward，而不是继续加因子。
- 交易数太少时，任何指标（Sharpe、Profit Factor）都不可信；先解决频率来源（通常是 `reentry`）。

---

## 5) 下一步动作（与本仓库脚本对齐）

- 因子消融（单因子对照）的可执行清单见：`docs/knowledge/factor_ablation_checklist_smallaccount_futures.md`
- 若要做样本外验证：优先用 `scripts/analysis/walk_forward_search.ps1` 的训练/验证拆分口径，避免只在训练期调参。

---

## 6) 长/短信号要不要“混合”：在单交易对里怎么落地

你在股票因子文献里看到的“long/short 因子混合 vs 分离长短腿”，翻译到本仓库的单交易对择时，大致对应的是：

- **同一条特征/规则在做多与做空上的边际价值是否对称**（往往不对称）。
- **是否把多头与空头当成两条独立的决策线来评估与约束**（通常更稳健）。

### 6.1 两种组合方式：Integrated vs Sleeves（概念对齐）

1) **集成法（Integrated）**：把所有信号组合成一个连续分数/决策函数，然后一次性输出目标仓位（例如 [-1, 1]）。
   - 优点：逻辑简单、天然避免“多空打架”；对“只做多”的现货更友好。
   - 缺点：多空的成本结构、可预测性差异会被平均掉，容易在某一侧出现系统性弱点（例如空头端更容易被挤压/强平链条主导）。

2) **分离法（Sleeves / 分段）**：分别构建多头信号与空头信号（两套阈值/两套权重/两套风控），最后在仓位层做合并与冲突处理。
   - 优点：可把“多头腿/空头腿”的差异显式化（成本、胜率、回撤、误触率），便于单独治理。
   - 缺点：需要明确冲突规则（两边同时强信号时怎么办），也更容易引入过度复杂。

### 6.2 本仓库可复用的“长短腿拆开评估”能力

本仓库的择时体检在研究层已经内置了“把长短腿拆开评估”的语义：同一因子会在 `side in (both, long, short)` 三种侧向下分别回放，并选择更稳健的一侧输出（见 `03_integration/trading_system/application/timing_audit.py` 中 `choose_timing_direction*()`）。

工程含义：

- 如果某个因子在 `side=long` 明显更稳，而 `side=short` 明显更差：不要强行把它当成“多空通吃”的信号。
- 如果 `side=both` 反而更好：这通常意味着该因子在多空两侧都能贡献边际价值，或它更像一个“风险体制/噪声门控”（而不是纯方向）。

### 6.3 实战建议（面向单交易对/合约择时）

1) **先按 side 拆开做基线对照**：至少回答三个问题：只做多是否稳定？只做空是否稳定？两者合并是否只是“更频繁翻仓导致成本更高”？
2) **多空两套门槛不要共用**：同一个指标在上涨与下跌段的分布/尺度往往不同，共用门槛会引入隐性偏置。
3) **先用“软缩放”再用“硬开关”**：把弱信号映射到仓位/杠杆折扣，比直接翻向更不容易被震荡洗掉。
4) **冲突时优先空仓**：当多头与空头同时给出强信号，很多时候代表“信息不一致/体制切换”，空仓往往比硬选一边更稳健。

---

## 7) “本征因子/投影”视角：在单交易对里做特征去冗余

你提到的“少数本征因子张成空间、其它因子都是投影/旋转”，放到单交易对择时里，最直接的工程含义是：

- 你堆叠的很多指标/规则，其实是同一类信息（例如动量/趋势）的不同表达；
- 如果不做去冗余，你以为自己在“多因子分散”，实际可能是在同一维度上加杠杆，导致制度切换时一起失效。

### 7.1 先做“线性世界”的最小体检（够用且便宜）

1) **相关性/聚类（对“信号/仓位序列”而不是原始因子值）**：先把每个候选因子落成同一口径的择时序列（例如仓位 `pos`，或净收益 `net_ret`），并在同一 `effective_tf=timeframe×horizon` 下对齐；再对这些序列做 `|corr|`/聚类，把高度相关的一簇当成“同一潜在维度/同一模态”的不同投影（TopK 时每簇只取一个代表）。本仓库已把这件事下沉到 policy 导出：`scripts/qlib/export_timing_policy.py` 默认基于 `timing_audit --export-series` 产出的 `pos` 序列做相关性去冗余。
2) **消融对照**：在固定口径下，一次只加/只删一个门槛或特征（见本文第 3 节与 `docs/knowledge/factor_ablation_checklist_smallaccount_futures.md`）。

### 7.2 用“spanning 思路”判断新特征是否真的新增维度

把“因子 spanning test”的直觉翻译成单交易对择时，就是问：

> 新特征带来的收益/稳定性提升，能否被已有特征线性解释掉？

最小可操作流程（建议只在研究层做）：

1) 用已有特征集构建一个基线信号/策略回放（固定成本口径）。
2) 引入新特征后，如果表面指标变好，继续做“去解释”：
   - 用线性回归/岭回归把新特征回归到旧特征上，取残差 `residual_new`；
   - 用 `residual_new` 替代原新特征再做回放/体检。
3) 判定：
   - 如果残差仍能在样本外稳定带来边际改善：说明它更可能提供了“新的维度/新的信息”；
   - 如果残差几乎不贡献：说明它很可能只是旧特征空间的另一个投影（冗余）。

工程提醒：

- 先做线性去冗余是“性价比最高”的一步；真正需要更复杂的非线性去冗余（MI/TE/AutoEncoder）时，往往意味着你已经把数据治理与样本外评估做到了足够稳健的水平。

### 7.3 Koopa-lite：把“本征模态”变成可体检的额外因子

如果你希望进一步逼近“本征函数/模态坐标”的直觉，本仓库提供了一个不依赖 torch 的原型：`scripts/qlib/koopman_lite.py`。

- 它会在每个交易对上生成一批额外特征（FFT 高通残差、rolling Koopman/DMD 多步预测等），输出为一个 pkl 文件（包含 `pair -> DataFrame` 的映射）。
- 然后你可以用 `scripts/qlib/timing_audit.py --extra-features ... --only-extra-factors` 把这些特征按同一口径验收，并继续用 `export_timing_policy.py` 基于 `pos` 序列做相关性去冗余。

---

## 8) 来源（已登记到 `docs/knowledge/source_registry.md`）

- [1] https://research-center.amundi.com/files/nuxeo/dl/64691927-6c77-4b12-b267-93cc85cd0619（S-1024）
- [2] https://www.gsam.com/content/dam/gsam/pdfs/institutions/en/articles/2018/Combining_Investment_Signals_in_LongShort_Strategies.pdf（S-1025）
- [3] https://alphaarchitect.com/should-investors-combine-or-separate-their-factor-exposures/（S-1026）
- [4] https://www.cfm.com/wp-content/uploads/2022/12/137-Equity-Factors-To-Short-Or-Not-To-Short-That-Is-The-Question.pdf（S-1027）
- [5] https://quantpedia.com/long-short-vs-long-only-implementation-of-equity-factors/（S-1028）
- [6] https://www.nber.org/system/files/working_papers/w24618/w24618.pdf（S-1029）
- [7] https://www.sciencedirect.com/science/article/abs/pii/S1566014119301669（S-1030）
- [8] https://en.wikipedia.org/wiki/Nyquist_frequency（S-1031）
- [9] https://pmc.ncbi.nlm.nih.gov/articles/PMC4447444/（S-1032）
- [10] https://www.hindawi.com/journals/mpe/2022/4024953/（S-1033）
- [11] http://arxiv.org/pdf/2201.10466.pdf（S-1034）
