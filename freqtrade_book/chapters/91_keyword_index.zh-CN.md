# 关键词索引（按参数/命令快速跳转）

[返回目录](../SUMMARY.zh-CN.md) | [上一章](./90_reference_library.zh-CN.md) | [下一章](./99_quick_reference.zh-CN.md)

用途：当你只记得“一个关键词/一个参数名/一个子命令”，但不知道该翻哪页时，用这份索引快速跳转到对应章节与参考库。

使用方式：

- 先在本页 `Ctrl+F` 搜关键词（例如 `stake_amount` / `timerange` / `unfilledtimeout`）。
- 需要更深挖时，打开对应的 `freqtrade_docs/*.zh-CN.md`，再 `Ctrl+F` 或用 `rg` 全仓搜索。

---

## A) 配置与资金（最常查）

- `config.json`：本书 [配置入门](./02_configuration.zh-CN.md)；参考库 [`freqtrade_docs/configuration.zh-CN.md`](../../freqtrade_docs/configuration.zh-CN.md)
- `show-config`：本书 [阅读指南](./00_reading_guide.zh-CN.md)；参考库 [`freqtrade_docs/utils.zh-CN.md`](../../freqtrade_docs/utils.zh-CN.md)
- `stake_amount`：每单金额（或 `unlimited` 动态分配）；本书 [配置入门](./02_configuration.zh-CN.md)；参考库 [`freqtrade_docs/configuration.zh-CN.md`](../../freqtrade_docs/configuration.zh-CN.md)
- `tradable_balance_ratio`：可用余额比例（预留手续费/舍入空间）；本书 [配置入门](./02_configuration.zh-CN.md)
- `dry_run_wallet`：dry-run 模拟本金；本书 [配置入门](./02_configuration.zh-CN.md)
- `max_open_trades`：最大并发持仓；本书 [配置入门](./02_configuration.zh-CN.md)
- `unfilledtimeout`：挂单超时处理（避免卡单）；本书 [实盘与风控](./06_live_risk.zh-CN.md)；参考库 [`freqtrade_docs/configuration.zh-CN.md`](../../freqtrade_docs/configuration.zh-CN.md)
- `entry_pricing` / `exit_pricing`：入场/出场定价与 orderbook；本书 [实盘与风控](./06_live_risk.zh-CN.md)
- `pairlists` / `StaticPairList`：交易对列表来源；参考库 [`freqtrade_docs/configuration.zh-CN.md`](../../freqtrade_docs/configuration.zh-CN.md)
- `exchange.pair_whitelist`：静态交易对清单；本书 [配置入门](./02_configuration.zh-CN.md)

---

## B) 数据与回测（高频工作流）

- `download-data`：下载 OHLCV；本书 [数据与回测](./03_data_backtest.zh-CN.md)；参考库 [`freqtrade_docs/data_download.zh-CN.md`](../../freqtrade_docs/data_download.zh-CN.md)
- `list-data`：检查数据是否落盘/是否完整；本书 [数据与回测](./03_data_backtest.zh-CN.md)
- `backtesting`：回测；本书 [数据与回测](./03_data_backtest.zh-CN.md)；参考库 [`freqtrade_docs/backtesting.zh-CN.md`](../../freqtrade_docs/backtesting.zh-CN.md)
- `--timerange`：固定回测区间（可复现）；本书 [数据与回测](./03_data_backtest.zh-CN.md)
- `--timeframe`：K 线周期；本书 [数据与回测](./03_data_backtest.zh-CN.md)
- `backtesting-analysis`：回测结果分析；参考库 [`freqtrade_docs/advanced_backtesting.zh-CN.md`](../../freqtrade_docs/advanced_backtesting.zh-CN.md)
- `plot-profit` / `plot-dataframe`：绘图与可视化；参考库 [`freqtrade_docs/plotting.zh-CN.md`](../../freqtrade_docs/plotting.zh-CN.md)
- `lookahead-analysis`：前视偏差检查（收益虚高先看它）；本书 [数据与回测](./03_data_backtest.zh-CN.md)；参考库 [`freqtrade_docs/lookahead_analysis.zh-CN.md`](../../freqtrade_docs/lookahead_analysis.zh-CN.md)
- `recursive-analysis`：递归分析；参考库 [`freqtrade_docs/recursive_analysis.zh-CN.md`](../../freqtrade_docs/recursive_analysis.zh-CN.md)
- `exit_reason`：回测输出常见关键词；参考库 [`freqtrade_docs/backtest_glossary.zh-CN.md`](../../freqtrade_docs/backtest_glossary.zh-CN.md)

---

## C) 策略开发（从能跑到能迭代）

