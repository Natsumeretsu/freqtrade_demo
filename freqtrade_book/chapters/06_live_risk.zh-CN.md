# 实盘与风控：从 dry-run 到 production 的安全路径

[返回目录](../SUMMARY.zh-CN.md) | [上一章](./05_hyperopt.zh-CN.md) | [下一章](./07_ops_monitoring.zh-CN.md)

## 本章目标

- 你能理解“切换实盘”需要改哪些配置，以及为什么要分离数据库与密钥。
- 你能把风险控制当成系统的一部分，而不是策略的附属品。

## 本章完成标准（学完你应该能做到）

- [ ] 能列出并执行“切实盘最小 checklist”（含数据库/密钥隔离）
- [ ] 能用两份配置叠加启动，并用 `show-config` 验证关键字段最终值
- [ ] 明白 `stoploss` / `unfilledtimeout` / `max_open_trades` / `stake_*` 等开关对风险的影响
- [ ] 知道在 dry-run 稳定后再切实盘，并保留可回滚路径

---

## 0) 最小命令模板（dry-run → 实盘）

```bash
uv run freqtrade trade --userdir "." --config "config.json"
uv run freqtrade show-config --userdir "." --config "config.json"
```

---

## 1) 实盘切换的最小 checklist

1. `dry_run: false`
2. 使用新的数据库（避免 dry-run 交易污染统计）
3. 交易所 API Key 正确、权限最小化（尽量只给需要的权限）
4. 风控参数明确（止损、最大持仓、超时、保护机制）

强烈建议：

- 密钥放在第二份私密配置或环境变量，不要写进公开文件。
- 实盘使用单独的配置与数据库（哪怕只改一项，也要能一键回滚到 dry-run 配置）。

---

## 2) 风控重点（你必须知道这几个开关）

- `stoploss`：策略/配置层面的硬止损
- `unfilledtimeout`：限价单超时处理（避免挂单卡死）
- `max_open_trades`：并发持仓上限（风险上限）
- `stake_amount` / `tradable_balance_ratio`：仓位与资金曲线形态

---

## 3) 做空与杠杆（如果你要上合约）

本仓库默认是现货（spot）。如果你要做合约/杠杆：

- 先读清楚交易所模式与保证金逻辑
- 再在回测/模拟里验证逻辑

---

## 4) 练习：把“切换实盘”做成可回滚的开关

目标：你能在不改动公开配置的情况下，切换 dry-run/实盘，并确保统计与密钥隔离。

1. 保留公开配置 `config.json`（不放密钥，且默认 `dry_run: true`）。
2. 新建私密配置（例如 `config-private.json`），只放密钥与实盘专用项（并确保被 git 忽略）。
3. 启动时叠加两份配置（私密覆盖公开）：

```bash
uv run freqtrade trade --userdir "." --config "config.json" --config "config-private.json"
```

4. 启动前先跑 `show-config`，确认 `dry_run`、交易所、数据库等关键字段确实是你期望的值。

---

## 5) 排错速查（实盘/风控）

- 订单长时间不成交：先看是否是限价单挂太远；再看 `unfilledtimeout`、`entry_pricing`/`exit_pricing` 的 orderbook 设置。
- 资金不足/下单金额不足：回到 `stake_amount`、`tradable_balance_ratio`、交易所最小下单额与手续费规则一起核对。
- 风险开关没生效：第一件事永远是 `show-config`（多配置/环境变量时尤其如此）。

---

## 延伸阅读（参考库）

- 启动与使用 Bot：[`freqtrade_docs/bot_usage.zh-CN.md`](../../freqtrade_docs/bot_usage.zh-CN.md)
- 止损：[`freqtrade_docs/stoploss.zh-CN.md`](../../freqtrade_docs/stoploss.zh-CN.md)
- 做空与杠杆：[`freqtrade_docs/leverage.zh-CN.md`](../../freqtrade_docs/leverage.zh-CN.md)
- 交易所说明：[`freqtrade_docs/exchanges.zh-CN.md`](../../freqtrade_docs/exchanges.zh-CN.md)
- 配置（含 dry-run/production 说明）：[`freqtrade_docs/configuration.zh-CN.md`](../../freqtrade_docs/configuration.zh-CN.md)

---

[返回目录](../SUMMARY.zh-CN.md) | [上一章](./05_hyperopt.zh-CN.md) | [下一章](./07_ops_monitoring.zh-CN.md)
