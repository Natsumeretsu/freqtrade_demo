# 配置（Configuration）

这份文档由 Freqtrade 官方页面离线保存后整理为适合快速上手/复用的 Markdown（偏"vibe coding" 风格）。

- 来源：https://www.freqtrade.io/en/stable/configuration/
- 离线保存时间：Mon Jan 05 2026 11:08:09 GMT+0800 (中国标准时间)

## 0) 本仓库的推荐运行方式（Windows + uv）

本仓库使用 `uv` 管理环境，且仓库根目录就是 Freqtrade 的 `userdir`，建议命令统一写成：

```bash
uv run freqtrade <命令> --userdir "." <参数...>
```

下文若出现 `freqtrade ...` 的官方示例，你可以直接在前面加上 `uv run`，并补上 `--userdir "."`。

---

## 1) 配置文件是什么？默认从哪里读？

- Freqtrade 运行时会读取一组配置参数（统称 bot configuration）。
- 默认读取当前工作目录下的 `config.json`。
- 可以用 `-c/--config` 指定其它配置文件路径。
- 如果你还没有配置文件，官方建议用 `freqtrade new-config --config user_data/config.json` 生成基础模板。

配置文件格式是 JSON，但 Freqtrade 额外支持：

- 单行注释：`// ...`
- 多行注释：`/* ... */`
- 列表末尾的 trailing comma（结尾逗号）

启动时 Freqtrade 会校验配置文件语法；如果写错，会提示问题所在行，按提示修正即可。

---

## 2) 参数优先级：谁会覆盖谁？

官方优先级（从高到低）：

1. CLI 参数（命令行 `--xxx`）覆盖所有其它来源
2. 环境变量（`FREQTRADE__...`）
3. 配置文件（支持多个，按加载顺序合并；后加载的通常覆盖先加载的）
4. 策略内的配置（仅在配置文件/环境变量/CLI 没设置时才会生效）

实用建议：当你发现“明明改了 `config.json` 但运行时不生效”，优先排查：

- 是否被环境变量覆盖（启动日志会打印检测到的环境变量）
- 是否被命令行参数覆盖（你启动时是否带了 `--config`、`--strategy`、`--timeframe` 等）
- 是否用了多个配置文件（合并后结果可能不是你以为的）

查看最终合并后的配置（非常推荐）：

```bash
uv run freqtrade show-config --config "config.json" --userdir "."
```

---

## 3) 用环境变量写配置（推荐：放密钥/敏感信息）

环境变量会覆盖配置文件与策略内同名配置，但仍低于 CLI 参数。

命名规则：

- 统一前缀：`FREQTRADE__`
- 通过双下划线 `__` 表示层级：`FREQTRADE__{section}__{key}`
- 例如：`FREQTRADE__STAKE_AMOUNT=200` 等价于配置里的 `"stake_amount": 200`

常见示例（官方写法）：

```text
FREQTRADE__TELEGRAM__CHAT_ID=<telegramchatid>
FREQTRADE__TELEGRAM__TOKEN=<telegramToken>
FREQTRADE__EXCHANGE__KEY=<yourExchangeKey>
FREQTRADE__EXCHANGE__SECRET=<yourExchangeSecret>
```

JSON 列表会按 JSON 解析，因此可以用环境变量设置交易对白名单：

```bash
export FREQTRADE__EXCHANGE__PAIR_WHITELIST='["BTC/USDT", "ETH/USDT"]'
```

Windows PowerShell 下可写成：

```powershell
$env:FREQTRADE__EXCHANGE__PAIR_WHITELIST = '["BTC/USDT", "ETH/USDT"]'
```

---

## 4) 多配置文件：把“公开配置”和“私密配置”拆开

### 4.1 临时用法：多个 `--config` 参数

适合一次性命令或快速验证：后面的配置会覆盖前面的同名项。

```bash
freqtrade trade --config user_data/config1.json --config user_data/config-private.json <...>
```

### 4.2 复用用法：`add_config_files`

在主配置里写 `add_config_files`，让 bot 自动加载额外配置文件并合并（路径相对主配置文件解析），避免每个命令都手写多个 `--config`：

```json
"add_config_files": [
  "config1.json",
  "config-private.json"
]
```

然后启动时只需指定主配置：

```bash
freqtrade trade --config user_data/config.json <...>
```

### 4.3 合并规则要点（避免踩坑）

- `--config A --config B`：同名项 **B 覆盖 A**（“后者赢”）。
- `add_config_files`：主配置（父配置）与被引入配置冲突时，主配置可以覆盖引入配置；多个被引入配置之间，越靠后的覆盖越靠前的（除非主配置已经定义了该键）。

强烈建议用 `show-config` 看合并后的最终结果，避免“脑补合并规则”。

---

## 5) 编辑器补全与校验（JSON Schema）

如果你的编辑器支持 JSON Schema，把下面这行放到配置文件最顶部可以获得自动补全与校验：

```json
{
  "$schema": "https://schema.freqtrade.io/schema.json"
}
```

官方还提供 develop 版 schema：`https://schema.freqtrade.io/schema_dev.json`（一般建议优先用 stable）。

---

## 6) 常用配置块速查（先把“跑起来/可控风险”）

这部分不是“逐条翻译配置表”，而是按最常用场景把关键项组织成更好用的说明。

### 6.1 交易所与交易对：`exchange` / `pairlists`

- `exchange.name`：交易所名（例如 `okx`、`binance`）。
- `exchange.key` / `exchange.secret`：API Key（dry-run 不要求真实可用；实盘必须正确）。
- `exchange.pair_whitelist`：静态白名单交易对列表（配合 `StaticPairList`）。
- `pairlists`：交易对列表生成器；新手建议先用 `StaticPairList`，可控、可复现。

### 6.2 资金与仓位：`max_open_trades` / `stake_amount` / `tradable_balance_ratio`

- `max_open_trades`：允许同时持仓的最大订单数；同一交易对最多只能开 1 单，因此交易对数量也会限制实际开仓数；设为 `-1` 表示忽略该限制（仍受交易对数量限制）。
- `stake_currency`：计价币（例如 `USDT`）。
- `stake_amount`：每次开仓使用的计价币金额。
  - 数字：每单固定金额（例如 `50` 表示每单 50 USDT）
  - `"unlimited"`：使用可用余额动态分配（更像“按余额自动配仓”，适合想做复利但也更容易踩最小下单额/手续费边界）
- `tradable_balance_ratio`：允许动用的余额比例（例如 `0.95` 表示预留 5% 不用来交易）。
- `available_capital`：当你用同一个交易所账户跑多个 bot 时，用它声明“这个 bot 可用的起始资金”以避免互相抢资金。

#### 最小下单额与安全余量（为什么你有钱也可能下不了单？）

交易所通常对不同交易对有最小下单量/最小下单金额限制。Freqtrade 为了保证止损可挂、避免被拒单，会在计算最小 stake 时额外预留一部分空间：

- `amount_reserve_percent`：默认 5%，会把最小 stake 往上抬一点（再叠加止损比例）
- 如果交易所最小限制因价格上涨而显得“很大”，Freqtrade 可能会把 stake 调整到更高；但如果需要上调的幅度超过你的目标 stake 的一定比例，交易会被拒绝

### 6.3 Dry-run 钱包：`dry_run_wallet`

dry-run 模式下，Freqtrade 使用模拟钱包执行模拟交易，其初始余额由 `dry_run_wallet` 决定（默认 1000，单位是 `stake_currency`）。

当你使用：

- `stake_amount: "unlimited"` + dry-run / backtesting / hyperopt

系统会从 `dry_run_wallet` 开始模拟资金曲线并“动态配仓”，因此 `dry_run_wallet` 必须设置成贴近你真实计划资金的值；否则会出现：

- 模拟每单资金大到离谱（例如用 100 BTC 在回测里下单）
- 模拟每单资金小到低于交易所最小下单限制

### 6.4 使用“加仓/仓位调整”（Position adjustment）时的注意点

如果你用“无限 stake + 仓位调整（DCA/加仓）”，通常需要在策略里实现 `custom_stake_amount`，并主动留出一部分余额作为后续加仓缓冲区；否则可能出现“第一单吃光资金，后续加仓没钱”的情况。

---

## 7) 哪些参数可以写在策略里？（配置文件会覆盖策略）

以下参数既可以写在配置文件，也可以写在策略里；但 **配置文件的值永远覆盖策略里的值**：

- `minimal_roi`
- `timeframe`
- `stoploss`
- `max_open_trades`
- `trailing_stop` / `trailing_stop_positive` / `trailing_stop_positive_offset` / `trailing_only_offset_is_reached`
- `use_custom_stoploss`
- `process_only_new_candles`
- `order_types`
- `order_time_in_force`
- `unfilledtimeout`
- `disable_dataframe_checks`
- `use_exit_signal`
- `exit_profit_only` / `exit_profit_offset`
- `ignore_roi_if_entry_signal`
- `ignore_buying_expired_candle_after`
- `position_adjustment_enable` / `max_entry_position_adjustment`

