# 数据下载与回测：从“有数据”到“看得懂结果”

[返回目录](../SUMMARY.zh-CN.md) | [上一章](./02_configuration.zh-CN.md) | [下一章](./04_strategy_development.zh-CN.md)

## 本章目标

- 你能为回测/超参下载 OHLCV 数据，并理解 timerange/timeframe。
- 你能跑一次回测，并知道怎么解读输出与定位策略问题。

## 本章完成标准（学完你应该能做到）

- [ ] 能完成 `download-data` 并用 `list-data` 确认数据落盘到 `data/`
- [ ] 能跑通 `backtesting` 并读懂回测区间、收益/回撤与 `exit_reason`
- [ ] 能固定 `--timeframe` + `--timerange` 产出可复现结果，支持迭代归因
- [ ] 遇到收益“虚高”时，知道优先做 `lookahead-analysis` 排查前视偏差

---

## 0) 最小命令模板（先跑通一条链路）

```powershell
uv run freqtrade download-data --userdir "." --config "config.json" --timeframes 5m --days 30
uv run freqtrade backtesting --userdir "." --config "config.json" --strategy "SimpleTrendFollowV6"
```

### 0.1 关键输出检查点

- `download-data`：无报错退出，且 `data/` 下能看到对应交易所/交易对/timeframe 的数据文件。
- `backtesting`：无报错退出，并生成 `backtest_results/backtest-result-*.zip`；终端输出里能看到 `Total profit %`、`Absolute drawdown`、`Exit reason` 等摘要。

---

## 1) 数据下载：先把输入准备好

最常用命令（以配置文件里的交易所/交易对为准）：

```powershell
uv run freqtrade download-data --userdir "." --config "config.json" --timeframes 5m --days 30
```

下载后的数据默认落在本仓库的 `data/` 目录（因为仓库根目录就是 userdir）。你可以用 `list-data` 快速确认：

```powershell
uv run freqtrade list-data --userdir "." --config "config.json"
```

建议把数据下载当成“持续维护”的事情：

- 老交易对：增量补齐缺口即可（通常不需要再写 `--days` / `--timerange`）
- 新交易对：用 `--new-pairs-days` 给新币单独补齐历史天数

---

## 2) 回测：先跑通，再逐步提高“可信度”

### 2.1 最小回测模板

```powershell
uv run freqtrade backtesting --userdir "." --config "config.json" --strategy "SimpleTrendFollowV6"
```

常用追加项：

- 指定时间范围：`--timerange 20240101-`
- 指定周期：`--timeframe 5m`
- 导出信号：`--export signals`

### 2.2 看懂结果：先看这三块

1. 回测区间（from/to），确认你跑的是你以为的那段时间。
2. `Total profit %` 与 `Absolute drawdown`，收益和回撤一起看。
3. `exit_reason` 统计，弄清盈利/亏损主要来自哪些退出原因。

回测指标速查建议直接打开：

- [`freqtrade_docs/backtest_glossary.zh-CN.md`](../../freqtrade_docs/backtest_glossary.zh-CN.md)

---

## 3) 常见坑：前视偏差与数据质量

- 指标预热不足（`startup_candle_count`）会影响回测起点与信号质量。
- “看起来收益很高”但一上实盘就崩，通常要先排查前视偏差：
  - 参考：[`freqtrade_docs/lookahead_analysis.zh-CN.md`](../../freqtrade_docs/lookahead_analysis.zh-CN.md)

---

## 4) 可视化与分析（建议你养成习惯）

回测不是只看一行收益率，推荐：

- 用 plotting 看资金曲线/交易分布
- 用 backtesting-analysis 做分组统计（按周/月/交易对/退出原因）

---

## 5) 练习：产出一份“可复现”的回测结果

目标：你能在固定时间范围与固定周期下复现同一份结果，便于迭代归因。

1. 下载数据（示例：5m，近 90 天）：

```powershell
uv run freqtrade download-data --userdir "." --config "config.json" --timeframes 5m --days 90
```

2. 固定回测范围跑回测（示例：从 20240101 开始）：

```powershell
uv run freqtrade backtesting --userdir "." --config "config.json" --strategy "SimpleTrendFollowV6" --timeframe 5m --timerange 20240101-
```

3. 需要进一步分析时，再导出信号：

```powershell
uv run freqtrade backtesting --userdir "." --config "config.json" --strategy "SimpleTrendFollowV6" --timeframe 5m --timerange 20240101- --export signals
```

---

## 6) 排错速查（数据/回测）

- 提示 “No data”/“数据为空”：先跑 `list-data` 确认数据确实落在 `data/`，再确认 `pair_whitelist` 与 `--timeframe` 一致。
- 回测起点很晚：通常是指标预热 `startup_candle_count` 导致，或数据本身在起点缺失。
- 回测“虚高”：优先做前视偏差检查（`lookahead-analysis`），再谈调参/加指标。

---

## 延伸阅读（参考库）

- 数据下载：[`freqtrade_docs/data_download.zh-CN.md`](../../freqtrade_docs/data_download.zh-CN.md)
- 回测：[`freqtrade_docs/backtesting.zh-CN.md`](../../freqtrade_docs/backtesting.zh-CN.md)
- 回测分析（高级）：[`freqtrade_docs/advanced_backtesting.zh-CN.md`](../../freqtrade_docs/advanced_backtesting.zh-CN.md)
- 绘图：[`freqtrade_docs/plotting.zh-CN.md`](../../freqtrade_docs/plotting.zh-CN.md)
- 前视偏差分析：[`freqtrade_docs/lookahead_analysis.zh-CN.md`](../../freqtrade_docs/lookahead_analysis.zh-CN.md)
- 递归分析：[`freqtrade_docs/recursive_analysis.zh-CN.md`](../../freqtrade_docs/recursive_analysis.zh-CN.md)
- SQL 速查（查数据库/结果）：[`freqtrade_docs/sql_cheatsheet.zh-CN.md`](../../freqtrade_docs/sql_cheatsheet.zh-CN.md)

---

[返回目录](../SUMMARY.zh-CN.md) | [上一章](./02_configuration.zh-CN.md) | [下一章](./04_strategy_development.zh-CN.md)
