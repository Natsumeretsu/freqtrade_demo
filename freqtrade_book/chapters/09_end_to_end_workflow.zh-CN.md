# 端到端实战：从回测跑通到 dry-run 稳定运行

[返回目录](../SUMMARY.zh-CN.md) | [上一章](./08_freqai.zh-CN.md) | [下一章](./90_reference_library.zh-CN.md)

## 本章目标

- 把前面章节的知识串成一条“可复现、可回滚”的端到端流程。
- 你能在不暴露密钥、不启用 API/UI 的前提下，让 dry-run 稳定跑起来，并知道该看哪些输出判断是否正常。

## 本章完成标准（学完你应该能做到）

- [ ] 能从 `config.example.json` 复制出可用的 `config.json`（并确保 `dry_run: true`）
- [ ] 能跑通“排错三件套”，并定位问题属于配置/策略/数据哪一类
- [ ] 能完成数据下载 + 固定区间回测，并生成可复现的结果文件
- [ ] 能启动 dry-run 持续运行，并知道如何安全停止、看日志、做最小回滚

---

## 0) 最小命令模板（一键验证：配置/策略/数据）

如果你只想确认“整个链路到底通没通”，先跑这三条：

```powershell
uv run freqtrade show-config --userdir "." --config "config.json"
uv run freqtrade list-strategies --userdir "." --config "config.json"
uv run freqtrade list-data --userdir "." --config "config.json"
```

### 0.1 关键输出检查点

- `show-config`：包含 `Your combined configuration is:`，并确认 `dry_run: true`、`strategy`、`stake_*` 等关键值符合预期。
- `list-strategies`：能看到你的策略（例如 `SimpleTrendFollowV6`），且 `Status` 为 `OK`。
- `list-data`：能列出数据文件（交易对 + timeframe），否则先回到“数据与回测”补齐数据。

---

## 1) 准备配置：从脱敏模板开始（推荐）

如果你还没有一份“可提交/可复制”的配置，建议从模板复制（并按需修改交易所与交易对）：

```powershell
Copy-Item "config.example.json" "config.json"
```

你可以先保持：

- `dry_run: true`
- `api_server.enabled: false`
- `telegram.enabled: false`

当你需要填入密钥/Token 时，推荐放到第二份私密配置（并确保被 git 忽略）：

```powershell
Copy-Item "config-private.example.json" "config-private.json"
```

启动时叠加两份配置（私密覆盖公开）：

```powershell
uv run freqtrade show-config --userdir "." --config "config.json" --config "config-private.json"
```

---

## 2) 数据：先把输入“钉牢”，再谈回测结果

建议先用一个最小集合跑通（例如：5m + 近 30 天）：

```powershell
uv run freqtrade download-data --userdir "." --config "config.json" --timeframes 5m --days 30
uv run freqtrade list-data --userdir "." --config "config.json"
```

如果你计划做可对比迭代，尽量固定：

- `--timeframe`
- `--timerange`
- 交易对列表（whitelist/pairlists）

---

## 3) 回测：固定区间，产出可复现结果

先跑一次最小回测（建议固定区间）：

```powershell
uv run freqtrade backtesting --userdir "." --config "config.json" --strategy "SimpleTrendFollowV6" --timeframe 5m --timerange 20240101-
```

你应该看到：

- 终端输出里有 `Total profit %`、`Absolute drawdown` 等摘要
- `backtest_results/` 目录下生成 `backtest-result-*.zip`

如果“完全无交易”，不要猜，先导出信号：

```powershell
uv run freqtrade backtesting --userdir "." --config "config.json" --strategy "SimpleTrendFollowV6" --timeframe 5m --timerange 20240101- --export signals
```

---

## 4) dry-run：安全启动、观察、停止、回滚

启动 dry-run（谨慎：会进入持续运行）：

```powershell
uv run freqtrade trade --userdir "." --config "config.json"
```

建议你在启动后按这个顺序观察：

1. 终端输出是否持续滚动、是否有明显报错（连接/权限/配置无效）。
2. `logs/` 目录是否产生/更新日志文件（排错第一入口）。
3. 是否出现“下单金额不足/最小下单额”等提示（回到 `stake_amount`、`max_open_trades`、`dry_run_wallet` 联合调整）。

停止运行：在终端按 `Ctrl+C`。

最小回滚路径（遇到异常先收敛风险）：

1. 确认 `dry_run` 仍为 `true`（先跑 `show-config`）。
2. 暂时减少交易对列表与并发（例如降低 `max_open_trades`），先把问题规模缩小。
3. 回到固定区间回测复现，再改策略/改配置（不要在运行中盲改一堆项）。

---

## 5) 一句话排错原则（本章最重要的“极简心法”）

当你卡住时，不要在“感觉”里打转：把问题缩小到“同一条命令、同一份配置、同一段时间范围”能稳定复现，再开始改动。

参考：本书 [排错与复现手册](./92_troubleshooting_playbook.zh-CN.md)

---

## 延伸阅读（参考库）

- 配置：[`freqtrade_docs/configuration.zh-CN.md`](../../freqtrade_docs/configuration.zh-CN.md)
- 数据下载：[`freqtrade_docs/data_download.zh-CN.md`](../../freqtrade_docs/data_download.zh-CN.md)
- 回测：[`freqtrade_docs/backtesting.zh-CN.md`](../../freqtrade_docs/backtesting.zh-CN.md)
- 回测输出解释：[`freqtrade_docs/backtest_glossary.zh-CN.md`](../../freqtrade_docs/backtest_glossary.zh-CN.md)
- 启动与使用 Bot：[`freqtrade_docs/bot_usage.zh-CN.md`](../../freqtrade_docs/bot_usage.zh-CN.md)

---

[返回目录](../SUMMARY.zh-CN.md) | [上一章](./08_freqai.zh-CN.md) | [下一章](./90_reference_library.zh-CN.md)

