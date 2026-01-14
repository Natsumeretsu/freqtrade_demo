# 风险痛点清单（年度窗口）：SmallAccountSpotTrendFilteredV1（BTC/USDT，4h）

更新日期：2026-01-12

本报告聚焦“只做多现货 + 小资金（10USDT）+ max_open_trades=1 + fee=0.0006”约束下，
策略在 **2021/2022** 两个年度窗口的回撤/亏损成因（逐笔交易级别可复现），并给出“仅改风险层”的优化方向，
用于后续资料搜集与迭代验证。

补充：
- 综合结论（局部帕累托前沿判断）见：`docs/reports/change_summary_2026-01-12.md`
- 注意：`artifacts/benchmarks/` 与 `01_freqtrade/backtest_results/` 默认不随 git 同步；本报告仅记录 RunId 与关键数字，跨设备请用 `-RunId` 复现。

---

## 1) 口径与数据来源

- 交易所与数据：OKX spot，本地 `01_freqtrade/data/okx`（BTC/USDT，4h）
- 小资金约束：dry_run_wallet=10、max_open_trades=1、tradable_balance_ratio=0.95
- 成本假设：fee=0.0006
- 年度窗口基准快照（用于痛点归因，风险收敛前的旧跑次）：
  - RunId：`bench_small10_SmallAccountSpotTrendFilteredV1_4h_2026-01-12_16-14-39`（默认输出到 `artifacts/benchmarks/`，不随 git 同步）

---

## 2) 年度窗口结果（2020-2023，按年拆分）

来源：RunId=`bench_small10_SmallAccountSpotTrendFilteredV1_4h_2026-01-12_16-14-39` 的 `summary.csv`（本地产物）

- 2020：profit=59.7560%，maxDD=18.2934%，trades=21（PASS）
- 2021：profit=-2.7595%，maxDD=26.2851%，trades=22（FAIL）
- 2022：profit=-26.7295%，maxDD=28.6817%，trades=8（FAIL）
- 2023：profit=51.2352%，maxDD=15.3857%，trades=15（PASS）

结论：当前策略对 2023+ 较稳健，但在 2021/2022 的“结构切换/深回撤”年份，**尾部风险控制不足**。

---

## 3) 2021：逐笔归因（问题在哪里）

### 3.1 退出原因贡献（profit_abs 汇总）

- `trailing_stop_loss`：14 笔，合计 `+7.1641`
- `stop_loss`：8 笔，合计 `-7.4400`

观察：**盈利主要靠趋势段追踪止损**，但被多笔止损几乎完全吃掉。

### 3.2 入场标签贡献（profit_abs 汇总）

- `bull`：16 笔，合计 `-2.0500`（净拖累）
- `cross`：4 笔，合计 `+1.1536`
- `reentry`：2 笔，合计 `+0.6204`

观察：2021 的核心问题不是“趋势启动/回踩再入”，而是 **bull 类入场在某些阶段承担了大量 -10% 尾部亏损**。

### 3.3 关键现象：大量 -10% 固定止损（疑似未触发 ATR 动态止损）

2021 的 8 笔 `stop_loss` 中：
- 约 87.5% 的 `profit_ratio` 极接近 `-0.101079...`（固定 `stoploss=-0.10` 口径）
- 主要来自 `enter_tag=bull`

含义：在这些亏损单里，策略的“ATR 动态止损收敛（目标 3%~6%）”大概率未能及时介入，
导致尾部风险直接落在固定 -10% 止损上。

### 3.4 2021 最差交易样本（按 profit_abs 由小到大）

用于“场景复盘/资料检索”的最差样本（时间均为 UTC）：

- 2021-02-21 → 2021-02-22：enter_tag=bull，exit=stop_loss，profit_ratio≈-10.11%，stake≈11.10
- 2021-02-25 → 2021-02-26：enter_tag=bull，exit=stop_loss，profit_ratio≈-10.11%，stake≈10.04
- 2021-03-18 → 2021-03-23：enter_tag=bull，exit=stop_loss，profit_ratio≈-10.11%，stake≈9.88
- 2021-10-21 → 2021-10-27：enter_tag=bull，exit=stop_loss，profit_ratio≈-10.11%，stake≈9.75
- 2021-01-04 → 2021-01-04：enter_tag=bull，exit=stop_loss，profit_ratio≈-10.11%，stake≈9.50
- 2021-04-13 → 2021-04-18：enter_tag=bull，exit=stop_loss，profit_ratio≈-10.11%，stake≈9.16
- 2021-07-31 → 2021-08-05：enter_tag=bull，exit=stop_loss，profit_ratio≈-10.11%，stake≈9.16
- 2021-09-16 → 2021-09-20：enter_tag=cross，exit=stop_loss，profit_ratio≈-6.11%，stake≈8.23

---

## 4) 2022：逐笔归因（问题在哪里）

### 4.1 退出原因贡献（profit_abs 汇总）

- `trailing_stop_loss`：2 笔，合计 `+1.1972`
- `stop_loss`：5 笔，合计 `-3.6199`
- `exit_signal`：1 笔，合计 `-0.2502`

观察：2022 是典型熊市，趋势段更少，**止损与死叉退出主导亏损**。

### 4.2 入场标签贡献（profit_abs 汇总）

- `bull`：3 笔，合计 `-2.8548`（核心拖累）
- `cross`：5 笔，合计 `+0.1819`（基本打平）

### 4.3 关键现象：出现“连续亏损/连续止损”链条