实用建议：你如果想“一个策略搭多个配置跑不同市场”，把这些参数放在 `config.json` 往往更方便。

---

## 8) 下单价格：`entry_pricing` / `exit_pricing`

Freqtrade 允许你控制下单时使用什么价格（盘口/最新成交价/插值等）。

- 开仓：`entry_pricing`
- 平仓：`exit_pricing`
- 下单前会实时拉取价格：要么用 ticker（`fetch_ticker(s)`），要么用 orderbook（`fetch_order_book()`）

### 8.1 `price_side`：建议优先用 `same` / `other`

`price_side` 决定从盘口的哪一侧取价；官方更推荐用：

- `same`：不跨价差（更像挂在“对自己有利”的一侧）
- `other`：跨价差（更像用更激进的价格去成交）

直接用 `ask` / `bid` 会在做多/做空时出现“直觉相反”的情况，因此官方不太推荐。

### 8.2 `use_order_book`：用盘口 top N 定价

- `use_order_book: true` 时，会拉取盘口前 N 档，然后取 `order_book_top` 指定的那一档作为价格
- `order_book_top: 1` 表示取第一档，`2` 表示第二档，以此类推

### 8.3 不用盘口时：`price_last_balance` 的插值逻辑

当 `use_order_book: false`：

- 如果盘口侧价格相对 `last` 更“有利”，就直接用盘口侧价格
- 否则会在盘口侧价格与 `last` 之间做插值，插值比例由 `price_last_balance` 决定：
  - `0.0`：更偏向盘口侧价格
  - `1.0`：直接用 `last`
  - 中间值：二者之间插值

### 8.4 深度过滤：`check_depth_of_market`

启用 `entry_pricing.check_depth_of_market.enabled: true` 后，会用盘口深度过滤入场信号：

- 计算：`bid_depth / ask_depth`
- 只有当该值 `>= bids_to_ask_delta` 才允许入场
- 小于 1 表示卖盘更厚；大于 1 表示买盘更厚

---

## 9) 市价单定价（Market order pricing）

当你把 `order_types.entry/exit` 都设为 `market` 时，官方建议把定价侧设为 `other`，以获得更现实的定价检测（示例）：

```json
"order_types": {
  "entry": "market",
  "exit": "market"
},
"entry_pricing": {
  "price_side": "other"
},
"exit_pricing": {
  "price_side": "other"
}
```

---

## 10) ROI、强制进场、过期信号

### 10.1 `minimal_roi`：分钟 → ROI 阈值

`minimal_roi` 是一个字典（JSON object）：

- key：持仓分钟数（字符串形式的数字）
- value：ROI 阈值（比例，例如 `0.01` 表示 1%）

含义示例：持仓达到 30 分钟后，只要利润 ≥ 1% 就允许按 ROI 规则退出。

另外有一个特殊用法：`"<N>": -1`，表示持仓 N 分钟后 **无论盈亏都强制退出**（时间限定的 force-exit）。

### 10.2 `force_entry_enable`：允许 Telegram/API 的强制开仓指令（谨慎）

开启后可通过 Telegram 或 REST API 使用强制进场命令（例如 `/forcelong`、`/forceshort` / `/forceenter`）。

出于安全原因默认关闭；开启后启动会有警告提示。该功能对某些策略可能很危险，请谨慎使用。

### 10.3 `ignore_buying_expired_candle_after`：忽略“过期入场信号”

大周期（例如 `1h`）+ 低 `max_open_trades` 时，可能出现“有空位了才处理到上一根 K 的信号”，导致信号已过时。

你可以设置 `ignore_buying_expired_candle_after`（秒），超过该时间的信号会被视为过期而忽略：

```json
"ignore_buying_expired_candle_after": 300
```

注意：这个设置会在每根新 K 线到来时重置；它不会阻止“连续多根 K 线都满足条件”的黏性信号，最好搭配只触发一根 K 的“trigger”类条件使用。

---

## 11) 订单类型：`order_types`（限价/市价/止损）

`order_types` 用一个字典把动作映射到订单类型，并配置是否把止损单挂到交易所：

- 动作：`entry`、`exit`、`stoploss`、`emergency_exit`、`force_exit`、`force_entry` 等
- 类型：`market`、`limit`（以及交易所支持的其它类型）

重要规则：

- 如果你在配置文件里设置了 `order_types`，它会整体覆盖策略里的 `order_types`（不是“局部合并”），因此要在一个地方把整个字典配完整。
- 至少需要包含：`entry`、`exit`、`stoploss`、`stoploss_on_exchange`，否则 bot 无法启动。

官方示例（配置文件）：

```json
"order_types": {
  "entry": "limit",
  "exit": "limit",
  "emergency_exit": "market",
  "force_entry": "market",
  "force_exit": "market",
  "stoploss": "market",
  "stoploss_on_exchange": false,
  "stoploss_on_exchange_interval": 60,
  "stoploss_on_exchange_limit_ratio": 0.99
}
```

警告：如果 `stoploss_on_exchange` 创建失败，会触发“紧急退出（emergency exit）”，默认用市价单退出；虽然可以通过 `order_types.emergency_exit` 修改，但官方不建议这么做。

---

## 12) 订单有效期：`order_time_in_force`（GTC/FOK/IOC/PO）

`order_time_in_force` 决定订单在交易所上以什么策略执行。

常见值：

- `GTC`（Good Till Canceled）：默认；一直挂着直到成交或被取消，可部分成交
- `FOK`（Fill Or Kill）：必须立刻全部成交，否则交易所取消
- `IOC`（Immediate Or Canceled）：立刻成交能成交的部分，剩余自动取消（可能导致部分成交后低于最小下单额，不一定推荐）
- `PO`（Post Only）：只作为 maker 挂单；如果会立刻吃单则取消

配置示例：

```json
"order_time_in_force": {
  "entry": "GTC",
  "exit": "GTC"
}
```

除非你非常确定影响，否则不建议随意改默认值；不同交易所支持的值也不同，需查交易所文档。

---

## 13) 法币换算：`fiat_display_currency` / Coingecko

Telegram 报告里的“币价换算成法币”使用 Coingecko。

- `fiat_display_currency`：设置法币（例如 `USD`、`CNY` 等）
- 如果你把 `fiat_display_currency` 从配置里 **彻底删除**，Freqtrade 会跳过初始化 coingecko，也就不会显示法币换算（不影响 bot 正常交易）

Coingecko API key 不是必需的，只用于法币换算；并支持 Demo/Pro key。示例：

```json
"fiat_display_currency": "USD",
"coingecko": {
  "api_key": "your-api",
  "is_demo": true
}
```

---

## 14) 交易所 WebSocket：`exchange.enable_ws`

Freqtrade 可通过 `ccxt.pro` 消费 WebSocket 数据；当 WebSocket 失败或被禁用时会回退到 REST API。

如果你怀疑问题由 WebSocket 引起，可以关闭：

```json
"exchange": {
  "enable_ws": false
}
```

---

## 15) Dry-run 模式（强烈建议先跑）

dry-run 模式会做“实时模拟交易”，不会在交易所真正下单，是验证策略与配置的第一步。

官方建议步骤：

1. 设置 `"dry_run": true`
2. 配好 `db_url` 用于持久化数据库（示例用 sqlite）

```json
"dry_run": true,
"db_url": "sqlite:///tradesv3.dryrun.sqlite"
```

dry-run 下：

- API key 可以不配或配只读（只会做不改变账户状态的读操作）
- 钱包由 `dry_run_wallet` 模拟
- 订单不会真正发到交易所
- 市价单成交按下单瞬间盘口量模拟，并限制最大滑点 5%
- 限价单在触价时成交，或按 `unfilledtimeout` 超时
- 限价单如果价格跨越超过 1%，会转为市价单并按市价规则立即成交
- 与 `stoploss_on_exchange` 联动时，会假设止损价能成交
- bot 重启后“未完成订单”会保留（假设离线期间没有成交）

---

## 16) 切换实盘（Production mode）前的 checklist

实盘模式会动用真实资金；策略或配置错误可能导致重大亏损。

官方要点：

- 切到实盘时请使用一份全新的数据库，避免 dry-run 的模拟交易污染你的统计
- 把 `"dry_run": false`
- 配好交易所 API key/secret（必要时还有 password）
- 强烈建议用“第二份私密配置文件”保存密钥，并且 **永远不要分享** 私密配置或密钥

---

## 17) 代理（Proxy）

为 telegram/coingecko 等设置代理（不包含交易所请求）：

```bash
export HTTP_PROXY="http://addr:port"
export HTTPS_PROXY="http://addr:port"
freqtrade
```

为交易所连接设置代理：在 `exchange.ccxt_config` 里配（示例）：

```json
{
  "exchange": {
    "ccxt_config": {
      "httpsProxy": "http://addr:port",
      "wsProxy": "http://addr:port"
    }
  }
}
```

