# 变更总结（2026-01-12）

更新日期：2026-01-12



> **⚠️ 历史文档说明（2026-01-17）**：
> 本文档中提及的 vbrain、vharvest、local_rag、in_memoria 等系统已于 2026-01-17 完全移除。
> 当前项目采用 Docker MCP ToolKit 的 `memory` 工具（知识图谱）+ 实时获取（fetch/playwright/context7/duckduckgo）方案。
> 本文档保留作为历史记录，文中相关内容仅供参考，不再适用于当前架构。


本次变更围绕 smallaccount 目标（稳定增长/控回撤，且尽量不跑输牛市）对 `SmallAccountSpotTrendFilteredV1` 做了“风险层优先、信号层尽量少动”的迭代，并同步补齐了可追溯的知识与资料管线（来源登记、抓取缓存、vbrain 本地索引）。

---

## 1) 策略侧（SmallAccountSpotTrendFilteredV1）

### 1.1 核心原则

- 不做“为了好看而调参”的高自由度优化，优先解决跨年不稳健的尾部风险（尤其是 2021/2022 类年份）。
- 将交易分型（`enter_tag`）用于归因，确保每一类入场/再入都可解释、可验证。

### 1.2 关键改动

- `reentry` 不再净拖累：对再入增加更强的趋势闸门（长周期 EMA 位置 + 短长 EMA 乖离阈值）。
- bull 交易的尾部收敛：仅当浮亏超过最小亏损阈值时，才允许启用 ATR 动态止损，避免牛市正常回踩被“过早洗出”。
- 弱势阶段的 bull 降仓：在更长 lookback 的弱势体制下，对 bull 档仓位单独降档，降低结构性下行期间的试错成本。
- 参数文件同步：新增/调整参数已写入 `01_freqtrade/strategies/SmallAccountSpotTrendFilteredV1.json`，便于复现与后续回测。

---

## 2) 回测结论（年度窗口 2020-2025）

在 BTC/USDT spot、4h、max_open_trades=1、小资金门槛（每窗 trades≥5、profit>0、maxDD≤20）约束下：

### 2.1 `riskB` 年度窗口快照（2020-2025）

说明：
- 本节数据来自 2026-01-12 的本地回测快照（不随 git 同步），用于固定口径讨论“收益-回撤”的权衡关系。
- `PASS/FAIL` 判定门槛：每窗 trades≥5、profit>0、maxDD≤20。

- 2020：profit=98.5739%，maxDD=13.0826%，trades=22，market=187.6888%（PASS）
- 2021：profit=6.2555%，maxDD=19.0404%，trades=24，market=61.1931%（PASS）
- 2022：profit=-0.9671%，maxDD=12.1705%，trades=8，market=-64.6289%（FAIL：profit≤0）
- 2023：profit=52.9110%，maxDD=9.1850%，trades=15，market=155.0050%（PASS）
- 2024：profit=46.1963%，maxDD=10.4235%，trades=14，market=118.5238%（PASS）
- 2025：profit=15.9095%，maxDD=4.0333%，trades=5，market=-5.7319%（PASS）

### 2.2 综合结论：是否已达“局部帕累托前沿”？

结论：在你限定的“BTC/USDT 现货、只做多、4h、max_open_trades=1、手续费 0.0006、并要求回撤≤20%且尽量不跑输牛市”的条件下，当前这套策略已经非常接近“局部帕累托前沿”，但不能说达到了“证明意义上的极限”。

- “尽量不跑输牛市”和“控回撤≤20%”在单币现货 long-only 下天然冲突：要更接近大盘涨幅，需要更高的 time-in-market（更像 buy&hold），这几乎必然抬高回撤；你看到的牛市捕获率（用 `profit_total_pct / market_change_pct` 粗略估算，2020/2023/2024 约 0.34~0.53）正是这个矛盾的量化体现。
- 我们已把当前策略族里最主要、最稳健的可控项基本做到位：`reentry` 从“净拖累”变为“更强趋势闸门下的补仓”；bull 交易的尾部止损从“吃满 -10%”向“3%~6% 的收敛区间”靠拢；弱势阶段通过风险预算/降仓把结构性下行期的试错成本压低。
- 再想“明显外移前沿”，通常需要放宽约束或引入新信息源，而不是继续在 EMA/阈值上微调：例如多币种分散、允许期货做空/对冲、提高持仓上限、或引入可回测的 L2/订单流/链上数据（否则容易在同一条曲线附近“挪点”）。
- 仍然存在“可尝试但收益递减”的低过拟合方向，但更可能是在前沿上“换点”（提升某一目标会牺牲另一目标），而非同时大幅改善：例如把 MACD 零轴用于风险预算门控、把 Pinbar/InsideBar 作为再入确认、用 OHLCV 的流动性代理做 risk-off 门控。

### 2.3 复现说明（跨设备）

注意：`artifacts/benchmarks/` 与 `01_freqtrade/backtest_results/` 默认不随 git 同步；跨设备请使用同名 `-RunId` 重新生成本地产物。

年度窗口（2020-2025）快照复现（建议固定 RunId 以便对齐目录名）：

```powershell
./scripts/analysis/small_account_benchmark.ps1 `
  -Pairs "BTC/USDT" `
  -Timeframe "4h" `
  -Timeranges @(
    "20200101-20201231",
    "20210101-20211231",
    "20220101-20221231",
    "20230101-20231231",
    "20240101-20241231",
    "20250101-20251231"
  ) `
  -RunId "bench_small10_annual_2020-2025_SmallAccountSpotTrendFilteredV1_4h_riskB_2026-01-12"
```

smallaccount 评估窗口（2023-2025）快照复现：

```powershell
./scripts/analysis/small_account_benchmark.ps1 `
  -Pairs "BTC/USDT" `
  -Timeframe "4h" `
  -RunId "bench_small10_SmallAccountSpotTrendFilteredV1_4h_2026-01-12_15-57-16"
```

---

## 3) 知识与资料（可追溯 + 可复用）

### 3.1 新增 playbook（工程化落地笔记）

- EMA/MACD/Vegas：`docs/knowledge/ema_macd_vegas_playbook.md`
- K线/Pin Bar：`docs/knowledge/candlestick_pinbar_playbook.md`
- 流动性/微观结构：`docs/knowledge/crypto_liquidity_microstructure_playbook.md`

### 3.2 来源登记与抓取缓存

- 已将新增来源登记到：`docs/knowledge/source_registry.md`
- 已批量抓取可访问来源并落盘到：`.vibe/knowledge/sources/S-xxx/`
- 部分来源因验证码/Cloudflare/付费墙等原因仍被阻断，需人工介入（如有合法访问权限可用 `--interactive` 流程）。

### 3.3 vbrain（Local RAG）索引

- 新增 playbook 已 ingest 到本地索引（Local RAG）。
- 抓取来源缓存已 ingest 到本地索引（仅 ingest 成功落盘的缓存；被阻断条目会被跳过）。

---

## 4) 分析与工具脚本

为便于复现与对比，补充/增强了部分分析脚本与工具脚本（用于回测对比、容量评估、以及本地 RAG ingest 工作流）。
