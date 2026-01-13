# 绘图与可视化（Plotting）

这份文档由 Freqtrade 官方页面离线保存后整理为便于“vibe coding 查阅使用”的 Markdown。

- 来源：https://www.freqtrade.io/en/stable/plotting/
- 离线保存时间：Mon Jan 05 2026 11:41:42 GMT+0800 (中国标准时间)

## 0) 本仓库的推荐运行方式（Windows + uv）

本仓库使用 `uv` 管理环境，且仓库根目录就是 Freqtrade 的 `userdir`，建议命令统一写成：

```bash
uv run freqtrade <命令> --userdir "." <参数...>
```

下文若出现 `freqtrade ...` 的官方示例，你可以直接在前面加上 `uv run`，并补上 `--userdir "."`。

---

## 1) 目录速览（H2）

下面列出原文的一级小节标题（H2），便于你快速定位内容：

- Installation / Setup
- Plot price and indicators
- Plot profit

---

## 2) 原文（自动 Markdown 化，便于搜索与复制）

This page explains how to plot prices, indicators and profits.

Deprecated

The commands described in this page (`plot-dataframe`, `plot-profit`) should be considered deprecated and are in maintenance mode.
This is mostly for the performance problems even medium sized plots can cause, but also because "store a file and open it in a browser" isn't very intuitive from a UI perspective.

While there are no immediate plans to remove them, they are not actively maintained - and may be removed short-term should major changes be required to keep them working.

Please use [FreqUI](https://www.freqtrade.io/en/stable/freq-ui/) for plotting needs, which doesn't struggle with the same performance problems.

### Installation / Setup

Plotting modules use the Plotly library. You can install / upgrade this by running the following command:

```text
pip install -U -r requirements-plot.txt
```

### Plot price and indicators

The `freqtrade plot-dataframe` subcommand shows an interactive graph with three subplots:

- Main plot with candlesticks and indicators following price (sma/ema)

- Volume bars

- Additional indicators as specified by `--indicators2`

Possible arguments:

```text
usage: freqtrade plot-dataframe [-h] [-v] [--no-color] [--logfile FILE] [-V]
                                [-c PATH] [-d PATH] [--userdir PATH] [-s NAME]
                                [--strategy-path PATH]
                                [--recursive-strategy-search]
                                [--freqaimodel NAME] [--freqaimodel-path PATH]
                                [-p PAIRS [PAIRS ...]]
                                [--indicators1 INDICATORS1 [INDICATORS1 ...]]
                                [--indicators2 INDICATORS2 [INDICATORS2 ...]]
                                [--plot-limit INT] [--db-url PATH]
                                [--trade-source {DB,file}]
                                [--export {none,trades,signals}]
                                [--backtest-filename PATH]
                                [--timerange TIMERANGE] [-i TIMEFRAME]
                                [--no-trades]

options:
  -h, --help            show this help message and exit
  -p, --pairs PAIRS [PAIRS ...]
                        Limit command to these pairs. Pairs are space-
                        separated.
  --indicators1 INDICATORS1 [INDICATORS1 ...]
                        Set indicators from your strategy you want in the
                        first row of the graph. Space-separated list. Example:
                        `ema3 ema5`. Default: `['sma', 'ema3', 'ema5']`.
  --indicators2 INDICATORS2 [INDICATORS2 ...]
                        Set indicators from your strategy you want in the
                        third row of the graph. Space-separated list. Example:
                        `fastd fastk`. Default: `['macd', 'macdsignal']`.
  --plot-limit INT      Specify tick limit for plotting. Notice: too high
                        values cause huge files. Default: 750.
  --db-url PATH         Override trades database URL, this is useful in custom
                        deployments (default: `sqlite:///tradesv3.sqlite` for
                        Live Run mode, `sqlite:///tradesv3.dryrun.sqlite` for
                        Dry Run).
  --trade-source {DB,file}
                        Specify the source for trades (Can be DB or file
                        (backtest file)) Default: file
  --export {none,trades,signals}
                        Export backtest results (default: trades).
  --backtest-filename, --export-filename PATH
                        Use this filename for backtest results.Example:
                        `--backtest-
                        filename=backtest_results_2020-09-27_16-20-48.json`.
                        Assumes either `user_data/backtest_results/` or
                        `--export-directory` as base directory.
  --timerange TIMERANGE
                        Specify what timerange of data to use.
  -i, --timeframe TIMEFRAME
                        Specify timeframe (`1m`, `5m`, `30m`, `1h`, `1d`).
  --no-trades           Skip using trades from backtesting file and DB.

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

Example:

```bash
freqtrade plot-dataframe -p BTC/ETH --strategy AwesomeStrategy
```