更多代理类型请参考 ccxt 文档：https://docs.ccxt.com/#/README?id=proxy

---

## 18) 下一步

配置完成后，就可以开始启动 bot 了：

- 官方： https://www.freqtrade.io/en/latest/bot-usage/
- 本仓库常用命令形式：`uv run freqtrade trade --userdir "." --config "config.json"`

---

## 附录：官方原文（自动 Markdown 化）

- 来源：https://www.freqtrade.io/en/stable/configuration/
- 离线保存时间：Mon Jan 05 2026 11:08:09 GMT+0800 (中国标准时间)

Freqtrade has many configurable features and possibilities.
By default, these settings are configured via the configuration file (see below).

### The Freqtrade configuration file

The bot uses a set of configuration parameters during its operation that all together conform to the bot configuration. It normally reads its configuration from a file (Freqtrade configuration file).

Per default, the bot loads the configuration from the `config.json` file, located in the current working directory.

You can specify a different configuration file used by the bot with the `-c/--config` command-line option.

If you used the [Quick start](https://www.freqtrade.io/en/latest/docker_quickstart/#docker-quick-start) method for installing
the bot, the installation script should have already created the default configuration file (`config.json`) for you.

If the default configuration file is not created we recommend to use `freqtrade new-config --config user_data/config.json` to generate a basic configuration file.

The Freqtrade configuration file is to be written in JSON format.

Additionally to the standard JSON syntax, you may use one-line `// ...` and multi-line `/* ... */` comments in your configuration files and trailing commas in the lists of parameters.

Do not worry if you are not familiar with JSON format -- simply open the configuration file with an editor of your choice, make some changes to the parameters you need, save your changes and, finally, restart the bot or, if it was previously stopped, run it again with the changes you made to the configuration. The bot validates the syntax of the configuration file at startup and will warn you if you made any errors editing it, pointing out problematic lines.

#### Environment variables

Set options in the Freqtrade configuration via environment variables.
This takes priority over the corresponding value in configuration or strategy.

Environment variables must be prefixed with `FREQTRADE__` to be loaded to the freqtrade configuration.

`__` serves as level separator, so the format used should correspond to `FREQTRADE__{section}__{key}`.
As such - an environment variable defined as `export FREQTRADE__STAKE_AMOUNT=200` would result in `{stake_amount: 200}`.

A more complex example might be `export FREQTRADE__EXCHANGE__KEY=` to keep your exchange key secret. This will move the value to the `exchange.key` section of the configuration.
Using this scheme, all configuration settings will also be available as environment variables.

Please note that Environment variables will overwrite corresponding settings in your configuration, but command line Arguments will always win.

Common example:

```text
FREQTRADE__TELEGRAM__CHAT_ID=<telegramchatid>
FREQTRADE__TELEGRAM__TOKEN=<telegramToken>
FREQTRADE__EXCHANGE__KEY=<yourExchangeKey>
FREQTRADE__EXCHANGE__SECRET=<yourExchangeSecret>
```

Json lists are parsed as json - so you can use the following to set a list of pairs:

```text
export FREQTRADE__EXCHANGE__PAIR_WHITELIST='["BTC/USDT", "ETH/USDT"]'
```

Note

Environment variables detected are logged at startup - so if you can't find why a value is not what you think it should be based on the configuration, make sure it's not loaded from an environment variable.

Validate combined result

You can use the [show-config subcommand](https://www.freqtrade.io/en/latest/utils/#show-config) to see the final, combined configuration.

Loading sequence
Environment variables are loaded after the initial configuration. As such, you cannot provide the path to the configuration through environment variables. Please use `--config path/to/config.json` for that.
This also applies to `user_dir` to some degree. while the user directory can be set through environment variables - the configuration will **not** be loaded from that location.

#### Multiple configuration files

Multiple configuration files can be specified and used by the bot or the bot can read its configuration parameters from the process standard input stream.

You can specify additional configuration files in `add_config_files`. Files specified in this parameter will be loaded and merged with the initial config file. The files are resolved relative to the initial configuration file.
This is similar to using multiple `--config` parameters, but simpler in usage as you don't have to specify all files for all commands.

Validate combined result

You can use the [show-config subcommand](https://www.freqtrade.io/en/latest/utils/#show-config) to see the final, combined configuration.

Use multiple configuration files to keep secrets secret

You can use a 2nd configuration file containing your secrets. That way you can share your "primary" configuration file, while still keeping your API keys for yourself.
The 2nd file should only specify what you intend to override.
If a key is in more than one of the configurations, then the "last specified configuration" wins (in the above example, `config-private.json`).

For one-off commands, you can also use the below syntax by specifying multiple "--config" parameters.

```bash
freqtrade trade --config user_data/config1.json --config user_data/config-private.json <...>
```

The below is equivalent to the example above - but having 2 configuration files in the configuration, for easier reuse.

文件：`user_data/config.json`

```text
"add_config_files": [
    "config1.json",
    "config-private.json"
]
```

```bash
freqtrade trade --config user_data/config.json <...>
```

config collision handling
If the same configuration setting takes place in both `config.json` and `config-import.json`, then the parent configuration wins.
In the below case, `max_open_trades` would be 3 after the merging - as the reusable "import" configuration has this key overwritten.

文件：`user_data/config.json`

```json
{
    "max_open_trades": 3,
    "stake_currency": "USDT",
    "add_config_files": [
        "config-import.json"
    ]
}
```

文件：`user_data/config-import.json`

```json
{
    "max_open_trades": 10,
    "stake_amount": "unlimited",
}
```

Resulting combined configuration:

文件：`Result`

```json
{
    "max_open_trades": 3,
    "stake_currency": "USDT",
    "stake_amount": "unlimited"
}
```

If multiple files are in the `add_config_files` section, then they will be assumed to be at identical levels, having the last occurrence override the earlier config (unless a parent already defined such a key).

### Editor autocomplete and validation

If you are using an editor that supports JSON schema, you can use the schema provided by Freqtrade to get autocompletion and validation of your configuration file by adding the following line to the top of your configuration file:

```json
{
    "$schema": "https://schema.freqtrade.io/schema.json",
}
```

Develop version
The develop schema is available as `https://schema.freqtrade.io/schema_dev.json` - though we recommend to stick to the stable version for the best experience.

### Configuration parameters

The table below will list all configuration parameters available.

Freqtrade can also load many options via command line (CLI) arguments (check out the commands `--help` output for details).

#### Configuration option prevalence

The prevalence for all Options is as follows:

- CLI arguments override any other option

- [Environment Variables](#environment-variables)

- Configuration files are used in sequence (the last file wins) and override Strategy configurations.

- Strategy configurations are only used if they are not set via configuration or command-line arguments. These options are marked with [Strategy Override](#parameters-in-the-strategy) in the below table.

#### Parameters table

Mandatory parameters are marked as **Required**, which means that they are required to be set in one of the possible ways.

| Parameter | Description |
| --- | --- |
| max_open_trades | Required. Number of open trades your bot is allowed to have. Only one open trade per pair is possible, so the length of your pairlist is another limitation that can apply. If -1 then it is ignored (i.e. potentially unlimited open trades, limited by the pairlist). More information below. Strategy Override. Datatype: Positive integer or -1. |
| stake_currency | Required. Crypto-currency used for trading. Datatype: String |
| stake_amount | Required. Amount of crypto-currency your bot will use for each trade. Set it to "unlimited" to allow the bot to use all available balance. More information below. Datatype: Positive float or "unlimited". |
| tradable_balance_ratio | Ratio of the total account balance the bot is allowed to trade. More information below. Defaults to 0.99 99%). Datatype: Positive float between 0.1 and 1.0. |
| available_capital | Available starting capital for the bot. Useful when running multiple bots on the same exchange account. More information below. Datatype: Positive float. |
| amend_last_stake_amount | Use reduced last stake amount if necessary. More information below. Defaults to false. Datatype: Boolean |
| last_stake_amount_min_ratio | Defines minimum stake amount that has to be left and executed. Applies only to the last stake amount when it's amended to a reduced value (i.e. if amend_last_stake_amount is set to true). More information below. Defaults to 0.5. Datatype: Float (as ratio) |
| amount_reserve_percent | Reserve some amount in min pair stake amount. The bot will reserve amount_reserve_percent + stoploss value when calculating min pair stake amount in order to avoid possible trade refusals. Defaults to 0.05 (5%). Datatype: Positive Float as ratio. |
| timeframe | The timeframe to use (e.g 1m, 5m, 15m, 30m, 1h ...). Usually missing in configuration, and specified in the strategy. Strategy Override. Datatype: String |
| fiat_display_currency | Fiat currency used to show your profits. More information below. Datatype: String |
| dry_run | Required. Define if the bot must be in Dry Run or production mode. Defaults to true. Datatype: Boolean |
| dry_run_wallet | Define the starting amount in stake currency for the simulated wallet used by the bot running in Dry Run mode. More information belowDefaults to 1000. Datatype: Float or Dict |
| cancel_open_orders_on_exit | Cancel open orders when the /stop RPC command is issued, Ctrl+C is pressed or the bot dies unexpectedly. When set to true, this allows you to use /stop to cancel unfilled and partially filled orders in the event of a market crash. It does not impact open positions. Defaults to false. Datatype: Boolean |
| process_only_new_candles | Enable processing of indicators only when new candles arrive. If false each loop populates the indicators, this will mean the same candle is processed many times creating system load but can be useful of your strategy depends on tick data not only candle. Strategy Override. Defaults to true. Datatype: Boolean |
| minimal_roi | Required. Set the threshold as ratio the bot will use to exit a trade. More information below. Strategy Override. Datatype: Dict |
| stoploss | Required. Value as ratio of the stoploss used by the bot. More details in the stoploss documentation. Strategy Override. Datatype: Float (as ratio) |
| trailing_stop | Enables trailing stoploss (based on stoploss in either configuration or strategy file). More details in the stoploss documentation. Strategy Override. Datatype: Boolean |
| trailing_stop_positive | Changes stoploss once profit has been reached. More details in the stoploss documentation. Strategy Override. Datatype: Float |
| trailing_stop_positive_offset | Offset on when to apply trailing_stop_positive. Percentage value which should be positive. More details in the stoploss documentation. Strategy Override. Defaults to 0.0 (no offset). Datatype: Float |
| trailing_only_offset_is_reached | Only apply trailing stoploss when the offset is reached. stoploss documentation. Strategy Override. Defaults to false. Datatype: Boolean |
| fee | Fee used during backtesting / dry-runs. Should normally not be configured, which has freqtrade fall back to the exchange default fee. Set as ratio (e.g. 0.001 = 0.1%). Fee is applied twice for each trade, once when buying, once when selling. Datatype: Float (as ratio) |
| futures_funding_rate | User-specified funding rate to be used when historical funding rates are not available from the exchange. This does not overwrite real historical rates. It is recommended that this be set to 0 unless you are testing a specific coin and you understand how the funding rate will affect freqtrade's profit calculations. More information here Defaults to None. Datatype: Float |
| trading_mode | Specifies if you want to trade regularly, trade with leverage, or trade contracts whose prices are derived from matching cryptocurrency prices. leverage documentation. Defaults to "spot". Datatype: String |
| margin_mode | When trading with leverage, this determines if the collateral owned by the trader will be shared or isolated to each trading pair leverage documentation. Datatype: String |
| liquidation_buffer | A ratio specifying how large of a safety net to place between the liquidation price and the stoploss to prevent a position from reaching the liquidation price leverage documentation. Defaults to 0.05. Datatype: Float |
|  | Unfilled timeout |
| unfilledtimeout.entry | Required. How long (in minutes or seconds) the bot will wait for an unfilled entry order to complete, after which the order will be cancelled. Strategy Override. Datatype: Integer |
| unfilledtimeout.exit | Required. How long (in minutes or seconds) the bot will wait for an unfilled exit order to complete, after which the order will be cancelled and repeated at current (new) price, as long as there is a signal. Strategy Override. Datatype: Integer |
| unfilledtimeout.unit | Unit to use in unfilledtimeout setting. Note: If you set unfilledtimeout.unit to "seconds", "internals.process_throttle_secs" must be inferior or equal to timeout Strategy Override. Defaults to "minutes". Datatype: String |
| unfilledtimeout.exit_timeout_count | How many times can exit orders time out. Once this number of timeouts is reached, an emergency exit is triggered. 0 to disable and allow unlimited order cancels. Strategy Override.Defaults to 0. Datatype: Integer |
|  | Pricing |
| entry_pricing.price_side | Select the side of the spread the bot should look at to get the entry rate. More information below. Defaults to "same". Datatype: String (either ask, bid, same or other). |
| entry_pricing.price_last_balance | Required. Interpolate the bidding price. More information below. |
| entry_pricing.use_order_book | Enable entering using the rates in Order Book Entry. Defaults to true. Datatype: Boolean |
| entry_pricing.order_book_top | Bot will use the top N rate in Order Book "price_side" to enter a trade. I.e. a value of 2 will allow the bot to pick the 2nd entry in Order Book Entry. Defaults to 1. Datatype: Positive Integer |
| entry_pricing. check_depth_of_market.enabled | Do not enter if the difference of buy orders and sell orders is met in Order Book. Check market depth. Defaults to false. Datatype: Boolean |
| entry_pricing. check_depth_of_market.bids_to_ask_delta | The difference ratio of buy orders and sell orders found in Order Book. A value below 1 means sell order size is greater, while value greater than 1 means buy order size is higher. Check market depth Defaults to 0. Datatype: Float (as ratio) |
| exit_pricing.price_side | Select the side of the spread the bot should look at to get the exit rate. More information below. Defaults to "same". Datatype: String (either ask, bid, same or other). |
| exit_pricing.price_last_balance | Interpolate the exiting price. More information below. |
| exit_pricing.use_order_book | Enable exiting of open trades using Order Book Exit. Defaults to true. Datatype: Boolean |
| exit_pricing.order_book_top | Bot will use the top N rate in Order Book "price_side" to exit. I.e. a value of 2 will allow the bot to pick the 2nd ask rate in Order Book ExitDefaults to 1. Datatype: Positive Integer |
| custom_price_max_distance_ratio | Configure maximum distance ratio between current and custom entry or exit price. Defaults to 0.02 2%). Datatype: Positive float |
|  | Order/Signal handling |
| use_exit_signal | Use exit signals produced by the strategy in addition to the minimal_roi. Setting this to false disables the usage of "exit_long" and "exit_short" columns. Has no influence on other exit methods (Stoploss, ROI, callbacks). Strategy Override. Defaults to true. Datatype: Boolean |
| exit_profit_only | Wait until the bot reaches exit_profit_offset before taking an exit decision. Strategy Override. Defaults to false. Datatype: Boolean |
| exit_profit_offset | Exit-signal is only active above this value. Only active in combination with exit_profit_only=True. Strategy Override. Defaults to 0.0. Datatype: Float (as ratio) |
| ignore_roi_if_entry_signal | Do not exit if the entry signal is still active. This setting takes preference over minimal_roi and use_exit_signal. Strategy Override. Defaults to false. Datatype: Boolean |
| ignore_buying_expired_candle_after | Specifies the number of seconds until a buy signal is no longer used. Datatype: Integer |
| order_types | Configure order-types depending on the action ("entry", "exit", "stoploss", "stoploss_on_exchange"). More information below. Strategy Override. Datatype: Dict |
| order_time_in_force | Configure time in force for entry and exit orders. More information below. Strategy Override. Datatype: Dict |
| position_adjustment_enable | Enables the strategy to use position adjustments (additional buys or sells). More information here. Strategy Override. Defaults to false. Datatype: Boolean |
| max_entry_position_adjustment | Maximum additional order(s) for each open trade on top of the first entry Order. Set it to -1 for unlimited additional orders. More information here. Strategy Override. Defaults to -1. Datatype: Positive Integer or -1 |
|  | Exchange |
| exchange.name | Required. Name of the exchange class to use. Datatype: String |
| exchange.key | API key to use for the exchange. Only required when you are in production mode.Keep it in secret, do not disclose publicly. Datatype: String |
| exchange.secret | API secret to use for the exchange. Only required when you are in production mode.Keep it in secret, do not disclose publicly. Datatype: String |
| exchange.password | API password to use for the exchange. Only required when you are in production mode and for exchanges that use password for API requests.Keep it in secret, do not disclose publicly. Datatype: String |
| exchange.uid | API uid to use for the exchange. Only required when you are in production mode and for exchanges that use uid for API requests.Keep it in secret, do not disclose publicly. Datatype: String |
| exchange.pair_whitelist | List of pairs to use by the bot for trading and to check for potential trades during backtesting. Supports regex pairs as .*/BTC. Not used by VolumePairList. More information. Datatype: List |
| exchange.pair_blacklist | List of pairs the bot must absolutely avoid for trading and backtesting. More information. Datatype: List |
| exchange.ccxt_config | Additional CCXT parameters passed to both ccxt instances (sync and async). This is usually the correct place for additional ccxt configurations. Parameters may differ from exchange to exchange and are documented in the ccxt documentation. Please avoid adding exchange secrets here (use the dedicated fields instead), as they may be contained in logs. Datatype: Dict |
| exchange.ccxt_sync_config | Additional CCXT parameters passed to the regular (sync) ccxt instance. Parameters may differ from exchange to exchange and are documented in the ccxt documentation Datatype: Dict |
| exchange.ccxt_async_config | Additional CCXT parameters passed to the async ccxt instance. Parameters may differ from exchange to exchange and are documented in the ccxt documentation Datatype: Dict |
| exchange.enable_ws | Enable the usage of Websockets for the exchange. More information.Defaults to true. Datatype: Boolean |
| exchange.markets_refresh_interval | The interval in minutes in which markets are reloaded. Defaults to 60 minutes. Datatype: Positive Integer |
| exchange.skip_open_order_update | Skips open order updates on startup should the exchange cause problems. Only relevant in live conditions.Defaults to false Datatype: Boolean |
| exchange.unknown_fee_rate | Fallback value to use when calculating trading fees. This can be useful for exchanges which have fees in non-tradable currencies. The value provided here will be multiplied with the "fee cost".Defaults to None Datatype:* float |
| exchange.log_responses | Log relevant exchange responses. For debug mode only - use with care.Defaults to false Datatype: Boolean |
| exchange.only_from_ccxt | Prevent data-download from data.binance.vision. Leaving this as false can greatly speed up downloads, but may be problematic if the site is not available.Defaults to false Datatype: Boolean |
| experimental.block_bad_exchanges | Block exchanges known to not work with freqtrade. Leave on default unless you want to test if that exchange works now. Defaults to true. Datatype: Boolean |
|  | Plugins |
| pairlists | Define one or more pairlists to be used. More information. Defaults to StaticPairList. Datatype: List of Dicts |
|  | Telegram |
| telegram.enabled | Enable the usage of Telegram. Datatype: Boolean |
| telegram.token | Your Telegram bot token. Only required if telegram.enabled is true. Keep it in secret, do not disclose publicly. Datatype: String |
| telegram.chat_id | Your personal Telegram account id. Only required if telegram.enabled is true. Keep it in secret, do not disclose publicly. Datatype: String |
| telegram.balance_dust_level | Dust-level (in stake currency) - currencies with a balance below this will not be shown by /balance. Datatype: float |
| telegram.reload | Allow "reload" buttons on telegram messages. Defaults to true. Datatype:* boolean |
| telegram.notification_settings.* | Detailed notification settings. Refer to the telegram documentation for details. Datatype: dictionary |
| telegram.allow_custom_messages | Enable the sending of Telegram messages from strategies via the dataprovider.send_msg() function. Datatype: Boolean |
|  | Webhook |
| webhook.enabled | Enable usage of Webhook notifications Datatype: Boolean |
| webhook.url | URL for the webhook. Only required if webhook.enabled is true. See the webhook documentation for more details. Datatype: String |
| webhook.entry | Payload to send on entry. Only required if webhook.enabled is true. See the webhook documentation for more details. Datatype: String |
| webhook.entry_cancel | Payload to send on entry order cancel. Only required if webhook.enabled is true. See the webhook documentation for more details. Datatype: String |
| webhook.entry_fill | Payload to send on entry order filled. Only required if webhook.enabled is true. See the webhook documentation for more details. Datatype: String |
| webhook.exit | Payload to send on exit. Only required if webhook.enabled is true. See the webhook documentation for more details. Datatype: String |
| webhook.exit_cancel | Payload to send on exit order cancel. Only required if webhook.enabled is true. See the webhook documentation for more details. Datatype: String |
| webhook.exit_fill | Payload to send on exit order filled. Only required if webhook.enabled is true. See the webhook documentation for more details. Datatype: String |
| webhook.status | Payload to send on status calls. Only required if webhook.enabled is true. See the webhook documentation for more details. Datatype: String |
| webhook.allow_custom_messages | Enable the sending of Webhook messages from strategies via the dataprovider.send_msg() function. Datatype: Boolean |
|  | Rest API / FreqUI / Producer-Consumer |
| api_server.enabled | Enable usage of API Server. See the API Server documentation for more details. Datatype: Boolean |
| api_server.listen_ip_address | Bind IP address. See the API Server documentation for more details. Datatype: IPv4 |
| api_server.listen_port | Bind Port. See the API Server documentation for more details. Datatype: Integer between 1024 and 65535 |
| api_server.verbosity | Logging verbosity. info will print all RPC Calls, while "error" will only display errors. Datatype: Enum, either info or error. Defaults to info. |
| api_server.username | Username for API server. See the API Server documentation for more details. Keep it in secret, do not disclose publicly. Datatype: String |
| api_server.password | Password for API server. See the API Server documentation for more details. Keep it in secret, do not disclose publicly. Datatype: String |
| api_server.ws_token | API token for the Message WebSocket. See the API Server documentation for more details. Keep it in secret, do not disclose publicly. Datatype: String |
| bot_name | Name of the bot. Passed via API to a client - can be shown to distinguish / name bots. Defaults to freqtrade Datatype: String |
| external_message_consumer | Enable Producer/Consumer mode for more details. Datatype: Dict |
|  | Other |
| initial_state | Defines the initial application state. If set to stopped, then the bot has to be explicitly started via /start RPC command. Defaults to stopped. Datatype: Enum, either running, paused or stopped |
| force_entry_enable | Enables the RPC Commands to force a Trade entry. More information below. Datatype: Boolean |
| disable_dataframe_checks | Disable checking the OHLCV dataframe returned from the strategy methods for correctness. Only use when intentionally changing the dataframe and understand what you are doing. Strategy Override. Defaults to False. Datatype: Boolean |
| internals.process_throttle_secs | Set the process throttle, or minimum loop duration for one bot iteration loop. Value in second. Defaults to 5 seconds. Datatype: Positive Integer |
| internals.heartbeat_interval | Print heartbeat message every N seconds. Set to 0 to disable heartbeat messages. Defaults to 60 seconds. Datatype: Positive Integer or 0 |
| internals.sd_notify | Enables use of the sd_notify protocol to tell systemd service manager about changes in the bot state and issue keep-alive pings. See here for more details. Datatype: Boolean |
| strategy | Required Defines Strategy class to use. Recommended to be set via --strategy NAME. Datatype: ClassName |
| strategy_path | Adds an additional strategy lookup path (must be a directory). Datatype: String |
| recursive_strategy_search | Set to true to recursively search sub-directories inside user_data/strategies for a strategy. Datatype: Boolean |
| user_data_dir | Directory containing user data. Defaults to ./user_data/. Datatype: String |
| db_url | Declares database URL to use. NOTE: This defaults to sqlite:///tradesv3.dryrun.sqlite if dry_run is true, and to sqlite:///tradesv3.sqlite for production instances. Datatype: String, SQLAlchemy connect string |
| logfile | Specifies logfile name. Uses a rolling strategy for log file rotation for 10 files with the 1MB limit per file. Datatype: String |
| add_config_files | Additional config files. These files will be loaded and merged with the current config file. The files are resolved relative to the initial file. Defaults to []. Datatype: List of strings |
| dataformat_ohlcv | Data format to use to store historical candle (OHLCV) data. Defaults to feather. Datatype: String |
| dataformat_trades | Data format to use to store historical trades data. Defaults to feather. Datatype: String |
| reduce_df_footprint | Recast all numeric columns to float32/int32, with the objective of reducing ram/disk usage (and decreasing train/inference timing backtesting/hyperopt and in FreqAI). Datatype: Boolean. Default: False. |
| log_config | Dictionary containing the log config for python logging. more info Datatype: dict. Default: FtRichHandler |

#### Parameters in the strategy

The following parameters can be set in the configuration file or strategy.
Values set in the configuration file always overwrite values set in the strategy.

- `minimal_roi`

- `timeframe`

- `stoploss`

- `max_open_trades`

- `trailing_stop`

- `trailing_stop_positive`

- `trailing_stop_positive_offset`

- `trailing_only_offset_is_reached`

- `use_custom_stoploss`

- `process_only_new_candles`

- `order_types`

- `order_time_in_force`

- `unfilledtimeout`

- `disable_dataframe_checks`

- `use_exit_signal`

- `exit_profit_only`

- `exit_profit_offset`

- `ignore_roi_if_entry_signal`

- `ignore_buying_expired_candle_after`

- `position_adjustment_enable`

- `max_entry_position_adjustment`

#### Configuring amount per trade

There are several methods to configure how much of the stake currency the bot will use to enter a trade. All methods respect the [available balance configuration](#tradable-balance) as explained below.

##### Minimum trade stake

The minimum stake amount will depend on exchange and pair and is usually listed in the exchange support pages.

Assuming the minimum tradable amount for XRP/USD is 20 XRP (given by the exchange), and the price is 0.6$, the minimum stake amount to buy this pair is `20 * 0.6 ~= 12`.
This exchange has also a limit on USD - where all orders must be > 10$ - which however does not apply in this case.

To guarantee safe execution, freqtrade will not allow buying with a stake-amount of 10.1$, instead, it'll make sure that there's enough space to place a stoploss below the pair (+ an offset, defined by `amount_reserve_percent`, which defaults to 5%).

With a reserve of 5%, the minimum stake amount would be ~12.6$ (`12 * (1 + 0.05)`). If we take into account a stoploss of 10% on top of that - we'd end up with a value of ~14$ (`12.6 / (1 - 0.1)`).

To limit this calculation in case of large stoploss values, the calculated minimum stake-limit will never be more than 50% above the real limit.

Warning

Since the limits on exchanges are usually stable and are not updated often, some pairs can show pretty high minimum limits, simply because the price increased a lot since the last limit adjustment by the exchange. Freqtrade adjusts the stake-amount to this value, unless it's > 30% more than the calculated/desired stake-amount - in which case the trade is rejected.

##### Dry-run wallet

When running in dry-run mode, the bot will use a simulated wallet to execute trades. The starting balance of this wallet is defined by `dry_run_wallet` (defaults to 1000).
For more complex scenarios, you can also assign a dictionary to `dry_run_wallet` to define the starting balance for each currency.

```text
"dry_run_wallet": {
    "BTC": 0.01,
    "ETH": 2,
    "USDT": 1000
}
```

Command line options (`--dry-run-wallet`) can be used to override the configuration value, but only for the float value, not for the dictionary. If you'd like to use the dictionary, please adjust the configuration file.

Note

Balances not in stake-currency will not be used for trading, but are shown as part of the wallet balance.
On Cross-margin exchanges, the wallet balance may be used to calculate the available collateral for trading.

##### Tradable balance

By default, the bot assumes that the `complete amount - 1%` is at it's disposal, and when using [dynamic stake amount](#dynamic-stake-amount), it will split the complete balance into `max_open_trades` buckets per trade.
Freqtrade will reserve 1% for eventual fees when entering a trade and will therefore not touch that by default.

You can configure the "untouched" amount by using the `tradable_balance_ratio` setting.

For example, if you have 10 ETH available in your wallet on the exchange and `tradable_balance_ratio=0.5` (which is 50%), then the bot will use a maximum amount of 5 ETH for trading and considers this as an available balance. The rest of the wallet is untouched by the trades.

Danger

This setting should **not** be used when running multiple bots on the same account. Please look at [Available Capital to the bot](#assign-available-capital) instead.

Warning

The `tradable_balance_ratio` setting applies to the current balance (free balance + tied up in trades). Therefore, assuming the starting balance of 1000, a configuration with `tradable_balance_ratio=0.99` will not guarantee that 10 currency units will always remain available on the exchange. For example, the free amount may reduce to 5 units if the total balance is reduced to 500 (either by a losing streak or by withdrawing balance).

##### Assign available Capital

To fully utilize compounding profits when using multiple bots on the same exchange account, you'll want to limit each bot to a certain starting balance.
This can be accomplished by setting `available_capital` to the desired starting balance.

Assuming your account has 10000 USDT and you want to run 2 different strategies on this exchange.
You'd set `available_capital=5000` - granting each bot an initial capital of 5000 USDT.
The bot will then split this starting balance equally into `max_open_trades` buckets.
Profitable trades will result in increased stake-sizes for this bot - without affecting the stake-sizes of the other bot.

Adjusting `available_capital` requires reloading the configuration to take effect. Adjusting the `available_capital` adds the difference between the previous `available_capital` and the new `available_capital`. Decreasing the available capital when trades are open doesn't exit the trades. The difference is returned to the wallet when the trades conclude. The outcome of this differs depending on the price movement between the adjustment and exiting the trades.

Incompatible with `tradable_balance_ratio`

Setting this option will replace any configuration of `tradable_balance_ratio`.

##### Amend last stake amount

Assuming we have the tradable balance of 1000 USDT, `stake_amount=400`, and `max_open_trades=3`.
The bot would open 2 trades and will be unable to fill the last trading slot, since the requested 400 USDT are no longer available since 800 USDT are already tied in other trades.

To overcome this, the option `amend_last_stake_amount` can be set to `True`, which will enable the bot to reduce stake_amount to the available balance to fill the last trade slot.

In the example above this would mean:

- Trade1: 400 USDT

- Trade2: 400 USDT

- Trade3: 200 USDT

Note

This option only applies with [Static stake amount](#static-stake-amount) - since [Dynamic stake amount](#dynamic-stake-amount) divides the balances evenly.

Note

The minimum last stake amount can be configured using `last_stake_amount_min_ratio` - which defaults to 0.5 (50%). This means that the minimum stake amount that's ever used is `stake_amount * 0.5`. This avoids very low stake amounts, that are close to the minimum tradable amount for the pair and can be refused by the exchange.

##### Static stake amount

The `stake_amount` configuration statically configures the amount of stake-currency your bot will use for each trade.

The minimal configuration value is 0.0001, however, please check your exchange's trading minimums for the stake currency you're using to avoid problems.

This setting works in combination with `max_open_trades`. The maximum capital engaged in trades is `stake_amount * max_open_trades`.
For example, the bot will at most use (0.05 BTC x 3) = 0.15 BTC, assuming a configuration of `max_open_trades=3` and `stake_amount=0.05`.

Note

This setting respects the [available balance configuration](#tradable-balance).

##### Dynamic stake amount

Alternatively, you can use a dynamic stake amount, which will use the available balance on the exchange, and divide that equally by the number of allowed trades (`max_open_trades`).

To configure this, set `stake_amount="unlimited"`. We also recommend to set `tradable_balance_ratio=0.99` (99%) - to keep a minimum balance for eventual fees.

In this case a trade amount is calculated as:

```text
currency_balance / (max_open_trades - current_open_trades)
```

To allow the bot to trade all the available `stake_currency` in your account (minus `tradable_balance_ratio`) set

```text
"stake_amount" : "unlimited",
"tradable_balance_ratio": 0.99,
```

Compounding profits

This configuration will allow increasing/decreasing stakes depending on the performance of the bot (lower stake if the bot is losing, higher stakes if the bot has a winning record since higher balances are available), and will result in profit compounding.

When using Dry-Run Mode

When using `"stake_amount" : "unlimited",` in combination with Dry-Run, Backtesting or Hyperopt, the balance will be simulated starting with a stake of `dry_run_wallet` which will evolve.
It is therefore important to set `dry_run_wallet` to a sensible value (like 0.05 or 0.01 for BTC and 1000 or 100 for USDT, for example), otherwise, it may simulate trades with 100 BTC (or more) or 0.05 USDT (or less) at once - which may not correspond to your real available balance or is less than the exchange minimal limit for the order amount for the stake currency.

##### Dynamic stake amount with position adjustment

When you want to use position adjustment with unlimited stakes, you must also implement `custom_stake_amount` to a return a value depending on your strategy.
Typical value would be in the range of 25% - 50% of the proposed stakes, but depends highly on your strategy and how much you wish to leave into the wallet as position adjustment buffer.

For example if your position adjustment assumes it can do 2 additional buys with the same stake amounts then your buffer should be 66.6667% of the initially proposed unlimited stake amount.

Or another example if your position adjustment assumes it can do 1 additional buy with 3x the original stake amount then `custom_stake_amount` should return 25% of proposed stake amount and leave 75% for possible later position adjustments.

### Prices used for orders

Prices for regular orders can be controlled via the parameter structures `entry_pricing` for trade entries and `exit_pricing` for trade exits.
Prices are always retrieved right before an order is placed, either by querying the exchange tickers or by using the orderbook data.

Note

Orderbook data used by Freqtrade are the data retrieved from exchange by the ccxt's function `fetch_order_book()`, i.e. are usually data from the L2-aggregated orderbook, while the ticker data are the structures returned by the ccxt's `fetch_ticker()`/`fetch_tickers()` functions. Refer to the ccxt library [documentation](https://github.com/ccxt/ccxt/wiki/Manual#market-data) for more details.

Using market orders

Please read the section [Market order pricing](#market-order-pricing) section when using market orders.

#### Entry price

##### Enter price side

The configuration setting `entry_pricing.price_side` defines the side of the orderbook the bot looks for when buying.

The following displays an orderbook.

```text
...
103
102
101  # ask
-------------Current spread
99   # bid
98
97
...
```

If `entry_pricing.price_side` is set to `"bid"`, then the bot will use 99 as entry price.

In line with that, if `entry_pricing.price_side` is set to `"ask"`, then the bot will use 101 as entry price.

Depending on the order direction (*long*/*short*), this will lead to different results. Therefore we recommend to use `"same"` or `"other"` for this configuration instead.
This would result in the following pricing matrix:

| direction | Order | setting | price | crosses spread |
| --- | --- | --- | --- | --- |
| long | buy | ask | 101 | yes |
| long | buy | bid | 99 | no |
| long | buy | same | 99 | no |
| long | buy | other | 101 | yes |
| short | sell | ask | 101 | no |
| short | sell | bid | 99 | yes |
| short | sell | same | 101 | no |
| short | sell | other | 99 | yes |

Using the other side of the orderbook often guarantees quicker filled orders, but the bot can also end up paying more than what would have been necessary.
Taker fees instead of maker fees will most likely apply even when using limit buy orders.
Also, prices at the "other" side of the spread are higher than prices at the "bid" side in the orderbook, so the order behaves similar to a market order (however with a maximum price).

##### Entry price with Orderbook enabled

When entering a trade with the orderbook enabled (`entry_pricing.use_order_book=True`), Freqtrade fetches the `entry_pricing.order_book_top` entries from the orderbook and uses the entry specified as `entry_pricing.order_book_top` on the configured side (`entry_pricing.price_side`) of the orderbook. 1 specifies the topmost entry in the orderbook, while 2 would use the 2nd entry in the orderbook, and so on.

##### Entry price without Orderbook enabled

The following section uses `side` as the configured `entry_pricing.price_side` (defaults to `"same"`).

When not using orderbook (`entry_pricing.use_order_book=False`), Freqtrade uses the best `side` price from the ticker if it's below the `last` traded price from the ticker. Otherwise (when the `side` price is above the `last` price), it calculates a rate between `side` and `last` price based on `entry_pricing.price_last_balance`.

The `entry_pricing.price_last_balance` configuration parameter controls this. A value of `0.0` will use `side` price, while `1.0` will use the `last` price and values between those interpolate between ask and last price.

##### Check depth of market

When check depth of market is enabled (`entry_pricing.check_depth_of_market.enabled=True`), the entry signals are filtered based on the orderbook depth (sum of all amounts) for each orderbook side.

Orderbook `bid` (buy) side depth is then divided by the orderbook `ask` (sell) side depth and the resulting delta is compared to the value of the `entry_pricing.check_depth_of_market.bids_to_ask_delta` parameter. The entry order is only executed if the orderbook delta is greater than or equal to the configured delta value.

Note

A delta value below 1 means that `ask` (sell) orderbook side depth is greater than the depth of the `bid` (buy) orderbook side, while a value greater than 1 means opposite (depth of the buy side is higher than the depth of the sell side).

#### Exit price

##### Exit price side

The configuration setting `exit_pricing.price_side` defines the side of the spread the bot looks for when exiting a trade.

The following displays an orderbook:

```text
...
103
102
101  # ask
-------------Current spread
99   # bid
98
97
...
```

If `exit_pricing.price_side` is set to `"ask"`, then the bot will use 101 as exiting price.

In line with that, if `exit_pricing.price_side` is set to `"bid"`, then the bot will use 99 as exiting price.

Depending on the order direction (*long*/*short*), this will lead to different results. Therefore we recommend to use `"same"` or `"other"` for this configuration instead.
This would result in the following pricing matrix:

| Direction | Order | setting | price | crosses spread |
| --- | --- | --- | --- | --- |
| long | sell | ask | 101 | no |
| long | sell | bid | 99 | yes |
| long | sell | same | 101 | no |
| long | sell | other | 99 | yes |
| short | buy | ask | 101 | yes |
| short | buy | bid | 99 | no |
| short | buy | same | 99 | no |
| short | buy | other | 101 | yes |

##### Exit price with Orderbook enabled

When exiting with the orderbook enabled (`exit_pricing.use_order_book=True`), Freqtrade fetches the `exit_pricing.order_book_top` entries in the orderbook and uses the entry specified as `exit_pricing.order_book_top` from the configured side (`exit_pricing.price_side`) as trade exit price.

1 specifies the topmost entry in the orderbook, while 2 would use the 2nd entry in the orderbook, and so on.

##### Exit price without Orderbook enabled

The following section uses `side` as the configured `exit_pricing.price_side` (defaults to `"ask"`).

When not using orderbook (`exit_pricing.use_order_book=False`), Freqtrade uses the best `side` price from the ticker if it's above the `last` traded price from the ticker. Otherwise (when the `side` price is below the `last` price), it calculates a rate between `side` and `last` price based on `exit_pricing.price_last_balance`.

The `exit_pricing.price_last_balance` configuration parameter controls this. A value of `0.0` will use `side` price, while `1.0` will use the last price and values between those interpolate between `side` and last price.

#### Market order pricing

When using market orders, prices should be configured to use the "correct" side of the orderbook to allow realistic pricing detection.
Assuming both entry and exits are using market orders, a configuration similar to the following must be used

```text
  "order_types": {
    "entry": "market",
    "exit": "market"
    // ...
  },
  "entry_pricing": {
    "price_side": "other",
    // ...
  },
  "exit_pricing":{
    "price_side": "other",
    // ...
  },
```

Obviously, if only one side is using limit orders, different pricing combinations can be used.

### Further Configuration details

#### Understand minimal_roi

The `minimal_roi` configuration parameter is a JSON object where the key is a duration
in minutes and the value is the minimum ROI as a ratio.
See the example below:

```text
"minimal_roi": {
    "40": 0.0,    # Exit after 40 minutes if the profit is not negative
    "30": 0.01,   # Exit after 30 minutes if there is at least 1% profit
    "20": 0.02,   # Exit after 20 minutes if there is at least 2% profit
    "0":  0.04    # Exit immediately if there is at least 4% profit
},
```

Most of the strategy files already include the optimal `minimal_roi` value.
This parameter can be set in either Strategy or Configuration file. If you use it in the configuration file, it will override the
`minimal_roi` value from the strategy file.
If it is not set in either Strategy or Configuration, a default of 1000% `{"0": 10}` is used, and minimal ROI is disabled unless your trade generates 1000% profit.

Special case to forceexit after a specific time

A special case presents using `"": -1` as ROI. This forces the bot to exit a trade after N Minutes, no matter if it's positive or negative, so represents a time-limited force-exit.

#### Understand force_entry_enable

The `force_entry_enable` configuration parameter enables the usage of force-enter (`/forcelong`, `/forceshort`) commands via Telegram and REST API.
For security reasons, it's disabled by default, and freqtrade will show a warning message on startup if enabled.
For example, you can send `/forceenter ETH/BTC` to the bot, which will result in freqtrade buying the pair and holds it until a regular exit-signal (ROI, stoploss, /forceexit) appears.

This can be dangerous with some strategies, so use with care.

See [the telegram documentation](https://www.freqtrade.io/en/latest/telegram-usage/) for details on usage.

#### Ignoring expired candles

When working with larger timeframes (for example 1h or more) and using a low `max_open_trades` value, the last candle can be processed as soon as a trade slot becomes available. When processing the last candle, this can lead to a situation where it may not be desirable to use the buy signal on that candle. For example, when using a condition in your strategy where you use a cross-over, that point may have passed too long ago for you to start a trade on it.

In these situations, you can enable the functionality to ignore candles that are beyond a specified period by setting `ignore_buying_expired_candle_after` to a positive number, indicating the number of seconds after which the buy signal becomes expired.

For example, if your strategy is using a 1h timeframe, and you only want to buy within the first 5 minutes when a new candle comes in, you can add the following configuration to your strategy:

```json
  {
    //...
    "ignore_buying_expired_candle_after": 300,
    // ...
  }
```

Note

This setting resets with each new candle, so it will not prevent sticking-signals from executing on the 2nd or 3rd candle they're active. Best use a "trigger" selector for buy signals, which are only active for one candle.

#### Understand order_types

The `order_types` configuration parameter maps actions (`entry`, `exit`, `stoploss`, `emergency_exit`, `force_exit`, `force_entry`) to order-types (`market`, `limit`, ...) as well as configures stoploss to be on the exchange and defines stoploss on exchange update interval in seconds.

This allows to enter using limit orders, exit using limit-orders, and create stoplosses using market orders.
It also allows to set the
stoploss "on exchange" which means stoploss order would be placed immediately once the buy order is fulfilled.

`order_types` set in the configuration file overwrites values set in the strategy as a whole, so you need to configure the whole `order_types` dictionary in one place.

If this is configured, the following 4 values (`entry`, `exit`, `stoploss` and `stoploss_on_exchange`) need to be present, otherwise, the bot will fail to start.

For information on (`emergency_exit`,`force_exit`, `force_entry`, `stoploss_on_exchange`,`stoploss_on_exchange_interval`,`stoploss_on_exchange_limit_ratio`) please see stop loss documentation [stop loss on exchange](https://www.freqtrade.io/en/latest/stoploss/)

Syntax for Strategy:

```text
order_types = {
    "entry": "limit",
    "exit": "limit",
    "emergency_exit": "market",
    "force_entry": "market",
    "force_exit": "market",
    "stoploss": "market",
    "stoploss_on_exchange": False,
    "stoploss_on_exchange_interval": 60,
    "stoploss_on_exchange_limit_ratio": 0.99,
}
```

Configuration:

```text
"order_types": {
    "entry": "limit",
    "exit": "limit",
    "emergency_exit": "market",
    "force_entry": "market",
    "force_exit": "market",
    "stoploss": "market",
    "stoploss_on_exchange": false,
    "stoploss_on_exchange_interval": 60
}
```

Market order support

Not all exchanges support "market" orders.
The following message will be shown if your exchange does not support market orders:
`"Exchange  does not support market orders."` and the bot will refuse to start.

Using market orders

Please carefully read the section [Market order pricing](#market-order-pricing) section when using market orders.

Stoploss on exchange

`order_types.stoploss_on_exchange_interval` is not mandatory. Do not change its value if you are
unsure of what you are doing. For more information about how stoploss works please
refer to [the stoploss documentation](https://www.freqtrade.io/en/latest/stoploss/).

If `order_types.stoploss_on_exchange` is enabled and the stoploss is cancelled manually on the exchange, then the bot will create a new stoploss order.

Warning: order_types.stoploss_on_exchange failures

If stoploss on exchange creation fails for some reason, then an "emergency exit" is initiated. By default, this will exit the trade using a market order. The order-type for the emergency-exit can be changed by setting the `emergency_exit` value in the `order_types` dictionary - however, this is not advised.

#### Understand order_time_in_force

The `order_time_in_force` configuration parameter defines the policy by which the order is executed on the exchange.

Commonly used time in force are:

**GTC (Good Till Canceled):**

This is most of the time the default time in force. It means the order will remain on exchange till it is cancelled by the user. It can be fully or partially fulfilled. If partially fulfilled, the remaining will stay on the exchange till cancelled.

**FOK (Fill Or Kill):**

It means if the order is not executed immediately AND fully then it is cancelled by the exchange.

**IOC (Immediate Or Canceled):**

It is the same as FOK (above) except it can be partially fulfilled. The remaining part is automatically cancelled by the exchange.

Not necessarily recommended, as this can lead to partial fills below the minimum trade size.

**PO (Post only):**

Post only order. The order is either placed as a maker order, or it is canceled.
This means the order must be placed on orderbook for at least time in an unfilled state.

Please check the [Exchange documentation](https://www.freqtrade.io/en/latest/exchanges/) for supported time in force values for your exchange.

##### time_in_force config

The `order_time_in_force` parameter contains a dict with entry and exit time in force policy values.
This can be set in the configuration file or in the strategy.
Values set in the configuration file overwrite values from in the strategy, following the regular [precedence rules](#configuration-option-prevalence).

The possible values are: `GTC` (default), `FOK` or `IOC`.

```text
"order_time_in_force": {
    "entry": "GTC",
    "exit": "GTC"
},
```

Warning

Please don't change the default value unless you know what you are doing and have researched the impact of using different values for your particular exchange.

#### Fiat conversion

Freqtrade uses the Coingecko API to convert the coin value to it's corresponding fiat value for the Telegram reports.
The FIAT currency can be set in the configuration file as `fiat_display_currency`.

Removing `fiat_display_currency` completely from the configuration will skip initializing coingecko, and will not show any FIAT currency conversion. This has no importance for the correct functioning of the bot.

##### What values can be used for fiat_display_currency?

The `fiat_display_currency` configuration parameter sets the base currency to use for the
conversion from coin to fiat in the bot Telegram reports.

The valid values are:

```text
"AUD", "BRL", "CAD", "CHF", "CLP", "CNY", "CZK", "DKK", "EUR", "GBP", "HKD", "HUF", "IDR", "ILS", "INR", "JPY", "KRW", "MXN", "MYR", "NOK", "NZD", "PHP", "PKR", "PLN", "RUB", "SEK", "SGD", "THB", "TRY", "TWD", "ZAR", "USD"
```

In addition to fiat currencies, a range of crypto currencies is supported.

The valid values are:

```text
"BTC", "ETH", "XRP", "LTC", "BCH", "BNB"
```

##### Coingecko Rate limit problems

On some IP ranges, coingecko is heavily rate-limiting.
In such cases, you may want to add your coingecko API key to the configuration.

```json
{
    "fiat_display_currency": "USD",
    "coingecko": {
        "api_key": "your-api",
        "is_demo": true
    }
}
```

Freqtrade supports both Demo and Pro coingecko API keys.

The Coingecko API key is NOT required for the bot to function correctly.
It is only used for the conversion of coin to fiat in the Telegram reports, which usually also work without API key.

### Consuming exchange Websockets

Freqtrade can consume websockets through ccxt.pro.

Freqtrade aims ensure data is available at all times.
Should the websocket connection fail (or be disabled), the bot will fall back to REST API calls.

Should you experience problems you suspect are caused by websockets, you can disable these via the setting `exchange.enable_ws`, which defaults to true.

```text
"exchange": {
    // ...
    "enable_ws": false,
    // ...
}
```

Should you be required to use a proxy, please refer to the [proxy section](#using-a-proxy-with-freqtrade) for more information.

Rollout

We're rolling this out slowly, ensuring stability of your bots.
Currently, usage is limited to ohlcv data streams.
It's also limited to a few exchanges, with new exchanges being added on an ongoing basis.

### Using Dry-run mode

We recommend starting the bot in the Dry-run mode to see how your bot will
behave and what is the performance of your strategy. In the Dry-run mode, the
bot does not engage your money. It only runs a live simulation without
creating trades on the exchange.

- Edit your `config.json` configuration file.

- Switch `dry-run` to `true` and specify `db_url` for a persistence database.

```text
"dry_run": true,
"db_url": "sqlite:///tradesv3.dryrun.sqlite",
```

- Remove your Exchange API key and secret (change them by empty values or fake credentials):

```text
"exchange": {
    "name": "binance",
    "key": "key",
    "secret": "secret",
    ...
}
```

Once you will be happy with your bot performance running in the Dry-run mode, you can switch it to production mode.

Note

A simulated wallet is available during dry-run mode and will assume a starting capital of `dry_run_wallet` (defaults to 1000).

#### Considerations for dry-run

- API-keys may or may not be provided. Only Read-Only operations (i.e. operations that do not alter account state) on the exchange are performed in dry-run mode.

- Wallets (`/balance`) are simulated based on `dry_run_wallet`.

- Orders are simulated, and will not be posted to the exchange.

- Market orders fill based on orderbook volume the moment the order is placed, with a maximum slippage of 5%.

- Limit orders fill once the price reaches the defined level - or time out based on `unfilledtimeout` settings.

- Limit orders will be converted to market orders if they cross the price by more than 1%, and will be filled immediately based regular market order rules (see point about Market orders above).

- In combination with `stoploss_on_exchange`, the stop_loss price is assumed to be filled.

- Open orders (not trades, which are stored in the database) are kept open after bot restarts, with the assumption that they were not filled while being offline.

### Switch to production mode

In production mode, the bot will engage your money. Be careful, since a wrong strategy can lose all your money.
Be aware of what you are doing when you run it in production mode.

When switching to Production mode, please make sure to use a different / fresh database to avoid dry-run trades messing with your exchange money and eventually tainting your statistics.

#### Setup your exchange account

You will need to create API Keys (usually you get `key` and `secret`, some exchanges require an additional `password`) from the Exchange website and you'll need to insert this into the appropriate fields in the configuration or when asked by the `freqtrade new-config` command.
API Keys are usually only required for live trading (trading for real money, bot running in "production mode", executing real orders on the exchange) and are not required for the bot running in dry-run (trade simulation) mode. When you set up the bot in dry-run mode, you may fill these fields with empty values.

#### To switch your bot in production mode

**Edit your `config.json` file.**

**Switch dry-run to false and don't forget to adapt your database URL if set:**

```text
"dry_run": false,
```

**Insert your Exchange API key (change them by fake API keys):**

```json
{
    "exchange": {
        "name": "binance",
        "key": "af8ddd35195e9dc500b9a6f799f6f5c93d89193b",
        "secret": "08a9dc6db3d7b53e1acebd9275677f4b0a04f1a5",
        //"password": "", // Optional, not needed by all exchanges)
        // ...
    }
    //...
}
```

You should also make sure to read the [Exchanges](https://www.freqtrade.io/en/latest/exchanges/) section of the documentation to be aware of potential configuration details specific to your exchange.

Keep your secrets secret

To keep your secrets secret, we recommend using a 2nd configuration for your API keys.
Simply use the above snippet in a new configuration file (e.g. `config-private.json`) and keep your settings in this file.
You can then start the bot with `freqtrade trade --config user_data/config.json --config user_data/config-private.json ` to have your keys loaded.

**NEVER** share your private configuration file or your exchange keys with anyone!

### Using a proxy with Freqtrade

To use a proxy with freqtrade, export your proxy settings using the variables `"HTTP_PROXY"` and `"HTTPS_PROXY"` set to the appropriate values.
This will have the proxy settings applied to everything (telegram, coingecko, ...) **except** for exchange requests.

```bash
export HTTP_PROXY="http://addr:port"
export HTTPS_PROXY="http://addr:port"
freqtrade
```

#### Proxy exchange requests

To use a proxy for exchange connections - you will have to define the proxies as part of the ccxt configuration.

```json
{
  "exchange": {
    "ccxt_config": {
      "httpsProxy": "http://addr:port",
      "wsProxy": "http://addr:port",
    }
  }
}
```

For more information on available proxy types, please consult the [ccxt proxy documentation](https://docs.ccxt.com/#/README?id=proxy).

### Next step

Now you have configured your config.json, the next step is to [start your bot](https://www.freqtrade.io/en/latest/bot-usage/).
