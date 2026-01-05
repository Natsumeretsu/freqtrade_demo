# 运维与监控：UI / API / 通知 / 更新

[返回目录](../SUMMARY.zh-CN.md) | [上一章](./06_live_risk.zh-CN.md) | [下一章](./08_freqai.zh-CN.md)

## 本章目标

- 你能在不暴露安全风险的前提下启用 UI/API，并建立基本监控链路。
- 你能更新版本并处理常见运维问题。

## 本章完成标准（学完你应该能做到）

- [ ] 不用 Web/API 时，能确认 `api_server.enabled: false` 且最终配置确实关闭
- [ ] 需要启用时，知道只监听 `127.0.0.1` 并用 SSH tunnel/VPN 远程访问
- [ ] 知道日志与结果目录（`logs/`、`backtest_results/` 等）作为固定排错入口
- [ ] 更新版本前后能用 dry-run/回测做最小验证，避免“升级后悄悄变行为”

---

## 0) 最小命令模板（先验证“接口是否真的关闭”）

```bash
uv run freqtrade show-config --userdir "." --config "config.json"
```

如果你目前“不用 Web/API 管理”，建议把 `api_server.enabled` 保持为 `false`，并用上面的命令确认最终合并配置里确实是关闭状态。

---

## 1) freqUI：用 UI 管理 bot（先想清楚安全边界）

freqUI 很方便，但默认不提供 https，安全边界要你自己负责：

- 优先只监听本机（`127.0.0.1`）
- 远程访问用 SSH tunnel / VPN，不要直接暴露到公网

---

## 2) REST API：不用就关，用就“强密码 + 不暴露公网”

如果你确实要启用 `api_server`：

- 强密码、随机 JWT secret、随机 ws token
- 不要把端口直接暴露到公网

---

## 3) 通知链路：Telegram / Webhook

通知是运维的一部分：让你能及时知道 bot 状态、异常、交易动作。

原则：

- Token/密钥永远脱敏（环境变量或私密配置）
- 把“可执行操作”的接口（强制进场/强制退出）视为高风险能力

---

## 4) 更新与插件

版本更新可能带来行为变化，建议：

- 更新前先看 changelog/重大变更
- 更新后先跑 dry-run 或回测验证策略是否受影响

---

## 5) 练习：给自己建一条“最小监控链路”

目标：出现异常时，你能第一时间知道“发生了什么、该去哪看”。

1. 明确你不用的能力并关掉（例如：不用 UI/API/Telegram 就全部 `enabled: false`）。
2. 约定一个固定的排错入口：优先看日志（`logs/`）、再看数据库/回测结果（`backtest_results/`、`hyperopt_results/`）。
3. 每次改配置后都先跑 `show-config`，避免“我以为开了/关了”的错觉。

---

## 6) 排错速查（运维常见问题）

- 端口占用：先改端口或关掉冲突服务，再启动。
- UI/API 能访问但不安全：优先改为只监听 `127.0.0.1`，远程访问用 SSH tunnel/VPN，不要直连公网。
- Token/密钥泄露风险：永远放到私密配置或环境变量；不要把可执行操作的接口暴露到公网。

---

## 延伸阅读（参考库）

- freqUI：[`freqtrade_docs/freq_ui.zh-CN.md`](../../freqtrade_docs/freq_ui.zh-CN.md)
- REST API：[`freqtrade_docs/rest_api.zh-CN.md`](../../freqtrade_docs/rest_api.zh-CN.md)
- Telegram：[`freqtrade_docs/telegram_usage.zh-CN.md`](../../freqtrade_docs/telegram_usage.zh-CN.md)
- Webhook：[`freqtrade_docs/webhook_config.zh-CN.md`](../../freqtrade_docs/webhook_config.zh-CN.md)
- 插件：[`freqtrade_docs/plugins.zh-CN.md`](../../freqtrade_docs/plugins.zh-CN.md)
- 更新：[`freqtrade_docs/updating.zh-CN.md`](../../freqtrade_docs/updating.zh-CN.md)

---

[返回目录](../SUMMARY.zh-CN.md) | [上一章](./06_live_risk.zh-CN.md) | [下一章](./08_freqai.zh-CN.md)
