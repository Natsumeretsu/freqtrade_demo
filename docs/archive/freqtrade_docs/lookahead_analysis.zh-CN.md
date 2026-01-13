# 前视偏差分析（Lookahead analysis）

这份文档由 Freqtrade 官方页面离线保存后整理为便于“vibe coding 查阅使用”的 Markdown。

- 来源：https://www.freqtrade.io/en/stable/lookahead-analysis/
- 离线保存时间：Mon Jan 05 2026 11:42:44 GMT+0800 (中国标准时间)

## 0) 本仓库的推荐运行方式（Windows + uv）

本仓库使用 `uv` 管理环境，且仓库根目录就是 Freqtrade 的 `userdir`，建议命令统一写成：

```bash
uv run freqtrade <命令> --userdir "." <参数...>
```

下文若出现 `freqtrade ...` 的官方示例，你可以直接在前面加上 `uv run`，并补上 `--userdir "."`。

---

## 1) 目录速览（H2）

下面列出原文的一级小节标题（H2），便于你快速定位内容：

- Lookahead-analysis command reference

---

## 2) 原文（自动 Markdown 化，便于搜索与复制）

This page explains how to validate your strategy in terms of lookahead bias.

Lookahead bias is the bane of any strategy since it is sometimes very easy to introduce this bias, but can be very hard to detect.

Backtesting initializes all timestamps (loads the whole dataframe into memory) and calculates all indicators at once.
This means that if your indicators or entry/exit signals look into future candles, this will falsify your backtest.

