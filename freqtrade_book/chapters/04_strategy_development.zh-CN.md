# 策略开发：从 SampleStrategy 到可迭代策略

[返回目录](../SUMMARY.zh-CN.md) | [上一章](./03_data_backtest.zh-CN.md) | [下一章](./05_hyperopt.zh-CN.md)

## 本章目标

- 你能在 `strategies/` 下创建/修改策略，并跑回测验证。
- 你能建立“写策略 → 回测 → 分析 → 修正”的迭代闭环。

## 本章完成标准（学完你应该能做到）

- [ ] 能用 `new-strategy` 生成策略模板，并在 `list-strategies` 里看到它
- [ ] 能用固定 `--timerange` 跑通回测，保证修改前后可对比
- [ ] 明白 `strategy` 填的是策略类名，而不是 `*.py` 文件名
- [ ] 遇到“没单/异常”时，知道用 `--export signals` 与排错清单定位问题

---

## 0) 最小命令模板（策略从创建到回测）

```powershell
uv run freqtrade new-strategy --userdir "." --strategy "MyStrategy" --template minimal
uv run freqtrade list-strategies --userdir "." --config "config.json"
uv run freqtrade backtesting --userdir "." --config "config.json" --strategy "MyStrategy"
```

### 0.1 关键输出检查点

- `new-strategy`：生成 `strategies/MyStrategy.py`（或提示已创建/已存在）。
- `list-strategies`：表格里能看到 `MyStrategy`，且 `Status` 为 `OK`。
- `backtesting`：能跑通并打印回测摘要（若“完全无交易”，按本章排错清单定位是否有入场信号）。

---

## 1) 策略文件放哪？怎么被发现？

本仓库的策略目录是 `strategies/`。

查看可用策略（非常推荐先确认名字）：

```powershell
uv run freqtrade list-strategies --userdir "." --config "config.json"
```

补充两条最常见规则（不记住就会卡很久）：

- `strategy` 配置/参数里填的是“策略类名”，不是 `*.py` 文件名。
- `list-strategies` 看不到你的策略时，通常是：文件不在 `strategies/`、类名不匹配、或策略文件有语法错误。

---

## 2) 策略迭代的最小闭环

1. 改策略（只改一个点，便于归因）
2. 跑回测（固定 timerange 与 timeframe）
3. 看 exit reason 与回撤
4. 需要时导出 signals 做进一步分析

---

## 3) 你最容易忽略的两件事

### 3.1 前视偏差（Lookahead bias）

任何涉及未来信息的计算都会让回测“虚高”。改完策略后，建议在关键版本跑一次：

- [`freqtrade_docs/lookahead_analysis.zh-CN.md`](../../freqtrade_docs/lookahead_analysis.zh-CN.md)

### 3.2 交易所最小下单额

策略回测/模拟用的 stake 太小，会导致：

- 回测成交逻辑与真实成交不一致
- 交易被拒绝/信号被跳过

你需要在策略与配置层面一起校验：`stake_amount`、`dry_run_wallet`、`max_open_trades`。

---

## 4) 进阶主题（按需）

- 回调（callbacks）：做更精细的行为控制
- 自定义止损/加仓：风险与收益都更极端，务必先在回测里验证
- 迁移：Freqtrade 升级后策略接口变动时如何迁移

---

## 5) 练习：从模板开始写你的第一个策略

目标：你能生成策略模板、跑通回测，并在只改一个点的前提下观察结果变化。

1. 生成一个最小模板：

```powershell
uv run freqtrade new-strategy --userdir "." --strategy "MyStrategy" --template minimal
```

2. 确认 Freqtrade 能加载到它：

```powershell
uv run freqtrade list-strategies --userdir "." --config "config.json"
```

3. 跑一次固定区间回测（建议固定 `--timerange` 便于复现）：

```powershell
uv run freqtrade backtesting --userdir "." --config "config.json" --strategy "MyStrategy" --timerange 20240101-
```

---

## 6) 排错速查（策略相关）

- `list-strategies` 看不到策略：先检查 `strategies/` 下是否存在对应 `*.py`，再检查文件内类名是否与 `--strategy` 一致。
- 报 `SyntaxError`/`ImportError`：先让策略文件能被 Python 正常导入；不要一上来就加复杂依赖。
- 回测没单：优先检查是否有入场信号（可用 `--export signals` 导出），再检查交易对/时间范围是否覆盖了信号出现的行情。

---

## 延伸阅读（参考库）

- 策略快速开始：[`freqtrade_docs/strategy_101.zh-CN.md`](../../freqtrade_docs/strategy_101.zh-CN.md)
- 策略自定义：[`freqtrade_docs/strategy_customization.zh-CN.md`](../../freqtrade_docs/strategy_customization.zh-CN.md)
- 策略回调：[`freqtrade_docs/strategy_callbacks.zh-CN.md`](../../freqtrade_docs/strategy_callbacks.zh-CN.md)
- 高级策略：[`freqtrade_docs/strategy_advanced.zh-CN.md`](../../freqtrade_docs/strategy_advanced.zh-CN.md)
- 策略迁移：[`freqtrade_docs/strategy_migration.zh-CN.md`](../../freqtrade_docs/strategy_migration.zh-CN.md)
- 策略分析示例：[`freqtrade_docs/strategy_analysis_example.zh-CN.md`](../../freqtrade_docs/strategy_analysis_example.zh-CN.md)

---

[返回目录](../SUMMARY.zh-CN.md) | [上一章](./03_data_backtest.zh-CN.md) | [下一章](./05_hyperopt.zh-CN.md)
