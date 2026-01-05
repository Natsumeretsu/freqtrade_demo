# Freqtrade（文档首页）（Home）

这份文档由 Freqtrade 官方页面离线保存后整理为便于“vibe coding 查阅使用”的 Markdown。

- 来源：https://www.freqtrade.io/en/stable/
- 离线保存时间：Mon Jan 05 2026 11:34:30 GMT+0800 (中国标准时间)

## 0) 本仓库的推荐运行方式（Windows + uv）

本仓库使用 `uv` 管理环境，且仓库根目录就是 Freqtrade 的 `userdir`，建议命令统一写成：

```bash
uv run freqtrade <命令> --userdir "." <参数...>
```

下文若出现 `freqtrade ...` 的官方示例，你可以直接在前面加上 `uv run`，并补上 `--userdir "."`。

---

## 1) 目录速览（H2）

下面列出原文的一级小节标题（H2），便于你快速定位内容：

- Introduction
- Features
- Supported exchange marketplaces
- Community showcase
- Requirements
- Support
- Ready to try?

---

## 2) 原文（自动 Markdown 化，便于搜索与复制）

https://github.com/freqtrade/freqtrade/actions/workflows/ci.yml
https://doi.org/10.21105/joss.04864
https://coveralls.io/github/freqtrade/freqtrade?branch=develop

[Star](https://github.com/freqtrade/freqtrade)
[Fork](https://github.com/freqtrade/freqtrade/fork)
[Download](https://github.com/freqtrade/freqtrade/archive/stable.zip)

### Introduction

Freqtrade is a free and open source crypto trading bot written in Python. It is designed to support all major exchanges and be controlled via Telegram or webUI. It contains backtesting, plotting and money management tools as well as strategy optimization by machine learning.

DISCLAIMER

This software is for educational purposes only. Do not risk money which you are afraid to lose. USE THE SOFTWARE AT YOUR OWN RISK. THE AUTHORS AND ALL AFFILIATES ASSUME NO RESPONSIBILITY FOR YOUR TRADING RESULTS.

Always start by running a trading bot in Dry-run and do not engage money before you understand how it works and what profit/loss you should expect.

We strongly recommend you to have basic coding skills and Python knowledge. Do not hesitate to read the source code and understand the mechanisms of this bot, algorithms and techniques implemented in it.

### Features

- Develop your Strategy: Write your strategy in python, using [pandas](https://pandas.pydata.org/). Example strategies to inspire you are available in the [strategy repository](https://github.com/freqtrade/freqtrade-strategies).

- Download market data: Download historical data of the exchange and the markets your may want to trade with.

- Backtest: Test your strategy on downloaded historical data.

- Optimize: Find the best parameters for your strategy using hyperoptimization which employs machine learning methods. You can optimize buy, sell, take profit (ROI), stop-loss and trailing stop-loss parameters for your strategy.

- Select markets: Create your static list or use an automatic one based on top traded volumes and/or prices (not available during backtesting). You can also explicitly blacklist markets you don't want to trade.

- Run: Test your strategy with simulated money (Dry-Run mode) or deploy it with real money (Live-Trade mode).

- Control/Monitor: Use Telegram or a WebUI (start/stop the bot, show profit/loss, daily summary, current open trades results, etc.).

- Analyze: Further analysis can be performed on either Backtesting data or Freqtrade trading history (SQL database), including automated standard plots, and methods to load the data into [interactive environments](https://www.freqtrade.io/en/stable/data-analysis/).

### Supported exchange marketplaces

Please read the [exchange specific notes](https://www.freqtrade.io/en/stable/exchanges/) to learn about eventual, special configurations needed for each exchange.

-  [Binance](https://www.binance.com/)

-  [BingX](https://bingx.com/invite/0EM9RX)

-  [Bitget](https://www.bitget.com/)

-  [Bitmart](https://bitmart.com/)

-  [Bybit](https://bybit.com/)

-  [Gate.io](https://www.gate.io/ref/6266643)

-  [HTX](https://www.htx.com/)

-  [Hyperliquid](https://hyperliquid.xyz/) (A decentralized exchange, or DEX)

-  [Kraken](https://kraken.com/)

-  [OKX](https://okx.com/)

-  [MyOKX](https://okx.com/) (OKX EEA)

-  [potentially many others through](https://github.com/ccxt/ccxt/). *(We cannot guarantee they will work)*

#### Supported Futures Exchanges (experimental)

-  [Binance](https://www.binance.com/)

-  [Bitget](https://www.bitget.com/)

-  [Bybit](https://bybit.com/)

-  [Gate.io](https://www.gate.io/ref/6266643)

-  [Hyperliquid](https://hyperliquid.xyz/) (A decentralized exchange, or DEX)

-  [OKX](https://okx.com/)

Please make sure to read the [exchange specific notes](https://www.freqtrade.io/en/stable/exchanges/), as well as the [trading with leverage](https://www.freqtrade.io/en/stable/leverage/) documentation before diving in.

#### Community tested

Exchanges confirmed working by the community:

-  [Bitvavo](https://bitvavo.com/)

-  [Kucoin](https://www.kucoin.com/)

### Community showcase

This section will highlight a few projects from members of the community.

Note

The projects below are for the most part not maintained by the freqtrade team, therefore use your own caution before using them.

- [Example freqtrade strategies](https://github.com/freqtrade/freqtrade-strategies/)

- [FrequentHippo - Statistics of dry/live runs and backtests](http://frequenthippo.ddns.net/) (by hippocritical).

- [Online pairlist generator](https://remotepairlist.com/) (by Blood4rc).

- [Freqtrade Backtesting Project](https://strat.ninja/) (by Blood4rc).

- [Freqtrade analysis notebook](https://github.com/froggleston/freqtrade_analysis_notebook) (by Froggleston).

- [FTUI - Terminal UI for freqtrade](https://github.com/freqtrade/ftui) (by Froggleston).

- [Bot Academy](https://botacademy.ddns.net/) (by stash86) - Blog about crypto bot projects.

### Requirements

#### Hardware requirements

To run this bot we recommend you a linux cloud instance with a minimum of:

- 2GB RAM

- 1GB disk space

- 2vCPU

#### Software requirements

- Docker (Recommended)

Alternatively

- Python 3.11+

- pip (pip3)

- git

- TA-Lib

- virtualenv (Recommended)

### Support

#### Help / Discord

For any questions not covered by the documentation or for further information about the bot, or to simply engage with like-minded individuals, we encourage you to join the Freqtrade [discord server](https://discord.gg/p7nuUNVfP7).

### Ready to try?

Begin by reading the installation guide [for docker](https://www.freqtrade.io/en/stable/docker_quickstart/) (recommended), or for [installation without docker](https://www.freqtrade.io/en/stable/installation/).

