# Freqtrade 回测输出关键词解释（中文速查）

这份文档用于帮助你看懂 Freqtrade `backtesting` 在终端里打印的英文指标，以及 `backtest_results/*.zip` 内的结果文件。

## 1) 你生成的“回测报告文件”分别是什么？

以 `backtest_results/backtest-result-2025-12-31_13-37-42.zip` 为例：

- `.last_result.json`：只记录“最新一次回测结果”的 zip 文件名。
- `*.meta.json`：元信息（策略名、周期、起止时间戳、run_id），不含盈亏明细。
- `*.zip`：完整结果包，通常包含：
  - `*.json`：本次回测的**完整统计 + 每笔交易明细**（最重要）。
  - `*_config.json`：本次回测使用的配置快照（便于复现）。
  - `*_Strategy.py`：本次回测使用的策略源码快照（便于复现）。
  - `*_market_change.feather`：市场涨跌参考数据。

## 2) 新手最快的阅读顺序（终端输出）

1. 看 `Backtesting from` / `Backtesting to`：这次回测覆盖的时间范围。
2. 看 `Trading Mode` / `Timeframe` / `Pairlist`：你回测的市场类型、K 线周期、交易对范围。
3. 看 `Total profit %` 与 `Absolute drawdown`：收益和最大回撤要一起看。
4. 看 `exit_reason_summary`（或终端的 `Exit reason stats`）：赚钱主要来自哪里，亏钱主要来自哪里。

## 3) 关键词速查（英文 → 中文怎么理解）

### A. 基础信息

- `Backtesting from` / `Backtesting to`：回测起止时间（通常为 UTC 时间）。
- `Backtesting ... (xx days)`：回测区间长度（天）。
- `Trading Mode`：交易模式。
  - `Spot`：现货（只能做多，买入再卖出）。
  - `Futures` / `Swap`：合约/永续（可做多做空，规则更复杂）。
- `Timeframe`：K 线周期（例如 `5m` 表示 5 分钟一根 K 线）。
- `Pairlist`：交易对列表（你回测/交易会覆盖哪些交易对）。
  - `StaticPairList`：静态交易对（你在 `exchange.pair_whitelist` 写死的列表）。
  - `VolumePairList`：按成交量动态选币（新手不建议一上来用，回测也更容易踩坑）。
- `Max open trades`：最大同时持仓单数（开仓数量上限）。
  - 你设置的上限可能是 3，但如果只有 2 个交易对，实际最多也只能同时开 2 单。

### B. 资金与收益

- `Starting balance`：回测起始资金（例如 1000 USDT）。
- `Final balance`：回测结束资金。
- `Absolute profit`：绝对收益（`Final - Starting`，以计价币显示，例如 USDT）。
- `Total profit %`：总收益率（`Absolute profit / Starting balance`）。
- `Avg. daily profit`：日均收益（绝对值）。
- `Total/Daily Avg Trades`：总交易笔数 / 日均交易笔数。
- `Avg. stake amount`：平均每笔使用资金（与你的 `stake_amount`、仓位管理有关）。
- `Total trade volume`：总成交额（所有交易的进出场累计成交额，越大不代表越好）。

### C. 胜率与交易分布

- `Win%` / `winrate`：胜率（盈利单占比）。
- `Win / Draw / Loss`：盈利 / 持平 / 亏损 的笔数统计。
- `Best Pair` / `Worst Pair`：表现最好/最差的交易对。
- `Best trade` / `Worst trade`：单笔交易的最好/最差收益。
- `Best day` / `Worst day`：单日最好/最差收益（绝对值）。
- `Days win/draw/lose`：盈利日/持平日/亏损日的天数统计。

### D. 风险与回撤（非常关键）

- `Min balance` / `Max balance`：回测期间资金曲线的最低/最高点。
- `Max % of account underwater`：最大回撤比例（资金从峰值回落的最大百分比）。
- `Absolute drawdown`：最大回撤金额（资金从峰值回落的最大金额）。
- `Drawdown duration`：从回撤开始到回撤结束经历了多久。
- `Drawdown start` / `Drawdown end`：最大回撤区间的起止时间点。
- `Profit at drawdown start` / `Profit at drawdown end`：回撤区间开始/结束时的累计利润位置。

### E. 退出原因（Exit reason）

回测里每笔交易最终都会以某个“退出原因”结束，常见的有：

- `roi`：达到策略/配置设定的 ROI（止盈规则）而退出。
- `stop_loss`：触发止损而退出（风险控制的底线）。
- `exit_signal`：策略给出了明确卖出信号而退出。
- `force_exit`：被强制退出（常见原因：回测结束时仓位仍未平仓，系统强制平仓用于统计）。

如果你看到 `roi` 赚钱很多，但 `stop_loss` 一次亏很多，通常说明策略“胜率高但容易踩一次大坑”，需要进一步优化止损/过滤条件/仓位控制。

### F. 常见量化指标（不用死背，先知道它们在比较“稳不稳”）

- `CAGR %`：年化复合收益率（由短期回测推算，样本越短越不可靠）。
- `Sharpe`：夏普比率（风险调整后收益；越高通常越好，但不同场景不可直接对比）。
- `Sortino`：索提诺比率（更关注下行波动的风险调整收益）。
- `Calmar`：卡玛比率（通常与最大回撤相关，越高越好）。
- `SQN`：系统质量数（System Quality Number，偏综合评价，样本太少时意义不大）。
- `Profit factor`：盈利因子（总盈利 / 总亏损，>1 才表示总体盈利）。
- `Expectancy (Ratio)`：单笔交易期望收益及其比率（看“平均每笔赚/亏”与稳定性）。

## 4) 小白常见疑问

- 为什么回测起始时间不是你下载数据的第一根 K 线？
  - 因为策略需要“预热K线”（例如 `startup_candle_count=200`），在凑够指标所需历史数据前不会交易，所以回测区间会从“预热结束后”开始统计。
- 为什么你配置了 3 个 `max_open_trades`，结果里显示最多只有 2？
  - 因为你只回测了 2 个交易对（`BTC/USDT`、`ETH/USDT`），同一时间最多就只能开 2 单。

