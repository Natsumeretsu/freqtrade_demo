# freqUI 界面（FreqUI）

这份文档由 Freqtrade 官方页面离线保存后整理为便于“vibe coding 查阅使用”的 Markdown。

- 来源：https://www.freqtrade.io/en/stable/freq-ui/
- 离线保存时间：Mon Jan 05 2026 11:38:20 GMT+0800 (中国标准时间)

## 0) 本仓库的推荐运行方式（Windows + uv）

本仓库使用 `uv` 管理环境，且仓库根目录就是 Freqtrade 的 `userdir`，建议命令统一写成：

```bash
uv run freqtrade <命令> --userdir "." <参数...>
```

下文若出现 `freqtrade ...` 的官方示例，你可以直接在前面加上 `uv run`，并补上 `--userdir "."`。

---

## 1) 目录速览（H2）

下面列出原文的一级小节标题（H2），便于你快速定位内容：

- Configuration
- UI
- Webserver mode
- CORS

---

## 2) 原文（自动 Markdown 化，便于搜索与复制）

Freqtrade provides a builtin webserver, which can serve [FreqUI](https://github.com/freqtrade/frequi), the freqtrade frontend.

By default, the UI is automatically installed as part of the installation (script, docker).
freqUI can also be manually installed by using the `freqtrade install-ui` command.
This same command can also be used to update freqUI to new releases.

Once the bot is started in trade / dry-run mode (with `freqtrade trade`) - the UI will be available under the configured API port (by default `http://127.0.0.1:8080`).

Looking to contribute to freqUI?
Developers should not use this method, but instead clone the corresponding use the method described in the [freqUI repository](https://github.com/freqtrade/frequi) to get the source-code of freqUI. A working installation of node will be required to build the frontend.

freqUI is not required to run freqtrade

freqUI is an optional component of freqtrade, and is not required to run the bot.
It is a frontend that can be used to monitor the bot and to interact with it - but freqtrade itself will work perfectly fine without it.

### Configuration

FreqUI does not have it's own configuration file - but assumes a working setup for the [rest-api](https://www.freqtrade.io/en/stable/rest-api/) is available.
Please refer to the corresponding documentation page to get setup with freqUI

### UI

FreqUI is a modern, responsive web application that can be used to monitor and interact with your bot.

FreqUI provides a light, as well as a dark theme.
Themes can be easily switched via a prominent button at the top of the page.
The theme of the screenshots on this page will adapt to the selected documentation Theme, so to see the dark (or light) version, please switch the theme of the Documentation.

#### Login

The below screenshot shows the login screen of freqUI.

CORS

The Cors error shown in this screenshot is due to the fact that the UI is running on a different port than the API, and [CORS](#cors) has not been setup correctly yet.

#### Trade view

The trade view allows you to visualize the trades that the bot is making and to interact with the bot.
On this page, you can also interact with the bot by starting and stopping it and - if configured - force trade entries and exits.

#### Plot Configurator

FreqUI Plots can be configured either via a `plot_config` configuration object in the strategy (which can be loaded via "from strategy" button) or via the UI.
Multiple plot configurations can be created and switched at will - allowing for flexible, different views into your charts.

The plot configuration can be accessed via the "Plot Configurator" (Cog icon) button in the top right corner of the trade view.

#### Settings

Several UI related settings can be changed by accessing the settings page.

Things you can change (among others):

- Timezone of the UI

- Visualization of open trades as part of the favicon (browser tab)

- Candle colors (up/down -> red/green)

- Enable / disable in-app notification types

### Webserver mode

when freqtrade is started in [webserver mode](https://www.freqtrade.io/en/stable/utils/#webserver-mode) (freqtrade started with `freqtrade webserver`), the webserver will start in a special mode allowing for additional features, for example:

- Downloading data

- Testing pairlists

- [Backtesting strategies](#backtesting)

- ... to be expanded

#### Backtesting

When freqtrade is started in [webserver mode](https://www.freqtrade.io/en/stable/utils/#webserver-mode) (freqtrade started with `freqtrade webserver`), the backtesting view becomes available.
This view allows you to backtest strategies and visualize the results.

You can also load and visualize previous backtest results, as well as compare the results with each other.

### CORS

This whole section is only necessary in cross-origin cases (where you multiple bot API's running on `localhost:8081`, `localhost:8082`, ...), and want to combine them into one FreqUI instance.

Technical explanation
All web-based front-ends are subject to [CORS](https://developer.mozilla.org/en-US/docs/Web/HTTP/CORS) - Cross-Origin Resource Sharing.
Since most of the requests to the Freqtrade API must be authenticated, a proper CORS policy is key to avoid security problems.
Also, the standard disallows `*` CORS policies for requests with credentials, so this setting must be set appropriately.

Users can allow access from different origin URL's to the bot API via the `CORS_origins` configuration setting.
It consists of a list of allowed URL's that are allowed to consume resources from the bot's API.

Assuming your application is deployed as `https://frequi.freqtrade.io/home/` - this would mean that the following configuration becomes necessary:

```json
{
    //...
    "jwt_secret_key": "somethingrandom",
    "CORS_origins": ["https://frequi.freqtrade.io"],
    //...
}
```

In the following (pretty common) case, FreqUI is accessible on `http://localhost:8080/trade` (this is what you see in your navbar when navigating to freqUI).

The correct configuration for this case is `http://localhost:8080` - the main part of the URL including the port.

```json
{
    //...
    "jwt_secret_key": "somethingrandom",
    "CORS_origins": ["http://localhost:8080"],
    //...
}
```

trailing Slash

The trailing slash is not allowed in the `CORS_origins` configuration (e.g. `"http://localhots:8080/"`).
Such a configuration will not take effect, and the cors errors will remain.

Note

We strongly recommend to also set `jwt_secret_key` to something random and known only to yourself to avoid unauthorized access to your bot.

