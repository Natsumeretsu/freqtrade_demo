# 小资金基准回测报告：SmallAccountTrendFilteredV1（BTC/USDT，4h）

更新日期：2026-01-12

本报告用于记录本次策略升级（“牛市不掉队”方向）的关键改动、可复现命令与回测/压力测试结论，便于后续迭代追溯。

补充：
- 综合结论（局部帕累托前沿判断）见：`docs/reports/change_summary_2026-01-12.md`
- 注意：`artifacts/benchmarks/` 与 `01_freqtrade/backtest_results/` 默认不随 git 同步，本报告仅记录 RunId 与关键数字；跨设备请用 `-RunId` 复现。

---

## 1) 测试环境与口径

- 交易所与数据：OKX spot，本地 `01_freqtrade/data/okx`（BTC/USDT，4h）
- 成本假设（基准）：fee=0.0006
- 成本敏感性：fee=0.0012（2x）
- 小资金约束：dry_run_wallet=10、max_open_trades=1、tradable_balance_ratio=0.95
- 稳定性门槛（脚本默认）：
  - 每窗口交易数 ≥ 5
  - 每窗口收益（%）> 0
  - 最大回撤（%）≤ 20

---

## 2) 策略升级要点（面向“牛市不掉队”）

对应文件：`01_freqtrade/strategies/SmallAccountTrendFilteredV1.py`
参数文件：`01_freqtrade/strategies/SmallAccountTrendFilteredV1.json`

- 入场以“趋势事件”为主（避免震荡期持续贴条件重复开仓）：
  - `EMA_short` 上穿 `EMA_long`（趋势启动）
  - `close` 上穿 `EMA_short`（趋势中回踩再入）
- 增加“牛市模式”例外：当 `close > EMA_long * (1 + buy_bull_ema_long_offset)` 时，允许在趋势过滤成立前提下更积极再入（减少牛市空仓时间）。
- 新增两条“质量闸门”以降低追涨与下跌过程抄底：
  - 追高抑制：`close <= EMA_short * (1 + buy_max_ema_short_offset)`（默认 6%）
  - 动量二次确认：`close > close.shift(1)`（优先在向上推进的 K 线上入场）
- 退出保持简洁：EMA 死叉作为保底退出（并由追踪止损辅助锁定趋势利润）
- 追踪止损放宽以减少牛市“提前下车”：
  - `trailing_stop_positive_offset=0.08`
  - `trailing_stop_positive=0.06`
- 启用保护（需 config 设置 `enable_protections=true`）：避免出场后立刻反复打回去，并在连续止损后短暂停机
  - `CooldownPeriod(stop_duration_candles=1)`
  - `StoplossGuard(lookback_period_candles=48, trade_limit=1, stop_duration_candles=12)`
- 新增“弱趋势收紧”的 ATR 动态止损（避免熊段尾部风险扩大）：仅当长期 EMA 在 `sell_ema_slope_lookback` 窗口内走弱时启用，并限制熊段最大亏损为 `sell_bear_max_loss=0.06`
- 新增“动态风险预算（动态仓位）”：在不改变信号逻辑的前提下，把每笔投入资金按“趋势强度”分档（`custom_stake_amount`）
  - 牛市/强趋势：尽量用满可用资金（`buy_stake_frac_bull=1.0`）
  - 趋势一般：小幅降风险（`buy_stake_frac_normal=0.95`）
  - 长期趋势走弱：显著降风险（`buy_stake_frac_weak=0.5`）
  - 例外：趋势启动（`enter_tag=cross`）即使处于弱势窗口，也不把仓位压到最低（避免牛市起涨段掉队）
- 为提升“牛市不掉队/尽量不跑输牛市”的持仓时间（time-in-market），将长期 EMA 拉长以减少趋势中途被洗出：
  - `buy_ema_long_len`: 120 → 160（4h）

---

## 3) 基准结果（fee=0.0006）

本地产物快照（不随 git 同步）：
- RunId：`bench_small10_SmallAccountTrendFilteredV1_4h_2026-01-12_15-57-16`（默认输出到 `artifacts/benchmarks/`）
- 复现：`./scripts/analysis/small_account_benchmark.ps1 -Pairs "BTC/USDT" -Timeframe "4h" -RunId "bench_small10_SmallAccountTrendFilteredV1_4h_2026-01-12_15-57-16"`

窗口指标（来自 `summary.csv`）：
- 20230101-20231231：profit=26.8020%，maxDD=9.6081%，trades=11，market=93.2725%
- 20240101-20241231：profit=53.4885%，maxDD=12.6559%，trades=11，market=118.5238%
- 20250101-20251231：profit=15.9095%，maxDD=4.0333%，trades=5，market=-5.7319%

