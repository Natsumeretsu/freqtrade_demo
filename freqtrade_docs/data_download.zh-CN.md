# 数据下载（Data Downloading）

这份文档由 Freqtrade 官方页面离线保存后整理为适合快速上手/复用的 Markdown（偏"vibe coding" 风格）。

- 来源：https://www.freqtrade.io/en/stable/data-download/
- 离线保存时间：Mon Jan 05 2026 09:07:56 GMT+0800 (中国标准时间)

## 0) 本仓库的推荐运行方式（Windows + uv）

本仓库使用 `uv` 管理环境，且仓库根目录就是 Freqtrade 的 `userdir`，建议命令统一写成：

```bash
uv run freqtrade <命令> --userdir "." <参数...>
```

下文若出现 `freqtrade ...` 的官方示例，你可以直接在前面加上 `uv run`，并补上 `--userdir "."`。

## 1) 为回测/超参下载 OHLCV（K 线）数据

使用 `freqtrade download-data` 下载回测（backtesting）与超参（hyperopt）需要的蜡烛图数据（OHLCV）。

默认行为：不额外传参时，会下载最近 30 天的 `1m` 与 `5m` 两个周期；交易所与交易对来自 `config.json`（通过 `-c/--config` 指定）。
如果未提供配置文件，则必须提供 `--exchange`。

时间范围支持两种写法：
- 相对范围：`--days 20`（推荐用于增量下载）
- 绝对起点：`--timerange 20200101-`（从某天开始一直到现在）

### 1.1 提示：更新已有数据（增量补齐）

如果数据目录里已经有历史数据，`download-data` 会自动计算缺口，只补齐从"已有数据的最新时间点"到"现在"的部分；此时无需指定 `--days` 或 `--timerange`。
如果你在更新已有数据的同时新增了"之前完全没下载过"的新交易对，请配合 `--new-pairs-days <天数>`，为新交易对单独下载指定天数的数据。

### 1.2 命令行参数一览（官方 usage）

```text
usage: freqtrade download-data [-h] [-v] [--no-color] [--logfile FILE] [-V]
                               [-c PATH] [-d PATH] [--userdir PATH]
                               [-p PAIRS [PAIRS ...]] [--pairs-file FILE]
                               [--days INT] [--new-pairs-days INT]
                               [--include-inactive-pairs]
                               [--no-parallel-download]
                               [--timerange TIMERANGE] [--dl-trades]
                               [--convert] [--exchange EXCHANGE]
                               [-t TIMEFRAMES [TIMEFRAMES ...]] [--erase]
                               [--data-format-ohlcv {json,jsongz,feather,parquet}]
                               [--data-format-trades {json,jsongz,feather,parquet}]
                               [--trading-mode {spot,margin,futures}]
                               [--candle-types {spot,futures,mark,index,premiumIndex,funding_rate} [{spot,futures,mark,index,premiumIndex,funding_rate} ...]]
                               [--prepend]

options:
  -h, --help            show this help message and exit
  -p, --pairs PAIRS [PAIRS ...]
                        Limit command to these pairs. Pairs are space-
                        separated.
  --pairs-file FILE     File containing a list of pairs. Takes precedence over
                        --pairs or pairs configured in the configuration.
  --days INT            Download data for given number of days.
  --new-pairs-days INT  Download data of new pairs for given number of days.
                        Default: `None`.
  --include-inactive-pairs
                        Also download data from inactive pairs.
  --no-parallel-download
                        Disable parallel startup download. Only use this if
                        you experience issues.
  --timerange TIMERANGE
                        Specify what timerange of data to use.
  --dl-trades           Download trades instead of OHLCV data.
  --convert             Convert downloaded trades to OHLCV data. Only
                        applicable in combination with `--dl-trades`. Will be
                        automatic for exchanges which don't have historic
                        OHLCV (e.g. Kraken). If not provided, use `trades-to-
                        ohlcv` to convert trades data to OHLCV data.
  --exchange EXCHANGE   Exchange name. Only valid if no config is provided.
  -t, --timeframes TIMEFRAMES [TIMEFRAMES ...]
                        Specify which tickers to download. Space-separated
                        list. Default: `1m 5m`.
  --erase               Clean all existing data for the selected
                        exchange/pairs/timeframes.
  --data-format-ohlcv {json,jsongz,feather,parquet}
                        Storage format for downloaded candle (OHLCV) data.
                        (default: `feather`).
  --data-format-trades {json,jsongz,feather,parquet}
                        Storage format for downloaded trades data. (default:
                        `feather`).
  --trading-mode, --tradingmode {spot,margin,futures}
                        Select Trading mode
  --candle-types {spot,futures,mark,index,premiumIndex,funding_rate} [{spot,futures,mark,index,premiumIndex,funding_rate} ...]
                        Select candle type to download. Defaults to the
                        necessary candles for the selected trading mode (e.g.
                        'spot' or ('futures', 'funding_rate' and 'mark') for
                        futures).
  --prepend             Allow data prepending. (Data-appending is disabled)

Common arguments:
  -v, --verbose         Verbose mode (-vv for more, -vvv to get all messages).
  --no-color            Disable colorization of hyperopt results. May be
                        useful if you are redirecting output to a file.
  --logfile, --log-file FILE
                        Log to the file specified. Special values are:
                        'syslog', 'journald'. See the documentation for more
                        details.
  -V, --version         show program's version number and exit
  -c, --config PATH     Specify configuration file (default:
                        `userdir/config.json` or `config.json` whichever
                        exists). Multiple --config options may be used. Can be
                        set to `-` to read config from stdin.
  -d, --datadir, --data-dir PATH
                        Path to the base directory of the exchange with
                        historical backtesting data. To see futures data, use
                        trading-mode additionally.
  --userdir, --user-data-dir PATH
                        Path to userdata directory.
```

### 1.3 常见用法：按报价币一次性下载所有交易对

很多时候你会想下载某个报价币（quote currency）下的所有交易对（例如所有 `*/USDT`）。可以使用正则形式的 pairs：

```bash
freqtrade download-data --exchange binance --pairs ".*/USDT"
```

该正则会展开为交易所上所有"活跃"交易对；如需包含"已下架"交易对，可加 `--include-inactive-pairs`。

