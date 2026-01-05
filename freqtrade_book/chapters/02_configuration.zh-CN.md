# 配置入门：从“能跑”到“可控风险”

[返回目录](../SUMMARY.zh-CN.md) | [上一章](./01_environment_setup.zh-CN.md) | [下一章](./03_data_backtest.zh-CN.md)

## 本章目标

- 你能读懂 `config.json` 的关键字段，并知道它们之间的关系。
- 你能用 `show-config` 验证最终生效配置，并把密钥与公开配置分离。

## 本章完成标准（学完你应该能做到）

- [ ] 会用 `show-config` 查看最终合并配置，避免“改了但没生效”
- [ ] 会用 `list-strategies` 验证 `strategy` 名称可加载（策略名是类名）
- [ ] 能解释 `stake_amount` / `max_open_trades` / `tradable_balance_ratio` / `dry_run_wallet` 的关系
- [ ] 已在 `config.json` 写入常用策略名（例如 `SimpleTrendFollowV6`）并验证生效

---

## 0) 最小命令模板（先确认配置生效）

```bash
uv run freqtrade show-config --userdir "." --config "config.json"
uv run freqtrade list-strategies --userdir "." --config "config.json"
```

- 第一条看“最终合并配置”；第二条确认策略名可被加载（避免拼写/路径问题）。

---

## 1) 最重要的心法：先看“最终合并配置”

只要你开始用多个配置文件/环境变量/命令行参数，就必须养成这个习惯：

```bash
uv run freqtrade show-config --userdir "." --config "config.json"
```

它会告诉你：当前运行时到底使用了什么配置（避免“我以为改了，但其实没生效”）。

---

## 2) 最小可用配置要包含什么？

以现货 + dry-run 为例，你至少需要：

- 交易模式：`trading_mode: "spot"`
- 交易所：`exchange.name`
- 交易对列表：`exchange.pair_whitelist` + `pairlists: StaticPairList`
- 仓位与并发：`stake_currency` / `stake_amount` / `max_open_trades`
- dry-run：`dry_run: true` + 合理的 `dry_run_wallet`

---

## 3) 一份最小可用的 spot + dry-run 配置（脱敏示例）

你不需要一次写全量配置，先从“能跑 + 风险可控”开始。下面是一份可参考的最小集合（示例已脱敏）：

```json
{
  "trading_mode": "spot",
  "dry_run": true,
  "dry_run_wallet": 100,
  "stake_currency": "USDT",
  "stake_amount": 10,
  "max_open_trades": 3,
  "tradable_balance_ratio": 0.95,
  "strategy": "SimpleTrendFollowV6",
  "exchange": {
    "name": "okx",
    "key": "<yourExchangeKey>",
    "secret": "<yourExchangeSecret>",
    "pair_whitelist": ["BTC/USDT"],
    "pair_blacklist": []
  },
  "pairlists": [
    { "method": "StaticPairList" }
  ],
  "api_server": { "enabled": false },
  "telegram": { "enabled": false }
}
```

要点：

- `strategy` 填的是“策略类名”，不是 `*.py` 文件名；用 `list-strategies` 先确认能加载到。
- `dry_run_wallet` / `stake_amount` 太小会让回测/模拟与真实最小下单额不一致，结果容易失真。

---

## 4) 密钥怎么放更安全？

推荐两种方式（优先级从高到低）：

1. 第二份私密配置文件（例如 `config-private.json`），在启动时追加 `--config`。
2. 环境变量注入（`FREQTRADE__EXCHANGE__KEY` 等）。

你可以在公开仓库里保留“非敏感配置”，把密钥永远留在私密配置或环境变量里。

本仓库已提供可提交的脱敏模板，方便你在其它设备拉取后直接用：

- `config.example.json`：公开配置模板（复制为 `config.json` 使用）。
- `config-private.example.json`：私密配置模板（复制为 `config-private.json`，填入密钥/Token 等）。

