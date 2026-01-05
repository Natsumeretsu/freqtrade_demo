# 快速速查（命令模板 + 排错路径）

[返回目录](../SUMMARY.zh-CN.md) | [上一章](./91_keyword_index.zh-CN.md) | 下一章：无

## 本章目标

- 把常用命令做成可直接复制的模板。
- 把常见问题的排查路径压缩到最短。

## 本章完成标准（你会用这份速查）

- [ ] 知道先用 `show-config` 确认“最终生效配置”
- [ ] 能用 1–2 条命令复现问题（下载数据/回测/导出信号）
- [ ] 遇到常见错误时，能按最短路径定位到对应参考页

## 1) 统一命令模板（本仓库）

```bash
uv run freqtrade <命令> --userdir "." <参数...>
```

---

## 2) 常用命令（按频率排序）

- 查看最终生效配置：
  - `uv run freqtrade show-config --config "config.json" --userdir "."`
- 列出可用策略：
  - `uv run freqtrade list-strategies --userdir "." --config "config.json"`
- 下载数据：
  - `uv run freqtrade download-data --userdir "." --config "config.json" --timeframes 5m --days 30`
- 回测：
  - `uv run freqtrade backtesting --userdir "." --config "config.json" --strategy "SimpleTrendFollowV6" --timerange 20240101-`
- 回测分析：
  - `uv run freqtrade backtesting-analysis --userdir "." --config "config.json" --help`
- 画图：
  - `uv run freqtrade plot-profit --userdir "." --config "config.json" --help`
- 超参优化：
  - `uv run freqtrade hyperopt --userdir "." --config "config.json" --strategy "SimpleTrendFollowV6" --help`

---

## 3) 常见问题排查（最短路径）

### 3.1 “我改了 config 但没生效”

1. 先跑 `show-config` 看最终配置
2. 再检查是否有环境变量覆盖（`FREQTRADE__...`）
3. 再检查是否有多份 `--config` 或 `add_config_files` 覆盖

参考：[`freqtrade_docs/configuration.zh-CN.md`](../../freqtrade_docs/configuration.zh-CN.md)

### 3.2 “下单被拒绝 / 最小下单额不足”

1. 检查 `stake_amount`、`max_open_trades`、`dry_run_wallet`
2. 把资金设得更贴近真实计划（尤其是用 `"unlimited"` 时）

参考：[`freqtrade_docs/configuration.zh-CN.md`](../../freqtrade_docs/configuration.zh-CN.md)

### 3.3 “回测收益虚高 / 实盘表现差”

1. 先做前视偏差检查：`lookahead-analysis`
2. 再固定 timerange/timeframe 复现问题

参考：[`freqtrade_docs/lookahead_analysis.zh-CN.md`](../../freqtrade_docs/lookahead_analysis.zh-CN.md)

---

## 4) 继续查阅

- 参考库索引：[90_reference_library.zh-CN.md](./90_reference_library.zh-CN.md)
- 回测输出速查：[`freqtrade_docs/backtest_glossary.zh-CN.md`](../../freqtrade_docs/backtest_glossary.zh-CN.md)

---

[返回目录](../SUMMARY.zh-CN.md) | [上一章](./91_keyword_index.zh-CN.md) | 下一章：无