### 1.4 说明：启动期（startup period）

`download-data` 与具体策略无关，因此不会读取策略里的 `startup_period`。
如果你的回测想从某个时间点开始，并且策略需要一定的"预热"K 线（startup period），那么请自行多下载一些天数，保证回测开始点之前有足够的数据。

### 1.5 开始下载（官方示例）

最简单的命令（假设已有可用的 `config.json`）：

```bash
freqtrade download-data --exchange binance
```

也可以显式指定交易对：

```bash
freqtrade download-data --exchange binance --pairs ETH/USDT XRP/USDT BTC/USDT
```

### 1.6 其他常用参数/注意事项

- `--datadir user_data/data/some_directory`：使用不同的数据目录（覆盖默认按交易所分目录的路径）。
- `--exchange <exchange>`：切换下载数据的交易所；或通过 `-c/--config` 指定不同的配置文件。
- `--pairs-file <path>`：从指定位置读取 `pairs.json`。
- `--days 10`：下载最近 10 天（默认 30 天）。
- `--timerange 20200101-`：从固定起点下载到现在；如果本地已有数据，会忽略已存在部分，仅补齐缺口。
- `-t/--timeframes 1m 5m ...`：指定要下载的周期；默认下载 `1m` 与 `5m`。
- 合约模式：当下载合约数据（`--trading-mode futures` 或配置指定合约模式）时，会自动下载必要的 candle types（例如 `mark`、`funding_rate`），除非你用 `--candle-types` 另行指定。

### 1.7 常见问题：Permission denied（Docker 生成的 user_data）

如果你的 `user_data` 目录由 Docker 创建，可能会遇到权限错误：

```text
cp: cannot create regular file 'user_data/data/binance/pairs.json': Permission denied
```

在 Linux 下可以通过修改目录所有权修复：

```bash
sudo chown -R $UID:$GID user_data
```

（Windows 环境一般不会遇到该问题；如果在 WSL/Docker 内运行，按上面方式处理即可。）

### 1.8 追加下载更早的数据（`--prepend`）

如果你之前只下载了从 2022 年开始的数据（例如 `--timerange 20220101-`），现在想补更早的数据，可用 `--prepend` 并指定一个结束日期：

```bash
freqtrade download-data --exchange binance --pairs ETH/USDT XRP/USDT BTC/USDT --prepend --timerange 20210101-20220101
```

注意：如果本地已有更早的数据，Freqtrade 会忽略你传入的 end-date，并自动把 end-date 更新为"已有数据的起点"。

### 1.9 数据格式（data format）

Freqtrade 支持的数据格式：
- `feather`：基于 Apache Arrow（默认）
- `json`：纯文本 JSON
- `jsongz`：gzip 压缩的 JSON
- `parquet`：列式存储（仅 OHLCV）

默认情况下，OHLCV 与 trades 数据都会存为 `feather`。你可以分别通过：
- `--data-format-ohlcv` 设置 OHLCV 格式
- `--data-format-trades` 设置 trades 格式

为了避免每次都要敲参数，建议把格式写进配置文件：

```jsonc
    // ...
    "dataformat_ohlcv": "feather",
    "dataformat_trades": "feather",
    // ...
```

如果你在下载时改了默认格式，那么配置里的 `dataformat_ohlcv` / `dataformat_trades` 也需要同步改成一致的值。
你也可以用 `convert-data` / `convert-trade-data` 在不同格式之间互转。

### 1.10 数据格式对比（体积/读取耗时）

官方对比基于如下数据集合：

```text
Found 6 pair / timeframe combinations.
+----------+-------------+--------+---------------------+---------------------+
|     Pair |   Timeframe |   Type |                From |                  To |
|----------+-------------+--------+---------------------+---------------------|
| BTC/USDT |          5m |   spot | 2017-08-17 04:00:00 | 2022-09-13 19:25:00 |
| ETH/USDT |          1m |   spot | 2017-08-17 04:00:00 | 2022-09-13 19:26:00 |
| BTC/USDT |          1m |   spot | 2017-08-17 04:00:00 | 2022-09-13 19:30:00 |
| XRP/USDT |          5m |   spot | 2018-05-04 08:10:00 | 2022-09-13 19:15:00 |
| XRP/USDT |          1m |   spot | 2018-05-04 08:11:00 | 2022-09-13 19:22:00 |
| ETH/USDT |          5m |   spot | 2017-08-17 04:00:00 | 2022-09-13 19:20:00 |
+----------+-------------+--------+---------------------+---------------------+
```

并通过以下命令（强制把数据读入内存）测量读取耗时：

```bash
time freqtrade list-data --show-timerange --data-format-ohlcv <dataformat>
```

对比结果（以 `BTC/USDT` 的 `1m spot` 为例）：

| 格式 | 体积 | 读取耗时 |
| --- | --- | --- |
| feather | 72Mb | 3.5s |
| json | 149Mb | 25.6s |
| jsongz | 39Mb | 27s |
| parquet | 83Mb | 3.8s |

综合性能与体积，建议优先使用默认的 `feather`，或使用 `parquet`。

### 1.11 `pairs.json`（不依赖 `config.json` 的下载方式）

如果不想从配置文件读取 whitelist，也可以使用 `pairs.json`。以 Binance 为例：
- 创建目录 `user_data/data/binance`，并在其中放置 `pairs.json`
- 编辑 `pairs.json`，填入你关心的交易对

```bash
mkdir -p user_data/data/binance
touch user_data/data/binance/pairs.json
```

`pairs.json` 的格式是一个简单的 JSON 列表；允许混合不同 stake 币种（因为这里只用于下载）。

```json
[
    "ETH/BTC",
    "ETH/USDT",
    "BTC/USDT",
    "XRP/ETH"
]
```

注意：`pairs.json` 只会在"没有加载任何配置"时使用（隐式或通过 `--config`）。
你可以用 `--pairs-file pairs.json` 强制使用该文件，但更推荐在配置里用 `exchange.pair_whitelist` 或 `pairs` 来管理交易对。

## 2) `convert-data`：转换 OHLCV 数据格式

用于在不同 OHLCV 数据格式之间转换（例如 `json` → `jsongz` / `feather` → `parquet` 等）。