启动时用“多配置叠加”让私密配置覆盖公开配置：

```bash
uv run freqtrade show-config --userdir "." --config "config.json" --config "config-private.json"
```

---

## 5) stake 相关参数怎么一起理解？

你最常用到的是这几个：

- `max_open_trades`：同时最多持仓多少单。
- `stake_amount`：每单使用多少 `stake_currency`（数字固定；`"unlimited"` 动态分配）。
- `tradable_balance_ratio`：账户里允许动用来交易的比例（留出手续费/舍入空间）。
- `dry_run_wallet`：dry-run 的模拟本金。

理解方式（够用的心智模型）：

- 固定 `stake_amount`：每次下单都用固定金额（单位就是 `stake_currency`，例如 `USDT`）。
- `stake_amount: "unlimited"`：把“可用资金 × `tradable_balance_ratio`”按 `max_open_trades` 做动态分配（并会扣除已占用资金/挂单占用）。
- `tradable_balance_ratio: 0.95`：相当于给手续费与舍入留出 5% 缓冲；钱包很小、或交易对精度/手续费占比更高时可再降一些。

新手常见坑：

- `dry_run_wallet` 太小 → 单笔资金可能低于交易所最小下单额，导致回测/模拟结果失真。
- `stake_amount: "unlimited"` + `max_open_trades` 较大 → 每单资金被“均分”得很小，仍可能低于最小下单额。

---

## 6) 安全最小化：不用就关掉

如果你不用 UI/API 管理，建议关闭：

- `api_server.enabled: false`
- `telegram.enabled: false`
- `webhook`（如有配置）

避免在本机之外暴露接口；更不要把 API 端口直接暴露到公网。

---

## 7) 练习：把策略名写进配置并验证

1. 在 `config.json` 设置（或确认已有）：

- `strategy: "SimpleTrendFollowV6"`

2. 运行下面两条验证：

```bash
uv run freqtrade list-strategies --userdir "." --config "config.json"
uv run freqtrade show-config --userdir "." --config "config.json"
```

你要看到：

- `list-strategies` 输出里包含 `SimpleTrendFollowV6`
- `show-config` 里 `strategy` 字段与你期望一致

---

## 8) 排错速查（配置相关）

- JSON 解析失败：优先检查是否多了逗号、引号不成对，或复制粘贴时混入了不可见字符。
- 策略加载失败：先用 `list-strategies` 定位；常见原因是类名不匹配、文件不在 `strategies/`、或策略依赖缺失。
- 下单金额不足：检查 `dry_run_wallet`、`stake_amount`、`max_open_trades`，并对照交易所最小下单额。
- 配置覆盖混乱：只要你使用了多份配置/环境变量，第一件事就是跑 `show-config` 看最终结果。

---

## 延伸阅读（参考库）

- 配置（全量）：[`freqtrade_docs/configuration.zh-CN.md`](../../freqtrade_docs/configuration.zh-CN.md)
- 工具子命令（含 `show-config`）：[`freqtrade_docs/utils.zh-CN.md`](../../freqtrade_docs/utils.zh-CN.md)
- REST API：[`freqtrade_docs/rest_api.zh-CN.md`](../../freqtrade_docs/rest_api.zh-CN.md)
- Telegram：[`freqtrade_docs/telegram_usage.zh-CN.md`](../../freqtrade_docs/telegram_usage.zh-CN.md)
- Webhook：[`freqtrade_docs/webhook_config.zh-CN.md`](../../freqtrade_docs/webhook_config.zh-CN.md)
- 交易所说明：[`freqtrade_docs/exchanges.zh-CN.md`](../../freqtrade_docs/exchanges.zh-CN.md)

---

[返回目录](../SUMMARY.zh-CN.md) | [上一章](./01_environment_setup.zh-CN.md) | [下一章](./03_data_backtest.zh-CN.md)
