# SmallAccountFuturesTrendV1 明日优化计划（风险控制优先）

## 0. 背景与现状（可复现口径）

目标不是“见信号就进”，而是把策略拆成两层：

1) **触发层（Signal）**：产生候选入场事件（例如均线交叉/回踩再入）。  
2) **准入层（Gate / Risk Filter）**：判断“该不该入”，不通过就直接放弃（或仅降低风险，而不是强行入场）。

本仓库口径（小资金合约）：

- config：`configs/small_account/config_small_futures_base.json`
- pair：`BTC/USDT:USDT`
- timeframe：`4h`
- timerange：`20200101-20251231`
- dry_run_wallet：`10`
- max_open_trades：`1`
- fee：`0.0006`

复现命令：

```powershell
./scripts/analysis/small_account_backtest.ps1 -Config "configs/small_account/config_small_futures_base.json" -Strategy "SmallAccountFuturesTrendV1" -Pairs "BTC/USDT:USDT" -Timeframe "4h" -TradingMode "futures" -Timerange "20200101-20251231"
```

## 1. 已完成的关键结论（为什么回测差 / 为什么要改触发器）

### 1.1 原版主要亏损来源

在原版触发器里，`bull/bear`（价格远离长期 EMA 的趋势模式）会直接触发入场，结果出现典型现象：

- `stop_loss` 的笔数/亏损略大于 `trailing_stop_loss` 的盈利 → 长期净值水下。
- 亏损集中在 `bull`（long）与 `bear`（short）两类“趋势模式直接入场”。

### 1.2 已做的改动（降低误入场，而不是追求更高频）

把 `bull_mode/bear_mode` 从“入场触发器”降级为“趋势强弱标签/风控档位依据”，仅保留：

- `cross_*`（均线交叉启动）
- `reentry_*`（趋势内回踩再入）

此改动已写入：`strategies/SmallAccountFuturesTrendV1.py`

（注意：`bull/bear` 仍可作为 `enter_tag`，用于仓位/杠杆档位或统计归因，但不再单独触发入场。）

## 2. 明日目标（你睡醒后继续的方向）

在“风险控制优先”的前提下，提高“有效交易频率”，核心做法是：

- **放宽触发层（让候选信号更容易出现）**：主要靠 `reentry`（趋势回踩再入）来增加频率；
- **收紧准入层（让差的候选被挡掉）**：主要针对 `cross_*` 的“弱交叉/假突破”做更严格过滤。

最终希望看到的不是“交易更多”，而是：

- `stop_loss` 占比下降（尤其 `cross_long` / `cross_short` 的止损占比）
- 在不显著抬高最大回撤的情况下，交易次数回升

## 3. 具体工作计划（可执行清单）

### 3.1 先定“硬约束”（避免目标漂移）

1) 最大可接受回撤（例如 20% / 30%）  
2) 目标交易频率（例如每年 10~30 笔，或每月 1~3 笔）  
3) 最高杠杆上限（即使交易所允许更高，也要策略内封顶，例如 2x/3x）  

### 3.2 做一次“准入层”数据归因（找到该挡的信号）

对现有回测 trades 做拆分统计（至少按以下维度）：

- `side`（long/short）
- `enter_tag`（cross_long/reentry_long/cross_short/reentry_short）
- `exit_reason`（重点看 stop_loss）
- 分年份窗口（2020/2021/2022/2023/2024/2025）

目标输出：

- 哪个 `enter_tag` 的 `stop_loss` 占比最高、亏损最大
- 这些止损单在“入场时”的指标分布特征（用于挑门槛）

### 3.3 在策略里实现“准入层 Gate”（不该入的直接不入）

优先改 `populate_entry_trend`（可回测、可统计、可超参）：

- 为 `cross_long` 增加更强确认门槛（示例思路）：
  - `ema_spread_abs`（短长 EMA 扩散）必须大于阈值（过滤弱交叉）
  - `macdhist_pct = macdhist / close` 必须大于阈值（过滤弱动量）
  - `ema_l_slope_pct` 必须大于阈值（过滤长期趋势不够强）
- 为 `cross_short` 增加对称门槛（`macdhist_pct` 为负且绝对值足够大、长期 EMA 下行足够明显）。

参数化（建议新增、可优化）：

- `buy_gate_cross_min_spread`
- `buy_gate_cross_min_macdhist_pct`
- `buy_gate_cross_min_slope_pct`
- （可选）分 long/short 两套阈值

注意事项：

- Gate 不要写成“硬门控导致 0 trades”，应优先“挡掉明显差的候选”，并保留 `reentry` 作为主要频率来源。
- Gate 的计算必须只依赖当前 dataframe 列（避免 `confirm_trade_entry` 做重计算导致性能下降）。

### 3.4 用“reentry”来提升频率，但不牺牲准入质量

如果交易次数太少，优先调整：

- `buy_reentry_min_ema_long_offset`
- `buy_reentry_min_ema_spread`

而不是重新放开 `bull/bear` 追涨追跌触发。

### 3.5 验证方法（避免只在单窗口好看）

1) 先跑全区间：`20200101-20251231`（看总收益/回撤/交易数/exit_reason 分布）  
2) 再跑分年窗口：每年一段（看最差窗口，防止某一年拖垮）  
3) 若需要自动化搜索：用仓库已有的 `pareto_neighborhood_search.ps1` / `walk_forward_search.ps1` 做邻域搜索 + walk-forward 验证

## 4. 明天我建议你优先回答我的 3 个问题（定门槛用）

1) 最大回撤你能接受多少？（20%/30%/更高？）  
2) 你希望频率大概到什么程度？（例如每年 10 笔还是 50 笔？）  
3) 你对杠杆上限的底线是多少？（2x/3x/5x？）

