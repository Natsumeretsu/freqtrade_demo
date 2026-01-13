# 启动与使用 Bot（Start the bot）

这份文档由 Freqtrade 官方页面离线保存后整理为便于“vibe coding 查阅使用”的 Markdown。

- 来源：https://www.freqtrade.io/en/stable/bot-usage/
- 离线保存时间：Mon Jan 05 2026 11:36:43 GMT+0800 (中国标准时间)

## 0) 本仓库的推荐运行方式（Windows + uv）

本仓库使用 `uv` 管理环境，且仓库根目录就是 Freqtrade 的 `userdir`，建议命令统一写成：

```bash
uv run freqtrade <命令> --userdir "." <参数...>
```

下文若出现 `freqtrade ...` 的官方示例，你可以直接在前面加上 `uv run`，并补上 `--userdir "."`。

---

## 1) 目录速览（H2）

下面列出原文的一级小节标题（H2），便于你快速定位内容：

- Bot commands
- Next step

---

## 2) 原文（自动 Markdown 化，便于搜索与复制）

This page explains the different parameters of the bot and how to run it.

Note

If you've used `setup.sh`, don't forget to activate your virtual environment (`source .venv/bin/activate`) before running freqtrade commands.

Up-to-date clock

The clock on the system running the bot must be accurate, synchronized to a NTP server frequently enough to avoid problems with communication to the exchanges.

### Bot commands

```text
usage: freqtrade [-h] [-V]
                 {trade,create-userdir,new-config,show-config,new-strategy,download-data,convert-data,convert-trade-data,trades-to-ohlcv,list-data,backtesting,backtesting-show,backtesting-analysis,edge,hyperopt,hyperopt-list,hyperopt-show,list-exchanges,list-markets,list-pairs,list-strategies,list-hyperoptloss,list-freqaimodels,list-timeframes,show-trades,test-pairlist,convert-db,install-ui,plot-dataframe,plot-profit,webserver,strategy-updater,lookahead-analysis,recursive-analysis} ...

Free, open source crypto trading bot

positional arguments:
  {trade,create-userdir,new-config,show-config,new-strategy,download-data,convert-data,convert-trade-data,trades-to-ohlcv,list-data,backtesting,backtesting-show,backtesting-analysis,edge,hyperopt,hyperopt-list,hyperopt-show,list-exchanges,list-markets,list-pairs,list-strategies,list-hyperoptloss,list-freqaimodels,list-timeframes,show-trades,test-pairlist,convert-db,install-ui,plot-dataframe,plot-profit,webserver,strategy-updater,lookahead-analysis,recursive-analysis}
    trade               Trade module.
    create-userdir      Create user-data directory.
    new-config          Create new config
    show-config         Show resolved config
    new-strategy        Create new strategy
    download-data       Download backtesting data.
    convert-data        Convert candle (OHLCV) data from one format to
                        another.
    convert-trade-data  Convert trade data from one format to another.
    trades-to-ohlcv     Convert trade data to OHLCV data.
    list-data           List downloaded data.
    backtesting         Backtesting module.
    backtesting-show    Show past Backtest results
    backtesting-analysis
                        Backtest Analysis module.
    edge                Edge module. No longer part of Freqtrade
    hyperopt            Hyperopt module.
    hyperopt-list       List Hyperopt results
    hyperopt-show       Show details of Hyperopt results
    list-exchanges      Print available exchanges.
    list-markets        Print markets on exchange.
    list-pairs          Print pairs on exchange.
    list-strategies     Print available strategies.
    list-hyperoptloss   Print available hyperopt loss functions.
    list-freqaimodels   Print available freqAI models.
    list-timeframes     Print available timeframes for the exchange.
    show-trades         Show trades.
    test-pairlist       Test your pairlist configuration.
    convert-db          Migrate database to different system
    install-ui          Install FreqUI
    plot-dataframe      Plot candles with indicators.
    plot-profit         Generate plot showing profits.
    webserver           Webserver module.
    strategy-updater    updates outdated strategy files to the current version
    lookahead-analysis  Check for potential look ahead bias.
    recursive-analysis  Check for potential recursive formula issue.

options:
  -h, --help            show this help message and exit
  -V, --version         show program's version number and exit
```

#### Bot trading commands

