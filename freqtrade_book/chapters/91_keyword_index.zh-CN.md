# 关键词索引（按参数/命令快速跳转）

[返回目录](../SUMMARY.zh-CN.md) | [上一章](./90_reference_library.zh-CN.md) | [下一章](./92_troubleshooting_playbook.zh-CN.md)

用途：当你只记得“一个关键词/一个参数名/一个子命令”，但不知道该翻哪页时，用这份索引快速跳转到对应章节与参考库。

使用方式：

- 先在本页 `Ctrl+F` 搜关键词（例如 `stake_amount` / `timerange` / `unfilledtimeout`）。
- 需要更深挖时，打开对应的 `freqtrade_docs/*.zh-CN.md`，再 `Ctrl+F` 或用 `rg` 全仓搜索。

## 本章目标

- 你能“只记得一个关键词”也能快速跳转到正确章节/参考页。
- 你能把高频参数/命令/概念映射到可执行的下一步（跑命令/改配置/看哪页）。

## 本章完成标准（你会用这份索引）

- [ ] 能用 `Ctrl+F` 在本页定位到目标关键词
- [ ] 能一跳到对应章节/参考页并完成下一步动作（跑命令或修改配置）
- [ ] 遇到报错时，能把报错关键词当作索引入口（先定位，再深挖）

---

## 0) 搜索模板（推荐）

当你不知道“应该去哪页”，先把关键词当作入口跑一遍（Windows / PowerShell）：

```powershell
rg -n "stake_amount|tradable_balance_ratio|dry_run|unfilledtimeout" "freqtrade_docs"
rg -n "Invalid configuration|No data|Strategy.*not.*found|ImportError|ModuleNotFoundError" "freqtrade_docs"
```

你应该看到：

- 返回匹配行（文件路径 + 行号），从而快速定位到权威参考页。
- 若没有输出：说明关键词不在参考库里（换同义词/确认拼写/确认目录）。

---

## A) 配置与资金（最常查）

- `config.json`：本书 [配置入门](./02_configuration.zh-CN.md)；参考库 [`freqtrade_docs/configuration.zh-CN.md`](../../freqtrade_docs/configuration.zh-CN.md)
- `config.example.json` / `config-private.example.json`：脱敏模板；本书 [配置入门](./02_configuration.zh-CN.md)
- `show-config`：本书 [阅读指南](./00_reading_guide.zh-CN.md)；参考库 [`freqtrade_docs/utils.zh-CN.md`](../../freqtrade_docs/utils.zh-CN.md)
- `add_config_files` / 多份 `--config`：配置叠加与覆盖顺序；本书 [配置入门](./02_configuration.zh-CN.md)；参考库 [`freqtrade_docs/configuration.zh-CN.md`](../../freqtrade_docs/configuration.zh-CN.md)
- `FREQTRADE__...`：环境变量覆盖配置；本书 [快速速查](./99_quick_reference.zh-CN.md)；参考库 [`freqtrade_docs/configuration.zh-CN.md`](../../freqtrade_docs/configuration.zh-CN.md)

- `dry_run`：模拟盘/实盘开关；本书 [实盘与风控](./06_live_risk.zh-CN.md)；参考库 [`freqtrade_docs/configuration.zh-CN.md`](../../freqtrade_docs/configuration.zh-CN.md)
- `trading_mode`：`spot` / `futures`；本书 [配置入门](./02_configuration.zh-CN.md)；参考库 [`freqtrade_docs/leverage.zh-CN.md`](../../freqtrade_docs/leverage.zh-CN.md)
- `exchange.name`：交易所名称（例如 `okx`）；参考库 [`freqtrade_docs/exchanges.zh-CN.md`](../../freqtrade_docs/exchanges.zh-CN.md)
- `exchange.key` / `exchange.secret` / `exchange.password`：交易所 API 密钥；参考库 [`freqtrade_docs/configuration.zh-CN.md`](../../freqtrade_docs/configuration.zh-CN.md)
- `exchange.pair_whitelist` / `exchange.pair_blacklist`：交易对白名单/黑名单；本书 [配置入门](./02_configuration.zh-CN.md)
- `stake_amount`：每单金额（或 `unlimited` 动态分配）；本书 [配置入门](./02_configuration.zh-CN.md)；参考库 [`freqtrade_docs/configuration.zh-CN.md`](../../freqtrade_docs/configuration.zh-CN.md)
- `tradable_balance_ratio`：可用余额比例（预留手续费/舍入空间）；本书 [配置入门](./02_configuration.zh-CN.md)
- `dry_run_wallet`：dry-run 模拟本金；本书 [配置入门](./02_configuration.zh-CN.md)
- `max_open_trades`：最大并发持仓；本书 [配置入门](./02_configuration.zh-CN.md)
- `unfilledtimeout`：挂单超时处理（避免卡单）；本书 [实盘与风控](./06_live_risk.zh-CN.md)；参考库 [`freqtrade_docs/configuration.zh-CN.md`](../../freqtrade_docs/configuration.zh-CN.md)
- `entry_pricing` / `exit_pricing`：入场/出场定价与 orderbook；本书 [实盘与风控](./06_live_risk.zh-CN.md)
- `pairlists` / `StaticPairList`：交易对列表来源；参考库 [`freqtrade_docs/configuration.zh-CN.md`](../../freqtrade_docs/configuration.zh-CN.md)

