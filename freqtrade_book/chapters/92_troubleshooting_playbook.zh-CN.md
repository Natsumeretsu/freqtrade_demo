# 排错与复现手册（把问题缩小到可解决）

[返回目录](../SUMMARY.zh-CN.md) | [上一章](./91_keyword_index.zh-CN.md) | [下一章](./99_quick_reference.zh-CN.md)

这章不讲“参数大全”，只讲一件事：当你卡住时，如何用最短路径把问题缩小到**可复现、可定位、可验证**的状态。

如果你还没跑通一遍完整流程，建议先按本书 [端到端实战](./09_end_to_end_workflow.zh-CN.md) 跑通“配置→数据→回测→dry-run”，再回到本章按症状排查。

## 本章目标

- 你能把“我觉得不对劲”变成一组可复现命令与可对比输出。
- 你能快速判断问题属于：配置 / 策略 / 数据 / 回测 / 实盘 / 运维 / 性能 哪一类。
- 你能在不泄露密钥的前提下打包证据，方便自己或他人帮你定位。

## 本章完成标准（学完你应该能做到）

- [ ] 遇到问题先跑“三件套”命令，确认配置/策略/数据三者至少有一项是确定的
- [ ] 能用固定 `--timeframe` + `--timerange` 复现同一份回测结果
- [ ] 能按症状走到“最短排查路径”，并知道下一步该改哪里
- [ ] 能输出一份脱敏的“问题描述包”（命令 + 关键输出 + 相关文件路径）

---

## 0) 排错三件套（先把地基钉牢）

这三条命令几乎适用于所有问题：先确认最终配置、策略是否可加载、数据是否存在。

```powershell
uv run freqtrade show-config --userdir "." --config "config.json"
uv run freqtrade list-strategies --userdir "." --config "config.json"
uv run freqtrade list-data --userdir "." --config "config.json"
```

你应该看到：

- `show-config`：包含 `Your combined configuration is:`，并能看到你期望的 `strategy` / `dry_run` / `stake_amount` 等字段。
- `list-strategies`：你的策略出现在列表里且 `Status` 为 `OK`。
- `list-data`：能列出已下载的数据（交易对 + timeframe）。

如果三件套里任意一条失败：先不要继续往下猜，优先把这一条修好（后面的排查才有意义）。

---

## 1) 配置问题（`Invalid configuration` / “改了但没生效”）

### 1.1 症状

- `Invalid configuration` / JSON 解析报错
- 你改了配置但行为没变（通常是覆盖顺序/多配置/环境变量导致）

### 1.2 最短排查路径

1. 用 `show-config` 看最终合并配置（一定要先看它）。
2. 确认是否叠加了多份 `--config`，以及覆盖顺序是否符合预期。
3. 检查是否有环境变量覆盖（`FREQTRADE__...`）。
4. 配置里只保留最小可用集，逐项加回去（不要一口气改 20 个字段）。

参考：

- 本书 [配置入门](./02_configuration.zh-CN.md)
- 参考库 [`freqtrade_docs/configuration.zh-CN.md`](../../freqtrade_docs/configuration.zh-CN.md)

---

## 2) 策略加载问题（`list-strategies` 看不到 / `ImportError`）

### 2.1 症状

- `list-strategies` 没有你的策略
- `SyntaxError` / `ImportError` / `ModuleNotFoundError`
- 回测启动时报 “Could not load strategy”

### 2.2 最短排查路径

1. 先跑 `list-strategies`，看 `Status` 列的具体错误（这是最快的定位入口）。
2. 确认：策略文件在 `strategies/` 下；策略类名与 `--strategy` / `config.strategy` 一致。
3. 让策略文件“能被 Python 正常导入”（先修语法/依赖，再谈逻辑）。

参考：

- 本书 [策略开发](./04_strategy_development.zh-CN.md)
- 参考库 [`freqtrade_docs/strategy_101.zh-CN.md`](../../freqtrade_docs/strategy_101.zh-CN.md)

---

## 3) 数据问题（`No data` / 回测起点异常 / timeframe 不匹配）

### 3.1 症状

- `No data` / `No candles` / `No data for pair ...`
- 明明下载了数据，但回测提示缺数据
- 回测起点比你设定的时间晚很多

### 3.2 最短排查路径

1. 用 `list-data` 确认数据确实存在（并且 timeframe 正确）。
2. 重新跑一次 `download-data`（明确指定 `--timeframes`，并给足 `--days` 或 `--timerange`）。
3. 核对 `exchange.pair_whitelist` 与你下载数据时的交易对一致。
4. 回测起点偏晚：通常是指标预热 `startup_candle_count` 或数据本身缺口导致。

参考：

- 本书 [数据与回测](./03_data_backtest.zh-CN.md)
- 参考库 [`freqtrade_docs/data_download.zh-CN.md`](../../freqtrade_docs/data_download.zh-CN.md)