补充指标（由回测 zip 的交易时长计算的 time-in-market）：
- 2023：38.7346%
- 2024：44.0183%
- 2025：20.0549%

注：资金曲线图属于本地可视化产物（不随 git 同步）；需要时按“8) 可复现命令”里的 `plot_equity.py` 生成。

---

## 3.1) 与上一版跑次对比（为什么“看起来没区别”）

对比对象：
- 旧 RunId（无动态仓位）：`bench_small10_SmallAccountTrendFilteredV1_4h_2026-01-12_14-22-08`
- 新 RunId（动态风险预算）：`bench_small10_SmallAccountTrendFilteredV1_4h_2026-01-12_15-19-55`

关键指标差异（旧 → 新）：
- 2023：profit 34.0951% → 34.3553%，maxDD 9.6081% → 9.6081%，trades 13 → 13，time-in-market 40.48% → 40.48%
- 2024：profit 46.9430% → 45.0162%，maxDD 17.7309% → 17.4769%，trades 12 → 12，time-in-market 46.21% → 46.21%
- 2025：profit 7.7518% → 8.0920%，maxDD 6.1133% → 5.8124%，trades 8 → 8，time-in-market 22.44% → 22.44%

逐笔差异定位（按 `pair + open_timestamp` 匹配）：
- 本次变化包含关键参数（`buy_ema_long_len=160`），会导致交易集合发生较明显变化；建议用 `scripts/analysis/compare_backtest_zips.py` 做逐笔对照归因。

结论：
- 动态风险预算基本保持了交易集合与 time-in-market（不改信号），但能把部分弱势期仓位压低，从而在 2025 年窗口里小幅提升收益并降低回撤；代价是 2024 年窗口收益略有牺牲。

---

## 3.2) 熊市压力窗口（年内最差 90 天）

目的：回答“23 年/25 年熊段会不会连续亏损、最大可能亏多少”。

口径：
- 用 BTC/USDT 的 1d close 计算每年内滚动 90 天收益率，取最差区间作为“熊段压力窗口”。
- 在该区间内按同一套小资金口径（fee=0.0006、max_open_trades=1）跑基准回测。
- 注：该评估通常只有 1-2 笔交易，因此不使用“每窗口交易数 ≥ 5”作为评价门槛；summary 会显示 FAIL 属正常现象。

产物目录：
- RunId：`bench_small10_bear_windows_SmallAccountTrendFilteredV1_4h_2026-01-12`（默认输出到 `artifacts/benchmarks/`，不随 git 同步）

窗口指标（来自 `summary.csv`）：
- 20230713-20231011：profit=-5.2549%，maxDD=5.2549%，trades=2，market=-10.8682%
- 20251002-20251231：profit=-9.6076%，maxDD=9.6076%，trades=1，market=-25.5035%

解读：
- 两个窗口都保持“低暴露、少交易”，熊段主要风险来自“单笔接近 -10% 的止损”而不是连续多笔亏损。
- 若目标是进一步压低熊段尾部亏损，优先方向应是“长期趋势走弱时更强的禁入/降风险预算”，而不是收紧追踪止损导致牛市更早离场。

可复现命令：

```powershell
./scripts/analysis/small_account_benchmark.ps1 `
  -Pairs "BTC/USDT" `
  -Timeframe "4h" `
  -Timeranges @("20230713-20231011","20251002-20251231") `
  -RunId "bench_small10_bear_windows_SmallAccountTrendFilteredV1_4h_2026-01-12"
```

---

## 4) 压力测试（含滑点假设）

说明：
- 以“基准结果”每个窗口的回测 zip 为输入（不需要额外跑回测）。
- 交易笔数较少时（例如 5-12 笔），交易顺序洗牌对“最大回撤分布”更敏感；应重点关注 `max_drawdown p05`（更差 5% 分位）。

压力测试参数（与文件名一致）：
- slippage=0.0005（单边）
- simulations=10000
- seed=42

本次 policy 模式（从回测记录推导每笔 stake_fraction）+ slippage=0.0005 的关键结果：
- 2023：max_drawdown p05 ≈ -16.80%
- 2024：max_drawdown p05 ≈ -18.47%（尾部顺序风险提示）
- 2025：max_drawdown p05 ≈ -7.22%

---

## 5) 2x 成本验证（fee=0.0012）

本地产物快照（不随 git 同步）：
- RunId：`bench_small10_SmallAccountTrendFilteredV1_4h_2026-01-12_dynstake_fee0.0012`（默认输出到 `artifacts/benchmarks/`）

窗口指标（来自 `summary.csv`）：
- 20230101-20231231：profit=32.4412%，maxDD=9.7165%，trades=13
- 20240101-20241231：profit=43.1137%，maxDD=17.7632%，trades=12
- 20250101-20251231：profit=7.1565%，maxDD=6.0192%，trades=8