- `order_types` / `order_time_in_force`：订单类型与有效期；参考库 [`freqtrade_docs/configuration.zh-CN.md`](../../freqtrade_docs/configuration.zh-CN.md)
- `cancel_open_orders_on_exit`：退出时是否取消挂单；本书 [配置入门](./02_configuration.zh-CN.md)
- `db_url` / 数据库：dry-run 与实盘分库；本书 [实盘与风控](./06_live_risk.zh-CN.md)；参考库 [`freqtrade_docs/configuration.zh-CN.md`](../../freqtrade_docs/configuration.zh-CN.md)
- `internals.process_throttle_secs`：主循环节流；参考库 [`freqtrade_docs/configuration.zh-CN.md`](../../freqtrade_docs/configuration.zh-CN.md)

---

## B) 数据与回测（高频工作流）

- `download-data`：下载 OHLCV；本书 [数据与回测](./03_data_backtest.zh-CN.md)；参考库 [`freqtrade_docs/data_download.zh-CN.md`](../../freqtrade_docs/data_download.zh-CN.md)
- `convert-data` / `convert-trade-data` / `trades-to-ohlcv`：数据格式转换；参考库 [`freqtrade_docs/data_download.zh-CN.md`](../../freqtrade_docs/data_download.zh-CN.md)
- `list-data`：检查数据是否落盘/是否完整；本书 [数据与回测](./03_data_backtest.zh-CN.md)
- `backtesting`：回测；本书 [数据与回测](./03_data_backtest.zh-CN.md)；参考库 [`freqtrade_docs/backtesting.zh-CN.md`](../../freqtrade_docs/backtesting.zh-CN.md)
- `backtesting-show`：查看已保存的回测结果；参考库 [`freqtrade_docs/backtesting.zh-CN.md`](../../freqtrade_docs/backtesting.zh-CN.md)
- `--timerange`：固定回测区间（可复现）；本书 [数据与回测](./03_data_backtest.zh-CN.md)
- `--timeframe`：K 线周期；本书 [数据与回测](./03_data_backtest.zh-CN.md)
- `backtesting-analysis`：回测结果分析；参考库 [`freqtrade_docs/advanced_backtesting.zh-CN.md`](../../freqtrade_docs/advanced_backtesting.zh-CN.md)
- `plot-profit` / `plot-dataframe`：绘图与可视化；参考库 [`freqtrade_docs/plotting.zh-CN.md`](../../freqtrade_docs/plotting.zh-CN.md)
- `lookahead-analysis`：前视偏差检查（收益虚高先看它）；本书 [数据与回测](./03_data_backtest.zh-CN.md)；参考库 [`freqtrade_docs/lookahead_analysis.zh-CN.md`](../../freqtrade_docs/lookahead_analysis.zh-CN.md)
- `recursive-analysis`：递归分析；参考库 [`freqtrade_docs/recursive_analysis.zh-CN.md`](../../freqtrade_docs/recursive_analysis.zh-CN.md)
- `exit_reason`：回测输出常见关键词；参考库 [`freqtrade_docs/backtest_glossary.zh-CN.md`](../../freqtrade_docs/backtest_glossary.zh-CN.md)
- `backtest_results/`：回测结果落盘目录；参考库 [`freqtrade_docs/backtest_glossary.zh-CN.md`](../../freqtrade_docs/backtest_glossary.zh-CN.md)

---

## C) 策略开发（从能跑到能迭代）

