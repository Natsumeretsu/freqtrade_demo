# 单因子 vs 多因子：择时视角（面向本仓库 / Freqtrade）

更新日期：2026-01-13

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