---

## 4) 回测结果异常（无交易 / 收益虚高 / 与实盘差异大）

### 4.1 症状

- 回测“完全无交易”
- 收益夸张但实盘/模拟表现差
- 不同时间区间结果差异极大

### 4.2 最短排查路径

1. 固定 `--timeframe` + `--timerange`，保证结果可复现：

```powershell
uv run freqtrade backtesting --userdir "." --config "config.json" --strategy "SimpleTrendFollowV6" --timeframe 5m --timerange 20240101-
```

2. 无交易：优先导出信号看是否真的有入场信号（不要靠猜）：

```powershell
uv run freqtrade backtesting --userdir "." --config "config.json" --strategy "SimpleTrendFollowV6" --timeframe 5m --timerange 20240101- --export signals
```

3. 收益虚高：先做前视偏差检查（不做这步，后面调参很可能是浪费时间）：

```powershell
uv run freqtrade lookahead-analysis --userdir "." --config "config.json" --strategy "SimpleTrendFollowV6"
```

参考：

- 参考库 [`freqtrade_docs/lookahead_analysis.zh-CN.md`](../../freqtrade_docs/lookahead_analysis.zh-CN.md)
- 参考库 [`freqtrade_docs/backtesting.zh-CN.md`](../../freqtrade_docs/backtesting.zh-CN.md)

---

## 5) 下单/实盘问题（最小下单额/余额不足/挂单不成交）

### 5.1 症状

- `Minimum trade amount` / `insufficient funds`
- 挂单长期不成交，交易卡住

### 5.2 最短排查路径

1. 回到 `stake_amount` / `max_open_trades` / `tradable_balance_ratio` / `dry_run_wallet`，对照交易所最小下单额校验。
2. 检查 `unfilledtimeout`（避免挂单卡死），以及 `entry_pricing`/`exit_pricing` 的 orderbook 设置。
3. 先在 dry-run 稳定跑通，再切实盘；实盘与 dry-run 建议分库并可回滚配置。

参考：

- 本书 [配置入门](./02_configuration.zh-CN.md)
- 本书 [实盘与风控](./06_live_risk.zh-CN.md)
- 参考库 [`freqtrade_docs/exchanges.zh-CN.md`](../../freqtrade_docs/exchanges.zh-CN.md)

---

## 6) 运维问题（API/UI/通知/端口/安全）

### 6.1 症状

- 端口占用 / `Connection refused`
- UI/API 可以访问但担心安全
- Telegram/Webhook 不工作

### 6.2 最短排查路径

1. 先 `show-config`，确认 `api_server.enabled`、监听地址/端口、用户名/密码等最终值。
2. 不用就关；要用也只监听 `127.0.0.1`，远程用 SSH tunnel/VPN，不要暴露公网。
3. Token/密钥只放私密配置或环境变量；不要写入可提交文件。

参考：

- 本书 [运维与监控](./07_ops_monitoring.zh-CN.md)
- 参考库 [`freqtrade_docs/rest_api.zh-CN.md`](../../freqtrade_docs/rest_api.zh-CN.md)
- 参考库 [`freqtrade_docs/telegram_usage.zh-CN.md`](../../freqtrade_docs/telegram_usage.zh-CN.md)

---

## 7) 性能问题（hyperopt/FreqAI 很慢）

### 7.1 最短排查路径

- 先缩小问题规模：减少 `--timerange`、降低 `--epochs`、减少参数空间/特征数量。
- 每次只改一个因素，并记录结果（否则你很难判断到底哪个改动带来的变化）。

参考：

- 本书 [超参优化](./05_hyperopt.zh-CN.md)
- 本书 [FreqAI](./08_freqai.zh-CN.md)

---

## 8) 你应该如何“描述一个问题”（脱敏版证据包）

当你准备把问题交给别人（或未来的自己）时，建议按下面清单输出，定位效率会暴涨：

- 你执行的命令（完整复制粘贴）
- `show-config` 的关键字段（不要贴全量密钥；只贴 `dry_run` / `strategy` / `stake_*` / `pair_whitelist` 等）
- 关键输出关键词（3–5 行即可，不贴整段长日志）
- 涉及的文件与目录：`config.json` / `strategies/<strategy>.py` / `data/` / `backtest_results/`
- 复现条件：`--timeframe` 与 `--timerange`

脱敏规则：

- 禁止出现真实 `exchange.key` / `exchange.secret` / Telegram token / API 密码 / JWT secret。
- 优先用模板：`config.example.json` + `config-private.example.json`。

---

[返回目录](../SUMMARY.zh-CN.md) | [上一章](./91_keyword_index.zh-CN.md) | [下一章](./99_quick_reference.zh-CN.md)