```text
usage: freqtrade trade [-h] [-v] [--no-color] [--logfile FILE] [-V] [-c PATH]
                       [-d PATH] [--userdir PATH] [-s NAME]
                       [--strategy-path PATH] [--recursive-strategy-search]
                       [--freqaimodel NAME] [--freqaimodel-path PATH]
                       [--db-url PATH] [--sd-notify] [--dry-run]
                       [--dry-run-wallet DRY_RUN_WALLET] [--fee FLOAT]

options:
  -h, --help            show this help message and exit
  --db-url PATH         Override trades database URL, this is useful in custom
                        deployments (default: `sqlite:///tradesv3.sqlite` for
                        Live Run mode, `sqlite:///tradesv3.dryrun.sqlite` for
                        Dry Run).
  --sd-notify           Notify systemd service manager.
  --dry-run             Enforce dry-run for trading (removes Exchange secrets
                        and simulates trades).
  --dry-run-wallet, --starting-balance DRY_RUN_WALLET
                        Starting balance, used for backtesting / hyperopt and
                        dry-runs.
  --fee FLOAT           Specify fee ratio. Will be applied twice (on trade
                        entry and exit).

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

Strategy arguments:
  -s, --strategy NAME   Specify strategy class name which will be used by the
                        bot.
  --strategy-path PATH  Specify additional strategy lookup path.
  --recursive-strategy-search
                        Recursively search for a strategy in the strategies
                        folder.
  --freqaimodel NAME    Specify a custom freqaimodels.
  --freqaimodel-path PATH
                        Specify additional lookup path for freqaimodels.
```

#### How to specify which configuration file be used?

The bot allows you to select which configuration file you want to use by means of
the `-c/--config` command line option:

```bash
freqtrade trade -c path/far/far/away/config.json
```

Per default, the bot loads the `config.json` configuration file from the current
working directory.

#### How to use multiple configuration files?

The bot allows you to use multiple configuration files by specifying multiple
`-c/--config` options in the command line. Configuration parameters
defined in the latter configuration files override parameters with the same name
defined in the previous configuration files specified in the command line earlier.

For example, you can make a separate configuration file with your key and secret
for the Exchange you use for trading, specify default configuration file with
empty key and secret values while running in the Dry Mode (which does not actually
require them):

```bash
freqtrade trade -c ./config.json
```

and specify both configuration files when running in the normal Live Trade Mode:

```bash
freqtrade trade -c ./config.json -c path/to/secrets/keys.config.json
```

This could help you hide your private Exchange key and Exchange secret on you local machine
by setting appropriate file permissions for the file which contains actual secrets and, additionally,
prevent unintended disclosure of sensitive private data when you publish examples
of your configuration in the project issues or in the Internet.

See more details on this technique with examples in the documentation page on
[configuration](https://www.freqtrade.io/en/stable/configuration/).

#### Where to store custom data

Freqtrade allows the creation of a user-data directory using `freqtrade create-userdir --userdir someDirectory`.
This directory will look as follows:

```text
user_data/
├── backtest_results
├── data
├── hyperopts
├── hyperopt_results
├── plot
└── strategies
```

You can add the entry "user_data_dir" setting to your configuration, to always point your bot to this directory.
Alternatively, pass in `--userdir` to every command.
The bot will fail to start if the directory does not exist, but will create necessary subdirectories.

This directory should contain your custom strategies, custom hyperopts and hyperopt loss functions, backtesting historical data (downloaded using either backtesting command or the download script) and plot outputs.

It is recommended to use version control to keep track of changes to your strategies.

#### How to use --strategy?

This parameter will allow you to load your custom strategy class.
To test the bot installation, you can use the `SampleStrategy` installed by the `create-userdir` subcommand (usually `user_data/strategy/sample_strategy.py`).

The bot will search your strategy file within `user_data/strategies`.
To use other directories, please read the next section about `--strategy-path`.

To load a strategy, simply pass the class name (e.g.: `CustomStrategy`) in this parameter.

**Example:**
In `user_data/strategies` you have a file `my_awesome_strategy.py` which has
a strategy class called `AwesomeStrategy` to load it:

```bash
freqtrade trade --strategy AwesomeStrategy
```

If the bot does not find your strategy file, it will display in an error
message the reason (File not found, or errors in your code).

Learn more about strategy file in
[Strategy Customization](https://www.freqtrade.io/en/stable/strategy-customization/).

#### How to use --strategy-path?

This parameter allows you to add an additional strategy lookup path, which gets
checked before the default locations (The passed path must be a directory!):

```bash
freqtrade trade --strategy AwesomeStrategy --strategy-path /some/directory
```

##### How to install a strategy?

This is very simple. Copy paste your strategy file into the directory
`user_data/strategies` or use `--strategy-path`. And voila, the bot is ready to use it.

#### How to use --db-url?

When you run the bot in Dry-run mode, per default no transactions are
stored in a database. If you want to store your bot actions in a DB
using `--db-url`. This can also be used to specify a custom database
in production mode. Example command:

```bash
freqtrade trade -c config.json --db-url sqlite:///tradesv3.dry_run.sqlite
```

### Next step

The optimal strategy of the bot will change with time depending of the market trends. The next step is to
[Strategy Customization](https://www.freqtrade.io/en/stable/strategy-customization/).