```text
usage: freqtrade convert-data [-h] [-v] [--no-color] [--logfile FILE] [-V]
                              [-c PATH] [-d PATH] [--userdir PATH]
                              [-p PAIRS [PAIRS ...]]
                              --format-from {json,jsongz,feather,parquet}
                              --format-to {json,jsongz,feather,parquet}
                              [--erase] [--exchange EXCHANGE]
                              [-t TIMEFRAMES [TIMEFRAMES ...]]
                              [--trading-mode {spot,margin,futures}]
                              [--candle-types {spot,futures,mark,index,premiumIndex,funding_rate} [{spot,futures,mark,index,premiumIndex,funding_rate} ...]]

options:
  -h, --help            show this help message and exit
  -p, --pairs PAIRS [PAIRS ...]
                        Limit command to these pairs. Pairs are space-
                        separated.
  --format-from {json,jsongz,feather,parquet}
                        Source format for data conversion.
  --format-to {json,jsongz,feather,parquet}
                        Destination format for data conversion.
  --erase               Clean all existing data for the selected
                        exchange/pairs/timeframes.
  --exchange EXCHANGE   Exchange name. Only valid if no config is provided.
  -t, --timeframes TIMEFRAMES [TIMEFRAMES ...]
                        Specify which tickers to download. Space-separated
                        list. Default: `1m 5m`.
  --trading-mode, --tradingmode {spot,margin,futures}
                        Select Trading mode
  --candle-types {spot,futures,mark,index,premiumIndex,funding_rate} [{spot,futures,mark,index,premiumIndex,funding_rate} ...]
                        Select candle type to convert. Defaults to all
                        available types.

Common arguments:
  -v, --verbose         Verbose mode (-vv for more, -vvv to get all messages).
  --no-color            Disable colorization of hyperopt results. May be
                        useful if you are redirecting output to a file.
  --logfile, --log-file FILE
                        Log to the file specified. Special values are:
                        'syslog', 'journald'. See the documentation for more
                        details.
  -V, --version         show program's version number and exit
  -c, --config PATH     Specify configuration file (default:
                        `userdir/config.json` or `config.json` whichever
                        exists). Multiple --config options may be used. Can be
                        set to `-` to read config from stdin.
  -d, --datadir, --data-dir PATH
                        Path to the base directory of the exchange with
                        historical backtesting data. To see futures data, use
                        trading-mode additionally.
  --userdir, --user-data-dir PATH
                        Path to userdata directory.
```

示例：把 `~/.freqtrade/data/binance` 下所有 OHLCV 数据从 `json` 转为 `jsongz`，并删除原始 `json` 文件（`--erase`）：

```bash
freqtrade convert-data --format-from json --format-to jsongz --datadir ~/.freqtrade/data/binance -t 5m 15m --erase
```

## 3) `convert-trade-data`：转换 trades（tick）数据格式

用于在不同 trades 数据格式之间转换。

```text
usage: freqtrade convert-trade-data [-h] [-v] [--no-color] [--logfile FILE]
                                    [-V] [-c PATH] [-d PATH] [--userdir PATH]
                                    [-p PAIRS [PAIRS ...]]
                                    --format-from {json,jsongz,feather,parquet,kraken_csv}
                                    --format-to {json,jsongz,feather,parquet}
                                    [--erase] [--exchange EXCHANGE]

options:
  -h, --help            show this help message and exit
  -p, --pairs PAIRS [PAIRS ...]
                        Limit command to these pairs. Pairs are space-
                        separated.
  --format-from {json,jsongz,feather,parquet,kraken_csv}
                        Source format for data conversion.
  --format-to {json,jsongz,feather,parquet}
                        Destination format for data conversion.
  --erase               Clean all existing data for the selected
                        exchange/pairs/timeframes.
  --exchange EXCHANGE   Exchange name. Only valid if no config is provided.

Common arguments:
  -v, --verbose         Verbose mode (-vv for more, -vvv to get all messages).
  --no-color            Disable colorization of hyperopt results. May be
                        useful if you are redirecting output to a file.
  --logfile, --log-file FILE
                        Log to the file specified. Special values are:
                        'syslog', 'journald'. See the documentation for more
                        details.
  -V, --version         show program's version number and exit
  -c, --config PATH     Specify configuration file (default:
                        `userdir/config.json` or `config.json` whichever
                        exists). Multiple --config options may be used. Can be
                        set to `-` to read config from stdin.
  -d, --datadir, --data-dir PATH
                        Path to the base directory of the exchange with
                        historical backtesting data. To see futures data, use
                        trading-mode additionally.
  --userdir, --user-data-dir PATH
                        Path to userdata directory.
```

示例：把 `~/.freqtrade/data/kraken` 下的 trades 数据从 `jsongz` 转为 `json`，并删除原始 `jsongz` 文件（`--erase`）：

```bash
freqtrade convert-trade-data --format-from jsongz --format-to json --datadir ~/.freqtrade/data/kraken --erase
```

## 4) `trades-to-ohlcv`：将 trades 重采样为 OHLCV

当你需要使用 `--dl-trades`（通常仅 Kraken 需要）下载 trades 数据时，最后一步是把 trades 转换为 OHLCV。
`trades-to-ohlcv` 允许你在"不重复下载 trades"的情况下，为更多周期重复执行"重采样"。