The `lookahead-analysis` command requires historic data to be available.
To learn how to get data for the pairs and exchange you're interested in,
head over to the [Data Downloading](https://www.freqtrade.io/en/stable/data-download/) section of the documentation.
`lookahead-analysis` also supports freqai strategies.

This command internally chains backtests and pokes at the strategy to provoke it to show lookahead bias.
This is done by not looking at the strategy code itself, but at changed indicator values and moved entries/exits compared to the full backtest.

`lookahead-analysis` can use the typical options of [Backtesting](https://www.freqtrade.io/en/stable/backtesting/), but forces the following options:

- `--cache` is forced to "none".

- `--max-open-trades` is forced to be at least equal to the number of pairs.

- `--dry-run-wallet` is forced to be basically infinite (1 billion).

- `--stake-amount` is forced to be a static 10000 (10k).

- `--enable-protections` is forced to be off.

- `order_types` are forced to be "market" (late entries) unless `--lookahead-allow-limit-orders` is set.

These are set to avoid users accidentally generating false positives.

### Lookahead-analysis command reference

```text
usage: freqtrade lookahead-analysis [-h] [-v] [--no-color] [--logfile FILE]
                                    [-V] [-c PATH] [-d PATH] [--userdir PATH]
                                    [-s NAME] [--strategy-path PATH]
                                    [--recursive-strategy-search]
                                    [--freqaimodel NAME]
                                    [--freqaimodel-path PATH] [-i TIMEFRAME]
                                    [--timerange TIMERANGE]
                                    [--data-format-ohlcv {json,jsongz,feather,parquet}]
                                    [--max-open-trades INT]
                                    [--stake-amount STAKE_AMOUNT]
                                    [--fee FLOAT] [-p PAIRS [PAIRS ...]]
                                    [--enable-protections]
                                    [--enable-dynamic-pairlist]
                                    [--dry-run-wallet DRY_RUN_WALLET]
                                    [--timeframe-detail TIMEFRAME_DETAIL]
                                    [--strategy-list STRATEGY_LIST [STRATEGY_LIST ...]]
                                    [--export {none,trades,signals}]
                                    [--backtest-filename PATH]
                                    [--backtest-directory PATH]
                                    [--freqai-backtest-live-models]
                                    [--minimum-trade-amount INT]
                                    [--targeted-trade-amount INT]
                                    [--lookahead-analysis-exportfilename LOOKAHEAD_ANALYSIS_EXPORTFILENAME]
                                    [--allow-limit-orders]

options:
  -h, --help            show this help message and exit
  -i, --timeframe TIMEFRAME
                        Specify timeframe (`1m`, `5m`, `30m`, `1h`, `1d`).
  --timerange TIMERANGE
                        Specify what timerange of data to use.
  --data-format-ohlcv {json,jsongz,feather,parquet}
                        Storage format for downloaded candle (OHLCV) data.
                        (default: `feather`).
  --max-open-trades INT
                        Override the value of the `max_open_trades`
                        configuration setting.
  --stake-amount STAKE_AMOUNT
                        Override the value of the `stake_amount` configuration
                        setting.
  --fee FLOAT           Specify fee ratio. Will be applied twice (on trade
                        entry and exit).
  -p, --pairs PAIRS [PAIRS ...]
                        Limit command to these pairs. Pairs are space-
                        separated.
  --enable-protections, --enableprotections
                        Enable protections for backtesting. Will slow
                        backtesting down by a considerable amount, but will
                        include configured protections
  --enable-dynamic-pairlist
                        Enables dynamic pairlist refreshes in backtesting. The
                        pairlist will be generated for each new candle if
                        you're using a pairlist handler that supports this
                        feature, for example, ShuffleFilter.
  --dry-run-wallet, --starting-balance DRY_RUN_WALLET
                        Starting balance, used for backtesting / hyperopt and
                        dry-runs.
  --timeframe-detail TIMEFRAME_DETAIL
                        Specify detail timeframe for backtesting (`1m`, `5m`,
                        `30m`, `1h`, `1d`).
  --strategy-list STRATEGY_LIST [STRATEGY_LIST ...]
                        Provide a space-separated list of strategies to
                        backtest. Please note that timeframe needs to be set
                        either in config or via command line. When using this
                        together with `--export trades`, the strategy-name is
                        injected into the filename (so `backtest-data.json`
                        becomes `backtest-data-SampleStrategy.json`
  --export {none,trades,signals}
                        Export backtest results (default: trades).
  --backtest-filename, --export-filename PATH
                        Use this filename for backtest results.Example:
                        `--backtest-
                        filename=backtest_results_2020-09-27_16-20-48.json`.
                        Assumes either `user_data/backtest_results/` or
                        `--export-directory` as base directory.
  --backtest-directory, --export-directory PATH
                        Directory to use for backtest results. Example:
                        `--export-directory=user_data/backtest_results/`.
  --freqai-backtest-live-models
                        Run backtest with ready models.
  --minimum-trade-amount INT
                        Minimum trade amount for lookahead-analysis
  --targeted-trade-amount INT
                        Targeted trade amount for lookahead analysis
  --lookahead-analysis-exportfilename LOOKAHEAD_ANALYSIS_EXPORTFILENAME
                        Use this csv-filename to store lookahead-analysis-
                        results
  --allow-limit-orders  Allow limit orders in lookahead analysis (could cause
                        false positives in lookahead analysis results).

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

Note

The above output was reduced to options that `lookahead-analysis` adds on top of regular backtesting commands.

#### Introduction

Many strategies, without the programmer knowing, have fallen prey to lookahead bias.
This typically makes the strategy backtest look profitable, sometimes to extremes, but this is not realistic as the strategy is "cheating" by looking at data it would not have in dry or live modes.

The reason why strategies can "cheat" is because the freqtrade backtesting process populates the full dataframe including all candle timestamps at the outset.
If the programmer is not careful or oblivious how things work internally
(which sometimes can be really hard to find out) then the strategy will look into the future.

This command is made to try to verify the validity in the form of the aforementioned lookahead bias.

#### How does the command work?

It will start with a backtest of all pairs to generate a baseline for indicators and entries/exits.
After this initial backtest runs, it will look if the `minimum-trade-amount` is met and if not cancel the lookahead-analysis for this strategy.

If this happens, use a wider timerange to get more trades for the analysis, or use a timerange where more trades occur.

After setting the baseline it will then do additional backtest runs for every entry and exit separately.

When these verification backtests complete, it will compare both dataframes (baseline and sliced) for any difference in columns' value and report the bias.
After all signals have been verified or falsified a result table will be generated for the user to see.

#### How to find and remove bias? How can I salvage a biased strategy?

If you found a biased strategy online and want to have the same results, just without bias,
then you will be out of luck most of the time.
Usually the bias in the strategy is THE driving factor for "too good to be true" profits.
Removing conditions or indicators that push the profits up from bias will usually make the strategy significantly worse.
You might be able to salvage it partially if the biased indicators or conditions are not the core of the strategy, or there
are other entry and exit signals that are not biased.

#### Examples of lookahead-bias

- `shift(-10)` looks 10 candles into the future.

- Using `iloc[]` in populate_* functions to access a specific row in the dataframe.

- For-loops are prone to introduce lookahead bias if you don't tightly control which numbers are looped through.

- Aggregation functions like `.mean()`, `.min()` and `.max()`, without a rolling window,
 will calculate the value over the **whole** dataframe, so the signal candle will "see" a value including future candles.
 A non-biased example would be to look back candles using `rolling()` instead:
 e.g. `dataframe['volume_mean_12'] = dataframe['volume'].rolling(12).mean()`

- `ta.MACD(dataframe, 12, 26, 1)` will introduce bias with a signalperiod of 1.

#### What do the columns in the results table mean?

- `filename`: name of the checked strategy file

- `strategy`: checked strategy class name

- `has_bias`: result of the lookahead-analysis. `No` would be good, `Yes` would be bad.

- `total_signals`: number of checked signals (default is 20)

- `biased_entry_signals`: found bias in that many entries

- `biased_exit_signals`: found bias in that many exits

- `biased_indicators`: shows you the indicators themselves that are defined in populate_indicators

You might get false positives in the `biased_exit_signals` if you have biased entry signals paired with those exits.
However, a biased entry will usually result in a biased exit too,
even if the exit itself does not produce the bias -
especially if your entry and exit conditions use the same biased indicator.

**Address the bias in the entries first, then address the exits.**

#### Caveats

- `lookahead-analysis` can only verify / falsify the trades it calculated and verified.
If the strategy has many different signals / signal types, it's up to you to select appropriate parameters to ensure that all signals have triggered at least once. Signals that are not triggered will not have been verified.

This would lead to a false-negative, i.e. the strategy will be reported as non-biased.

- `lookahead-analysis` has access to the same backtesting options and this can introduce problems.
Please don't use any options like enabling position stacking as this will distort the number of checked signals.
If you decide to do so, then make doubly sure that you won't ever run out of `max_open_trades` slots,
and that you have enough capital in the backtest wallet configuration.

- limit orders in combination with `custom_entry_price()` and `custom_exit_price()` callbacks can cause late / delayed entries and exists, causing false positives.
To avoid this - market orders are forced for this command. This implicitly means that `custom_entry_price()` and `custom_exit_price()` callbacks are not called.
Using `--lookahead-allow-limit-orders` will skip the override and use your configured order types - however has shown to eventually produce false positives.

- In the results table, the `biased_indicators` column
will falsely flag FreqAI target indicators defined in `set_freqai_targets()` as biased.

**These are not biased and can safely be ignored.**