- `new-strategy`：生成策略模板；本书 [策略开发](./04_strategy_development.zh-CN.md)；参考库 [`freqtrade_docs/utils.zh-CN.md`](../../freqtrade_docs/utils.zh-CN.md)
- `list-strategies`：确认策略是否可加载（策略名=类名）；本书 [策略开发](./04_strategy_development.zh-CN.md)
- `strategy`：配置里的策略名字段；本书 [配置入门](./02_configuration.zh-CN.md)
- `--export signals`：导出信号用于分析“为啥没单”；本书 [数据与回测](./03_data_backtest.zh-CN.md)
- `strategy_101` / `strategy_customization`：策略入门与扩展点；参考库 [`freqtrade_docs/strategy_101.zh-CN.md`](../../freqtrade_docs/strategy_101.zh-CN.md)、[`freqtrade_docs/strategy_customization.zh-CN.md`](../../freqtrade_docs/strategy_customization.zh-CN.md)
- `strategy_callbacks`：回调能力（更精细的控制）；参考库 [`freqtrade_docs/strategy_callbacks.zh-CN.md`](../../freqtrade_docs/strategy_callbacks.zh-CN.md)
- `stoploss`：止损机制与配置；本书 [实盘与风控](./06_live_risk.zh-CN.md)；参考库 [`freqtrade_docs/stoploss.zh-CN.md`](../../freqtrade_docs/stoploss.zh-CN.md)

---

## D) 超参优化（Hyperopt）

- `hyperopt`：超参优化入口；本书 [超参优化](./05_hyperopt.zh-CN.md)；参考库 [`freqtrade_docs/hyperopt.zh-CN.md`](../../freqtrade_docs/hyperopt.zh-CN.md)
- `hyperopt-show`：查看最优解/指定 epoch；本书 [超参优化](./05_hyperopt.zh-CN.md)；参考库 [`freqtrade_docs/utils.zh-CN.md`](../../freqtrade_docs/utils.zh-CN.md)
- `loss` / 自定义 loss：性能要紧；本书 [超参优化](./05_hyperopt.zh-CN.md)

---

## E) 运维 / API / 通知 / 集成

- `api_server.enabled`：不用就关；本书 [运维与监控](./07_ops_monitoring.zh-CN.md)；参考库 [`freqtrade_docs/configuration.zh-CN.md`](../../freqtrade_docs/configuration.zh-CN.md)
- `jwt_secret_key` / `ws_token`：接口安全要点；参考库 [`freqtrade_docs/rest_api.zh-CN.md`](../../freqtrade_docs/rest_api.zh-CN.md)
- `freqUI`：UI 管理与安全边界；本书 [运维与监控](./07_ops_monitoring.zh-CN.md)；参考库 [`freqtrade_docs/freq_ui.zh-CN.md`](../../freqtrade_docs/freq_ui.zh-CN.md)
- `telegram`：通知；参考库 [`freqtrade_docs/telegram_usage.zh-CN.md`](../../freqtrade_docs/telegram_usage.zh-CN.md)
- `webhook`：Webhook 通知/控制；参考库 [`freqtrade_docs/webhook_config.zh-CN.md`](../../freqtrade_docs/webhook_config.zh-CN.md)
- `producer` / `consumer`：生产者/消费者模式（复用指标与信号）；参考库 [`freqtrade_docs/producer_consumer.zh-CN.md`](../../freqtrade_docs/producer_consumer.zh-CN.md)
- `plugins`：插件能力；参考库 [`freqtrade_docs/plugins.zh-CN.md`](../../freqtrade_docs/plugins.zh-CN.md)

---

## F) FreqAI（机器学习）

- `identifier`：模型/实验标识；本书 [FreqAI](./08_freqai.zh-CN.md)；参考库 [`freqtrade_docs/freqai_configuration.zh-CN.md`](../../freqtrade_docs/freqai_configuration.zh-CN.md)
- `train_period_days` / `backtest_period_days`：训练窗口与重训节奏；本书 [FreqAI](./08_freqai.zh-CN.md)
- `freqai_parameter_table`：参数表（字典式查阅）；参考库 [`freqtrade_docs/freqai_parameter_table.zh-CN.md`](../../freqtrade_docs/freqai_parameter_table.zh-CN.md)
- `freqai_feature_engineering`：特征工程；参考库 [`freqtrade_docs/freqai_feature_engineering.zh-CN.md`](../../freqtrade_docs/freqai_feature_engineering.zh-CN.md)

---

[返回目录](../SUMMARY.zh-CN.md) | [上一章](./90_reference_library.zh-CN.md) | [下一章](./99_quick_reference.zh-CN.md)
