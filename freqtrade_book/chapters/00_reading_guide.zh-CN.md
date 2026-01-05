# 阅读指南（如何用这套手册学习与查阅）

[返回目录](../SUMMARY.zh-CN.md) | 上一章：无 | [下一章](./01_environment_setup.zh-CN.md)

## 本章目标

- 你能理解这套“手册 + 参考库”的分工。
- 你能选择适合自己的学习路径，并知道遇到问题该去哪里查。

## 本章完成标准（学完你应该能做到）

- [ ] 能说清 `freqtrade_book/`（手册）与 `freqtrade_docs/`（参考库）的分工
- [ ] 能按目标选一条学习路线，并知道下一章该读哪一篇
- [ ] 知道统一命令模板，并会用 `show-config` 验证配置是否生效
- [ ] 会用 `rg` 在 `freqtrade_docs/` 里检索参数/报错关键词

---

## 1) 这套资料怎么分层？

### 1.1 手册（freqtrade_book）

手册是“教你怎么做”的：

- 按学习顺序组织（从环境 → 配置 → 数据 → 回测 → 策略 → 优化 → 运维 → 实盘）。
- 重点写：常用命令模板、踩坑点、排错路径、该看哪些文档。

### 1.2 参考库（freqtrade_docs）

参考库是“权威原文 + 可全文搜索”的：

- 每页都包含“原文自动 Markdown 化”，你可以在编辑器里 `Ctrl+F` 搜关键词，也可以用 `rg` 全仓搜索。
- 参考库里正文可能包含英文（这是刻意保留，避免丢信息/丢示例）。

---

## 2) 三条学习路线（按你的目标选）

### 2.1 2 小时：先跑通回测

目标：能下载数据、能回测、能看懂结果。

1. 环境准备：[01_environment_setup.zh-CN.md](./01_environment_setup.zh-CN.md)
2. 配置最小化：[02_configuration.zh-CN.md](./02_configuration.zh-CN.md)
3. 数据下载：[03_data_backtest.zh-CN.md](./03_data_backtest.zh-CN.md)（配合 [`freqtrade_docs/data_download.zh-CN.md`](../../freqtrade_docs/data_download.zh-CN.md)）
4. 回测：[03_data_backtest.zh-CN.md](./03_data_backtest.zh-CN.md)（配合 [`freqtrade_docs/backtesting.zh-CN.md`](../../freqtrade_docs/backtesting.zh-CN.md)）
5. 看懂输出：[`freqtrade_docs/backtest_glossary.zh-CN.md`](../../freqtrade_docs/backtest_glossary.zh-CN.md)

### 2.2 1–2 天：写出能跑的策略并迭代

目标：能从 SampleStrategy 出发，写出自己的策略，做回测迭代。

1. 策略入门：[04_strategy_development.zh-CN.md](./04_strategy_development.zh-CN.md)
2. 防前视偏差：[`freqtrade_docs/lookahead_analysis.zh-CN.md`](../../freqtrade_docs/lookahead_analysis.zh-CN.md)
3. 可视化与分析：[`freqtrade_docs/plotting.zh-CN.md`](../../freqtrade_docs/plotting.zh-CN.md)、[`freqtrade_docs/strategy_analysis_example.zh-CN.md`](../../freqtrade_docs/strategy_analysis_example.zh-CN.md)

### 2.3 上实盘：风险控制 + 运维监控

目标：能在 dry-run 稳定运行后，逐步切到实盘，并具备监控与回滚能力。

1. 风控与实盘切换：[06_live_risk.zh-CN.md](./06_live_risk.zh-CN.md)
2. 运维监控：[07_ops_monitoring.zh-CN.md](./07_ops_monitoring.zh-CN.md)
3. 安全相关：[`freqtrade_docs/rest_api.zh-CN.md`](../../freqtrade_docs/rest_api.zh-CN.md)、[`freqtrade_docs/telegram_usage.zh-CN.md`](../../freqtrade_docs/telegram_usage.zh-CN.md)、[`freqtrade_docs/webhook_config.zh-CN.md`](../../freqtrade_docs/webhook_config.zh-CN.md)

---

## 3) 统一命令模板（本仓库约定）

本仓库使用 `uv` 管理环境，且仓库根目录就是 Freqtrade 的 `userdir`。

```bash
uv run freqtrade <命令> --userdir "." <参数...>
```

当你怀疑配置没生效时，先跑这个看最终合并配置：

```bash
uv run freqtrade show-config --userdir "." --config "config.json"
```

---

## 4) 查阅技巧（让你更像在“搜本地百科”）

- 先在手册里定位主题 → 再跳到参考库原文页 → 用 `Ctrl+F` 或 `rg` 搜关键词。
- 在仓库根目录用 `rg` 全局搜索（例：找 `stake_amount`）：

```bash
rg -n "stake_amount" "freqtrade_docs"
```

---

## 延伸阅读（参考库）

- 配置：[`freqtrade_docs/configuration.zh-CN.md`](../../freqtrade_docs/configuration.zh-CN.md)
- 工具子命令：[`freqtrade_docs/utils.zh-CN.md`](../../freqtrade_docs/utils.zh-CN.md)
- 回测：[`freqtrade_docs/backtesting.zh-CN.md`](../../freqtrade_docs/backtesting.zh-CN.md)

---

[返回目录](../SUMMARY.zh-CN.md) | 上一章：无 | [下一章](./01_environment_setup.zh-CN.md)