```text
usage: freqtrade trades-to-ohlcv [-h] [-v] [--no-color] [--logfile FILE] [-V]
                                 [-c PATH] [-d PATH] [--userdir PATH]
                                 [-p PAIRS [PAIRS ...]]
                                 [-t TIMEFRAMES [TIMEFRAMES ...]]
                                 [--exchange EXCHANGE]
                                 [--data-format-ohlcv {json,jsongz,feather,parquet}]
                                 [--data-format-trades {json,jsongz,feather,parquet}]
                                 [--trading-mode {spot,margin,futures}]

options:
  -h, --help            show this help message and exit
  -p, --pairs PAIRS [PAIRS ...]
                        Limit command to these pairs. Pairs are space-
                        separated.
  -t, --timeframes TIMEFRAMES [TIMEFRAMES ...]
                        Specify which tickers to download. Space-separated
                        list. Default: `1m 5m`.
  --exchange EXCHANGE   Exchange name. Only valid if no config is provided.
  --data-format-ohlcv {json,jsongz,feather,parquet}
                        Storage format for downloaded candle (OHLCV) data.
                        (default: `feather`).
  --data-format-trades {json,jsongz,feather,parquet}
                        Storage format for downloaded trades data. (default:
                        `feather`).
  --trading-mode, --tradingmode {spot,margin,futures}
                        Select Trading mode

Common arguments:
  -v, --verbose         Verbose mode (-vv for more, -vvv to get all messages).
  --no-color            Disable colorization of hyperopt results. May be
                        useful if you are redirecting output to a file.
  --logfile, --log-file FILE
                        Log to the file specified. Special values are:
                        'syslog', 'journald'. See the documentation for more
                        details.
  -V, --version         show program's version number and exit
  -c, --config PATH     Specify configuration file (default:
                        `userdir/config.json` or `config.json` whichever
                        exists). Multiple --config options may be used. Can be
                        set to `-` to read config from stdin.
  -d, --datadir, --data-dir PATH
                        Path to the base directory of the exchange with
                        historical backtesting data. To see futures data, use
                        trading-mode additionally.
  --userdir, --user-data-dir PATH
                        Path to userdata directory.
```

示例：把 Kraken 的 trades 数据转换成 `5m`、`1h`、`1d` 的 OHLCV：

```bash
freqtrade trades-to-ohlcv --exchange kraken -t 5m 1h 1d --pairs BTC/EUR ETH/EUR
```

## 5) `list-data`：列出已下载的数据

查看本地已有的 OHLCV / trades 数据。

```text
usage: freqtrade list-data [-h] [-v] [--no-color] [--logfile FILE] [-V]
                           [-c PATH] [-d PATH] [--userdir PATH]
                           [--exchange EXCHANGE]
                           [--data-format-ohlcv {json,jsongz,feather,parquet}]
                           [--data-format-trades {json,jsongz,feather,parquet}]
                           [--trades] [-p PAIRS [PAIRS ...]]
                           [--trading-mode {spot,margin,futures}]
                           [--show-timerange]

options:
  -h, --help            show this help message and exit
  --exchange EXCHANGE   Exchange name. Only valid if no config is provided.
  --data-format-ohlcv {json,jsongz,feather,parquet}
                        Storage format for downloaded candle (OHLCV) data.
                        (default: `feather`).
  --data-format-trades {json,jsongz,feather,parquet}
                        Storage format for downloaded trades data. (default:
                        `feather`).
  --trades              Work on trades data instead of OHLCV data.
  -p, --pairs PAIRS [PAIRS ...]
                        Limit command to these pairs. Pairs are space-
                        separated.
  --trading-mode, --tradingmode {spot,margin,futures}
                        Select Trading mode
  --show-timerange      Show timerange available for available data. (May take
                        a while to calculate).

Common arguments:
  -v, --verbose         Verbose mode (-vv for more, -vvv to get all messages).
  --no-color            Disable colorization of hyperopt results. May be
                        useful if you are redirecting output to a file.
  --logfile, --log-file FILE
                        Log to the file specified. Special values are:
                        'syslog', 'journald'. See the documentation for more
                        details.
  -V, --version         show program's version number and exit
  -c, --config PATH     Specify configuration file (default:
                        `userdir/config.json` or `config.json` whichever
                        exists). Multiple --config options may be used. Can be
                        set to `-` to read config from stdin.
  -d, --datadir, --data-dir PATH
                        Path to the base directory of the exchange with
                        historical backtesting data. To see futures data, use
                        trading-mode additionally.
  --userdir, --user-data-dir PATH
                        Path to userdata directory.
```

示例：列出下载的数据概览：

```text
> freqtrade list-data --userdir ~/.freqtrade/user_data/

              Found 33 pair / timeframe combinations.
┏━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━┓
┃          Pair ┃                                 Timeframe ┃ Type ┃
┡━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━┩
│       ADA/BTC │     5m, 15m, 30m, 1h, 2h, 4h, 6h, 12h, 1d │ spot │
│       ADA/ETH │     5m, 15m, 30m, 1h, 2h, 4h, 6h, 12h, 1d │ spot │
│       ETH/BTC │     5m, 15m, 30m, 1h, 2h, 4h, 6h, 12h, 1d │ spot │
│      ETH/USDT │                  5m, 15m, 30m, 1h, 2h, 4h │ spot │
└───────────────┴───────────────────────────────────────────┴──────┘
```

示例：显示所有 trades 数据并包含起止时间：

```text
> freqtrade list-data --show --trades
                     Found trades data for 1 pair.                     
┏━━━━━━━━━┳━━━━━━┳━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━┓
┃    Pair ┃ Type ┃                From ┃                  To ┃ Trades ┃
┡━━━━━━━━━╇━━━━━━╇━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━┩
│ XRP/ETH │ spot │ 2019-10-11 00:00:11 │ 2019-10-13 11:19:28 │  12477 │
└─────────┴──────┴─────────────────────┴─────────────────────┴────────┘
```

## 6) 下载 trades（tick）数据：`--dl-trades`

`download-data` 默认下载 OHLCV。大多数交易所也提供历史 trades（逐笔成交）数据。
trades 数据的价值在于：只需下载一次，然后可以在本地重采样出多个不同周期（timeframe）的 OHLCV。

由于 trades 数据量通常很大，默认使用 `feather` 保存，文件命名形如 `<pair>-trades.feather`（例如 `ETH_BTC-trades.feather`）。
trades 同样支持增量下载；例如每周执行一次 `--days 8` 可以逐步补齐数据仓库。

使用方式：在 `download-data` 后追加 `--dl-trades`。
如果同时提供 `--convert`，会自动执行重采样，并覆盖指定交易对/周期上可能已存在的 OHLCV 数据。

### 6.1 警告：非 Kraken 用户不要用

除非你是 Kraken 用户（Kraken 不提供历史 OHLCV），否则不建议使用 `--dl-trades`。
对于大多数交易所，直接下载 OHLCV 会更快、更省事；即使你需要多个周期，也通常比下载 trades 更高效。