The `-p/--pairs` argument can be used to specify pairs you would like to plot.

Note

The `freqtrade plot-dataframe` subcommand generates one plot-file per pair.

Specify custom indicators.
Use `--indicators1` for the main plot and `--indicators2` for the subplot below (if values are in a different range than prices).

```bash
freqtrade plot-dataframe --strategy AwesomeStrategy -p BTC/ETH --indicators1 sma ema --indicators2 macd
```

#### Further usage examples

To plot multiple pairs, separate them with a space:

```bash
freqtrade plot-dataframe --strategy AwesomeStrategy -p BTC/ETH XRP/ETH
```

To plot a timerange (to zoom in)

```bash
freqtrade plot-dataframe --strategy AwesomeStrategy -p BTC/ETH --timerange=20180801-20180805
```

To plot trades stored in a database use `--db-url` in combination with `--trade-source DB`:

```bash
freqtrade plot-dataframe --strategy AwesomeStrategy --db-url sqlite:///tradesv3.dry_run.sqlite -p BTC/ETH --trade-source DB
```

To plot trades from a backtesting result, use `--export-filename `

```bash
freqtrade plot-dataframe --strategy AwesomeStrategy --export-filename user_data/backtest_results/backtest-result.json -p BTC/ETH
```

#### Plot dataframe basics

The `plot-dataframe` subcommand requires backtesting data, a strategy and either a backtesting-results file or a database, containing trades corresponding to the strategy.

The resulting plot will have the following elements:

- Green triangles: Buy signals from the strategy. (Note: not every buy signal generates a trade, compare to cyan circles.)

- Red triangles: Sell signals from the strategy. (Also, not every sell signal terminates a trade, compare to red and green squares.)

- Cyan circles: Trade entry points.

- Red squares: Trade exit points for trades with loss or 0% profit.

- Green squares: Trade exit points for profitable trades.

- Indicators with values corresponding to the candle scale (e.g. SMA/EMA), as specified with `--indicators1`.

- Volume (bar chart at the bottom of the main chart).

- Indicators with values in different scales (e.g. MACD, RSI) below the volume bars, as specified with `--indicators2`.

Bollinger Bands

Bollinger bands are automatically added to the plot if the columns `bb_lowerband` and `bb_upperband` exist, and are painted as a light blue area spanning from the lower band to the upper band.

##### Advanced plot configuration

An advanced plot configuration can be specified in the strategy in the `plot_config` parameter.

Additional features when using `plot_config` include:

- Specify colors per indicator

- Specify additional subplots

- Specify indicator pairs to fill area in between

The sample plot configuration below specifies fixed colors for the indicators. Otherwise, consecutive plots may produce different color schemes each time, making comparisons difficult.
It also allows multiple subplots to display both MACD and RSI at the same time.

Plot type can be configured using `type` key. Possible types are:

- `scatter` corresponding to `plotly.graph_objects.Scatter` class (default).

- `bar` corresponding to `plotly.graph_objects.Bar` class.

Extra parameters to `plotly.graph_objects.*` constructor can be specified in `plotly` dict.

Sample configuration with inline comments explaining the process:

```python
@property
def plot_config(self):
    """
        There are a lot of solutions how to build the return dictionary.
        The only important point is the return value.
        Example:
            plot_config = {'main_plot': {}, 'subplots': {}}

    """
    plot_config = {}
    plot_config['main_plot'] = {
        # Configuration for main plot indicators.
        # Assumes 2 parameters, emashort and emalong to be specified.
        f'ema_{self.emashort.value}': {'color': 'red'},
        f'ema_{self.emalong.value}': {'color': '#CCCCCC'},
        # By omitting color, a random color is selected.
        'sar': {},
        # fill area between senkou_a and senkou_b
        'senkou_a': {
            'color': 'green', #optional
            'fill_to': 'senkou_b',
            'fill_label': 'Ichimoku Cloud', #optional
            'fill_color': 'rgba(255,76,46,0.2)', #optional
        },
        # plot senkou_b, too. Not only the area to it.
        'senkou_b': {}
    }
    plot_config['subplots'] = {
         # Create subplot MACD
        "MACD": {
            'macd': {'color': 'blue', 'fill_to': 'macdhist'},
            'macdsignal': {'color': 'orange'},
            'macdhist': {'type': 'bar', 'plotly': {'opacity': 0.9}}
        },
        # Additional subplot RSI
        "RSI": {
            'rsi': {'color': 'red'}
        }
    }

    return plot_config
```

As attribute (former method)
Assigning plot_config is also possible as Attribute (this used to be the default way).
This has the disadvantage that strategy parameters are not available, preventing certain configurations from working.