- `new-strategy`：生成策略模板；本书 [策略开发](./04_strategy_development.zh-CN.md)；参考库 [`freqtrade_docs/utils.zh-CN.md`](../../freqtrade_docs/utils.zh-CN.md)
- `list-strategies`：确认策略是否可加载（策略名=类名）；本书 [策略开发](./04_strategy_development.zh-CN.md)
- `strategy`：配置里的策略名字段；本书 [配置入门](./02_configuration.zh-CN.md)
- `strategies/`：策略目录（本仓库 userdir）；本书 [策略开发](./04_strategy_development.zh-CN.md)
- `--export signals`：导出信号用于分析“为啥没单”；本书 [数据与回测](./03_data_backtest.zh-CN.md)
- `strategy_101` / `strategy_customization`：策略入门与扩展点；参考库 [`freqtrade_docs/strategy_101.zh-CN.md`](../../freqtrade_docs/strategy_101.zh-CN.md)、[`freqtrade_docs/strategy_customization.zh-CN.md`](../../freqtrade_docs/strategy_customization.zh-CN.md)
- `strategy_callbacks`：回调能力（更精细的控制）；参考库 [`freqtrade_docs/strategy_callbacks.zh-CN.md`](../../freqtrade_docs/strategy_callbacks.zh-CN.md)
- `stoploss`：止损机制与配置；本书 [实盘与风控](./06_live_risk.zh-CN.md)；参考库 [`freqtrade_docs/stoploss.zh-CN.md`](../../freqtrade_docs/stoploss.zh-CN.md)
- `strategy-updater`：策略迁移/升级助手；参考库 [`freqtrade_docs/utils.zh-CN.md`](../../freqtrade_docs/utils.zh-CN.md)

---

## D) 超参优化（Hyperopt）

- `hyperopt`：超参优化入口；本书 [超参优化](./05_hyperopt.zh-CN.md)；参考库 [`freqtrade_docs/hyperopt.zh-CN.md`](../../freqtrade_docs/hyperopt.zh-CN.md)
- `hyperopt-show`：查看最优解/指定 epoch；本书 [超参优化](./05_hyperopt.zh-CN.md)；参考库 [`freqtrade_docs/utils.zh-CN.md`](../../freqtrade_docs/utils.zh-CN.md)
- `hyperopt-list`：列出已生成的 hyperopt 结果；参考库 [`freqtrade_docs/utils.zh-CN.md`](../../freqtrade_docs/utils.zh-CN.md)
- `loss` / 自定义 loss：性能要紧；本书 [超参优化](./05_hyperopt.zh-CN.md)
- `hyperopt_results/`：结果落盘目录；本书 [超参优化](./05_hyperopt.zh-CN.md)

---

## E) 运维 / API / 通知 / 集成

- `api_server.enabled`：不用就关；本书 [运维与监控](./07_ops_monitoring.zh-CN.md)；参考库 [`freqtrade_docs/configuration.zh-CN.md`](../../freqtrade_docs/configuration.zh-CN.md)
- `jwt_secret_key` / `ws_token`：接口安全要点；参考库 [`freqtrade_docs/rest_api.zh-CN.md`](../../freqtrade_docs/rest_api.zh-CN.md)
- `freqUI`：UI 管理与安全边界；本书 [运维与监控](./07_ops_monitoring.zh-CN.md)；参考库 [`freqtrade_docs/freq_ui.zh-CN.md`](../../freqtrade_docs/freq_ui.zh-CN.md)
- `telegram`：通知；参考库 [`freqtrade_docs/telegram_usage.zh-CN.md`](../../freqtrade_docs/telegram_usage.zh-CN.md)
- `webhook`：Webhook 通知/控制；参考库 [`freqtrade_docs/webhook_config.zh-CN.md`](../../freqtrade_docs/webhook_config.zh-CN.md)
- `producer` / `consumer`：生产者/消费者模式（复用指标与信号）；参考库 [`freqtrade_docs/producer_consumer.zh-CN.md`](../../freqtrade_docs/producer_consumer.zh-CN.md)
- `plugins`：插件能力；参考库 [`freqtrade_docs/plugins.zh-CN.md`](../../freqtrade_docs/plugins.zh-CN.md)
- `logs/`：运行日志目录（默认被 git 忽略）；本书 [运维与监控](./07_ops_monitoring.zh-CN.md)

---

## F) FreqAI（机器学习）

- `identifier`：模型/实验标识；本书 [FreqAI](./08_freqai.zh-CN.md)；参考库 [`freqtrade_docs/freqai_configuration.zh-CN.md`](../../freqtrade_docs/freqai_configuration.zh-CN.md)
- `train_period_days` / `backtest_period_days`：训练窗口与重训节奏；本书 [FreqAI](./08_freqai.zh-CN.md)
- `freqai_parameter_table`：参数表（字典式查阅）；参考库 [`freqtrade_docs/freqai_parameter_table.zh-CN.md`](../../freqtrade_docs/freqai_parameter_table.zh-CN.md)
- `freqai_feature_engineering`：特征工程；参考库 [`freqtrade_docs/freqai_feature_engineering.zh-CN.md`](../../freqtrade_docs/freqai_feature_engineering.zh-CN.md)
- `freqaimodels/`：模型落盘目录（默认被 git 忽略）；本书 [FreqAI](./08_freqai.zh-CN.md)