以回测交易顺序统计：
- 最大连续亏损笔数：5
- 最大连续 `stop_loss`：3

含义：熊市阶段存在“反弹-再跌”的结构，策略在 **bull/趋势内加仓** 场景下容易被多次打穿止损，
回撤会被迅速放大。

### 4.4 2022 最差交易样本（按 profit_abs 由小到大）

用于“场景复盘/资料检索”的最差样本（时间均为 UTC）：

- 2022-03-02 → 2022-03-04：enter_tag=bull，exit=stop_loss，profit_ratio≈-10.11%，stake≈9.76
- 2022-07-20 → 2022-07-26：enter_tag=bull，exit=stop_loss，profit_ratio≈-10.11%，stake≈9.70
- 2022-07-29 → 2022-08-19：enter_tag=bull，exit=stop_loss，profit_ratio≈-10.11%，stake≈8.77
- 2022-09-11 → 2022-09-13：enter_tag=cross，exit=stop_loss，profit_ratio≈-6.11%，stake≈7.53
- 2022-10-25 → 2022-11-08：enter_tag=cross，exit=stop_loss，profit_ratio≈-4.42%，stake≈6.89
- 2022-10-05 → 2022-10-08：enter_tag=cross，exit=exit_signal，profit_ratio≈-3.52%，stake≈7.11

---

## 5) 痛点总结（可直接用于资料检索的关键词）

1. **尾部风险收敛不够及时**：ATR 动态止损只在“长期 EMA 走弱”条件下启用，遇到“EMA 仍上行但价格急跌”的场景，仍可能吃满 -10% 固定止损。
2. **bull 模式的风险暴露偏高**：bull 类交易在 2021/2022 都是净拖累，且止损亏损占比高，说明“牛市不掉队”的机制需要与尾部风险更强绑定（不应只提高曝险/时长）。
3. **熊市缺少更强的去风险机制**：2022 的连续亏损表明仅靠 EMA/ADX/MACD 过滤不足以应对深熊结构，应引入更强的“去现金/降曝险/快速收敛”方案。

---

## 6) 仅改风险层的优先优化方向（建议按顺序验证）

> 原则：尽量不改入场逻辑（信号层），优先在“止损/仓位/保护”层面做可解释、低过拟合的改动。

1. **改造 ATR 动态止损的触发条件（优先级最高）**
   - 方向：当价格跌破长期 EMA（或出现显著浮亏）时，即使长期 EMA 斜率仍为正，也启用 ATR 动态止损把最大亏损从 -10% 收敛到 3%~6%。
   - 关键词：Chandelier Exit、Volatility Stop、breakdown stop、intratrade drawdown stop
2. **弱势阶段降低 bull 仓位（风险预算更保守）**
   - 方向：在“长期趋势走弱/宏观弱势”阶段，bull 模式不再 100% 仓位；趋势启动（cross）仍保留中等仓位以避免错过反转。
   - 关键词：volatility targeting、risk parity、dynamic position sizing
3. **增强止损后的冷却/去风险（防止连续止损链条）**
   - 方向：适度加强 `StoplossGuard` 或引入“亏损后降仓/暂停 N 根 K 线”的规则，减少熊市反弹中的重复试错成本。
   - 关键词：circuit breaker、loss streak cooldown、trade suspension

---

## 7) 可复现命令

年度窗口基准（2020-2023）：

```powershell
./scripts/analysis/small_account_benchmark.ps1 `
  -Pairs "BTC/USDT" `
  -Timeframe "4h" `
  -Timeranges @("20200101-20201231","20210101-20211231","20220101-20221231","20230101-20231231")
```

---

## 8) 已验证的风险改进（控制变量：只动风险层）

### 8.1 方案A（已落地）：bull 的“尾部风险收敛”

改动点（代码层）：
- bull 交易仅在浮亏超过 `sell_stop_min_loss`（默认 3%）后，才允许启用 ATR 动态止损收敛尾部风险（避免牛市正常回踩就被洗出）。

年度窗口（2020-2025）回测目录：
- RunId：`bench_small10_annual_2020-2025_SmallAccountSpotTrendFilteredV1_4h_riskA2_2026-01-12`（默认输出到 `artifacts/benchmarks/`，不随 git 同步）

关键结果（仅摘 2021/2022）：
- 2021：profit=8.8235%，maxDD=19.0404%（回撤已回到 20% 内）
- 2022：profit=-9.5318%，maxDD=14.9658%（回撤已回到 20% 内，但收益仍为负）

### 8.2 方案B（已落地）：宏观弱势下 bull 降仓（更贴合 smallaccount）

改动点（仓位层）：
- 用更长窗口判定“宏观弱势”：`buy_stake_weak_regime_lookback=72`（约 12 天）
- 宏观弱势下的 bull 仓位单独降档：`buy_stake_frac_bull_weak=0.25`

年度窗口（2020-2025）回测目录：
- RunId：`bench_small10_annual_2020-2025_SmallAccountSpotTrendFilteredV1_4h_riskB_2026-01-12`（默认输出到 `artifacts/benchmarks/`，不随 git 同步）

关键结果（仅摘 2021/2022）：
- 2021：profit=6.2555%，maxDD=19.0404%
- 2022：profit=-0.9671%，maxDD=12.1705%（接近打平，且回撤进一步降低）

结论：在不改信号层的前提下，方案B 更符合“稳定增长/控回撤”的 smallaccount 目标；
若你能接受深熊年份“接近现金/接近打平”的结果，这已经接近 long-only spot 的合理前沿。