### 6.2 Kraken 示例

示例：下载 Kraken trades 数据（并按需要的天数增量补齐）：

```bash
freqtrade download-data --exchange kraken --pairs XRP/EUR ETH/EUR --days 20 --dl-trades
```

注意：该模式虽然使用异步调用，但整体仍会较慢（每次请求通常依赖上一次请求的结果来生成下一次请求）。

## 7) 下一步

数据下载完成后，就可以开始回测你的策略了（`freqtrade backtesting`）。

---

## 附录：官方原文（自动 Markdown 化）

- 来源：https://www.freqtrade.io/en/stable/data-download/
- 离线保存时间：Mon Jan 05 2026 09:07:56 GMT+0800 (中国标准时间)

### Getting data for backtesting and hyperopt

To download data (candles / OHLCV) needed for backtesting and hyperoptimization use the `freqtrade download-data` command.

If no additional parameter is specified, freqtrade will download data for `"1m"` and `"5m"` timeframes for the last 30 days.
Exchange and pairs will come from `config.json` (if specified using `-c/--config`).
Without provided configuration, `--exchange` becomes mandatory.

You can use a relative timerange (`--days 20`) or an absolute starting point (`--timerange 20200101-`). For incremental downloads, the relative approach should be used.

Tip: Updating existing data

If you already have backtesting data available in your data-directory and would like to refresh this data up to today, freqtrade will automatically calculate the missing timerange for the existing pairs and the download will occur from the latest available point until "now", neither `--days` or `--timerange` parameters are required. Freqtrade will keep the available data and only download the missing data.

If you are updating existing data after inserting new pairs that you have no data for, use the `--new-pairs-days xx` parameter. Specified number of days will be downloaded for new pairs while old pairs will be updated with missing data only.

#### Usage

```text
usage: freqtrade download-data [-h] [-v] [--no-color] [--logfile FILE] [-V]
                               [-c PATH] [-d PATH] [--userdir PATH]
                               [-p PAIRS [PAIRS ...]] [--pairs-file FILE]
                               [--days INT] [--new-pairs-days INT]
                               [--include-inactive-pairs]
                               [--no-parallel-download]
                               [--timerange TIMERANGE] [--dl-trades]
                               [--convert] [--exchange EXCHANGE]
                               [-t TIMEFRAMES [TIMEFRAMES ...]] [--erase]
                               [--data-format-ohlcv {json,jsongz,feather,parquet}]
                               [--data-format-trades {json,jsongz,feather,parquet}]
                               [--trading-mode {spot,margin,futures}]
                               [--candle-types {spot,futures,mark,index,premiumIndex,funding_rate} [{spot,futures,mark,index,premiumIndex,funding_rate} ...]]
                               [--prepend]

options:
  -h, --help            show this help message and exit
  -p, --pairs PAIRS [PAIRS ...]
                        Limit command to these pairs. Pairs are space-
                        separated.
  --pairs-file FILE     File containing a list of pairs. Takes precedence over
                        --pairs or pairs configured in the configuration.
  --days INT            Download data for given number of days.
  --new-pairs-days INT  Download data of new pairs for given number of days.
                        Default: `None`.
  --include-inactive-pairs
                        Also download data from inactive pairs.
  --no-parallel-download
                        Disable parallel startup download. Only use this if
                        you experience issues.
  --timerange TIMERANGE
                        Specify what timerange of data to use.
  --dl-trades           Download trades instead of OHLCV data.
  --convert             Convert downloaded trades to OHLCV data. Only
                        applicable in combination with `--dl-trades`. Will be
                        automatic for exchanges which don't have historic
                        OHLCV (e.g. Kraken). If not provided, use `trades-to-
                        ohlcv` to convert trades data to OHLCV data.
  --exchange EXCHANGE   Exchange name. Only valid if no config is provided.
  -t, --timeframes TIMEFRAMES [TIMEFRAMES ...]
                        Specify which tickers to download. Space-separated
                        list. Default: `1m 5m`.
  --erase               Clean all existing data for the selected
                        exchange/pairs/timeframes.
  --data-format-ohlcv {json,jsongz,feather,parquet}
                        Storage format for downloaded candle (OHLCV) data.
                        (default: `feather`).
  --data-format-trades {json,jsongz,feather,parquet}
                        Storage format for downloaded trades data. (default:
                        `feather`).
  --trading-mode, --tradingmode {spot,margin,futures}
                        Select Trading mode
  --candle-types {spot,futures,mark,index,premiumIndex,funding_rate} [{spot,futures,mark,index,premiumIndex,funding_rate} ...]
                        Select candle type to download. Defaults to the
                        necessary candles for the selected trading mode (e.g.
                        'spot' or ('futures', 'funding_rate' and 'mark') for
                        futures).
  --prepend             Allow data prepending. (Data-appending is disabled)

Common arguments:
  -v, --verbose         Verbose mode (-vv for more, -vvv to get all messages).
  --no-color            Disable colorization of hyperopt results. May be
                        useful if you are redirecting output to a file.
  --logfile, --log-file FILE
                        Log to the file specified. Special values are:
                        'syslog', 'journald'. See the documentation for more
                        details.
  -V, --version         show program's version number and exit
  -c, --config PATH     Specify configuration file (default:
                        `userdir/config.json` or `config.json` whichever
                        exists). Multiple --config options may be used. Can be
                        set to `-` to read config from stdin.
  -d, --datadir, --data-dir PATH
                        Path to the base directory of the exchange with
                        historical backtesting data. To see futures data, use
                        trading-mode additionally.
  --userdir, --user-data-dir PATH
                        Path to userdata directory.
```

Downloading all data for one quote currency

Often, you'll want to download data for all pairs of a specific quote-currency. In such cases, you can use the following shorthand:
`freqtrade download-data --exchange binance --pairs ".*/USDT" `. The provided "pairs" string will be expanded to contain all active pairs on the exchange.
To also download data for inactive (delisted) pairs, add `--include-inactive-pairs` to the command.

Startup period

`download-data` is a strategy-independent command. The idea is to download a big chunk of data once, and then iteratively increase the amount of data stored.

For that reason, `download-data` does not care about the "startup-period" defined in a strategy. It's up to the user to download additional days if the backtest should start at a specific point in time (while respecting startup period).