```text
    plot_config = {
        'main_plot': {
            # Configuration for main plot indicators.
            # Specifies `ema10` to be red, and `ema50` to be a shade of gray
            'ema10': {'color': 'red'},
            'ema50': {'color': '#CCCCCC'},
            # By omitting color, a random color is selected.
            'sar': {},
        # fill area between senkou_a and senkou_b
        'senkou_a': {
            'color': 'green', #optional
            'fill_to': 'senkou_b',
            'fill_label': 'Ichimoku Cloud', #optional
            'fill_color': 'rgba(255,76,46,0.2)', #optional
        },
        # plot senkou_b, too. Not only the area to it.
        'senkou_b': {}
        },
        'subplots': {
            # Create subplot MACD
            "MACD": {
                'macd': {'color': 'blue', 'fill_to': 'macdhist'},
                'macdsignal': {'color': 'orange'},
                'macdhist': {'type': 'bar', 'plotly': {'opacity': 0.9}}
            },
            # Additional subplot RSI
            "RSI": {
                'rsi': {'color': 'red'}
            }
        }
    }
```

Note

The above configuration assumes that `ema10`, `ema50`, `senkou_a`, `senkou_b`,
`macd`, `macdsignal`, `macdhist` and `rsi` are columns in the DataFrame created by the strategy.

Warning

`plotly` arguments are only supported with plotly library and will not work with freq-ui.

Trade position adjustments

If `position_adjustment_enable` / `adjust_trade_position()` is used, the trade initial buy price is averaged over multiple orders and the trade start price will most likely appear outside the candle range.

### Plot profit

The `plot-profit` subcommand shows an interactive graph with three plots:

- Average closing price for all pairs.

- The summarized profit made by backtesting.
Note that this is not the real-world profit, but more of an estimate.

- Profit for each individual pair.

- Parallelism of trades.

- Underwater (Periods of drawdown).

The first graph is good to get a grip of how the overall market progresses.

The second graph will show if your algorithm works or doesn't.
Perhaps you want an algorithm that steadily makes small profits, or one that acts less often, but makes big swings.
This graph will also highlight the start (and end) of the Max drawdown period.

The third graph can be useful to spot outliers, events in pairs that cause profit spikes.

The forth graph can help you analyze trade parallelism, showing how often max_open_trades have been maxed out.

Possible options for the `freqtrade plot-profit` subcommand:

```text
usage: freqtrade plot-profit [-h] [-v] [--no-color] [--logfile FILE] [-V]
                             [-c PATH] [-d PATH] [--userdir PATH] [-s NAME]
                             [--strategy-path PATH]
                             [--recursive-strategy-search]
                             [--freqaimodel NAME] [--freqaimodel-path PATH]
                             [-p PAIRS [PAIRS ...]] [--timerange TIMERANGE]
                             [--export {none,trades,signals}]
                             [--backtest-filename PATH] [--db-url PATH]
                             [--trade-source {DB,file}] [-i TIMEFRAME]
                             [--auto-open]

options:
  -h, --help            show this help message and exit
  -p, --pairs PAIRS [PAIRS ...]
                        Limit command to these pairs. Pairs are space-
                        separated.
  --timerange TIMERANGE
                        Specify what timerange of data to use.
  --export {none,trades,signals}
                        Export backtest results (default: trades).
  --backtest-filename, --export-filename PATH
                        Use this filename for backtest results.Example:
                        `--backtest-
                        filename=backtest_results_2020-09-27_16-20-48.json`.
                        Assumes either `user_data/backtest_results/` or
                        `--export-directory` as base directory.
  --db-url PATH         Override trades database URL, this is useful in custom
                        deployments (default: `sqlite:///tradesv3.sqlite` for
                        Live Run mode, `sqlite:///tradesv3.dryrun.sqlite` for
                        Dry Run).
  --trade-source {DB,file}
                        Specify the source for trades (Can be DB or file
                        (backtest file)) Default: file
  -i, --timeframe TIMEFRAME
                        Specify timeframe (`1m`, `5m`, `30m`, `1h`, `1d`).
  --auto-open           Automatically open generated plot.

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

The `-p/--pairs` argument, can be used to limit the pairs that are considered for this calculation.

Examples:

Use custom backtest-export file

```bash
freqtrade plot-profit  -p LTC/BTC --export-filename user_data/backtest_results/backtest-result.json
```

Use custom database

```bash
freqtrade plot-profit  -p LTC/BTC --db-url sqlite:///tradesv3.sqlite --trade-source DB
```

```bash
freqtrade --datadir user_data/data/binance_save/ plot-profit -p LTC/BTC
```

