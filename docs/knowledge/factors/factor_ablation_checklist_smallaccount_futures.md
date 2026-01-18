# 因子消融（Ablation）检查清单：SmallAccountFuturesTrendV1（合约择时）

更新日期：2026-01-13

目标：把“单因子 vs 多因子”的讨论落到可复现的回测对照上，回答两件事：

1) **某个门控/阈值是否真的有用**（单因子：一次只动一个）。
2) **多个门控组合后是否更稳**（多因子：逐步叠加，做样本外验证）。

---

## 0) 强制固定口径（否则结果不可比）

建议先固定以下口径，之后所有实验都用同一套参数：

- config：`04_shared/configs/small_account/config_small_futures_base.json`
- pair：`BTC/USDT:USDT`
- timeframe：`4h`
- trading_mode：`futures`（isolated）
- dry_run_wallet：10
- max_open_trades：1
- fee：0.0006

统一回测入口（本仓库约定，不要直接跑 `freqtrade`）：

```powershell
./scripts/analysis/small_account_backtest.ps1 -Config "04_shared/configs/small_account/config_small_futures_base.json" -Strategy "SmallAccountFuturesTrendV1" -Pairs "BTC/USDT:USDT" -Timeframe "4h" -TradingMode "futures" -Timerange "20200101-20251231"
```

指标提取（可选，但强烈推荐用于对照表）：

```powershell
uv run python -X utf8 "scripts/analysis/backtest_metrics.py" --zip "<上一步输出的zip路径>" --strategy "SmallAccountFuturesTrendV1"
```

---

## 1) 基线（Baseline）

1) 确认当前策略参数文件：`01_freqtrade/strategies/SmallAccountFuturesTrendV1.json`
2) 跑一次全区间基线回测（建议先全区间，再按年拆分）
3) 记录至少四个数：`profit_total_pct`、`max_relative_drawdown_pct`、`total_trades`、`stop_loss` 占比（如需归因再看 enter_tag）

---

## 2) 单因子消融：推荐顺序（一次只改一个开关/门槛）

说明：本策略把“交易频率”主要交给 `reentry_*`，因此消融时优先改动“容易产生噪声亏损”的交叉触发（`cross_*`）。

### 2.1 `cross_*` 专用准入 Gate（优先级最高）

目标：减少“弱交叉/假突破”的止损占比。

- 开关：`buy_use_cross_gate`
- 门槛：
  - `buy_gate_cross_min_spread`
  - `buy_gate_cross_adx_delta`
  - `buy_gate_cross_slope_lookback`
  - `buy_gate_cross_min_slope_pct`
  - `buy_gate_cross_min_macdhist_pct`

对照建议：

- 实验 1：`buy_use_cross_gate=false`（关闭 Gate）
- 实验 2：`buy_use_cross_gate=true`（开启 Gate，使用默认门槛）
- 实验 3：只提高 1 个门槛（例如 `buy_gate_cross_min_spread`），其余不动

判定要点：

- `total_trades` 不应塌缩到极低
- `stop_loss`（尤其 `cross_*`）占比应下降，或“同等 trade 下回撤下降”

### 2.2 宏观体制：硬门控 vs 软门控

目标：熊段更保守，但避免 0 trades。

- 硬门控：`buy_use_macro_trend_filter`（默认关闭）
- 软门控：`buy_use_macro_trend_stake_scale + buy_macro_stake_scale_floor`（默认开启）

对照建议（只改动一个开关）：

- 实验 4：只开硬门控（`buy_use_macro_trend_filter=true`，其余不动）
- 实验 5：只开软门控（baseline 通常已是这种形态）
- 实验 6：两者都关（更激进，看看收益/回撤是否恶化）

判定要点：

- 硬门控若导致交易数明显不足，优先回退到软门控而不是硬拧参数。

### 2.3 波动率门控：`atr_pct` 的上下限

目标：过滤“波动不足导致手续费吞噬”，以及（可选）极端高波动段的尾部风险。

- 下限（默认启用）：`buy_atr_pct_min`
- 上限（可选）：`buy_use_atr_pct_max_filter + buy_atr_pct_max`

对照建议：

- 实验 7：只提高 `buy_atr_pct_min`（例如 0.004 → 0.006）
- 实验 8：开启上限过滤（`buy_use_atr_pct_max_filter=true`），观察是否导致 0 trades 或错过大趋势

### 2.4 流动性门控：`volume_ratio`

目标：避开极端低流动性段（滑点/冲击成本更糟）。

- 开关：`buy_use_volume_ratio_filter`
- 门槛：`buy_volume_ratio_lookback`、`buy_volume_ratio_min`

对照建议：

- 实验 9：`buy_use_volume_ratio_filter=true`（默认门槛）
- 实验 10：只调整 `buy_volume_ratio_min`（例如 0.8 → 0.9）

注意：BTC 主流永续通常不会缺流动性，这个因子更适合扩展到小币/多币时再评估。

### 2.5 小账户杠杆封顶（生存护栏）

目标：让“账户规模很小”时杠杆不会过激（即使交易所允许）。

- 开关：`buy_use_account_leverage_cap`（默认开启）
- 分档：`buy_account_tier1_usdt`、`buy_account_tier2_usdt`
- 封顶：`buy_account_leverage_cap_tier1/tier2/tier3`

对照建议：

- 实验 11：关闭封顶（`buy_use_account_leverage_cap=false`）
- 实验 12：更保守封顶（例如 tier1 2.0 → 1.5）

判定要点：

- 回测中它可能主要影响“杠杆曲线”，未必立刻改变胜率；但对小资金的尾部风险控制更重要。

### 2.6 资金费率过滤（仅实盘/干跑更有意义）

本仓库的实现是“有数据才拦截，没数据就放行”，因此：

- 回测里如果没有 `funding_rate` 数据序列，开关不会产生效果（这是刻意设计，避免回测报错）。

参数：

- `buy_use_funding_rate_filter`（默认关闭）
- `buy_funding_rate_max`（默认 0.0003）

建议：把它当作“实盘前的最后一道保险”，而不是回测里的主要收益来源。

---

## 3) 多因子组合：逐步叠加（不要一次全开）

推荐的叠加顺序（每一步都跑一次全区间 + 分年窗口）：

1) baseline
2) `cross gate`（只影响 `cross_*`）
3) 宏观软门控（若 baseline 已开则跳过）
4) `atr_pct` 上限（可选，若导致交易不足则撤回）
5) `volume_ratio`（仅在扩展到小币/多币时重点关注）
6) 小账户杠杆封顶（始终建议开启）

---

## 4) 样本外验证（Walk-forward）

当你找到了 1~3 个看起来“更稳”的组合，才进入样本外验证：

```powershell
./scripts/analysis/walk_forward_search.ps1 -Strategy "SmallAccountFuturesTrendV1" -Config "04_shared/configs/small_account/config_small_futures_base.json" -Pairs "BTC/USDT:USDT" -Timeframe "4h" -TrainTimerange "20200101-20211231" -TestTimerange "20220101-20221231" -DryRunWallet 10 -MaxOpenTrades 1 -Fee 0.0006
```

判定要点：

- 以验证期（TestTimerange）为准，不要只看训练期。
- 若验证期交易数过低，优先调整 `reentry` 相关门槛来恢复频率，而不是继续叠因子。

---

## 5) 结果记录模板（建议）

每次实验至少记录：

- RunId / 时间窗
- 改了哪一个参数（仅 1 个或 1 组）
- `profit_total_pct` / `max_relative_drawdown_pct` / `total_trades` / `profit_factor`
- 你观察到的“失败模式”是否改善（例如止损占比、震荡段误入场）
