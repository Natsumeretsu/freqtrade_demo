# 策略快速开始（Freqtrade Strategies 101: A Quick Start for Strategy Development）

这份文档由 Freqtrade 官方页面离线保存后整理为便于“vibe coding 查阅使用”的 Markdown。

- 来源：https://www.freqtrade.io/en/stable/strategy-101/
- 离线保存时间：Mon Jan 05 2026 11:35:31 GMT+0800 (中国标准时间)

## 0) 本仓库的推荐运行方式（Windows + uv）

本仓库使用 `uv` 管理环境，且仓库根目录就是 Freqtrade 的 `userdir`，建议命令统一写成：

```bash
uv run freqtrade <命令> --userdir "." <参数...>
```

下文若出现 `freqtrade ...` 的官方示例，你可以直接在前面加上 `uv run`，并补上 `--userdir "."`。

---

## 1) 目录速览（H2）

下面列出原文的一级小节标题（H2），便于你快速定位内容：

- Required Knowledge
- Structure of a Basic Strategy
- A simple strategy
- Making trades
- Backtesting and forward testing
- Controlling or monitoring a running bot
- Final Thoughts
- Conclusion

---

## 2) 原文（自动 Markdown 化，便于搜索与复制）

For the purposes of this quick start, we are assuming you are familiar with the basics of trading, and have read the
[Freqtrade basics](https://www.freqtrade.io/en/stable/bot-basics/) page.

### Required Knowledge

A strategy in Freqtrade is a Python class that defines the logic for buying and selling cryptocurrency `assets`.

Assets are defined as `pairs`, which represent the `coin` and the `stake`. The coin is the asset you are trading using another currency as the stake.

Data is supplied by the exchange in the form of `candles`, which are made up of a six values: `date`, `open`, `high`, `low`, `close` and `volume`.

`Technical analysis` functions analyse the candle data using various computational and statistical formulae, and produce secondary values called `indicators`.

Indicators are analysed on the asset pair candles to generate `signals`.

Signals are turned into `orders` on a cryptocurrency `exchange`, i.e. `trades`.

We use the terms `entry` and `exit` instead of `buying` and `selling` because Freqtrade supports both `long` and `short` trades.

- **long**: You buy the coin based on a stake, e.g. buying the coin BTC using USDT as your stake, and you make a profit by selling the coin at a higher rate than you paid for. In long trades, profits are made by the coin value going up versus the stake.

- **short**: You borrow capital from the exchange in the form of the coin, and you pay back the stake value of the coin later. In short trades profits are made by the coin value going down versus the stake (you pay the loan off at a lower rate).

Whilst Freqtrade supports spot and futures markets for certain exchanges, for simplicity we will focus on spot (long) trades only.

### Structure of a Basic Strategy

#### Main dataframe

Freqtrade strategies use a tabular data structure with rows and columns known as a `dataframe` to generate signals to enter and exit trades.

Each pair in your configured pairlist has its own dataframe. Dataframes are indexed by the `date` column, e.g. `2024-06-31 12:00`.

The next 5 columns represent the `open`, `high`, `low`, `close` and `volume` (OHLCV) data.

#### Populate indicator values

The `populate_indicators` function adds columns to the dataframe that represent the technical analysis indicator values.

Examples of common indicators include Relative Strength Index, Bollinger Bands, Money Flow Index, Moving Average, and Average True Range.

Columns are added to the dataframe by calling technical analysis functions, e.g. ta-lib's RSI function `ta.RSI()`, and assigning them to a column name, e.g. `rsi`

```text
dataframe['rsi'] = ta.RSI(dataframe)
```

Technical Analysis libraries
Different libraries work in different ways to generate indicator values. Please check the documentation of each library to understand
how to integrate it into your strategy. You can also check the [Freqtrade example strategies](https://github.com/freqtrade/freqtrade-strategies) to give you ideas.

#### Populate entry signals

The `populate_entry_trend` function defines conditions for an entry signal.

The dataframe column `enter_long` is added to the dataframe, and when a value of `1` is in this column, Freqtrade sees an entry signal.

Shorting
To enter short trades, use the `enter_short` column.

#### Populate exit signals

The `populate_exit_trend` function defines conditions for an exit signal.

The dataframe column `exit_long` is added to the dataframe, and when a value of `1` is in this column, Freqtrade sees an exit signal.

Shorting
To exit short trades, use the `exit_short` column.

### A simple strategy

Here is a minimal example of a Freqtrade strategy:

```python
from freqtrade.strategy import IStrategy
from pandas import DataFrame
import talib.abstract as ta

class MyStrategy(IStrategy):

    timeframe = '15m'

    # set the initial stoploss to -10%
    stoploss = -0.10

    # exit profitable positions at any time when the profit is greater than 1%
    minimal_roi = {"0": 0.01}

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # generate values for technical analysis indicators
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # generate entry signals based on indicator values
        dataframe.loc[
            (dataframe['rsi'] < 30),
            'enter_long'] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # generate exit signals based on indicator values
        dataframe.loc[
            (dataframe['rsi'] > 70),
            'exit_long'] = 1

        return dataframe
```

### Making trades

When a signal is found (a `1` in an entry or exit column), Freqtrade will attempt to make an order, i.e. a `trade` or `position`.

Each new trade position takes up a `slot`. Slots represent the maximum number of concurrent new trades that can be opened.

The number of slots is defined by the `max_open_trades` [configuration](https://www.freqtrade.io/en/stable/configuration/) option.

However, there can be a range of scenarios where generating a signal does not always create a trade order. These include:

- not enough remaining stake to buy an asset, or funds in your wallet to sell an asset (including any fees)

- not enough remaining free slots for a new trade to be opened (the number of positions you have open equals the `max_open_trades` option)

- there is already an open trade for a pair (Freqtrade cannot stack positions - however it can [adjust existing positions](https://www.freqtrade.io/en/stable/strategy-callbacks/#adjust-trade-position))

- if an entry and exit signal is present on the same candle, they are considered as [colliding](https://www.freqtrade.io/en/stable/strategy-customization/#colliding-signals), and no order will be raised

- the strategy actively rejects the trade order due to logic you specify by using one of the relevant [entry](https://www.freqtrade.io/en/stable/strategy-callbacks/#trade-entry-buy-order-confirmation) or [exit](https://www.freqtrade.io/en/stable/strategy-callbacks/#trade-exit-sell-order-confirmation) callbacks

Read through the [strategy customization](https://www.freqtrade.io/en/stable/strategy-customization/) documentation for more details.

### Backtesting and forward testing

Strategy development can be a long and frustrating process, as turning our human "gut instincts" into a working computer-controlled
("algo") strategy is not always straightforward.

Therefore a strategy should be tested to verify that it is going to work as intended.

Freqtrade has two testing modes:

- **backtesting**: using historical data that you [download from an exchange](https://www.freqtrade.io/en/stable/data-download/), backtesting is a quick way to assess performance of a strategy. However, it can be very easy to distort results so a strategy will look a lot more profitable than it really is. Check the [backtesting documentation](https://www.freqtrade.io/en/stable/backtesting/) for more information.

- **dry run**: often referred to as *forward testing*, dry runs use real time data from the exchange. However, any signals that would result in trades are tracked as normal by Freqtrade, but do not have any trades opened on the exchange itself. Forward testing runs in real time, so whilst it takes longer to get results it is a much more reliable indicator of **potential** performance than backtesting.

Dry runs are enabled by setting `dry_run` to true in your [configuration](https://www.freqtrade.io/en/stable/configuration/#using-dry-run-mode).

Backtests can be very inaccurate

There are many reasons why backtest results may not match reality. Please check the [backtesting assumptions](https://www.freqtrade.io/en/stable/backtesting/#assumptions-made-by-backtesting) and [common strategy mistakes](https://www.freqtrade.io/en/stable/strategy-customization/#common-mistakes-when-developing-strategies) documentation.
Some websites that list and rank Freqtrade strategies show impressive backtest results. Do not assume these results are achieveable or realistic.

Useful commands
Freqtrade includes two useful commands to check for basic flaws in strategies: [lookahead-analysis](https://www.freqtrade.io/en/stable/lookahead-analysis/) and [recursive-analysis](https://www.freqtrade.io/en/stable/recursive-analysis/).

#### Assessing backtesting and dry run results

Always dry run your strategy after backtesting it to see if backtesting and dry run results are sufficiently similar.

If there is any significant difference, verify that your entry and exit signals are consistent and appear on the same candles between the two modes. However, there will always be differences between dry runs and backtests:

- Backtesting assumes all orders fill. In dry runs this might not be the case if using limit orders or there is no volume on the exchange.

- Following an entry signal on candle close, backtesting assumes trades enter at the next candle's open price (unless you have custom pricing callbacks in your strategy). In dry runs, there is often a delay between signals and trades opening.
 This is because when new candles come in on your main timeframe, e.g. every 5 minutes, it takes time for Freqtrade to analyse all pair dataframes. Therefore, Freqtrade will attempt to open trades a few seconds (ideally a small a delay as possible)
 after candle open.

- As entry rates in dry runs might not match backtesting, this means profit calculations will also differ. Therefore, it is normal if ROI, stoploss, trailing stoploss and callback exits are not identical.

- The more computational "lag" you have between new candles coming in and your signals being raised and trades being opened will result in greater price unpredictability. Make sure your computer is powerful enough to process the data for the number
 of pairs you have in your pairlist within a reasonable time. Freqtrade will warn you in the logs if there are significant data processing delays.

### Controlling or monitoring a running bot

Once your bot is running in dry or live mode, Freqtrade has six mechanisms to control or monitor a running bot:

- **[FreqUI](https://www.freqtrade.io/en/stable/freq-ui/)**: The easiest to get started with, FreqUI is a web interface to see and control current activity of your bot.

- **[Telegram](https://www.freqtrade.io/en/stable/telegram-usage/)**: On mobile devices, Telegram integration is available to get alerts about your bot activity and to control certain aspects.

- **[FTUI](https://github.com/freqtrade/ftui)**: FTUI is a terminal (command line) interface to Freqtrade, and allows monitoring of a running bot only.

- **[freqtrade-client](https://www.freqtrade.io/en/stable/rest-api/#consuming-the-api)**: A python implementation of the REST API, making it easy to make requests and consume bot responses from your python apps or the command line.

- **[REST API endpoints](https://www.freqtrade.io/en/stable/rest-api/#available-endpoints)**: The REST API allows programmers to develop their own tools to interact with a Freqtrade bot.

- **[Webhooks](https://www.freqtrade.io/en/stable/webhook-config/)**: Freqtrade can send information to other services, e.g. discord, by webhooks.

#### Logs

Freqtrade generates extensive debugging logs to help you understand what's happening. Please familiarise yourself with the information and error messages you might see in your bot logs.

Logging by default occurs on standard out (the command line). If you want to write out to a file instead, many freqtrade commands, including the `trade` command, accept the `--logfile` option to write to a file.

Check the [FAQ](https://www.freqtrade.io/en/stable/faq/#how-do-i-search-the-bot-logs-for-something) for examples.

### Final Thoughts

Algo trading is difficult, and most public strategies are not good performers due to the time and effort to make a strategy work profitably in multiple scenarios.

Therefore, taking public strategies and using backtests as a way to assess performance is often problematic. However, Freqtrade provides useful ways to help you make decisions and do your due diligence.

There are many different ways to achieve profitability, and there is no one single tip, trick or config option that will fix a poorly performing strategy.

Freqtrade is an open source platform with a large and helpful community - make sure to visit our [discord channel](https://discord.gg/p7nuUNVfP7) to discuss your strategy with others!

As always, only invest what you are willing to lose.

### Conclusion

Developing a strategy in Freqtrade involves defining entry and exit signals based on technical indicators. By following the structure and methods outlined above, you can create and test your own trading strategies.

Common questions and answers are available on our [FAQ](https://www.freqtrade.io/en/stable/faq/).

To continue, refer to the more in-depth [Freqtrade strategy customization documentation](https://www.freqtrade.io/en/stable/strategy-customization/).