#### Start download

A very simple command (assuming an available `config.json` file) can look as follows.

```bash
freqtrade download-data --exchange binance
```

This will download historical candle (OHLCV) data for all the currency pairs defined in the configuration.

Alternatively, specify the pairs directly

```bash
freqtrade download-data --exchange binance --pairs ETH/USDT XRP/USDT BTC/USDT
```

or as regex (in this case, to download all active USDT pairs)

```bash
freqtrade download-data --exchange binance --pairs ".*/USDT"
```

#### Other Notes

- To use a different directory than the exchange specific default, use `--datadir user_data/data/some_directory`.

- To change the exchange used to download the historical data from, either use `--exchange ` - or specify a different configuration file.

- To use `pairs.json` from some other directory, use `--pairs-file some_other_dir/pairs.json`.

- To download historical candle (OHLCV) data for only 10 days, use `--days 10` (defaults to 30 days).

- To download historical candle (OHLCV) data from a fixed starting point, use `--timerange 20200101-` - which will download all data from January 1st, 2020.

- Given starting points are ignored if data is already available, downloading only missing data up to today.

- Use `--timeframes` to specify what timeframe download the historical candle (OHLCV) data for. Default is `--timeframes 1m 5m` which will download 1-minute and 5-minute data.

- To use exchange, timeframe and list of pairs as defined in your configuration file, use the `-c/--config` option. With this, the script uses the whitelist defined in the config as the list of currency pairs to download data for and does not require the pairs.json file. You can combine `-c/--config` with most other options.

- When downloading futures data (`--trading-mode futures` or a configuration specifying futures mode), freqtrade will automatically download the necessary candle types (e.g. `mark` and `funding_rate` candles) unless specified otherwise via `--candle-types`.

Permission denied errors
If your configuration directory `user_data` was made by docker, you may get the following error:

```text
cp: cannot create regular file 'user_data/data/binance/pairs.json': Permission denied
```

You can fix the permissions of your user-data directory as follows:

```text
sudo chown -R $UID:$GID user_data
```

#### Download additional data before the current timerange

Assuming you downloaded all data from 2022 (`--timerange 20220101-`) - but you'd now like to also backtest with earlier data.
You can do so by using the `--prepend` flag, combined with `--timerange` - specifying an end-date.

```bash
freqtrade download-data --exchange binance --pairs ETH/USDT XRP/USDT BTC/USDT --prepend --timerange 20210101-20220101
```

Note

Freqtrade will ignore the end-date in this mode if data is available, updating the end-date to the existing data start point.

#### Data format

Freqtrade currently supports the following data-formats:

- `feather` - a dataformat based on Apache Arrow

- `json` - plain "text" json files

- `jsongz` - a gzip-zipped version of json files

- `parquet` - columnar datastore (OHLCV only)

By default, both OHLCV data and trades data are stored in the `feather` format.

This can be changed via the `--data-format-ohlcv` and `--data-format-trades` command line arguments respectively.
To persist this change, you should also add the following snippet to your configuration, so you don't have to insert the above arguments each time:

```text
    // ...
    "dataformat_ohlcv": "feather",
    "dataformat_trades": "feather",
    // ...
```

If the default data-format has been changed during download, then the keys `dataformat_ohlcv` and `dataformat_trades` in the configuration file need to be adjusted to the selected dataformat as well.

Note