---

## G) 常见报错关键词（复制粘贴来搜）

下面这些关键词最适合拿来做“索引入口”（先定位到参考页/章节，再顺着排查）：

- `Invalid configuration` / `Configuration error`：配置无效（优先看 `show-config` 输出）；本书 [配置入门](./02_configuration.zh-CN.md)；参考库 [`freqtrade_docs/configuration.zh-CN.md`](../../freqtrade_docs/configuration.zh-CN.md)
- `No data` / `No candles`：没数据/数据不全/周期不匹配；本书 [数据与回测](./03_data_backtest.zh-CN.md)；参考库 [`freqtrade_docs/data_download.zh-CN.md`](../../freqtrade_docs/data_download.zh-CN.md)
- `Strategy.*not.*found` / `Could not load strategy`：策略没被发现/加载失败；本书 [策略开发](./04_strategy_development.zh-CN.md)
- `ImportError` / `ModuleNotFoundError` / `SyntaxError`：策略文件语法或依赖问题；本书 [策略开发](./04_strategy_development.zh-CN.md)
- `Minimum trade amount` / `insufficient funds`：最小下单额/余额不足；本书 [配置入门](./02_configuration.zh-CN.md)；参考库 [`freqtrade_docs/exchanges.zh-CN.md`](../../freqtrade_docs/exchanges.zh-CN.md)
- `DDoSProtection` / `RateLimit` / `RequestTimeout`：交易所限流/网络问题；参考库 [`freqtrade_docs/exchanges.zh-CN.md`](../../freqtrade_docs/exchanges.zh-CN.md)
- `Connection refused`（API/UI）：端口/监听地址/防火墙问题；本书 [运维与监控](./07_ops_monitoring.zh-CN.md)；参考库 [`freqtrade_docs/rest_api.zh-CN.md`](../../freqtrade_docs/rest_api.zh-CN.md)
- `lookahead`：回测虚高/前视偏差相关；本书 [数据与回测](./03_data_backtest.zh-CN.md)；参考库 [`freqtrade_docs/lookahead_analysis.zh-CN.md`](../../freqtrade_docs/lookahead_analysis.zh-CN.md)

---

## H) 文件与目录（你应该去哪找东西）

- `strategies/`：你的策略源码（新策略模板也会生成在这里）。
- `data/`：下载的历史数据（OHLCV 等）。
- `backtest_results/`：回测结果（zip + meta + config 快照）。
- `hyperopt_results/`：超参优化结果。
- `freqaimodels/`：FreqAI 模型落盘。
- `logs/`：运行日志（排错第一入口）。
- `notebooks/`：数据分析/策略分析 notebook。

---

## I) 常见任务（我现在想做什么？）

- 我想验证配置有没有生效：先跑 `show-config`；本书 [配置入门](./02_configuration.zh-CN.md)
- 我想确认策略是否能加载：跑 `list-strategies`；本书 [策略开发](./04_strategy_development.zh-CN.md)
- 我想下载/补齐历史数据：用 `download-data`；本书 [数据与回测](./03_data_backtest.zh-CN.md)
- 我想跑一轮可复现回测：固定 `--timeframe` + `--timerange`；本书 [数据与回测](./03_data_backtest.zh-CN.md)
- 我想端到端跑通一遍（回测→dry-run→排错）：按章节一步步执行；本书 [端到端实战](./09_end_to_end_workflow.zh-CN.md)
- 我想排查“回测虚高”：先做 `lookahead-analysis`；本书 [数据与回测](./03_data_backtest.zh-CN.md)
- 我想让参数更稳：先小 `--epochs` 跑 hyperopt，再换区间做 sanity check；本书 [超参优化](./05_hyperopt.zh-CN.md)
- 我想切实盘但可回滚：用 `config.json` + `config-private.json` 叠加启动；本书 [实盘与风控](./06_live_risk.zh-CN.md)
- 我想启用 UI/API 但不暴露公网：只监听 `127.0.0.1`，远程用 SSH tunnel/VPN；本书 [运维与监控](./07_ops_monitoring.zh-CN.md)
- 我想引入 FreqAI：先固定窗口 + `identifier`，每次只改一个因素；本书 [FreqAI](./08_freqai.zh-CN.md)

---

[返回目录](../SUMMARY.zh-CN.md) | [上一章](./90_reference_library.zh-CN.md) | [下一章](./92_troubleshooting_playbook.zh-CN.md)