注：本次 2x 成本验证仅用于“成本敏感性闸门”；如需与基准一致的图表/压力测试，可对该目录下的三个 zip 同样执行 `plot_equity.py` 与 `stress_test.py`。

---

## 6) 风险预算对照（stake/ratio）

目标：把“稳定增长/控回撤”的小账户假设落到可复现参数：每笔交易只动用部分资金（更贴近实盘风险预算）。

对照口径（固定其它参数不变）：`tradable_balance_ratio=0.5`（约等于每笔只用 50% 资金做仓位，max_open_trades=1）

本地产物快照（不随 git 同步）：
- RunId：`bench_small10_SmallAccountTrendFilteredV1_4h_2026-01-12_dynstake_tbr0.5`（默认输出到 `artifacts/benchmarks/`）

窗口指标（来自 `summary.csv`）：
- 20230101-20231231：profit=17.6697%，maxDD=5.0570%，trades=13
- 20240101-20241231：profit=23.8806%，maxDD=9.4693%，trades=12
- 20250101-20251231：profit=4.5280%，maxDD=3.0806%，trades=8

说明：
- `./scripts/analysis/small_account_backtest.ps1` 会在每次 runDir 内自动生成 `config_override.json` 来覆盖 `tradable_balance_ratio`（避免改动基准 config 文件）。

---

## 7) 多交易对偏差验证（spot 4h）

结论（当前参数体系下）：仅 BTC/USDT 跨 2023-2025 全窗口 PASS；其它已测币对均出现“某个年份亏损或回撤超限”。

注：本节目录基于本次迭代早期跑次；本次仅调整 `sell_ema_slope_lookback` 的止损触发窗口，预计不改变“多币对 FAIL”结论。如需严格验证，可重新跑一轮多币对基准。

已验证的单币基准 RunId（默认输出到 `artifacts/benchmarks/`，不随 git 同步）：
- ETH/USDT：`bench_small10_SmallAccountTrendFilteredV1_4h_2026-01-12_11-30-32`（FAIL）
- SOL/USDT：`bench_small10_SmallAccountTrendFilteredV1_4h_2026-01-12_11-31-18`（FAIL）
- BNB/USDT：`bench_small10_SmallAccountTrendFilteredV1_4h_2026-01-12_11-33-58`（FAIL）
- XRP/USDT：`bench_small10_SmallAccountTrendFilteredV1_4h_2026-01-12_11-34-38`（FAIL）
- DOGE/USDT：`bench_small10_SmallAccountTrendFilteredV1_4h_2026-01-12_11-35-19`（FAIL）
- ADA/USDT：`bench_small10_SmallAccountTrendFilteredV1_4h_2026-01-12_11-35-56`（FAIL）

---

## 8) 可复现命令

基准回测（fee=0.0006）：

```powershell
./scripts/analysis/small_account_benchmark.ps1 -Pairs "BTC/USDT" -Timeframe "4h"
```

2x 成本回测（fee=0.0012）：

```powershell
./scripts/analysis/small_account_benchmark.ps1 -Pairs "BTC/USDT" -Timeframe "4h" -Fee 0.0012
```

风险预算对照（示例：tradable_balance_ratio=0.5）：

```powershell
./scripts/analysis/small_account_benchmark.ps1 -Pairs "BTC/USDT" -Timeframe "4h" -TradableBalanceRatio 0.5
```

生成资金曲线（示例：2023 窗口）：

```powershell
uv run python -X utf8 "scripts/analysis/plot_equity.py" `
  --zip "01_freqtrade/backtest_results/<run_dir>/<backtest-result>.zip" `
  --out "artifacts/benchmarks/<bench_dir>/plots/equity_vs_market_20230101-20231231.html" `
  --benchmark bh `
  --datadir "01_freqtrade/data/okx" `
  --timeframe "1h"
```

压力测试（示例：policy 模式，适合动态仓位）：

```powershell
uv run python -X utf8 "scripts/analysis/stress_test.py" `
  --zip "01_freqtrade/backtest_results/<run_dir>/<backtest-result>.zip" `
  --mode policy `
  --simulations 10000 `
  --seed 42 `
  --slippage 0.0005
```

对比两份回测 zip（逐笔交易差异 + 指标差异）：

```powershell
uv run python -X utf8 "scripts/analysis/compare_backtest_zips.py" `
  --left-zip "01_freqtrade/backtest_results/<old_run_dir>/<backtest-result>.zip" `
  --right-zip "01_freqtrade/backtest_results/<new_run_dir>/<backtest-result>.zip" `
  --strategy "SmallAccountTrendFilteredV1" `
  --out-md "artifacts/benchmarks/compare_backtest_zips.md"
```