You can convert between data-formats using the [convert-data](#sub-command-convert-data) and [convert-trade-data](#sub-command-convert-trade-data) methods.

##### Dataformat comparison

The following comparisons have been made with the following data, and by using the linux `time` command.

```text
Found 6 pair / timeframe combinations.
+----------+-------------+--------+---------------------+---------------------+
|     Pair |   Timeframe |   Type |                From |                  To |
|----------+-------------+--------+---------------------+---------------------|
| BTC/USDT |          5m |   spot | 2017-08-17 04:00:00 | 2022-09-13 19:25:00 |
| ETH/USDT |          1m |   spot | 2017-08-17 04:00:00 | 2022-09-13 19:26:00 |
| BTC/USDT |          1m |   spot | 2017-08-17 04:00:00 | 2022-09-13 19:30:00 |
| XRP/USDT |          5m |   spot | 2018-05-04 08:10:00 | 2022-09-13 19:15:00 |
| XRP/USDT |          1m |   spot | 2018-05-04 08:11:00 | 2022-09-13 19:22:00 |
| ETH/USDT |          5m |   spot | 2017-08-17 04:00:00 | 2022-09-13 19:20:00 |
+----------+-------------+--------+---------------------+---------------------+
```

Timings have been taken in a not very scientific way with the following command, which forces reading the data into memory.

```text
time freqtrade list-data --show-timerange --data-format-ohlcv <dataformat>
```

| Format | Size | timing |
| --- | --- | --- |
| feather | 72Mb | 3.5s |
| json | 149Mb | 25.6s |
| jsongz | 39Mb | 27s |
| parquet | 83Mb | 3.8s |

Size has been taken from the BTC/USDT 1m spot combination for the timerange specified above.

To have a best performance/size mix, we recommend using the default feather format, or parquet.

#### Pairs file

In alternative to the whitelist from `config.json`, a `pairs.json` file can be used.
If you are using Binance for example:

- create a directory `user_data/data/binance` and copy or create the `pairs.json` file in that directory.

- update the `pairs.json` file to contain the currency pairs you are interested in.

```text
mkdir -p user_data/data/binance
touch user_data/data/binance/pairs.json
```

The format of the `pairs.json` file is a simple json list.
Mixing different stake-currencies is allowed for this file, since it's only used for downloading.

```json
[
    "ETH/BTC",
    "ETH/USDT",
    "BTC/USDT",
    "XRP/ETH"
]
```

Note

The `pairs.json` file is only used when no configuration is loaded (implicitly by naming, or via `--config` flag).
You can force the usage of this file via `--pairs-file pairs.json` - however we recommend to use the pairlist from within the configuration, either via `exchange.pair_whitelist` or `pairs` setting in the configuration.

### Sub-command convert data

```text
usage: freqtrade convert-data [-h] [-v] [--no-color] [--logfile FILE] [-V]
                              [-c PATH] [-d PATH] [--userdir PATH]
                              [-p PAIRS [PAIRS ...]]
                              --format-from {json,jsongz,feather,parquet}
                              --format-to {json,jsongz,feather,parquet}
                              [--erase] [--exchange EXCHANGE]
                              [-t TIMEFRAMES [TIMEFRAMES ...]]
                              [--trading-mode {spot,margin,futures}]
                              [--candle-types {spot,futures,mark,index,premiumIndex,funding_rate} [{spot,futures,mark,index,premiumIndex,funding_rate} ...]]

options:
  -h, --help            show this help message and exit
  -p, --pairs PAIRS [PAIRS ...]
                        Limit command to these pairs. Pairs are space-
                        separated.
  --format-from {json,jsongz,feather,parquet}
                        Source format for data conversion.
  --format-to {json,jsongz,feather,parquet}
                        Destination format for data conversion.
  --erase               Clean all existing data for the selected
                        exchange/pairs/timeframes.
  --exchange EXCHANGE   Exchange name. Only valid if no config is provided.
  -t, --timeframes TIMEFRAMES [TIMEFRAMES ...]
                        Specify which tickers to download. Space-separated
                        list. Default: `1m 5m`.
  --trading-mode, --tradingmode {spot,margin,futures}
                        Select Trading mode
  --candle-types {spot,futures,mark,index,premiumIndex,funding_rate} [{spot,futures,mark,index,premiumIndex,funding_rate} ...]
                        Select candle type to convert. Defaults to all
                        available types.

Common arguments:
  -v, --verbose         Verbose mode (-vv for more, -vvv to get all messages).
  --no-color            Disable colorization of hyperopt results. May be
                        useful if you are redirecting output to a file.
  --logfile, --log-file FILE
                        Log to the file specified. Special values are:
                        'syslog', 'journald'. See the documentation for more
                        details.
  -V, --version         show program's version number and exit
  -c, --config PATH     Specify configuration file (default:
                        `userdir/config.json` or `config.json` whichever
                        exists). Multiple --config options may be used. Can be
                        set to `-` to read config from stdin.
  -d, --datadir, --data-dir PATH
                        Path to the base directory of the exchange with
                        historical backtesting data. To see futures data, use
                        trading-mode additionally.
  --userdir, --user-data-dir PATH
                        Path to userdata directory.
```

#### Example converting data

The following command will convert all candle (OHLCV) data available in `~/.freqtrade/data/binance` from json to jsongz, saving diskspace in the process.
It'll also remove original json data files (`--erase` parameter).

```bash
freqtrade convert-data --format-from json --format-to jsongz --datadir ~/.freqtrade/data/binance -t 5m 15m --erase
```

### Sub-command convert trade data

```text
usage: freqtrade convert-trade-data [-h] [-v] [--no-color] [--logfile FILE]
                                    [-V] [-c PATH] [-d PATH] [--userdir PATH]
                                    [-p PAIRS [PAIRS ...]]
                                    --format-from {json,jsongz,feather,parquet,kraken_csv}
                                    --format-to {json,jsongz,feather,parquet}
                                    [--erase] [--exchange EXCHANGE]

options:
  -h, --help            show this help message and exit
  -p, --pairs PAIRS [PAIRS ...]
                        Limit command to these pairs. Pairs are space-
                        separated.
  --format-from {json,jsongz,feather,parquet,kraken_csv}
                        Source format for data conversion.
  --format-to {json,jsongz,feather,parquet}
                        Destination format for data conversion.
  --erase               Clean all existing data for the selected
                        exchange/pairs/timeframes.
  --exchange EXCHANGE   Exchange name. Only valid if no config is provided.

Common arguments:
  -v, --verbose         Verbose mode (-vv for more, -vvv to get all messages).
  --no-color            Disable colorization of hyperopt results. May be
                        useful if you are redirecting output to a file.
  --logfile, --log-file FILE
                        Log to the file specified. Special values are:
                        'syslog', 'journald'. See the documentation for more
                        details.
  -V, --version         show program's version number and exit
  -c, --config PATH     Specify configuration file (default:
                        `userdir/config.json` or `config.json` whichever
                        exists). Multiple --config options may be used. Can be
                        set to `-` to read config from stdin.
  -d, --datadir, --data-dir PATH
                        Path to the base directory of the exchange with
                        historical backtesting data. To see futures data, use
                        trading-mode additionally.
  --userdir, --user-data-dir PATH
                        Path to userdata directory.
```

#### Example converting trades

The following command will convert all available trade-data in `~/.freqtrade/data/kraken` from jsongz to json.
It'll also remove original jsongz data files (`--erase` parameter).

```bash
freqtrade convert-trade-data --format-from jsongz --format-to json --datadir ~/.freqtrade/data/kraken --erase
```

### Sub-command trades to ohlcv

When you need to use `--dl-trades` (kraken only) to download data, conversion of trades data to ohlcv data is the last step.
This command will allow you to repeat this last step for additional timeframes without re-downloading the data.

```text
usage: freqtrade trades-to-ohlcv [-h] [-v] [--no-color] [--logfile FILE] [-V]
                                 [-c PATH] [-d PATH] [--userdir PATH]
                                 [-p PAIRS [PAIRS ...]]
                                 [-t TIMEFRAMES [TIMEFRAMES ...]]
                                 [--exchange EXCHANGE]
                                 [--data-format-ohlcv {json,jsongz,feather,parquet}]
                                 [--data-format-trades {json,jsongz,feather,parquet}]
                                 [--trading-mode {spot,margin,futures}]

options:
  -h, --help            show this help message and exit
  -p, --pairs PAIRS [PAIRS ...]
                        Limit command to these pairs. Pairs are space-
                        separated.
  -t, --timeframes TIMEFRAMES [TIMEFRAMES ...]
                        Specify which tickers to download. Space-separated
                        list. Default: `1m 5m`.
  --exchange EXCHANGE   Exchange name. Only valid if no config is provided.
  --data-format-ohlcv {json,jsongz,feather,parquet}
                        Storage format for downloaded candle (OHLCV) data.
                        (default: `feather`).
  --data-format-trades {json,jsongz,feather,parquet}
                        Storage format for downloaded trades data. (default:
                        `feather`).
  --trading-mode, --tradingmode {spot,margin,futures}
                        Select Trading mode

Common arguments:
  -v, --verbose         Verbose mode (-vv for more, -vvv to get all messages).
  --no-color            Disable colorization of hyperopt results. May be
                        useful if you are redirecting output to a file.
  --logfile, --log-file FILE
                        Log to the file specified. Special values are:
                        'syslog', 'journald'. See the documentation for more
                        details.
  -V, --version         show program's version number and exit
  -c, --config PATH     Specify configuration file (default:
                        `userdir/config.json` or `config.json` whichever
                        exists). Multiple --config options may be used. Can be
                        set to `-` to read config from stdin.
  -d, --datadir, --data-dir PATH
                        Path to the base directory of the exchange with
                        historical backtesting data. To see futures data, use
                        trading-mode additionally.
  --userdir, --user-data-dir PATH
                        Path to userdata directory.
```

#### Example trade-to-ohlcv conversion

```bash
freqtrade trades-to-ohlcv --exchange kraken -t 5m 1h 1d --pairs BTC/EUR ETH/EUR
```

### Sub-command list-data

You can get a list of downloaded data using the `list-data` sub-command.

```text
usage: freqtrade list-data [-h] [-v] [--no-color] [--logfile FILE] [-V]
                           [-c PATH] [-d PATH] [--userdir PATH]
                           [--exchange EXCHANGE]
                           [--data-format-ohlcv {json,jsongz,feather,parquet}]
                           [--data-format-trades {json,jsongz,feather,parquet}]
                           [--trades] [-p PAIRS [PAIRS ...]]
                           [--trading-mode {spot,margin,futures}]
                           [--show-timerange]

options:
  -h, --help            show this help message and exit
  --exchange EXCHANGE   Exchange name. Only valid if no config is provided.
  --data-format-ohlcv {json,jsongz,feather,parquet}
                        Storage format for downloaded candle (OHLCV) data.
                        (default: `feather`).
  --data-format-trades {json,jsongz,feather,parquet}
                        Storage format for downloaded trades data. (default:
                        `feather`).
  --trades              Work on trades data instead of OHLCV data.
  -p, --pairs PAIRS [PAIRS ...]
                        Limit command to these pairs. Pairs are space-
                        separated.
  --trading-mode, --tradingmode {spot,margin,futures}
                        Select Trading mode
  --show-timerange      Show timerange available for available data. (May take
                        a while to calculate).

Common arguments:
  -v, --verbose         Verbose mode (-vv for more, -vvv to get all messages).
  --no-color            Disable colorization of hyperopt results. May be
                        useful if you are redirecting output to a file.
  --logfile, --log-file FILE
                        Log to the file specified. Special values are:
                        'syslog', 'journald'. See the documentation for more
                        details.
  -V, --version         show program's version number and exit
  -c, --config PATH     Specify configuration file (default:
                        `userdir/config.json` or `config.json` whichever
                        exists). Multiple --config options may be used. Can be
                        set to `-` to read config from stdin.
  -d, --datadir, --data-dir PATH
                        Path to the base directory of the exchange with
                        historical backtesting data. To see futures data, use
                        trading-mode additionally.
  --userdir, --user-data-dir PATH
                        Path to userdata directory.
```

#### Example list-data

```text
> freqtrade list-data --userdir ~/.freqtrade/user_data/

              Found 33 pair / timeframe combinations.
┏━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━┓
┃          Pair ┃                                 Timeframe ┃ Type ┃
┡━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━┩
│       ADA/BTC │     5m, 15m, 30m, 1h, 2h, 4h, 6h, 12h, 1d │ spot │
│       ADA/ETH │     5m, 15m, 30m, 1h, 2h, 4h, 6h, 12h, 1d │ spot │
│       ETH/BTC │     5m, 15m, 30m, 1h, 2h, 4h, 6h, 12h, 1d │ spot │
│      ETH/USDT │                  5m, 15m, 30m, 1h, 2h, 4h │ spot │
└───────────────┴───────────────────────────────────────────┴──────┘
```

Show all trades data including from/to timerange

```text
> freqtrade list-data --show --trades
                     Found trades data for 1 pair.
┏━━━━━━━━━┳━━━━━━┳━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━┓
┃    Pair ┃ Type ┃                From ┃                  To ┃ Trades ┃
┡━━━━━━━━━╇━━━━━━╇━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━┩
│ XRP/ETH │ spot │ 2019-10-11 00:00:11 │ 2019-10-13 11:19:28 │  12477 │
└─────────┴──────┴─────────────────────┴─────────────────────┴────────┘
```

### Trades (tick) data

By default, `download-data` sub-command downloads Candles (OHLCV) data. Most exchanges also provide historic trade-data via their API.
This data can be useful if you need many different timeframes, since it is only downloaded once, and then resampled locally to the desired timeframes.

Since this data is large by default, the files use the feather file format by default. They are stored in your data-directory with the naming convention of `-trades.feather` (`ETH_BTC-trades.feather`). Incremental mode is also supported, as for historic OHLCV data, so downloading the data once per week with `--days 8` will create an incremental data-repository.

To use this mode, simply add `--dl-trades` to your call. This will swap the download method to download trades.
If `--convert` is also provided, the resample step will happen automatically and overwrite eventually existing OHLCV data for the given pair/timeframe combinations.

Do not use

You should not use this unless you're a kraken user (Kraken does not provide historic OHLCV data).

Most other exchanges provide OHLCV data with sufficient history, so downloading multiple timeframes through that method will still proof to be a lot faster than downloading trades data.

Kraken user

Kraken users should read [this](https://www.freqtrade.io/en/stable/exchanges/#historic-kraken-data) before starting to download data.

Example call:

```bash
freqtrade download-data --exchange kraken --pairs XRP/EUR ETH/EUR --days 20 --dl-trades
```

Note

While this method uses async calls, it will be slow, since it requires the result of the previous call to generate the next request to the exchange.

### Next step

Great, you now have some data downloaded, so you can now start [backtesting](https://www.freqtrade.io/en/stable/backtesting/) your strategy.
