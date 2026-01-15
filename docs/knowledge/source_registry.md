# 外部来源登记（MCP 抓取记录）

更新日期：2026-01-15
说明：

- 本清单用于记录“外部链接 → 可用性 → 关键要点 → 在本仓库的落地映射”。
- 抓取优先使用 MCP：`markitdown`（静态页面）→ `playwright`（需要 JS）→ 记录为 blocked（403/robot）。
- 仅记录**摘要要点**，不存放大段原文。
- 批量采集脚本（落盘为本地 feed 缓存，默认 gitignore）：`python -X utf8 scripts/tools/vharvest.py fetch -- --limit 5`
- 对 `js-required` / `blocked` 的条目可再尝试浏览器渲染采集：`python -X utf8 scripts/tools/vharvest.py fetch-playwright -- --only-failed --limit 10`
- 如遇登录/订阅/验证码阻断且你有合法访问权限：追加 `--interactive`（默认 `--interactive-mode deferred` 不阻塞其它抓取），按提示在浏览器窗口人工介入后重试；如仍受阻，可选择导出 HTML/PDF 离线转写为 `manual_markitdown.md`。
- 本地缓存默认落在：`.vibe/knowledge/sources/S-xxx/`（markitdown 输出为 `markitdown.md` + `meta.json`；浏览器输出为 `playwright_snapshot.md` + `playwright_dom.html` + `playwright_network.json` + `meta_playwright.json`，可选 `screenshot.png`）。

---

## A) 网格 / 均值回归（震荡赛道）

### S-001 TradingView：Mean Reverse Grid Algorithm（The Quant Science）

- URL：https://www.tradingview.com/script/gdNtbzel-Mean-Reverse-Grid-Algorithm-The-Quant-Science/
- 抓取方式：MCP `markitdown`
- 抓取状态：ok（内容可见，但脚本为 invite-only，源码不可见）
- 可复用要点（摘要）：
  - “网格通道”由 10 层构成（上 5 / 下 5），以百分比变化定义层级。
  - 多头示例：价格下穿更低网格则分批开仓（示例为 20% 资金/层，最多 5 笔），上穿更高网格逐层止盈。
  - 空头示例同理（上穿开空、下穿平空）。
- 落地到本仓库：
  - 概念参考：`docs/archive/design/crypto_futures_strategy_options.md`
  - “网格风格”原型策略：`01_freqtrade/strategies_archive/FreqaiVolatilityGridV1.py`

### S-002 Cryptohopper：What is Grid Trading?

- URL：https://www.cryptohopper.com/blog/what-is-grid-trading-11252
- 抓取方式：MCP `markitdown`
- 抓取状态：ok
- 可复用要点（摘要）：
  - 网格核心是“固定间隔挂单，吃波动”，不要求预测方向，但对区间/趋势体制敏感。
  - 关键风险在强趋势段（持续单边），需要体制过滤/止损/暂停机制。
- 落地到本仓库：
  - 体制过滤（bull regime）+ 波动率门控：`01_freqtrade/strategies_archive/FreqaiVolatilityGridV1.py`

### S-003 QuantifiedStrategies：Grid Trading Strategies
- 本地缓存：.vibe/knowledge/sources/S-003/playwright_snapshot.md

- URL：https://www.quantifiedstrategies.com/grid-trading-strategies/
- 抓取方式：MCP `playwright`
- 抓取状态：ok
- 抓取日期：2026-01-11
- 处理建议：
  - 该站点有反爬限制，后续如需纳入，可尝试 MCP `playwright`；若仍失败则更换来源。

### S-004 Antier Solutions：8 Key Considerations for Grid Trading Bot Development

- URL：https://www.antiersolutions.com/blogs/8-key-considerations-for-grid-trading-bot-development/
- 抓取方式：MCP `markitdown`
- 抓取状态：ok（正文可抓取，但页面包含大量导航/营销内容）
- 可复用要点（摘要）：
  - 网格机器人落地重点在“参数 + 风控 + 执行”：区间/层数/间距、仓位与风险上限、交易成本与滑点。
  - 工程侧需要关注：交易所对接稳定性、异常处理、监控告警与回测验证（避免只凭主观经验上线）。
- 落地到本仓库：
  - 网格风格原型（maker 入场 + 均值退出 + 门控）：`01_freqtrade/strategies_archive/FreqaiVolatilityGridV1.py`
  - 赛道设计总览：`docs/archive/design/crypto_futures_strategy_options.md`
- 本地缓存：.vibe/knowledge/sources/S-005/playwright_snapshot.md

### S-005 WunderTrading：Grid Bot（概览）

- URL：https://wundertrading.com/en/grid-bot
- 抓取方式：MCP `playwright`
- 抓取状态：ok
- 抓取日期：2026-01-11

### S-006 OKX Help：Spot Grid Bot（现货网格机器人）

- URL：https://www.okx.com/en-us/help/whats-the-spot-grid-bot-and-how-to-use-it
- 抓取方式：MCP `playwright`
- 抓取状态：ok
- 抓取日期：2026-01-11
- 本地缓存：.vibe/knowledge/sources/S-006/playwright_snapshot.md
- 引入原因：来自用户提供的“交易所策略表现汇总”中的关键引用，用于校准网格策略在交易所侧的产品形态与参数口径。
- 可复用要点（摘要）：
  - 网格 bot 的定义：在指定价格区间与网格间距内自动挂买卖单，目标是在区间内“低买高卖”（不保证盈利）。
  - 明确限制：强趋势时可能出现买/卖单长期不成交；下跌趋势中成交的买单可能导致亏损；市场突变时策略不够灵活；多次成交会放大交易成本。
  - 参数口径清晰：需要至少设置上下边界（Price Range），并以网格数/间距把区间离散化；文中示例包含 `Price Range` 与 `Number of Grids` 等字段。
- 落地到本仓库：
  - 网格赛道设计与风险边界：`docs/archive/design/crypto_futures_strategy_options.md`
  - 网格风格原型策略：`01_freqtrade/strategies_archive/FreqaiVolatilityGridV1.py`

### S-007 OKX Marketplace：Swing Grid（摇摆网格）

- URL：https://www.okx.com/marketplace/education/swing-grid
- 抓取方式：MCP `playwright`
- 抓取状态：ok
- 抓取日期：2026-01-11
- 本地缓存：.vibe/knowledge/sources/S-007/playwright_snapshot.md
- 引入原因：来自用户提供的“交易所策略表现汇总”中的关键引用，用于补齐“趋势/震荡体制切换下”的网格产品化思路。
- 可复用要点（摘要）：
  - swing grid 的定位：在预期区间内设置一系列买入/卖出点，自动捕捉较大波动的“上下摆动收益”，属于震荡/波动利用类。
  - 叙事案例强调：在波动回撤中自动“买低卖高”，并对比“单纯持有”的收益差异（属于营销口径，需谨慎对待）。
  - 结论：本质仍是网格，核心风险依旧是单边趋势与成本；应优先配合体制过滤/门控。
- 落地到本仓库：
  - 网格赛道设计与风险边界：`docs/archive/design/crypto_futures_strategy_options.md`

---

## B) 套利（低风险收益赛道，偏工程/执行）

### S-101 Gemini Cryptopedia：Crypto Arbitrage

- URL：https://www.gemini.com/cryptopedia/crypto-arbitrage-crypto-exchange-prices
- 抓取方式：MCP `markitdown`
- 抓取状态：ok（页面含 JS 组件，但正文可抓取）
- 可复用要点（摘要）：
  - 套利类型：跨交易所套利、三角套利、DEX/CEX 套利、闪电贷套利。
  - 主要风险：波动与滑点、转账/提现延迟、链上拥堵费用、监管与平台规则差异。
  - 成功关键：速度 + 成本核算 + 风险控制（延迟导致机会消失）。
- 落地到本仓库：
  - 赛道选型参考：`docs/archive/design/crypto_futures_strategy_options.md`
  - 说明：此赛道更可能需要专用执行器/跨市场协调，不建议直接硬塞进现有 FreqAI 策略。

### S-102 Crypto.com Learn：What is crypto arbitrage?

- URL：https://crypto.com/us/crypto/learn/what-is-arbitrage-in-crypto-trading
- 抓取方式：MCP `markitdown`
- 抓取状态：ok（正文较长）
- 可复用要点（摘要）：
  - 套利本质：同时买低卖高，利润来自价差，但对手续费、滑点、提现速度高度敏感。
- 抓取方式：MCP `playwright`
- 本地缓存：.vibe/knowledge/sources/S-103/playwright_snapshot.md
- 抓取日期：2026-01-11
- 抓取状态：ok
  - 常用实现：自动化工具（监控/报警/机器人） + 成本计算器（含手续费与转账成本）。
- 落地到本仓库：
  - 同 S-101。

### S-103 Highstrike：Perpetual futures（科普）

- URL：https://highstrike.com/perpetual-futures/
- 抓取方式：MCP `playwright`
- 抓取状态：ok
- 抓取日期：2026-01-11
- 本地缓存：.vibe/knowledge/sources/S-103/playwright_snapshot.md

### S-104 CoinMarketCap Academy：Arbitrage Opportunities in DeFi

- URL：https://coinmarketcap.com/academy/article/arbitrage-opportunities-in-defi
- 抓取方式：MCP `playwright`
- 抓取状态：ok
- 抓取日期：2026-01-11
- 本地缓存：.vibe/knowledge/sources/S-104/playwright_snapshot.md
- 可复用要点（摘要）：
  - DeFi 套利类型拆分：桥套利、稳定币套利、收益套利、资产套利、批处理/闪电贷套利、抢跑/MEV。
  - 风险拆分：智能合约风险、Gas/拥堵风险、资产价格风险；越“自动化/链上”的套利越工程密集且竞争激烈。
  - 结论倾向：系统化 DeFi 套利更适合专业团队（监控 mempool、编写合约/机器人、成本核算严格）。
- 落地到本仓库：
  - 赛道选型参考：`docs/archive/design/crypto_futures_strategy_options.md`
  - 说明：该类套利更偏执行器/链上工程，通常不直接落在 FreqAI 策略内。

### S-105 TastyCrypto：DeFi Arbitrage（概览）

- URL：https://www.tastycrypto.com/blog/defi-arbitrage/
- 抓取方式：MCP `playwright`
- 抓取状态：ok
- 抓取日期：2026-01-11
- 本地缓存：.vibe/knowledge/sources/S-105/playwright_snapshot.md

### S-106 Quidax Blog：What is crypto arbitrage?

- URL：https://blog.quidax.io/what-is-crypto-arbitrage-the-arbitrage-trading-strategy/
- 抓取方式：MCP `playwright`
- 抓取状态：blocked（检测到人机验证/风控页面（需要人工验证）；如有合法访问权限可用 --interactive）
- 抓取日期：2026-01-11
- 本地缓存：.vibe/knowledge/sources/S-106/playwright_snapshot.md

### S-107 OKX Marketplace：Smart Arbitrage（智能套利）

- URL：https://www.okx.com/marketplace/education/smart-arbitrage
- 抓取方式：MCP `playwright`
- 抓取状态：ok
- 抓取日期：2026-01-11
- 本地缓存：.vibe/knowledge/sources/S-107/playwright_snapshot.md
- 引入原因：来自用户提供的“交易所策略表现汇总”中的关键引用，用于理解交易所“套利/对冲”产品化形态与风险提示。
- 可复用要点（摘要）：
  - smart arbitrage 的定义：买入现货 + 卖出等量永续/期货（方向相反），用多空对冲降低价格波动影响，主要收益来自资金费率（本质是 delta-neutral / funding arb 的产品化）。
  - 风险提示：资金费率并非恒定为正；当费率转负或市场结构异常时，“稳定收益”的前提可能失效，需要退出/切换。
  - 交易所强调的卖点：免管理费/默认参数/可编辑设置（属于产品化描述，不能替代本仓库回测与风控设计）。
- 落地到本仓库：
  - 套利赛道工程预期校准：`docs/archive/design/crypto_futures_strategy_options.md`

### S-108 Gate Learn：Perpetual Contract Funding Rate Arbitrage

- URL：https://www.gate.com/learn/articles/perpetual-contract-funding-rate-arbitrage/2166
- 抓取方式：MCP `markitdown`
- 抓取状态：ok
- 抓取日期：2026-01-11
- 本地缓存：.vibe/knowledge/sources/S-108/markitdown.md
- 引入原因：来自用户提供的“交易所策略表现汇总”中的关键引用，用于校准“资金费率套利”收益来源/风险与拥挤度风险。
- 可复用要点（摘要）：
  - 给出 funding arb 的基础定义：现货与永续/合约同标的、相反方向、等量对冲，收益来自资金费率结算（每 8 小时结算一次）。
  - 给出收益口径公式：`Funding Fee = Position Value * Funding Rate`，并强调交易成本/借贷利息/滑点会显著影响净收益。
  - 风险点：费率方向可能变化；杠杆/强平是主要尾部风险；文中提到平台会限制杠杆（示例为最高 3x）（属于交易所口径，需再用多来源交叉验证）。
- 落地到本仓库：
  - 套利赛道总览（资金费率/基差）：`docs/archive/design/crypto_futures_strategy_options.md`

### S-109 OKX Markets：Funding rate arbitrage（USDT）数据页

- URL：https://www.okx.com/markets/arbitrage/funding-usdt
- 抓取方式：MCP `markitdown`
- 抓取状态：ok
- 抓取日期：2026-01-11
- 引入原因：来自用户提供的“交易所策略表现汇总”中的关键引用，用于对齐“资金费率套利”在交易所侧的机会展示字段与数据口径。
- 可复用要点（摘要）：
  - 提供 funding rate arbitrage 数据表，字段包括：Crypto、Pairs、Revenue/10k (3D)、APY、Total funding rate (3D)、Curr. funding rate、Spread rate、Position value 等，可用于候选标的筛选与容量/流动性评估。
  - 资金费率存在正负变化，套利方向需要随费率符号切换；策略侧必须明确“收费率”的持仓方向与退出机制。
- 落地到本仓库：
  - 套利赛道总览（资金费率/基差）：`docs/archive/design/crypto_futures_strategy_options.md`

---

## C) 期货交易系统 / 风险管理（通用参考）

### S-201 Bitunix：2025 Futures Trading System Guide

- URL：https://blog.bitunix.com/en/futures-trading-tips-crypto-2025/
- 抓取方式：MCP `playwright`
- 抓取状态：ok
- 抓取状态：ok（正文可抓取，内容偏交易所教育向）
- 可复用要点（摘要）：
  - 强调“系统化流程”：策略设计 → 标的选择 → 回测/验证 → 盈亏结构与止损止盈优化 → 风险管理。
  - 期货关键要点：杠杆/保证金、仓位大小、止损纪律与对冲思维（强调成本与执行）。
- 落地到本仓库：
  - 回测与报表标准：`docs/guidelines/backtest_reporting_standard.md`
  - 风控口径（futures）：策略侧 `custom_stoploss` 必须返回“本次交易风险%（含杠杆）”。

### S-202 MetroTrade：Futures Trading Strategies

- URL：https://www.metrotrade.com/futures-trading-strategies/
- 抓取方式：MCP `playwright`
- 抓取状态：ok
- 抓取日期：2026-01-11
- 本地缓存：.vibe/knowledge/sources/S-202/playwright_snapshot.md

### S-203 BitMEX Blog：State of Crypto Perps 2025

- URL：https://www.bitmex.com/blog/state-of-crypto-perps-2025
- 抓取方式：MCP `playwright`
- 抓取状态：ok
- 抓取日期：2026-01-11
- 本地缓存：.vibe/knowledge/sources/S-203/playwright_snapshot.md
- 引入原因：来自用户提供的“交易所策略表现汇总”中的关键引用，用于验证“资金费率/拥挤度/市场结构变化”对套利与 CTA 的影响。
- 可复用要点（摘要）：
  - 指出 2025 年出现“结构性压力 + 流动性冲击”：极端行情下 ADL 反馈环可能破坏所谓“中性对冲”的稳定性，流动性提供者会撤单导致盘口变薄。
  - 明确提出“funding rate arbitrage 过度拥挤、费率塌缩”的风险叙事（属于 BitMEX 视角，需结合其它来源与本地数据校准）。
  - 强调“平台风险/规则风险”：交易所风控与条款可能影响套利/对冲策略的可兑现性（where you trade matters）。
- 落地到本仓库：
  - 赛道选型与工程预期校准：`docs/archive/design/crypto_futures_strategy_options.md`

---

## D) 机构视角 / 基金策略框架（宏观与工程参考）

### S-301 CryptoResearchReport：Mastering Crypto Hedge Fund Strategies: A 2025 Outlook

- URL：https://cryptoresearch.report/crypto-research/mastering-crypto-hedge-fund-strategies-a-2025-outlook/
- 抓取方式：MCP `markitdown`
- 抓取状态：ok（正文可抓取）
- 可复用要点（摘要）：
  - 强调从“选币”转向“体制识别 + 风险管理 + 对冲工具”（perp delta-neutral、期权保护等）。
  - 强调技术/数据侧：AI/机器学习、链上数据监控、流动性与执行风险预警。
  - 结论倾向：在高效市场环境下，收益更依赖“结构化策略组合”而非单一指标信号。
- 落地到本仓库：
  - 赛道选型与落地路线：`docs/archive/design/crypto_futures_strategy_options.md`
  - 说明：该文属于“框架性指导”，用于校准我们对 CTA/套利/门控策略的预期与工程投入。

### S-302 XBTO：Best practices / Active management（机构化视角）

- URL：https://www.xbto.com/resources/building-a-diversified-crypto-portfolio-best-practices-for-institutions-in-2025
- 抓取方式：MCP `markitdown`
- 抓取状态：ok（正文可抓取，但页面包含合格投资者声明与大量公司信息）
- 可复用要点（摘要）：
  - 24/7 市场与多交易场所使“主动管理”更可行：可快速响应、执行策略更多样（现货 + 衍生品）。
  - 市场结构带来定价偏差与机会：统计套利/均值回归等属于常见“利用错定价”的工具箱。
  - 衍生品可用于对冲与风险管理，提升组合的韧性（相对“纯方向押注”更稳健）。
- 落地到本仓库：
  - 震荡/门控类策略优先路径：`docs/archive/design/crypto_futures_strategy_options.md`

### S-303 1Token：Crypto Quant Strategy Index IV（2025-07）

- URL：https://blog.1token.tech/crypto-quant-strategy-index-iv-july-2025/
- 抓取方式：MCP `markitdown`
- 抓取状态：ok
- 抓取日期：2026-01-11
- 本地缓存：.vibe/knowledge/sources/S-303/markitdown.md
- 引入原因：来自用户提供的“交易所策略表现汇总”中的关键引用，用于校准“策略赛道在样本期内的相对表现”（仅作为外部参考，最终仍以本仓库回测为准）。
- 可复用要点（摘要）：
  - 报告方法：基于多团队真实交易数据，以 TWR（Time-Weighted Return）对齐起点后取算术平均形成指数（强调样本量较小时不做加权）。
  - 指标框架：同时讨论收益/回撤、风险调整指标（Sharpe/Sortino/Calmar）、策略特征（持仓周期/资金利用率）与持仓币种分布。
  - 对本仓库启示：除了收益指标，应补充“持仓周期/资金利用率”类指标作为策略工程评价维度（尤其对套利/高频/短持仓）。
- 落地到本仓库：
  - 赛道选型与证据锚点：`docs/archive/design/crypto_futures_strategy_options.md`

### S-304 1Token：Strategy Index（Long-Short I & Funding Arb II）

- URL：https://blog.1token.tech/strategy-index-long-short-i-and-funding-arb-ii/
- 抓取方式：MCP `markitdown`
- 抓取状态：ok
- 抓取日期：2026-01-11
- 本地缓存：.vibe/knowledge/sources/S-304/markitdown.md
- 引入原因：来自用户提供的“交易所策略表现汇总”中的关键引用，用于补齐“多空/资金费率套利”的外部量化口径（仅作参考，需与本仓库回测口径对齐）。
- 可复用要点（摘要）：
  - 指出对 funding arb 的拆解口径：将收益拆成 funding income、交易费用、利息、交易 PnL，并提出 FYpGE（Funding Yield per Gross Exposure）评估“捕获费率”的能力。
  - 指出“多空策略”的流动性/资金效率评价维度（持仓周期、资金利用率），可用于校准我们对策略容量与执行成本的预期。
  - 对本仓库启示：把“费率占比/净收益拆解/资金效率”纳入回测报告与策略复用结论，而不是只看总收益曲线。
- 落地到本仓库：
  - 套利赛道与多空赛道讨论：`docs/archive/design/crypto_futures_strategy_options.md`

### S-305 Cayman Finance（AIMA & PwC）：7th Annual Global Crypto Hedge Fund Report（2025）

- URL：https://caymanfinance.ky/wp-content/uploads/2025/11/7th-Annual-Global-Crypto-Hedge-Fund-Report.pdf
- 抓取方式：MCP `markitdown`（PDF 文本提取）
- 抓取状态：ok
- 抓取日期：2026-01-11
- 引入原因：来自用户提供的“交易所策略表现汇总”中的关键引用，用于校准“机构配置加密资产的比例与动因”的外部叙事锚点。
- 可复用要点（摘要）：
  - 2025 年有数字资产曝露的对冲基金占比约 55%，高于 2024 年的 47%（机构参与度提升的佐证）。
  - 报告强调：监管清晰度提升与机构级基础设施成熟（托管、交易、合规、prime brokerage 等）是进一步配置的关键推动因素。
- 落地到本仓库：
  - 赛道外部基准与机构叙事锚点：`docs/archive/design/crypto_futures_strategy_options.md`

### S-306 XBTO：Sharpe / Sortino / Calmar（加密风险调整收益指标指南）

- URL：https://www.xbto.com/resources/sharpe-sortino-and-calmar-a-practical-guide-to-risk-adjusted-return-metrics-for-crypto-investors
- 抓取方式：MCP `markitdown` + `Invoke-WebRequest`（提取 HTML 内嵌 `<markdown>` 块）
- 抓取状态：ok
- 抓取日期：2026-01-11
- 引入原因：来自用户提供的“交易所策略表现汇总”中的关键引用，用于对齐 Sharpe/Sortino/Calmar 的解释口径与对比方式。
- 可复用要点（摘要）：
  - 用 Sharpe/Sortino/Calmar 从“总波动/下行波动/最大回撤”三个视角评估风险调整收益，并给出对比表格示例（同年化收益下的稳定性与回撤差异）。
  - 强调仅看年化收益会误判，应结合波动率与回撤评估“收益效率/下行风险效率/回撤效率”。 
- 落地到本仓库：
  - 回测汇报指标口径对标：`docs/guidelines/backtest_reporting_standard.md`
  - 赛道选型与指标对标说明：`docs/archive/design/crypto_futures_strategy_options.md`

---

## E) 学术 / 研究（方法论与市场结构）

### S-401 arXiv：Fundamentals of Perpetual Futures（2212.06888）

- URL：https://arxiv.org/abs/2212.06888
- 抓取方式：MCP `markitdown`
- 抓取状态：ok（摘要可抓取）
- 可复用要点（摘要）：
  - 永续合约不保证收敛现货，通过资金费率（long→short 支付）来缩小价差。
  - 给出无套利定价（含交易成本边界），并指出加密市场偏离更大、跨币相关、随时间减弱。
  - 提到“隐含套利策略”可获得较高夏普（更偏市场结构/定价研究，非直接可抄策略）。
- 落地到本仓库：
  - “资金费率/基差套利”赛道的理论背景参考：`docs/archive/design/crypto_futures_strategy_options.md`

### S-402 arXiv：Liquidation, Leverage and Optimal Margin in Bitcoin Futures（2102.04591）

- URL：https://arxiv.org/abs/2102.04591
- 抓取方式：MCP `markitdown`
- 抓取状态：ok（摘要可抓取）
- 可复用要点（摘要）：
  - 用极值理论刻画尾部风险，讨论强平、杠杆与“最优保证金”。
  - 结论倾向：高杠杆会显著提高强平/追加保证金概率；在某些样本下建议将保证金提升到更高水平以降低强平概率。
  - 对本项目的启示：不要把策略胜率/盈亏比当作唯一指标，杠杆与尾部风险会主导“生存性”。
- 落地到本仓库：
  - 杠杆建议（2~5x 优先）与 futures 风控口径校准（`custom_stoploss`）：`docs/archive/design/freqai_cta_trend_v3.md`

### S-403 arXiv：Forecasting Cryptocurrencies Log-Returns（LASSO-VAR + Sentiment）（2210.00883）

- URL：https://arxiv.org/abs/2210.00883
- 抓取方式：MCP `markitdown`
- 抓取状态：ok（摘要可抓取）
- 可复用要点（摘要）：
  - 研究表明“方向预测”可能略高于随机（>50%），但提升幅度有限，且不同指标对不同度量（方向 vs RMSE）的贡献不同。
  - 对本项目的启示：把 ML 主要用于“过滤/门控/风险识别”往往比纯方向预测更稳健。
- 落地到本仓库：
  - “波动率门控”思路的合理性参考：`docs/archive/design/crypto_futures_strategy_options.md`

### S-404 arXiv：Hedging with Bitcoin Futures（Liquidation risk）（2101.01261）

- URL：https://arxiv.org/abs/2101.01261
- 抓取方式：MCP `markitdown`
- 抓取状态：ok（摘要可抓取）
- 可复用要点（摘要）：
  - 讨论在“可能被交易所自动强平”的约束下进行对冲，目标同时最小化组合方差与强平概率。
  - 结论倾向：最优对冲与杠杆/保证金管理强相关；不同交易所/合约类型表现差异明显（执行细节重要）。
- 落地到本仓库：
  - 强平风险作为 futures 策略的一级风险源：`docs/archive/design/freqai_cta_trend_v3.md`

### S-405 arXiv：Cryptocurrency Valuation: An Explainable AI Approach（2201.12893）

- URL：https://arxiv.org/abs/2201.12893
- 抓取方式：MCP `markitdown`
- 抓取状态：ok（摘要可抓取）
- 可复用要点（摘要）：
  - 提出“Price-to-Utility (PU) ratio”作为市场对基本面的比率指标，并称其对长期回报更有效。
  - 指出多种“基本面比率”对短期收益预测力有限；更适合作为长期体制/估值框架参考而非短线入场信号。
- 落地到本仓库：
  - 作为“体制识别/长期估值”思路参考（非直接交易信号）：`docs/archive/design/crypto_futures_strategy_options.md`

### S-406 VilniusTech（BM 2025）：Analysis of investment strategies in cryptocurrencies（bm.2025.1460）

- URL：https://etalpykla.vilniustech.lt/handle/123456789/159266
- 抓取方式：MCP `playwright`
- 本地缓存：.vibe/knowledge/sources/S-408/playwright_snapshot.md
- 抓取状态：ok
- 抓取日期：2026-01-11
- 可复用要点（摘要）：
  - 总结常见策略（HODL/分散/短线交易），并强调高波动下的风险管理与外部因素敏感性。
  - 提到可用 LASSO/AutoEncoder 等模型辅助预测与策略优化（偏综述/比较研究）。
- 落地到本仓库：
  - 作为“策略赛道对比 + 风控重要性”的背景材料：`docs/archive/design/crypto_futures_strategy_options.md`
- 本地缓存：.vibe/knowledge/sources/S-409/playwright_snapshot.md
- 抓取日期：2026-01-11

### S-407 Notas Económicas（2023）：Native Market Factors for Pricing Cryptocurrencies

- URL：https://impactum-journals.uc.pt/notaseconomicas/article/download/14048/9705
- 本地缓存：.vibe/knowledge/sources/S-410/playwright_snapshot.md
- 抓取方式：MCP `playwright`
- 抓取状态：ok
- 抓取日期：2026-01-11
- 抓取状态：ok（PDF 可抓取）
- 可复用要点（摘要）：
  - 用 CoinMarketCap 全样本构建加密货币因子：size、reversal（类似“反转”）、illiquidity、maturity 等；提出 5 因子模型优于 3 因子模型。
  - 启示：横截面收益的解释更偏“市场结构因子”而非单一技术信号；也提示“流动性/成熟度”可能是重要风险溢价来源。
- 落地到本仓库：
  - 可作为后续特征工程候选（流动性/成熟度代理变量）的理论依据：`docs/archive/design/crypto_futures_strategy_options.md`

### S-408 MDPI：Enhanced Genetic-Algorithm-Driven Triple Barrier Labeling（2227-7390/13/10/1551）

- URL：https://www.mdpi.com/2227-7390/13/10/1551
- 抓取方式：MCP `playwright`
- 抓取状态：ok
- 抓取日期：2026-01-11
- 本地缓存：.vibe/knowledge/sources/S-408/playwright_snapshot.md
- 处理建议：
  - 该站点当前请求不稳定，后续可择时重试或改用可直达的 PDF/镜像来源。

### S-409 MDPI：Journal of Risk and Financial Management（1911-8074/13/11/278）

- URL：https://www.mdpi.com/1911-8074/13/11/278
- 抓取方式：MCP `playwright`
- 抓取状态：ok
- 抓取日期：2026-01-11
- 本地缓存：.vibe/knowledge/sources/S-409/playwright_snapshot.md

### S-410 IJIRIS PDF：18.NVIS10097（订阅/邮箱墙）

- URL：https://www.ijiris.com/volumes/Vol11/iss-09/18.NVIS10097.pdf
- 抓取方式：MCP `playwright`
- 抓取状态：ok
- 抓取日期：2026-01-11
- 本地缓存：.vibe/knowledge/sources/S-410/playwright_snapshot.md

---

## F) 框架 / 参数文档（Freqtrade/FreqAI/LightGBM）

### S-501 Freqtrade 文档：FreqAI（Introduction）

- URL：https://www.freqtrade.io/en/stable/freqai/
- 抓取方式：MCP `markitdown`
- 抓取状态：ok
- 可复用要点（摘要）：
  - FreqAI 的定位是“训练/预测/滚动再训练”的框架化流水线，强调把 ML 库落到可回测/可实盘的工程闭环。
  - 常见坑：FreqAI 不适合与“动态增删币对”的 pairlist 组合（训练数据与预测节奏会被破坏）。
- 落地到本仓库：
  - 赛道选型与工程预期校准：`docs/archive/design/crypto_futures_strategy_options.md`
  - 策略入口统一：`docs/archive/freqai/freqai_core_strategy_guide.md`

### S-502 Freqtrade 文档：FreqAI Configuration

- URL：https://www.freqtrade.io/en/stable/freqai-configuration/
- 抓取方式：MCP `markitdown`
- 抓取状态：ok
- 可复用要点（摘要）：
  - 分类器使用时，需要在 `set_freqai_targets()` 明确设置 `self.freqai.class_names`，以确保推理阶段输出稳定的概率列（类名即列名）。
  - 文档强调了 FreqAI DataFrame 的关键字段模式（targets、features、do_predict 等），建议围绕“阈值/门控”做策略层优化。
- 落地到本仓库：
  - 多分类 TB + 概率列驱动入场：`docs/archive/design/freqai_cta_trend_v3.md`

### S-503 Freqtrade 文档：FreqAI Parameter Table

- URL：https://www.freqtrade.io/en/stable/freqai-parameter-table/
- 抓取方式：MCP `markitdown`
- 抓取状态：ok
- 可复用要点（摘要）：
  - 给出 freqai 配置字段的权威口径：训练窗口 `train_period_days`、回测推理窗口 `backtest_period_days`、标识符 `identifier`、以及 `feature_parameters` / `model_training_parameters` 的含义与约束。
  - 适合作为“配置审计清单”的基准来源，避免策略/配置口径漂移。
- 落地到本仓库：
  - 参考配置：`04_shared/configs/archive/freqai/meta_label_1h_v2.json`
  - 参考配置：`04_shared/configs/archive/freqai/cta_trend_btc_1h_v3.json`

### S-504 Freqtrade 文档：Running FreqAI（Backtesting / Live retrain / Hyperopt）

- URL：https://www.freqtrade.io/en/stable/freqai-running/
- 抓取方式：MCP `markitdown`
- 抓取状态：ok
- 可复用要点（摘要）：
  - 说明“滚动窗口训练 + 周期性再训练”的回测/实盘机制；影响结果的核心旋钮是训练窗口与回测推理窗口（以及是否保存预测/模型）。
  - Hyperopt 的建议是：重点优化“入场/出场阈值与门控条件”，不要在 `feature_engineering_*()` 与 `set_freqai_targets()` 内做超参搜索（回测与复用机制不匹配）。
- 落地到本仓库：
  - 回测汇报与复用流程约定：`docs/guidelines/backtest_reporting_standard.md`

### S-505 LightGBM 文档：Parameters（class imbalance 关键参数）

- URL：https://lightgbm.readthedocs.io/en/latest/Parameters.html
- 抓取方式：MCP `markitdown`（正文）+ `Invoke-WebRequest`（定位关键字段）
- 抓取状态：ok
- 可复用要点（摘要）：
  - `is_unbalance` / `scale_pos_weight` 仅适用于 `binary` 与 `multiclassova`，二者不可同时启用（只能选一个）。
  - 文档明确提示：启用不平衡权重可能提升整体指标，但会导致“类别概率估计变差”（对阈值交易/概率门控很关键）。
- 落地到本仓库：
  - LightGBMClassifier 配置口径（`is_unbalance`）：`04_shared/configs/archive/freqai/meta_label_1h_v2.json`
  - 概率阈值与 `prob_margin` 的风险提示：`docs/archive/design/freqai_cta_trend_v3.md`

---

## G) Triple Barrier / Meta-Labeling（方法论与开源实现）
- 本地缓存：.vibe/knowledge/sources/S-603/playwright_snapshot.md

### S-601 Mlfin.py 文档：Data Labelling（Triple-Barrier + Meta-Labeling + Trend Scanning）

- URL：https://mlfinpy.readthedocs.io/en/latest/Labelling.html
- 抓取方式：MCP `playwright`
- 抓取状态：ok
- 抓取日期：2026-01-11
- 可复用要点（摘要）：
  - 强调“金融时序回归预测难度高”，分类（离散标签）更现实；这与本项目从回归转向分类器的方向一致。
  - 以 Triple Barrier + Meta-Labeling 为核心：先有基础信号，再由二级模型判断“是否值得执行”，从而缓解噪声与目标错位。
  - Trend Scanning 可用于体制识别（down / neutral / up）与样本权重（t-value 可做 sample weight），适合进一步强化“体制过滤 + 门控”。
- 落地到本仓库：
  - 三分类方向标签 + 概率列门控：`docs/archive/design/freqai_cta_trend_v3.md`
  - 赛道选型（门控优于纯方向）：`docs/archive/design/crypto_futures_strategy_options.md`

### S-602 GitHub：mchiuminatto/triple_barrier（半向量化交易标签器）

- URL：https://github.com/mchiuminatto/triple_barrier
- 抓取方式：MCP `markitdown`
- 抓取状态：ok
- 可复用要点（摘要）：
  - 提供“以入场信号列为事件”的交易级 Triple Barrier 标注范式：open/high/low/close + 入场标记 + 止盈/止损宽度 + 时间障碍 → 输出 trades DataFrame。
  - 强调可视化核验（单笔交易绘图）与可扩展接口（dynamic_exit），适合作为“标签正确性验证”的参考实现。
- 落地到本仓库：
  - TB 标签生成与性能重构（避免嵌套循环）：`docs/archive/design/freqai_triple_barrier_v3.md`

### S-603 Hudson & Thames：Meta Labeling（A Toy Example）

- URL：https://hudsonthames.org/meta-labeling-a-toy-example/
- 抓取方式：MCP `playwright`
- 抓取状态：ok
- 抓取日期：2026-01-11
- 本地缓存：.vibe/knowledge/sources/S-603/playwright_snapshot.md
- 处理建议：
  - 该站点对非浏览器抓取较敏感；如需继续抓取，可先运行 `./scripts/tools/fix_chrome_for_mcp.ps1` 以启用 `playwright_mcp`/`chrome_devtools_mcp`。
  - 可用替代来源：S-601（mlfinpy Labelling）已覆盖 Meta-Labeling 的关键概念与落地接口。

---

## H) 性能 / 向量化（实现策略的工程约束）

### S-701 Python⇒Speed：Pandas vectorization（性能 vs 内存）

- URL：https://pythonspeed.com/articles/pandas-vectorization/
- 抓取方式：MCP `markitdown`
- 抓取状态：ok
- 可复用要点（摘要）：
  - “向量化”不等于一定更快：Pandas 的批量 API 有时仍会回落到 Python 循环（尤其字符串/对象类型）。
  - 向量化可能引入巨大的临时对象，导致内存从 O(1) 变为 O(N) 甚至 O(N×L)（对 TB 标注的未来窗口矩阵尤需警惕）。
  - 结论：必须以 profiling/测量为准，避免“为了向量化而向量化”。
- 落地到本仓库：
  - TB 标签“半向量化/分块”重构原则：`docs/archive/design/freqai_triple_barrier_v3.md`

### S-702 Investopedia：Trailing Stop/Stop-Loss Combo Leads to Winning Trades

- URL：https://www.investopedia.com/articles/trading/08/trailing-stop-loss-combo.asp
- 抓取方式：MCP `playwright`
- 抓取状态：ok
- 抓取日期：2026-01-11
- 本地缓存：.vibe/knowledge/sources/S-702/playwright_snapshot.md
- 处理建议：
  - 该站点对自动化抓取限制较强；如需继续抓取，可先运行 `./scripts/tools/fix_chrome_for_mcp.ps1` 以启用 `playwright_mcp`/`chrome_devtools_mcp`。
  - 本项目的“止损/止盈/跟踪止损”工程口径优先以 Freqtrade 官方文档与可回测实现为准（见 S-502/S-504）。

---

## I) 模型实践参考（可借鉴但不直接复用）

### S-801 GitHub：Netanelshoshan/freqAI-LSTM（动态加权与聚合评分）

- URL：https://github.com/Netanelshoshan/freqAI-LSTM
- 抓取方式：MCP `markitdown`
- 抓取状态：ok
- 可复用要点（摘要）：
  - 给出“严格阈值 + 加权聚合评分 + 控制信号稀疏度”的实践思路，强调用阈值过滤噪声而非追求高频预测。
  - 其报告的高精度结果样本期较短，存在过拟合风险；更适合作为“工程结构/特征组织/训练流程”的参考，而非收益预期依据。
- 落地到本仓库：
  - 门控/阈值/概率优势的结构化写法：`docs/archive/design/freqai_cta_trend_v3.md`

---

## J) 抓取流程验证（访问受限/人工介入）

### S-802 linux.do：访问受限验证（登录/验证码）

- URL：https://linux.do/login
- 抓取方式：MCP `playwright`
- 抓取状态：ok
- 抓取日期：2026-01-11
- 本地缓存：.vibe/knowledge/sources/S-802/playwright_snapshot.md
- 用途：验证“受阻 → 提示人工介入 → 介入后恢复抓取”的工作流（非策略研究来源）。

---

## K) 用户提供：策略深入分析报告参考（待提炼）

### S-803 onlinelibrary.wiley.com：10.1002/nem.70030

- URL：https://onlinelibrary.wiley.com/doi/10.1002/nem.70030
- 抓取方式：MCP `playwright`
- 抓取状态：blocked（检测到人机验证/风控页面（需要人工验证）；如有合法访问权限可用 --interactive）
- 抓取状态备注：blocked（抓取失败，详见本地缓存 meta.json）
- 抓取日期：2026-01-11
- 本地缓存：.vibe/knowledge/sources/S-803/playwright_snapshot.md
- 引入原因：用户提供的“交易策略深入分析报告”参考链接，待提炼。
- 落地到本仓库：
  - 深度分析报告：`docs/knowledge/crypto_exchange_strategy_deep_dive.md`

### S-804 www.wne.uw.edu.pl：6165/0

- URL：https://www.wne.uw.edu.pl/download_file/6165/0
- 抓取方式：MCP `markitdown`
- 抓取状态：ok
- 抓取日期：2026-01-11
- 本地缓存：.vibe/knowledge/sources/S-804/markitdown.md
- 引入原因：用户提供的“交易策略深入分析报告”参考链接，待提炼。
- 落地到本仓库：
  - 深度分析报告：`docs/knowledge/crypto_exchange_strategy_deep_dive.md`

### S-805 www.sciencedirect.com：pii/S0261560625000671

- URL：https://www.sciencedirect.com/science/article/abs/pii/S0261560625000671
- 抓取方式：MCP `playwright`
- 抓取状态：ok
- 抓取日期：2026-01-11
- 本地缓存：.vibe/knowledge/sources/S-805/playwright_snapshot.md
- 引入原因：用户提供的“交易策略深入分析报告”参考链接，待提炼。
- 落地到本仓库：
  - 深度分析报告：`docs/knowledge/crypto_exchange_strategy_deep_dive.md`

### S-806 journalspress.com：LJRMB_Volume25/Enhancing-Pairs-Trading-Strategies-in-the-Cryptocurrency-Industry-using-Machine-Learning-Clustering-Algorithms.pdf

- URL：https://journalspress.com/LJRMB_Volume25/Enhancing-Pairs-Trading-Strategies-in-the-Cryptocurrency-Industry-using-Machine-Learning-Clustering-Algorithms.pdf
- 抓取方式：MCP `playwright`
- 抓取状态：ok
- 抓取日期：2026-01-11
- 本地缓存：.vibe/knowledge/sources/S-806/playwright_snapshot.md
- 引入原因：用户提供的“交易策略深入分析报告”参考链接，待提炼。
- 落地到本仓库：
  - 深度分析报告：`docs/knowledge/crypto_exchange_strategy_deep_dive.md`

### S-807 robotwealth.com：exploring-mean-reversion-and-cointegration-part-2

- URL：https://robotwealth.com/exploring-mean-reversion-and-cointegration-part-2/
- 抓取方式：MCP `playwright`
- 抓取状态：ok
- 抓取日期：2026-01-11
- 本地缓存：.vibe/knowledge/sources/S-807/playwright_snapshot.md
- 引入原因：用户提供的“交易策略深入分析报告”参考链接，待提炼。
- 落地到本仓库：
  - 深度分析报告：`docs/knowledge/crypto_exchange_strategy_deep_dive.md`

### S-808 arXiv：2109.10662

- URL：https://arxiv.org/abs/2109.10662
- 抓取方式：MCP `markitdown`
- 抓取状态：ok
- 抓取日期：2026-01-11
- 本地缓存：.vibe/knowledge/sources/S-808/markitdown.md
- 引入原因：用户提供的“交易策略深入分析报告”参考链接，待提炼。
- 落地到本仓库：
  - 深度分析报告：`docs/knowledge/crypto_exchange_strategy_deep_dive.md`

### S-809 jurnal.uinsu.ac.id：view/27373

- URL：https://jurnal.uinsu.ac.id/index.php/zero/article/view/27373
- 抓取方式：MCP `markitdown`
- 抓取状态：ok
- 抓取日期：2026-01-11
- 本地缓存：.vibe/knowledge/sources/S-809/markitdown.md
- 引入原因：用户提供的“交易策略深入分析报告”参考链接，待提炼。
- 落地到本仓库：
  - 深度分析报告：`docs/knowledge/crypto_exchange_strategy_deep_dive.md`

### S-810 m.theblockbeats.info：news/57546

- URL：https://m.theblockbeats.info/en/news/57546
- 抓取方式：MCP `markitdown`
- 抓取状态：ok
- 抓取日期：2026-01-11
- 本地缓存：.vibe/knowledge/sources/S-810/markitdown.md
- 引入原因：用户提供的“交易策略深入分析报告”参考链接，待提炼。
- 落地到本仓库：
  - 深度分析报告：`docs/knowledge/crypto_exchange_strategy_deep_dive.md`

### S-811 www.chaincatcher.com：article/2174555

- URL：https://www.chaincatcher.com/en/article/2174555
- 抓取方式：MCP `markitdown`
- 抓取状态：ok
- 抓取日期：2026-01-11
- 本地缓存：.vibe/knowledge/sources/S-811/markitdown.md
- 引入原因：用户提供的“交易策略深入分析报告”参考链接，待提炼。
- 落地到本仓库：
  - 深度分析报告：`docs/knowledge/crypto_exchange_strategy_deep_dive.md`

### S-812 www.tv-hub.org：guide/automated-trading-mistakes

- URL：https://www.tv-hub.org/guide/automated-trading-mistakes
- 抓取方式：MCP `markitdown`
- 抓取状态：ok
- 抓取日期：2026-01-11
- 本地缓存：.vibe/knowledge/sources/S-812/markitdown.md
- 引入原因：用户提供的“交易策略深入分析报告”参考链接，待提炼。
- 落地到本仓库：
  - 深度分析报告：`docs/knowledge/crypto_exchange_strategy_deep_dive.md`

### S-813 www.clarigro.com：ai-impact-on-hedge-fund-returns-performance

- URL：https://www.clarigro.com/ai-impact-on-hedge-fund-returns-performance/
- 抓取方式：MCP `playwright`
- 抓取状态：blocked（检测到人机验证/风控页面（需要人工验证）；如有合法访问权限可用 --interactive）
- 抓取状态备注：blocked（抓取失败，详见本地缓存 meta.json）
- 抓取日期：2026-01-11
- 本地缓存：.vibe/knowledge/sources/S-813/playwright_snapshot.md
- 引入原因：用户提供的“交易策略深入分析报告”参考链接，待提炼。
- 落地到本仓库：
  - 深度分析报告：`docs/knowledge/crypto_exchange_strategy_deep_dive.md`

### S-814 magistralconsulting.com：ai-in-hedge-funds-driving-smarter-investment-choices

- URL：https://magistralconsulting.com/ai-in-hedge-funds-driving-smarter-investment-choices/
- 抓取方式：MCP `playwright`
- 抓取状态：ok
- 抓取日期：2026-01-11
- 本地缓存：.vibe/knowledge/sources/S-814/playwright_snapshot.md
- 引入原因：用户提供的“交易策略深入分析报告”参考链接，待提炼。
- 落地到本仓库：
  - 深度分析报告：`docs/knowledge/crypto_exchange_strategy_deep_dive.md`

### S-815 www.gate.io：perpetual-contract-funding-rate-arbitrage/2166

- URL：https://www.gate.io/learn/articles/perpetual-contract-funding-rate-arbitrage/2166
- 抓取方式：MCP `markitdown`
- 抓取状态：ok
- 抓取日期：2026-01-11
- 本地缓存：.vibe/knowledge/sources/S-815/markitdown.md
- 引入原因：用户提供的“交易策略深入分析报告”参考链接，待提炼。
- 落地到本仓库：
  - 深度分析报告：`docs/knowledge/crypto_exchange_strategy_deep_dive.md`

### S-816 www.ainvest.com：news/arbitraging-funding-rate-gaps-pacifica-high-perpetual-trading-strategy-2512

- URL：https://www.ainvest.com/news/arbitraging-funding-rate-gaps-pacifica-high-perpetual-trading-strategy-2512/
- 抓取方式：MCP `markitdown`
- 抓取状态：ok
- 抓取日期：2026-01-11
- 本地缓存：.vibe/knowledge/sources/S-816/markitdown.md
- 引入原因：用户提供的“交易策略深入分析报告”参考链接，待提炼。
- 落地到本仓库：
  - 深度分析报告：`docs/knowledge/crypto_exchange_strategy_deep_dive.md`

### S-817 www.gate.com：article/a-complete-guide-to-statistical-arbitrage-strategies-in-cryptocurrency-trading-20251208

- URL：https://www.gate.com/crypto-wiki/article/a-complete-guide-to-statistical-arbitrage-strategies-in-cryptocurrency-trading-20251208
- 抓取方式：MCP `playwright`
- 抓取状态：ok
- 抓取日期：2026-01-11
- 本地缓存：.vibe/knowledge/sources/S-817/playwright_snapshot.md
- 引入原因：用户提供的“交易策略深入分析报告”参考链接，待提炼。
- 落地到本仓库：
  - 深度分析报告：`docs/knowledge/crypto_exchange_strategy_deep_dive.md`

### S-818 prismafinancehub.com：cryptocurrency-mean-reversion-statistical-arbitrage-strategies

- URL：https://prismafinancehub.com/cryptocurrency-mean-reversion-statistical-arbitrage-strategies/
- 抓取方式：MCP `markitdown`
- 抓取状态：ok
- 抓取日期：2026-01-11
- 本地缓存：.vibe/knowledge/sources/S-818/markitdown.md
- 引入原因：用户提供的“交易策略深入分析报告”参考链接，待提炼。
- 落地到本仓库：
  - 深度分析报告：`docs/knowledge/crypto_exchange_strategy_deep_dive.md`

### S-819 jonathankinlay.com：03/optimal-mean-reversion-strategies

- URL：https://jonathankinlay.com/2024/03/optimal-mean-reversion-strategies/
- 抓取方式：MCP `playwright`
- 抓取状态：ok
- 抓取日期：2026-01-11
- 本地缓存：.vibe/knowledge/sources/S-819/playwright_snapshot.md
- 引入原因：用户提供的“交易策略深入分析报告”参考链接，待提炼。
- 落地到本仓库：
  - 深度分析报告：`docs/knowledge/crypto_exchange_strategy_deep_dive.md`

### S-820 chartswatcher.com：blog/8-best-indicators-for-swing-trading-to-use-in-2025

- URL：https://chartswatcher.com/pages/blog/8-best-indicators-for-swing-trading-to-use-in-2025
- 抓取方式：MCP `markitdown`
- 抓取状态：ok
- 抓取日期：2026-01-11
- 本地缓存：.vibe/knowledge/sources/S-820/markitdown.md
- 引入原因：用户提供的“交易策略深入分析报告”参考链接，待提炼。
- 落地到本仓库：
  - 深度分析报告：`docs/knowledge/crypto_exchange_strategy_deep_dive.md`

### S-821 www.reddit.com：1ituqkw/common_mistakes_that_destroy_trading_accounts

- URL：https://www.reddit.com/r/Daytrading/comments/1ituqkw/common_mistakes_that_destroy_trading_accounts/
- 抓取方式：MCP `markitdown`
- 抓取状态：ok
- 抓取日期：2026-01-11
- 本地缓存：.vibe/knowledge/sources/S-821/markitdown.md
- 引入原因：用户提供的“交易策略深入分析报告”参考链接，待提炼。
- 落地到本仓库：
  - 深度分析报告：`docs/knowledge/crypto_exchange_strategy_deep_dive.md`

### S-822 gainium.io：help/grid-step

- URL：https://gainium.io/help/grid-step
- 抓取方式：MCP `markitdown`
- 抓取状态：ok
- 抓取日期：2026-01-11
- 本地缓存：.vibe/knowledge/sources/S-822/markitdown.md
- 引入原因：用户提供的“交易策略深入分析报告”参考链接，待提炼。
- 落地到本仓库：
  - 深度分析报告：`docs/knowledge/crypto_exchange_strategy_deep_dive.md`

### S-823 www.altrady.com：crypto-trading-strategies/grid-trading-strategy

- URL：https://www.altrady.com/blog/crypto-trading-strategies/grid-trading-strategy
- 抓取方式：MCP `markitdown`
- 抓取状态：ok
- 抓取日期：2026-01-11
- 本地缓存：.vibe/knowledge/sources/S-823/markitdown.md
- 引入原因：用户提供的“交易策略深入分析报告”参考链接，待提炼。
- 落地到本仓库：
  - 深度分析报告：`docs/knowledge/crypto_exchange_strategy_deep_dive.md`

### S-824 pocketoption.com：trading-strategies/grid-trading

- URL：https://pocketoption.com/blog/en/interesting/trading-strategies/grid-trading/
- 抓取方式：MCP `markitdown`
- 抓取状态：ok
- 抓取日期：2026-01-11
- 本地缓存：.vibe/knowledge/sources/S-824/markitdown.md
- 引入原因：用户提供的“交易策略深入分析报告”参考链接，待提炼。
- 落地到本仓库：
  - 深度分析报告：`docs/knowledge/crypto_exchange_strategy_deep_dive.md`

### S-825 hub.algotrade.vn：knowledge-hub/grid-strategy

- URL：https://hub.algotrade.vn/knowledge-hub/grid-strategy/
- 抓取方式：MCP `markitdown`
- 抓取状态：ok
- 抓取日期：2026-01-11
- 本地缓存：.vibe/knowledge/sources/S-825/markitdown.md
- 引入原因：用户提供的“交易策略深入分析报告”参考链接，待提炼。
- 落地到本仓库：
  - 深度分析报告：`docs/knowledge/crypto_exchange_strategy_deep_dive.md`

### S-826 www.luxalgo.com：indicator/fibonacci-grid

- URL：https://www.luxalgo.com/library/indicator/fibonacci-grid
- 抓取方式：MCP `markitdown`
- 抓取状态：ok
- 抓取日期：2026-01-11
- 本地缓存：.vibe/knowledge/sources/S-826/markitdown.md
- 引入原因：用户提供的“交易策略深入分析报告”参考链接，待提炼。
- 落地到本仓库：
  - 深度分析报告：`docs/knowledge/crypto_exchange_strategy_deep_dive.md`

### S-827 ijsrem.com：download/effectiveness-of-technical-indicators-in-stock-trading

- URL：https://ijsrem.com/download/effectiveness-of-technical-indicators-in-stock-trading/
- 抓取方式：MCP `markitdown`
- 抓取状态：ok
- 抓取日期：2026-01-11
- 本地缓存：.vibe/knowledge/sources/S-827/markitdown.md
- 引入原因：用户提供的“交易策略深入分析报告”参考链接，待提炼。
- 落地到本仓库：
  - 深度分析报告：`docs/knowledge/crypto_exchange_strategy_deep_dive.md`

### S-828 phemex.com：academy/how-to-swing-trade-bitcoin

- URL：https://phemex.com/academy/how-to-swing-trade-bitcoin
- 抓取方式：MCP `markitdown`
- 抓取状态：ok
- 抓取日期：2026-01-11
- 本地缓存：.vibe/knowledge/sources/S-828/markitdown.md
- 引入原因：用户提供的“交易策略深入分析报告”参考链接，待提炼。
- 落地到本仓库：
  - 深度分析报告：`docs/knowledge/crypto_exchange_strategy_deep_dive.md`

### S-829 www.altrady.com：swing-trading/technical-indicators-crypto-trading-setups

- URL：https://www.altrady.com/blog/swing-trading/technical-indicators-crypto-trading-setups
- 抓取方式：MCP `markitdown`
- 抓取状态：ok
- 抓取日期：2026-01-11
- 本地缓存：.vibe/knowledge/sources/S-829/markitdown.md
- 引入原因：用户提供的“交易策略深入分析报告”参考链接，待提炼。
- 落地到本仓库：
  - 深度分析报告：`docs/knowledge/crypto_exchange_strategy_deep_dive.md`

### S-830 finst.com：articles/mistakes-made-by-crypto-traders

- URL：https://finst.com/en/learn/articles/mistakes-made-by-crypto-traders
- 抓取方式：MCP `markitdown`
- 抓取状态：ok
- 抓取日期：2026-01-11
- 本地缓存：.vibe/knowledge/sources/S-830/markitdown.md
- 引入原因：用户提供的“交易策略深入分析报告”参考链接，待提炼。
- 落地到本仓库：
  - 深度分析报告：`docs/knowledge/crypto_exchange_strategy_deep_dive.md`

### S-831 www.linkedin.com：pulse/common-crypto-trading-mistakes-getbusha-fcyef

- URL：https://www.linkedin.com/pulse/common-crypto-trading-mistakes-getbusha-fcyef
- 抓取方式：MCP `markitdown`
- 抓取状态：ok
- 抓取日期：2026-01-11
- 本地缓存：.vibe/knowledge/sources/S-831/markitdown.md
- 引入原因：用户提供的“交易策略深入分析报告”参考链接，待提炼。
- 落地到本仓库：
  - 深度分析报告：`docs/knowledge/crypto_exchange_strategy_deep_dive.md`

### S-832 arXiv：2410.06935.pdf

- URL：https://arxiv.org/pdf/2410.06935.pdf
- 抓取方式：MCP `markitdown`
- 抓取状态：ok
- 抓取日期：2026-01-11
- 本地缓存：.vibe/knowledge/sources/S-832/markitdown.md
- 引入原因：用户提供的“交易策略深入分析报告”参考链接，待提炼。
- 落地到本仓库：
  - 深度分析报告：`docs/knowledge/crypto_exchange_strategy_deep_dive.md`

### S-833 arXiv：2503.18096

- URL：https://arxiv.org/html/2503.18096
- 抓取方式：MCP `playwright`
- 抓取状态：ok
- 抓取日期：2026-01-11
- 本地缓存：.vibe/knowledge/sources/S-833/playwright_snapshot.md
- 引入原因：用户提供的“交易策略深入分析报告”参考链接，待提炼。
- 落地到本仓库：
  - 深度分析报告：`docs/knowledge/crypto_exchange_strategy_deep_dive.md`

### S-834 capital.com：trading-strategies/crypto-day-trading

- URL：https://capital.com/en-int/learn/trading-strategies/crypto-day-trading
- 抓取方式：MCP `markitdown`
- 抓取状态：ok
- 抓取日期：2026-01-11
- 本地缓存：.vibe/knowledge/sources/S-834/markitdown.md
- 引入原因：用户提供的“交易策略深入分析报告”参考链接，待提炼。
- 落地到本仓库：
  - 深度分析报告：`docs/knowledge/crypto_exchange_strategy_deep_dive.md`

### S-835 www.reddit.com：1jatfoh/how_much_and_how_often_exactly_do_you_dca

- URL：https://www.reddit.com/r/investing/comments/1jatfoh/how_much_and_how_often_exactly_do_you_dca/
- 抓取方式：MCP `markitdown`
- 抓取状态：ok
- 抓取日期：2026-01-11
- 本地缓存：.vibe/knowledge/sources/S-835/markitdown.md
- 引入原因：用户提供的“交易策略深入分析报告”参考链接，待提炼。
- 落地到本仓库：
  - 深度分析报告：`docs/knowledge/crypto_exchange_strategy_deep_dive.md`

### S-836 www.financialsamurai.com：better-investing-figuring-out-how-much-more-to-dollar-cost-average

- URL：https://www.financialsamurai.com/better-investing-figuring-out-how-much-more-to-dollar-cost-average/
- 抓取方式：MCP `markitdown`
- 抓取状态：ok
- 抓取日期：2026-01-11
- 本地缓存：.vibe/knowledge/sources/S-836/markitdown.md
- 引入原因：用户提供的“交易策略深入分析报告”参考链接，待提炼。
- 落地到本仓库：
  - 深度分析报告：`docs/knowledge/crypto_exchange_strategy_deep_dive.md`

### S-837 onemoneyway.com：dictionary/dollar-cost-averaging

- URL：https://onemoneyway.com/en/dictionary/dollar-cost-averaging/
- 抓取方式：MCP `playwright`
- 抓取状态：ok
- 抓取日期：2026-01-11
- 本地缓存：.vibe/knowledge/sources/S-837/playwright_snapshot.md
- 引入原因：用户提供的“交易策略深入分析报告”参考链接，待提炼。
- 落地到本仓库：
  - 深度分析报告：`docs/knowledge/crypto_exchange_strategy_deep_dive.md`

### S-838 www.valueaveraging.ca：research/DCA%20Investigation%20Study.pdf

- URL：http://www.valueaveraging.ca/research/DCA%20Investigation%20Study.pdf
- 抓取方式：MCP `playwright`
- 抓取状态：blocked（too_short，详见本地缓存 meta_playwright.json）
- 抓取状态备注：blocked（抓取失败，详见本地缓存 meta.json）
- 抓取日期：2026-01-11
- 本地缓存：.vibe/knowledge/sources/S-838/playwright_snapshot.md
- 引入原因：用户提供的“交易策略深入分析报告”参考链接，待提炼。
- 落地到本仓库：
  - 深度分析报告：`docs/knowledge/crypto_exchange_strategy_deep_dive.md`

### S-839 arXiv：2403.00770.pdf

- URL：https://arxiv.org/pdf/2403.00770.pdf
- 抓取方式：MCP `markitdown`
- 抓取状态：ok
- 抓取日期：2026-01-11
- 本地缓存：.vibe/knowledge/sources/S-839/markitdown.md
- 引入原因：用户提供的“交易策略深入分析报告”参考链接，待提炼。
- 落地到本仓库：
  - 深度分析报告：`docs/knowledge/crypto_exchange_strategy_deep_dive.md`

### S-840 SpringerLink：论文条目

- URL：https://link.springer.com/10.1007/s42979-025-04419-x
- 抓取方式：MCP `markitdown`
- 抓取状态：ok
- 抓取日期：2026-01-11
- 本地缓存：.vibe/knowledge/sources/S-840/markitdown.md
- 引入原因：用户提供的“交易策略深入分析报告”参考链接，待提炼。
- 落地到本仓库：
  - 深度分析报告：`docs/knowledge/crypto_exchange_strategy_deep_dive.md`

### S-841 aijfr.com：research-paper.php

- URL：https://aijfr.com/research-paper.php?id=1485
- 抓取方式：MCP `markitdown`
- 抓取状态：ok
- 抓取日期：2026-01-11
- 本地缓存：.vibe/knowledge/sources/S-841/markitdown.md
- 引入原因：用户提供的“交易策略深入分析报告”参考链接，待提炼。
- 落地到本仓库：
  - 深度分析报告：`docs/knowledge/crypto_exchange_strategy_deep_dive.md`

### S-842 SemanticScholar：论文条目

- URL：https://www.semanticscholar.org/paper/c1564b02c875faadc02fc8d31b5fa086d29ab02a
- 抓取方式：MCP `playwright`
- 抓取状态：ok
- 抓取日期：2026-01-11
- 本地缓存：.vibe/knowledge/sources/S-842/playwright_snapshot.md
- 引入原因：用户提供的“交易策略深入分析报告”参考链接，待提炼。
- 落地到本仓库：
  - 深度分析报告：`docs/knowledge/crypto_exchange_strategy_deep_dive.md`

### S-843 thesai.org：Publications/ViewPaper

- URL：http://thesai.org/Publications/ViewPaper?Volume=16&Issue=11&Code=ijacsa&SerialNo=81
- 抓取方式：MCP `markitdown`
- 抓取状态：ok
- 抓取日期：2026-01-11
- 本地缓存：.vibe/knowledge/sources/S-843/markitdown.md
- 引入原因：用户提供的“交易策略深入分析报告”参考链接，待提炼。
- 落地到本仓库：
  - 深度分析报告：`docs/knowledge/crypto_exchange_strategy_deep_dive.md`

### S-844 epstem.net：view/1057

- URL：https://epstem.net/index.php/epstem/article/view/1057
- 抓取方式：MCP `markitdown`
- 抓取状态：ok
- 抓取日期：2026-01-11
- 本地缓存：.vibe/knowledge/sources/S-844/markitdown.md
- 引入原因：用户提供的“交易策略深入分析报告”参考链接，待提炼。
- 落地到本仓库：
  - 深度分析报告：`docs/knowledge/crypto_exchange_strategy_deep_dive.md`

### S-845 www.mdpi.com：1/74

- URL：https://www.mdpi.com/2673-4591/38/1/74
- 抓取方式：MCP `playwright`
- 抓取状态：ok
- 抓取日期：2026-01-11
- 本地缓存：.vibe/knowledge/sources/S-845/playwright_snapshot.md
- 引入原因：用户提供的“交易策略深入分析报告”参考链接，待提炼。
- 落地到本仓库：
  - 深度分析报告：`docs/knowledge/crypto_exchange_strategy_deep_dive.md`

### S-846 IEEE Xplore：论文条目

- URL：https://ieeexplore.ieee.org/document/8459920/
- 抓取方式：MCP `playwright`
- 抓取状态：ok
- 抓取日期：2026-01-11
- 本地缓存：.vibe/knowledge/sources/S-846/playwright_snapshot.md
- 引入原因：用户提供的“交易策略深入分析报告”参考链接，待提炼。
- 落地到本仓库：
  - 深度分析报告：`docs/knowledge/crypto_exchange_strategy_deep_dive.md`

### S-847 arXiv：1903.06033.pdf

- URL：https://arxiv.org/pdf/1903.06033.pdf
- 抓取方式：MCP `markitdown`
- 抓取状态：ok
- 抓取日期：2026-01-11
- 本地缓存：.vibe/knowledge/sources/S-847/markitdown.md
- 引入原因：用户提供的“交易策略深入分析报告”参考链接，待提炼。
- 落地到本仓库：
  - 深度分析报告：`docs/knowledge/crypto_exchange_strategy_deep_dive.md`

### S-848 arXiv：2405.15461.pdf

- URL：https://arxiv.org/pdf/2405.15461.pdf
- 抓取方式：MCP `markitdown`
- 抓取状态：ok
- 抓取日期：2026-01-11
- 本地缓存：.vibe/knowledge/sources/S-848/markitdown.md
- 引入原因：用户提供的“交易策略深入分析报告”参考链接，待提炼。
- 落地到本仓库：
  - 深度分析报告：`docs/knowledge/crypto_exchange_strategy_deep_dive.md`

### S-849 arXiv：2305.06961.pdf

- URL：https://arxiv.org/pdf/2305.06961.pdf
- 抓取方式：MCP `markitdown`
- 抓取状态：ok
- 抓取日期：2026-01-11
- 本地缓存：.vibe/knowledge/sources/S-849/markitdown.md
- 引入原因：用户提供的“交易策略深入分析报告”参考链接，待提炼。
- 落地到本仓库：
  - 深度分析报告：`docs/knowledge/crypto_exchange_strategy_deep_dive.md`

### S-850 arXiv：2407.16103.pdf

- URL：https://arxiv.org/pdf/2407.16103.pdf
- 抓取方式：MCP `playwright`
- 抓取状态：blocked（too_short，详见本地缓存 meta_playwright.json）
- 抓取状态备注：blocked（抓取失败，详见本地缓存 meta.json）
- 抓取日期：2026-01-11
- 本地缓存：.vibe/knowledge/sources/S-850/playwright_snapshot.md
- 引入原因：用户提供的“交易策略深入分析报告”参考链接，待提炼。
- 落地到本仓库：
  - 深度分析报告：`docs/knowledge/crypto_exchange_strategy_deep_dive.md`

### S-851 arXiv：2310.08284.pdf

- URL：https://arxiv.org/pdf/2310.08284.pdf
- 抓取方式：MCP `markitdown`
- 抓取状态：ok
- 抓取日期：2026-01-11
- 本地缓存：.vibe/knowledge/sources/S-851/markitdown.md
- 引入原因：用户提供的“交易策略深入分析报告”参考链接，待提炼。
- 落地到本仓库：
  - 深度分析报告：`docs/knowledge/crypto_exchange_strategy_deep_dive.md`

### S-852 arXiv：2308.01427.pdf

- URL：https://arxiv.org/pdf/2308.01427.pdf
- 抓取方式：MCP `markitdown`
- 抓取状态：ok
- 抓取日期：2026-01-11
- 本地缓存：.vibe/knowledge/sources/S-852/markitdown.md
- 引入原因：用户提供的“交易策略深入分析报告”参考链接，待提炼。
- 落地到本仓库：
  - 深度分析报告：`docs/knowledge/crypto_exchange_strategy_deep_dive.md`

### S-853 arXiv：2104.14214.pdf

- URL：https://arxiv.org/pdf/2104.14214.pdf
- 抓取方式：MCP `playwright`
- 抓取状态：blocked（too_short，详见本地缓存 meta_playwright.json）
- 抓取状态备注：blocked（抓取失败，详见本地缓存 meta.json）
- 抓取日期：2026-01-11
- 本地缓存：.vibe/knowledge/sources/S-853/playwright_snapshot.md
- 引入原因：用户提供的“交易策略深入分析报告”参考链接，待提炼。
- 落地到本仓库：
  - 深度分析报告：`docs/knowledge/crypto_exchange_strategy_deep_dive.md`

### S-854 arXiv：2406.16573.pdf

- URL：https://arxiv.org/pdf/2406.16573.pdf
- 抓取方式：MCP `markitdown`
- 抓取状态：ok
- 抓取日期：2026-01-11
- 本地缓存：.vibe/knowledge/sources/S-854/markitdown.md
- 引入原因：用户提供的“交易策略深入分析报告”参考链接，待提炼。
- 落地到本仓库：
  - 深度分析报告：`docs/knowledge/crypto_exchange_strategy_deep_dive.md`

### S-855 www.dydx.xyz：crypto-learning/statistical-arbitrage

- URL：https://www.dydx.xyz/crypto-learning/statistical-arbitrage
- 抓取方式：MCP `markitdown`
- 抓取状态：ok
- 抓取日期：2026-01-11
- 本地缓存：.vibe/knowledge/sources/S-855/markitdown.md
- 引入原因：用户提供的“交易策略深入分析报告”参考链接，待提炼。
- 落地到本仓库：
  - 深度分析报告：`docs/knowledge/crypto_exchange_strategy_deep_dive.md`

### S-856 SSRN：论文预印本

- URL：https://papers.ssrn.com/sol3/Delivery.cfm/5263475.pdf?abstractid=5263475&mirid=1
- 抓取方式：MCP `playwright`
- 抓取状态：ok
- 抓取日期：2026-01-11
- 本地缓存：.vibe/knowledge/sources/S-856/playwright_snapshot.md
- 引入原因：用户提供的“交易策略深入分析报告”参考链接，待提炼。
- 落地到本仓库：
  - 深度分析报告：`docs/knowledge/crypto_exchange_strategy_deep_dive.md`

### S-857 mathematicsconsultants.com：17/ridge-regression-for-statistical-arbitrage-in-crypto-pairs-trading

- URL：https://mathematicsconsultants.com/2025/08/17/ridge-regression-for-statistical-arbitrage-in-crypto-pairs-trading/
- 抓取方式：MCP `playwright`
- 抓取状态：blocked（检测到人机验证/风控页面（需要人工验证）；如有合法访问权限可用 --interactive）
- 抓取状态备注：blocked（抓取失败，详见本地缓存 meta.json）
- 抓取日期：2026-01-11
- 本地缓存：.vibe/knowledge/sources/S-857/playwright_snapshot.md
- 引入原因：用户提供的“交易策略深入分析报告”参考链接，待提炼。
- 落地到本仓库：
  - 深度分析报告：`docs/knowledge/crypto_exchange_strategy_deep_dive.md`

### S-858 digitaldefynd.com：IQ/predictions-about-the-future-of-hedge-funds

- URL：https://digitaldefynd.com/IQ/predictions-about-the-future-of-hedge-funds/
- 抓取方式：MCP `markitdown`
- 抓取状态：ok
- 抓取日期：2026-01-11
- 本地缓存：.vibe/knowledge/sources/S-858/markitdown.md
- 引入原因：用户提供的“交易策略深入分析报告”参考链接，待提炼。
- 落地到本仓库：
  - 深度分析报告：`docs/knowledge/crypto_exchange_strategy_deep_dive.md`

### S-859 zignaly.com：algorithmic-strategies/algorithmic-crypto-trading

- URL：https://zignaly.com/crypto-trading/algorithmic-strategies/algorithmic-crypto-trading
- 抓取方式：MCP `playwright`
- 抓取状态：blocked（检测到权限/访问拒绝（可能需要授权或站点限制）；如有合法访问权限可用 --interactive）
- 抓取状态备注：blocked（抓取失败，详见本地缓存 meta.json）
- 抓取日期：2026-01-11
- 本地缓存：.vibe/knowledge/sources/S-859/playwright_snapshot.md
- 引入原因：用户提供的“交易策略深入分析报告”参考链接，待提炼。
- 落地到本仓库：
  - 深度分析报告：`docs/knowledge/crypto_exchange_strategy_deep_dive.md`

### S-860 iknowfirst.com：ai-powered-strategies-deliver-record-breaking-returns-december-2025-update

- URL：https://iknowfirst.com/ai-powered-strategies-deliver-record-breaking-returns-december-2025-update
- 抓取方式：MCP `playwright`
- 抓取状态：ok
- 抓取日期：2026-01-11
- 本地缓存：.vibe/knowledge/sources/S-860/playwright_snapshot.md
- 引入原因：用户提供的“交易策略深入分析报告”参考链接，待提炼。
- 落地到本仓库：
  - 深度分析报告：`docs/knowledge/crypto_exchange_strategy_deep_dive.md`

### S-861 arXiv：2410.13105.pdf

- URL：https://arxiv.org/pdf/2410.13105.pdf
- 抓取方式：MCP `playwright`
- 抓取状态：blocked（too_short，详见本地缓存 meta_playwright.json）
- 抓取状态备注：blocked（抓取失败，详见本地缓存 meta.json）
- 抓取日期：2026-01-11
- 本地缓存：.vibe/knowledge/sources/S-861/playwright_snapshot.md
- 引入原因：用户提供的“交易策略深入分析报告”参考链接，待提炼。
- 落地到本仓库：
  - 深度分析报告：`docs/knowledge/crypto_exchange_strategy_deep_dive.md`

### S-862 arXiv：2409.04233.pdf

- URL：http://arxiv.org/pdf/2409.04233.pdf
- 抓取方式：MCP `playwright`
- 抓取状态：blocked（too_short，详见本地缓存 meta_playwright.json）
- 抓取状态备注：blocked（抓取失败，详见本地缓存 meta.json）
- 抓取日期：2026-01-11
- 本地缓存：.vibe/knowledge/sources/S-862/playwright_snapshot.md
- 引入原因：用户提供的“交易策略深入分析报告”参考链接，待提炼。
- 落地到本仓库：
  - 深度分析报告：`docs/knowledge/crypto_exchange_strategy_deep_dive.md`

### S-863 arXiv：2411.19637.pdf

- URL：http://arxiv.org/pdf/2411.19637.pdf
- 抓取方式：MCP `playwright`
- 抓取状态：blocked（too_short，详见本地缓存 meta_playwright.json）
- 抓取状态备注：blocked（抓取失败，详见本地缓存 meta.json）
- 抓取日期：2026-01-11
- 本地缓存：.vibe/knowledge/sources/S-863/playwright_snapshot.md
- 引入原因：用户提供的“交易策略深入分析报告”参考链接，待提炼。
- 落地到本仓库：
  - 深度分析报告：`docs/knowledge/crypto_exchange_strategy_deep_dive.md`

### S-864 arXiv：2304.04453.pdf

- URL：http://arxiv.org/pdf/2304.04453.pdf
- 抓取方式：MCP `markitdown`
- 抓取状态：ok
- 抓取日期：2026-01-11
- 本地缓存：.vibe/knowledge/sources/S-864/markitdown.md
- 引入原因：用户提供的“交易策略深入分析报告”参考链接，待提炼。
- 落地到本仓库：
  - 深度分析报告：`docs/knowledge/crypto_exchange_strategy_deep_dive.md`

### S-865 arXiv：2208.06046.pdf

- URL：https://arxiv.org/pdf/2208.06046.pdf
- 抓取方式：MCP `playwright`
- 抓取状态：blocked（too_short，详见本地缓存 meta_playwright.json）
- 抓取状态备注：blocked（抓取失败，详见本地缓存 meta.json）
- 抓取日期：2026-01-11
- 本地缓存：.vibe/knowledge/sources/S-865/playwright_snapshot.md
- 引入原因：用户提供的“交易策略深入分析报告”参考链接，待提炼。
- 落地到本仓库：
  - 深度分析报告：`docs/knowledge/crypto_exchange_strategy_deep_dive.md`

### S-866 arXiv：1605.07884.pdf

- URL：https://arxiv.org/pdf/1605.07884.pdf
- 抓取方式：MCP `markitdown`
- 抓取状态：ok
- 抓取日期：2026-01-11
- 本地缓存：.vibe/knowledge/sources/S-866/markitdown.md
- 引入原因：用户提供的“交易策略深入分析报告”参考链接，待提炼。
- 落地到本仓库：
  - 深度分析报告：`docs/knowledge/crypto_exchange_strategy_deep_dive.md`

### S-867 arXiv：2309.08431.pdf

- URL：https://arxiv.org/pdf/2309.08431.pdf
- 抓取方式：MCP `markitdown`
- 抓取状态：ok
- 抓取日期：2026-01-11
- 本地缓存：.vibe/knowledge/sources/S-867/markitdown.md
- 引入原因：用户提供的“交易策略深入分析报告”参考链接，待提炼。
- 落地到本仓库：
  - 深度分析报告：`docs/knowledge/crypto_exchange_strategy_deep_dive.md`

### S-868 arXiv：2502.12774.pdf

- URL：https://arxiv.org/pdf/2502.12774.pdf
- 抓取方式：MCP `markitdown`
- 抓取状态：ok
- 抓取日期：2026-01-11
- 本地缓存：.vibe/knowledge/sources/S-868/markitdown.md
- 引入原因：用户提供的“交易策略深入分析报告”参考链接，待提炼。
- 落地到本仓库：
  - 深度分析报告：`docs/knowledge/crypto_exchange_strategy_deep_dive.md`

### S-869 pmc.ncbi.nlm.nih.gov：articles/PMC11935774

- URL：https://pmc.ncbi.nlm.nih.gov/articles/PMC11935774/
- 抓取方式：MCP `playwright`
- 抓取状态：ok
- 抓取日期：2026-01-11
- 本地缓存：.vibe/knowledge/sources/S-869/playwright_snapshot.md
- 引入原因：用户提供的“交易策略深入分析报告”参考链接，待提炼。
- 落地到本仓库：
  - 深度分析报告：`docs/knowledge/crypto_exchange_strategy_deep_dive.md`

### S-870 www.atlantis-press.com：article/125999624.pdf

- URL：https://www.atlantis-press.com/article/125999624.pdf
- 抓取方式：MCP `playwright`
- 抓取状态：ok
- 抓取日期：2026-01-11
- 本地缓存：.vibe/knowledge/sources/S-870/playwright_snapshot.md
- 引入原因：用户提供的“交易策略深入分析报告”参考链接，待提炼。
- 落地到本仓库：
  - 深度分析报告：`docs/knowledge/crypto_exchange_strategy_deep_dive.md`

### S-871 www.sciencedirect.com：pii/S2772941925000274

- URL：https://www.sciencedirect.com/science/article/pii/S2772941925000274
- 抓取方式：MCP `playwright`
- 抓取状态：blocked（检测到人机验证/风控页面（需要人工验证）；如有合法访问权限可用 --interactive）
- 抓取状态备注：blocked（抓取失败，详见本地缓存 meta.json）
- 抓取日期：2026-01-11
- 本地缓存：.vibe/knowledge/sources/S-871/playwright_snapshot.md
- 引入原因：用户提供的“交易策略深入分析报告”参考链接，待提炼。
- 落地到本仓库：
  - 深度分析报告：`docs/knowledge/crypto_exchange_strategy_deep_dive.md`

### S-872 al-kindipublishers.org：10158/9091

- URL：https://al-kindipublishers.org/index.php/jefas/article/view/10158/9091
- 抓取方式：MCP `markitdown`
- 抓取状态：ok
- 抓取日期：2026-01-11
- 本地缓存：.vibe/knowledge/sources/S-872/markitdown.md
- 引入原因：用户提供的“交易策略深入分析报告”参考链接，待提炼。
- 落地到本仓库：
  - 深度分析报告：`docs/knowledge/crypto_exchange_strategy_deep_dive.md`

### S-873 arXiv：2403.03606.pdf

- URL：https://arxiv.org/pdf/2403.03606.pdf
- 抓取方式：MCP `markitdown`
- 抓取状态：ok
- 抓取日期：2026-01-11
- 本地缓存：.vibe/knowledge/sources/S-873/markitdown.md
- 引入原因：用户提供的“交易策略深入分析报告”参考链接，待提炼。
- 落地到本仓库：
  - 深度分析报告：`docs/knowledge/crypto_exchange_strategy_deep_dive.md`

### S-874 faba.bg：view/284

- URL：https://faba.bg/index.php/faba/article/view/284
- 抓取方式：MCP `markitdown`
- 抓取状态：ok
- 抓取日期：2026-01-11
- 本地缓存：.vibe/knowledge/sources/S-874/markitdown.md
- 引入原因：用户提供的“交易策略深入分析报告”参考链接，待提炼。
- 落地到本仓库：
  - 深度分析报告：`docs/knowledge/crypto_exchange_strategy_deep_dive.md`

### S-875 SemanticScholar：论文条目

- URL：https://www.semanticscholar.org/paper/a7f5bda156f4f45e3448494905a5bebae40df79f
- 抓取方式：MCP `playwright`
- 抓取状态：ok
- 抓取日期：2026-01-11
- 本地缓存：.vibe/knowledge/sources/S-875/playwright_snapshot.md
- 引入原因：用户提供的“交易策略深入分析报告”参考链接，待提炼。
- 落地到本仓库：
  - 深度分析报告：`docs/knowledge/crypto_exchange_strategy_deep_dive.md`

### S-876 SemanticScholar：论文条目

- URL：https://www.semanticscholar.org/paper/d8195c30e4167322994b8c72f3101573f90afc0c
- 抓取方式：MCP `playwright`
- 抓取状态：ok
- 抓取日期：2026-01-11
- 本地缓存：.vibe/knowledge/sources/S-876/playwright_snapshot.md
- 引入原因：用户提供的“交易策略深入分析报告”参考链接，待提炼。
- 落地到本仓库：
  - 深度分析报告：`docs/knowledge/crypto_exchange_strategy_deep_dive.md`

### S-877 SemanticScholar：论文条目

- URL：https://www.semanticscholar.org/paper/451d04631bc81538dc9f742f60c2905f4f831b38
- 抓取方式：MCP `playwright`
- 抓取状态：ok
- 抓取日期：2026-01-11
- 本地缓存：.vibe/knowledge/sources/S-877/playwright_snapshot.md
- 引入原因：用户提供的“交易策略深入分析报告”参考链接，待提炼。
- 落地到本仓库：
  - 深度分析报告：`docs/knowledge/crypto_exchange_strategy_deep_dive.md`

### S-878 SemanticScholar：论文条目

- URL：https://www.semanticscholar.org/paper/d8e16cb3c464e80534f2d4f987a84bcb53603406
- 抓取方式：MCP `playwright`
- 抓取状态：ok
- 抓取日期：2026-01-11
- 本地缓存：.vibe/knowledge/sources/S-878/playwright_snapshot.md
- 引入原因：用户提供的“交易策略深入分析报告”参考链接，待提炼。
- 落地到本仓库：
  - 深度分析报告：`docs/knowledge/crypto_exchange_strategy_deep_dive.md`

### S-879 arXiv：2502.19349.pdf

- URL：https://arxiv.org/pdf/2502.19349.pdf
- 抓取方式：MCP `playwright`
- 抓取状态：ok
- 抓取日期：2026-01-11
- 本地缓存：.vibe/knowledge/sources/S-879/playwright_snapshot.md
- 引入原因：用户提供的“交易策略深入分析报告”参考链接，待提炼。
- 落地到本仓库：
  - 深度分析报告：`docs/knowledge/crypto_exchange_strategy_deep_dive.md`

### S-880 www.mdpi.com：3/34

- URL：https://www.mdpi.com/2571-9394/6/3/34
- 抓取方式：MCP `playwright`
- 抓取状态：ok
- 抓取日期：2026-01-11
- 本地缓存：.vibe/knowledge/sources/S-880/playwright_snapshot.md
- 引入原因：用户提供的“交易策略深入分析报告”参考链接，待提炼。
- 落地到本仓库：
  - 深度分析报告：`docs/knowledge/crypto_exchange_strategy_deep_dive.md`

### S-881 virtusinterpress.org：spip.php

- URL：https://virtusinterpress.org/spip.php?action=telecharger&arg=13130&hash=14ff875c4e76427b80c0a394cca2af7c07153021
- 抓取方式：MCP `playwright`
- 抓取状态：ok
- 抓取日期：2026-01-11
- 本地缓存：.vibe/knowledge/sources/S-881/playwright_snapshot.md
- 引入原因：用户提供的“交易策略深入分析报告”参考链接，待提炼。
- 落地到本仓库：
  - 深度分析报告：`docs/knowledge/crypto_exchange_strategy_deep_dive.md`

### S-882 arXiv：2306.08157.pdf

- URL：http://arxiv.org/pdf/2306.08157.pdf
- 抓取方式：MCP `markitdown`
- 抓取状态：ok
- 抓取日期：2026-01-11
- 本地缓存：.vibe/knowledge/sources/S-882/markitdown.md
- 引入原因：用户提供的“交易策略深入分析报告”参考链接，待提炼。
- 落地到本仓库：
  - 深度分析报告：`docs/knowledge/crypto_exchange_strategy_deep_dive.md`

### S-883 veli.io：blog/how-to-profit-from-volatility-a-guide-to-crypto-swing-trading

- URL：https://veli.io/blog/how-to-profit-from-volatility-a-guide-to-crypto-swing-trading/
- 抓取方式：MCP `markitdown`
- 抓取状态：ok
- 抓取日期：2026-01-11
- 本地缓存：.vibe/knowledge/sources/S-883/markitdown.md
- 引入原因：用户提供的“交易策略深入分析报告”参考链接，待提炼。
- 落地到本仓库：
  - 深度分析报告：`docs/knowledge/crypto_exchange_strategy_deep_dive.md`

### S-884 en.arincen.com：crypto/swing-trading-crypto

- URL：https://en.arincen.com/blog/crypto/swing-trading-crypto
- 抓取方式：MCP `markitdown`
- 抓取状态：ok
- 抓取日期：2026-01-11
- 本地缓存：.vibe/knowledge/sources/S-884/markitdown.md
- 引入原因：用户提供的“交易策略深入分析报告”参考链接，待提炼。
- 落地到本仓库：
  - 深度分析报告：`docs/knowledge/crypto_exchange_strategy_deep_dive.md`

### S-885 ironwoodwm.com：how-dca-investing-helps-manage-risk-in-volatile-markets

- URL：https://ironwoodwm.com/how-dca-investing-helps-manage-risk-in-volatile-markets/
- 抓取方式：MCP `playwright`
- 抓取状态：blocked（检测到人机验证/风控页面（需要人工验证）；如有合法访问权限可用 --interactive）
- 抓取状态备注：blocked（抓取失败，详见本地缓存 meta.json）
- 抓取日期：2026-01-11
- 本地缓存：.vibe/knowledge/sources/S-885/playwright_snapshot.md
- 引入原因：用户提供的“交易策略深入分析报告”参考链接，待提炼。
- 落地到本仓库：
  - 深度分析报告：`docs/knowledge/crypto_exchange_strategy_deep_dive.md`

---

## L) 用户提供：小账户到大账户实践指南参考（待提炼）

### S-886 www.reddit.com：hpka8u/anyone_succesfully_or_tried_and_failed_to_apply

- URL：https://www.reddit.com/r/Daytrading/comments/hpka8u/anyone_succesfully_or_tried_and_failed_to_apply/
- 抓取方式：MCP `markitdown`
- 抓取状态：ok
- 抓取日期：2026-01-11
- 本地缓存：.vibe/knowledge/sources/S-886/markitdown.md
- 引入原因：用户提供的“小账户（$10）到大账户（$10,000+）实践指南”参考链接，待提炼。
- 落地到本仓库：
  - 实践指南：`docs/knowledge/small_account_10_to_10000_practice_guide.md`

### S-887 www.reddit.com：r8pc7y/making_a_daily_2_gain

- URL：https://www.reddit.com/r/Daytrading/comments/r8pc7y/making_a_daily_2_gain/
- 抓取方式：MCP `markitdown`
- 抓取状态：ok
- 抓取日期：2026-01-11
- 本地缓存：.vibe/knowledge/sources/S-887/markitdown.md
- 引入原因：用户提供的“小账户（$10）到大账户（$10,000+）实践指南”参考链接，待提炼。
- 落地到本仓库：
  - 实践指南：`docs/knowledge/small_account_10_to_10000_practice_guide.md`

### S-888 www.home.saxo：how-to-maximise-your-compounding-returns-a-comprehensive-guide

- URL：https://www.home.saxo/learn/guides/trading-strategies/how-to-maximise-your-compounding-returns-a-comprehensive-guide
- 抓取方式：MCP `markitdown`
- 抓取状态：ok
- 抓取日期：2026-01-11
- 本地缓存：.vibe/knowledge/sources/S-888/markitdown.md
- 引入原因：用户提供的“小账户（$10）到大账户（$10,000+）实践指南”参考链接，待提炼。
- 落地到本仓库：
  - 实践指南：`docs/knowledge/small_account_10_to_10000_practice_guide.md`

### S-889 www.dukascopy.com：can-forex-make-a-millionaire

- URL：https://www.dukascopy.com/swiss/english/marketwatch/articles/can-forex-make-a-millionaire/
- 抓取方式：MCP `playwright`
- 抓取状态：ok
- 抓取日期：2026-01-11
- 本地缓存：.vibe/knowledge/sources/S-889/playwright_snapshot.md
- 引入原因：用户提供的“小账户（$10）到大账户（$10,000+）实践指南”参考链接，待提炼。
- 落地到本仓库：
  - 实践指南：`docs/knowledge/small_account_10_to_10000_practice_guide.md`

### S-890 pocketoption.com：day-trading-with-small-account

- URL：https://pocketoption.com/blog/en/knowledge-base/learning/day-trading-with-small-account/
- 抓取方式：MCP `markitdown`
- 抓取状态：ok
- 抓取日期：2026-01-11
- 本地缓存：.vibe/knowledge/sources/S-890/markitdown.md
- 引入原因：用户提供的“小账户（$10）到大账户（$10,000+）实践指南”参考链接，待提炼。
- 落地到本仓库：
  - 实践指南：`docs/knowledge/small_account_10_to_10000_practice_guide.md`

### S-891 www.reddit.com：FuturesTrading/1cjudca/growing_a_small_account_fast_is_indeed_possible

- URL：https://www.reddit.com/r/FuturesTrading/comments/1cjudca/growing_a_small_account_fast_is_indeed_possible/
- 抓取方式：MCP `markitdown`
- 抓取状态：ok
- 抓取日期：2026-01-11
- 本地缓存：.vibe/knowledge/sources/S-891/markitdown.md
- 引入原因：用户提供的“小账户（$10）到大账户（$10,000+）实践指南”参考链接，待提炼。
- 落地到本仓库：
  - 实践指南：`docs/knowledge/small_account_10_to_10000_practice_guide.md`

### S-892 www.dominionmarkets.com：best-leverage-for-small-account

- URL：https://www.dominionmarkets.com/best-leverage-for-small-account/
- 抓取方式：MCP `playwright`
- 抓取状态：ok
- 抓取日期：2026-01-11
- 本地缓存：.vibe/knowledge/sources/S-892/playwright_snapshot.md
- 引入原因：用户提供的“小账户（$10）到大账户（$10,000+）实践指南”参考链接，待提炼。
- 落地到本仓库：
  - 实践指南：`docs/knowledge/small_account_10_to_10000_practice_guide.md`

### S-893 www.reddit.com：PMTraders/1am7lcy/using_kelly_criterion_to_estimate_position_sizing

- URL：https://www.reddit.com/r/PMTraders/comments/1am7lcy/using_kelly_criterion_to_estimate_position_sizing/
- 抓取方式：MCP `markitdown`
- 抓取状态：ok
- 抓取日期：2026-01-11
- 本地缓存：.vibe/knowledge/sources/S-893/markitdown.md
- 引入原因：用户提供的“小账户（$10）到大账户（$10,000+）实践指南”参考链接，待提炼。
- 落地到本仓库：
  - 实践指南：`docs/knowledge/small_account_10_to_10000_practice_guide.md`

### S-894 www.tradingsetupsreview.com：position-sizing-important-trading-rule

- URL：https://www.tradingsetupsreview.com/position-sizing-important-trading-rule/
- 抓取方式：MCP `markitdown`
- 抓取状态：ok
- 抓取日期：2026-01-11
- 本地缓存：.vibe/knowledge/sources/S-894/markitdown.md
- 引入原因：用户提供的“小账户（$10）到大账户（$10,000+）实践指南”参考链接，待提炼。
- 落地到本仓库：
  - 实践指南：`docs/knowledge/small_account_10_to_10000_practice_guide.md`

### S-895 astuteinvestorscalculus.com：the-kelly-criterion

- URL：https://astuteinvestorscalculus.com/the-kelly-criterion/
- 抓取方式：MCP `markitdown`
- 抓取状态：ok
- 抓取日期：2026-01-11
- 本地缓存：.vibe/knowledge/sources/S-895/markitdown.md
- 引入原因：用户提供的“小账户（$10）到大账户（$10,000+）实践指南”参考链接，待提炼。
- 落地到本仓库：
  - 实践指南：`docs/knowledge/small_account_10_to_10000_practice_guide.md`

### S-896 blog.oneuptrader.com：optimizing-risk-management-in-trading-using-the-kelly-criterion

- URL：https://blog.oneuptrader.com/strategies/optimizing-risk-management-in-trading-using-the-kelly-criterion/
- 抓取方式：MCP `markitdown`
- 抓取状态：ok
- 抓取日期：2026-01-11
- 本地缓存：.vibe/knowledge/sources/S-896/markitdown.md
- 引入原因：用户提供的“小账户（$10）到大账户（$10,000+）实践指南”参考链接，待提炼。
- 落地到本仓库：
  - 实践指南：`docs/knowledge/small_account_10_to_10000_practice_guide.md`

### S-897 trakx.io：9-common-crypto-trading-mistakes-to-avoid

- URL：https://trakx.io/resources/insights/9-common-crypto-trading-mistakes-to-avoid/
- 抓取方式：MCP `playwright`
- 抓取状态：ok
- 抓取日期：2026-01-11
- 本地缓存：.vibe/knowledge/sources/S-897/playwright_snapshot.md
- 引入原因：用户提供的“小账户（$10）到大账户（$10,000+）实践指南”参考链接，待提炼。
- 落地到本仓库：
  - 实践指南：`docs/knowledge/small_account_10_to_10000_practice_guide.md`

### S-898 liquidityfinder.com：why-most-traders-fail-trading-psychology-and-the-hidden-mental-game

- URL：https://liquidityfinder.com/news/why-most-traders-fail-trading-psychology-and-the-hidden-mental-game-b08a4
- 抓取方式：MCP `playwright`
- 抓取状态：ok
- 抓取日期：2026-01-11
- 本地缓存：.vibe/knowledge/sources/S-898/playwright_snapshot.md
- 引入原因：用户提供的“小账户（$10）到大账户（$10,000+）实践指南”参考链接，待提炼。
- 落地到本仓库：
  - 实践指南：`docs/knowledge/small_account_10_to_10000_practice_guide.md`

### S-899 optimusfutures.com：day-trading-psychology-start-over

- URL：https://optimusfutures.com/blog/day-trading-psychology-start-over/
- 抓取方式：MCP `markitdown`
- 抓取状态：ok
- 抓取日期：2026-01-11
- 本地缓存：.vibe/knowledge/sources/S-899/markitdown.md
- 引入原因：用户提供的“小账户（$10）到大账户（$10,000+）实践指南”参考链接，待提炼。
- 落地到本仓库：
  - 实践指南：`docs/knowledge/small_account_10_to_10000_practice_guide.md`

### S-900 arxiv.org：pdf/2101.07217

- URL：https://arxiv.org/pdf/2101.07217.pdf
- 抓取方式：MCP `markitdown`
- 抓取状态：ok
- 抓取日期：2026-01-11
- 本地缓存：.vibe/knowledge/sources/S-900/markitdown.md
- 引入原因：用户提供的“小账户（$10）到大账户（$10,000+）实践指南”参考链接，待提炼。
- 落地到本仓库：
  - 实践指南：`docs/knowledge/small_account_10_to_10000_practice_guide.md`

### S-901 arxiv.org：pdf/1812.02527

- URL：https://arxiv.org/pdf/1812.02527.pdf
- 抓取方式：MCP `markitdown`
- 抓取状态：ok
- 抓取日期：2026-01-11
- 本地缓存：.vibe/knowledge/sources/S-901/markitdown.md
- 引入原因：用户提供的“小账户（$10）到大账户（$10,000+）实践指南”参考链接，待提炼。
- 落地到本仓库：
  - 实践指南：`docs/knowledge/small_account_10_to_10000_practice_guide.md`

### S-902 arxiv.org：pdf/1009.4683

- URL：http://arxiv.org/pdf/1009.4683.pdf
- 抓取方式：MCP `markitdown`
- 抓取状态：ok
- 抓取日期：2026-01-11
- 本地缓存：.vibe/knowledge/sources/S-902/markitdown.md
- 引入原因：用户提供的“小账户（$10）到大账户（$10,000+）实践指南”参考链接，待提炼。
- 落地到本仓库：
  - 实践指南：`docs/knowledge/small_account_10_to_10000_practice_guide.md`

### S-903 arxiv.org：pdf/1107.0036

- URL：https://arxiv.org/pdf/1107.0036.pdf
- 抓取方式：MCP `markitdown`
- 抓取状态：ok
- 抓取日期：2026-01-11
- 本地缓存：.vibe/knowledge/sources/S-903/markitdown.md
- 引入原因：用户提供的“小账户（$10）到大账户（$10,000+）实践指南”参考链接，待提炼。
- 落地到本仓库：
  - 实践指南：`docs/knowledge/small_account_10_to_10000_practice_guide.md`

### S-904 arxiv.org：pdf/1712.07649

- URL：http://arxiv.org/pdf/1712.07649.pdf
- 抓取方式：MCP `playwright`
- 抓取状态：blocked（too_short，详见本地缓存 meta_playwright.json）
- 抓取状态备注：blocked（抓取失败，详见本地缓存 meta.json）
- 抓取日期：2026-01-11
- 本地缓存：.vibe/knowledge/sources/S-904/playwright_snapshot.md
- 引入原因：用户提供的“小账户（$10）到大账户（$10,000+）实践指南”参考链接，待提炼。
- 落地到本仓库：
  - 实践指南：`docs/knowledge/small_account_10_to_10000_practice_guide.md`

### S-905 dx.plos.org：10.1371/journal.pone.0294970

- URL：https://dx.plos.org/10.1371/journal.pone.0294970
- 抓取方式：MCP `markitdown`
- 抓取状态：ok
- 抓取日期：2026-01-11
- 本地缓存：.vibe/knowledge/sources/S-905/markitdown.md
- 引入原因：用户提供的“小账户（$10）到大账户（$10,000+）实践指南”参考链接，待提炼。
- 落地到本仓库：
  - 实践指南：`docs/knowledge/small_account_10_to_10000_practice_guide.md`

### S-906 www.reddit.com：options/1q49yi7/starting_new_account_with_1000

- URL：https://www.reddit.com/r/options/comments/1q49yi7/starting_new_account_with_1000/
- 抓取方式：MCP `markitdown`
- 抓取状态：ok
- 抓取日期：2026-01-11
- 本地缓存：.vibe/knowledge/sources/S-906/markitdown.md
- 引入原因：用户提供的“小账户（$10）到大账户（$10,000+）实践指南”参考链接，待提炼。
- 落地到本仓库：
  - 实践指南：`docs/knowledge/small_account_10_to_10000_practice_guide.md`

### S-907 www.tradingsim.com：small-account-strategy

- URL：https://www.tradingsim.com/blog/small-account-strategy
- 抓取方式：MCP `playwright`
- 抓取状态：ok
- 抓取日期：2026-01-11
- 本地缓存：.vibe/knowledge/sources/S-907/playwright_snapshot.md
- 引入原因：用户提供的“小账户（$10）到大账户（$10,000+）实践指南”参考链接，待提炼。
- 落地到本仓库：
  - 实践指南：`docs/knowledge/small_account_10_to_10000_practice_guide.md`

### S-908 tradingstrategyguides.com：trading-a-small-account-with-patience

- URL：https://tradingstrategyguides.com/trading-a-small-account-with-patience/
- 抓取方式：MCP `markitdown`
- 抓取状态：ok
- 抓取日期：2026-01-11
- 本地缓存：.vibe/knowledge/sources/S-908/markitdown.md
- 引入原因：用户提供的“小账户（$10）到大账户（$10,000+）实践指南”参考链接，待提炼。
- 落地到本仓库：
  - 实践指南：`docs/knowledge/small_account_10_to_10000_practice_guide.md`

### S-909 matthewdowney.github.io：uncertainty-kelly-criterion-optimal-bet-size

- URL：https://matthewdowney.github.io/uncertainty-kelly-criterion-optimal-bet-size.html
- 抓取方式：MCP `markitdown`
- 抓取状态：ok
- 抓取日期：2026-01-11
- 本地缓存：.vibe/knowledge/sources/S-909/markitdown.md
- 引入原因：用户提供的“小账户（$10）到大账户（$10,000+）实践指南”参考链接，待提炼。
- 落地到本仓库：
  - 实践指南：`docs/knowledge/small_account_10_to_10000_practice_guide.md`

### S-910 arxiv.org：pdf/2305.10624

- URL：https://arxiv.org/pdf/2305.10624.pdf
- 抓取方式：MCP `markitdown`
- 抓取状态：ok
- 抓取日期：2026-01-11
- 本地缓存：.vibe/knowledge/sources/S-910/markitdown.md
- 引入原因：用户提供的“小账户（$10）到大账户（$10,000+）实践指南”参考链接，待提炼。
- 落地到本仓库：
  - 实践指南：`docs/knowledge/small_account_10_to_10000_practice_guide.md`

### S-911 arxiv.org：pdf/2411.14068

- URL：http://arxiv.org/pdf/2411.14068.pdf
- 抓取方式：MCP `markitdown`
- 抓取状态：ok
- 抓取日期：2026-01-11
- 本地缓存：.vibe/knowledge/sources/S-911/markitdown.md
- 引入原因：用户提供的“小账户（$10）到大账户（$10,000+）实践指南”参考链接，待提炼。
- 落地到本仓库：
  - 实践指南：`docs/knowledge/small_account_10_to_10000_practice_guide.md`

### S-912 optimusfutures.com：micro-vs-mini-futures

- URL：https://optimusfutures.com/blog/micro-vs-mini-futures/
- 抓取方式：MCP `markitdown`
- 抓取状态：ok
- 抓取日期：2026-01-11
- 本地缓存：.vibe/knowledge/sources/S-912/markitdown.md
- 引入原因：用户提供的“小账户（$10）到大账户（$10,000+）实践指南”参考链接，待提炼。
- 落地到本仓库：
  - 实践指南：`docs/knowledge/small_account_10_to_10000_practice_guide.md`

### S-913 highstrike.com：mes-point-value

- URL：https://highstrike.com/mes-point-value/
- 抓取方式：MCP `playwright`
- 抓取状态：ok
- 抓取日期：2026-01-11
- 本地缓存：.vibe/knowledge/sources/S-913/playwright_snapshot.md
- 引入原因：用户提供的“小账户（$10）到大账户（$10,000+）实践指南”参考链接，待提炼。
- 落地到本仓库：
  - 实践指南：`docs/knowledge/small_account_10_to_10000_practice_guide.md`

### S-914 insigniafutures.com：mastering-emini-sp-500-futures-trading-guide

- URL：https://insigniafutures.com/mastering-emini-sp-500-futures-trading-guide/
- 抓取方式：MCP `playwright`
- 抓取状态：ok
- 抓取日期：2026-01-11
- 本地缓存：.vibe/knowledge/sources/S-914/playwright_snapshot.md
- 引入原因：用户提供的“小账户（$10）到大账户（$10,000+）实践指南”参考链接，待提炼。
- 落地到本仓库：
  - 实践指南：`docs/knowledge/small_account_10_to_10000_practice_guide.md`

### S-915 www.cmegroup.com：micro-e-mini-futures/hedging-with-the-micro-e-mini-futures

- URL：https://www.cmegroup.com/education/courses/micro-e-mini-futures/hedging-with-the-micro-e-mini-futures.html
- 抓取方式：MCP `playwright`
- 抓取状态：ok
- 抓取日期：2026-01-11
- 本地缓存：.vibe/knowledge/sources/S-915/playwright_snapshot.md
- 引入原因：用户提供的“小账户（$10）到大账户（$10,000+）实践指南”参考链接，待提炼。
- 落地到本仓库：
  - 实践指南：`docs/knowledge/small_account_10_to_10000_practice_guide.md`

### S-916 www.reddit.com：RealDayTrading/sm4ldy/an_sp_futures_challenge_for_traders

- URL：https://www.reddit.com/r/RealDayTrading/comments/sm4ldy/an_sp_futures_challenge_for_traders/
- 抓取方式：MCP `playwright`
- 抓取状态：ok
- 抓取日期：2026-01-11
- 本地缓存：.vibe/knowledge/sources/S-916/playwright_snapshot.md
- 引入原因：用户提供的“小账户（$10）到大账户（$10,000+）实践指南”参考链接，待提炼。
- 落地到本仓库：
  - 实践指南：`docs/knowledge/small_account_10_to_10000_practice_guide.md`

### S-917 www.freqtrade.io：stable/backtesting

- URL：https://www.freqtrade.io/en/stable/backtesting/
- 抓取方式：MCP `markitdown`
- 抓取状态：ok
- 抓取日期：2026-01-11
- 本地缓存：.vibe/knowledge/sources/S-917/markitdown.md
- 引入原因：用户提供的“Freqtrade + OKX 实现路线图”参考链接，待提炼。
- 落地到本仓库：
  - 实践指南：`docs/knowledge/small_account_10_to_10000_practice_guide.md`

### S-918 www.freqtrade.io：stable/hyperopt

- URL：https://www.freqtrade.io/en/stable/hyperopt/
- 抓取方式：MCP `markitdown`
- 抓取状态：ok
- 抓取日期：2026-01-11
- 本地缓存：.vibe/knowledge/sources/S-918/markitdown.md
- 引入原因：用户提供的“Freqtrade + OKX 实现路线图”参考链接，待提炼。
- 落地到本仓库：
  - 实践指南：`docs/knowledge/small_account_10_to_10000_practice_guide.md`

### S-919 www.freqtrade.io：stable/strategy-customization

- URL：https://www.freqtrade.io/en/stable/strategy-customization/
- 抓取方式：MCP `markitdown`
- 抓取状态：ok
- 抓取日期：2026-01-11
- 本地缓存：.vibe/knowledge/sources/S-919/markitdown.md
- 引入原因：用户提供的“Freqtrade + OKX 实现路线图”参考链接，待提炼。
- 落地到本仓库：
  - 实践指南：`docs/knowledge/small_account_10_to_10000_practice_guide.md`

### S-920 www.freqtrade.io：stable/configuration

- URL：https://www.freqtrade.io/en/stable/configuration/
- 抓取方式：MCP `markitdown`
- 抓取状态：ok
- 抓取日期：2026-01-11
- 本地缓存：.vibe/knowledge/sources/S-920/markitdown.md
- 引入原因：用户提供的“Freqtrade + OKX 实现路线图”参考链接，待提炼。
- 落地到本仓库：
  - 实践指南：`docs/knowledge/small_account_10_to_10000_practice_guide.md`

### S-921 www.okx.com：docs-v5/en

- URL：https://www.okx.com/docs-v5/en/
- 抓取方式：MCP `markitdown`
- 抓取状态：ok
- 抓取日期：2026-01-11
- 本地缓存：.vibe/knowledge/sources/S-921/markitdown.md
- 引入原因：用户提供的“Freqtrade + OKX 实现路线图”参考链接，待提炼。
- 落地到本仓库：
  - 实践指南：`docs/knowledge/small_account_10_to_10000_practice_guide.md`

### S-922 docs.ccxt.com：exchanges/okx

- URL：https://docs.ccxt.com/exchanges/okx
- 抓取方式：MCP `playwright`
- 抓取状态：ok
- 抓取日期：2026-01-11
- 本地缓存：.vibe/knowledge/sources/S-922/playwright_snapshot.md
- 引入原因：用户提供的“Freqtrade + OKX 实现路线图”参考链接，待提炼。
- 落地到本仓库：
  - 实践指南：`docs/knowledge/small_account_10_to_10000_practice_guide.md`

### S-923 github.com：ccxt/issues/19618

- URL：https://github.com/ccxt/ccxt/issues/19618
- 抓取方式：MCP `playwright`
- 抓取状态：blocked（检测到人机验证/风控页面（需要人工验证）；如有合法访问权限可用 --interactive）
- 抓取状态备注：blocked（抓取失败，详见本地缓存 meta.json）
- 抓取日期：2026-01-11
- 本地缓存：.vibe/knowledge/sources/S-923/playwright_snapshot.md
- 引入原因：用户提供的“Freqtrade + OKX 实现路线图”参考链接，待提炼。
- 落地到本仓库：
  - 实践指南：`docs/knowledge/small_account_10_to_10000_practice_guide.md`

### S-924 github.com：freqtrade/issues/6422

- URL：https://github.com/freqtrade/freqtrade/issues/6422
- 抓取方式：MCP `markitdown`
- 抓取状态：ok
- 抓取日期：2026-01-11
- 本地缓存：.vibe/knowledge/sources/S-924/markitdown.md
- 引入原因：用户提供的“Freqtrade + OKX 实现路线图”参考链接，待提炼。
- 落地到本仓库：
  - 实践指南：`docs/knowledge/small_account_10_to_10000_practice_guide.md`

### S-925 stackoverflow.com：72173451/creating-okex-orders-using-ccxt

- URL：https://stackoverflow.com/questions/72173451/creating-okex-orders-using-ccxt
- 抓取方式：MCP `markitdown`
- 抓取状态：ok
- 抓取日期：2026-01-11
- 本地缓存：.vibe/knowledge/sources/S-925/markitdown.md
- 引入原因：用户提供的“Freqtrade + OKX 实现路线图”参考链接，待提炼。
- 落地到本仓库：
  - 实践指南：`docs/knowledge/small_account_10_to_10000_practice_guide.md`

### S-926 arxiv.org：html/2506.11921v1

- URL：https://arxiv.org/html/2506.11921v1
- 抓取方式：MCP `playwright`
- 抓取状态：ok
- 抓取日期：2026-01-11
- 本地缓存：.vibe/knowledge/sources/S-926/playwright_snapshot.md
- 引入原因：用户提供的“动态网格交易（DGT）”参考链接，待提炼。
- 落地到本仓库：
  - 实践指南：`docs/knowledge/small_account_10_to_10000_practice_guide.md`

### S-927 www.quantifiedstrategies.com：macd-and-rsi-strategy

- URL：https://www.quantifiedstrategies.com/macd-and-rsi-strategy/
- 抓取方式：MCP `markitdown`
- 抓取状态：ok
- 抓取日期：2026-01-11
- 本地缓存：.vibe/knowledge/sources/S-927/markitdown.md
- 引入原因：用户提供的“RSI+MACD 信号交易”参考链接，待提炼。
- 落地到本仓库：
  - 实践指南：`docs/knowledge/small_account_10_to_10000_practice_guide.md`

---

## M) 用户提供：技术分析形态（EMA/MACD/Vegas）（已提炼）

### S-928 acy.com：MACD 全指南（零轴/金叉/死叉/背离）

- URL：https://acy.com/zh/market-news/trading-education/macd-full-guide-golden-cross-death-cross-divergence-zh-170812/
- 抓取方式：MCP `markitdown`
- 抓取状态：ok
- 抓取状态备注：todo（待抓取）
- 抓取日期：2026-01-12
- 本地缓存：.vibe/knowledge/sources/S-928/markitdown.md
- 引入原因：用户提供的 MACD 形态/零轴/鞭打 等参考，用于提炼可程序化条件与风险门控思路。
- 落地到本仓库：
  - 形态体系落地笔记：`docs/knowledge/ema_macd_vegas_playbook.md`

### S-929 fidelity.com：MACD 指标指南（陷阱/假信号）

- URL：https://www.fidelity.com/learning-center/trading-investing/technical-analysis/technical-indicator-guide/macd
- 抓取方式：MCP `markitdown`
- 抓取状态：ok
- 抓取状态备注：todo（待抓取）
- 抓取日期：2026-01-12
- 本地缓存：.vibe/knowledge/sources/S-929/markitdown.md
- 引入原因：用户提供的 MACD 指标使用注意事项（假信号/鞭打）参考链接，作为“减少交易噪声”的方法论补充。
- 落地到本仓库：
  - 形态体系落地笔记：`docs/knowledge/ema_macd_vegas_playbook.md`

### S-930 investopedia.com：MACD（基础解释与注意事项）

- URL：https://www.investopedia.com/trading/macd/
- 抓取方式：MCP `playwright`
- 抓取状态：ok
- 抓取日期：2026-01-12
- 本地缓存：.vibe/knowledge/sources/S-930/playwright_snapshot.md
- 引入原因：用户提供的 MACD 基础解释参考，用于校准术语与避免概念误用。
- 落地到本仓库：
  - 形态体系落地笔记：`docs/knowledge/ema_macd_vegas_playbook.md`

### S-931 binance.com：Golden Cross / Death Cross（均线交叉）

- URL：https://www.binance.com/zh-CN/academy/articles/golden-cross-and-death-cross-explained
- 抓取方式：MCP `playwright`
- 抓取状态：ok
- 抓取日期：2026-01-12
- 本地缓存：.vibe/knowledge/sources/S-931/playwright_snapshot.md
- 引入原因：用户提供的 EMA/均线交叉“金叉/死叉”解释参考，用于对齐“交叉事件”的定义与风险提示。
- 落地到本仓库：
  - 形态体系落地笔记：`docs/knowledge/ema_macd_vegas_playbook.md`

### S-932 blog.tangly1024.com：Vegas Tunnel（隧道系统概述）

- URL：https://blog.tangly1024.com/article/vegas-tunnel
- 抓取方式：MCP `markitdown`
- 抓取状态：ok
- 抓取状态备注：todo（待抓取）
- 抓取日期：2026-01-12
- 本地缓存：.vibe/knowledge/sources/S-932/markitdown.md
- 引入原因：用户提供的 Vegas 隧道系统说明，用于把“多层 EMA 过滤 + 中继/假突破”转成可落地的工程约束。
- 落地到本仓库：
  - 形态体系落地笔记：`docs/knowledge/ema_macd_vegas_playbook.md`

### S-933 research-api.cbs.dk：Which Trend Is Your Friend（MACROSS ≡ TSMOM）

- URL：https://research-api.cbs.dk/ws/files/60084063/lasse_heje_pedersen_et_al_which_trend_is_your_friend_publishersversion.pdf
- 抓取方式：MCP `markitdown`
- 抓取状态：ok
- 抓取状态备注：todo（待抓取）
- 抓取日期：2026-01-12
- 本地缓存：.vibe/knowledge/sources/S-933/markitdown.md
- 引入原因：用户提供的趋势追踪/均线交叉理论等价性参考，用于解释“为什么长周期趋势过滤具有统计意义”。
- 落地到本仓库：
  - 形态体系落地笔记：`docs/knowledge/ema_macd_vegas_playbook.md`

### S-934 stockcharts.com：Reducing moving average whipsaws（鞭打减少）

- URL：https://articles.stockcharts.com/article/articles-arthurhill-2018-10-systemtrader---reducing-moving-average-whipsaws-with-smoothing-and-quantifying-filters-/
- 抓取方式：MCP `markitdown`
- 抓取状态：ok
- 抓取状态备注：todo（待抓取）
- 抓取日期：2026-01-12
- 本地缓存：.vibe/knowledge/sources/S-934/markitdown.md
- 引入原因：用户提供的“减少 MA 鞭打”工程化思路参考，用于后续评估 ADX/Bollinger/平滑 等过滤手段的成本与收益。
- 落地到本仓库：
  - 形态体系落地笔记：`docs/knowledge/ema_macd_vegas_playbook.md`

---

## N) 用户提供：K线 / Pin Bar（已提炼）

### S-935 priceaction.com：Pin Bar + Inside Bar Combo

- URL：https://priceaction.com/price-action-university/strategies/pin-bar-inside-bar-combo/
- 抓取方式：MCP `markitdown`
- 抓取状态：ok
- 抓取状态备注：todo（待抓取）
- 抓取日期：2026-01-12
- 本地缓存：.vibe/knowledge/sources/S-935/markitdown.md
- 引入原因：用户提供的“Pin Bar + Inside Bar 组合确认框架”参考，用于提炼可程序化的多层确认与触发条件。
- 落地到本仓库：
  - 工程化落地笔记：`docs/knowledge/candlestick_pinbar_playbook.md`

### S-936 priceaction.com：Pin Bar

- URL：https://priceaction.com/price-action-university/strategies/pin-bar/
- 抓取方式：MCP `markitdown`
- 抓取状态：ok
- 抓取状态备注：todo（待抓取）
- 抓取日期：2026-01-12
- 本地缓存：.vibe/knowledge/sources/S-936/markitdown.md
- 引入原因：用户提供的 Pin Bar 定义与实战要点参考，用于校准“尾/实体比、确认K线”等规则口径。
- 落地到本仓库：
  - 工程化落地笔记：`docs/knowledge/candlestick_pinbar_playbook.md`

### S-937 tradingwithrayner.com：Pinbar trading strategy

- URL：https://www.tradingwithrayner.com/pinbar-trading-strategy/
- 抓取方式：MCP `markitdown`
- 抓取状态：ok
- 抓取状态备注：todo（待抓取）
- 抓取日期：2026-01-12
- 本地缓存：.vibe/knowledge/sources/S-937/markitdown.md
- 引入原因：用户提供的 Pin Bar 交易规则与案例参考，用于交叉验证“确认/进场/止损”常见写法。
- 落地到本仓库：
  - 工程化落地笔记：`docs/knowledge/candlestick_pinbar_playbook.md`

### S-938 dukascopy.com：Reversal candlestick patterns

- URL：https://www.dukascopy.com/swiss/english/marketwatch/articles/reversal-candlestick-patterns/
- 抓取方式：MCP `playwright`
- 抓取状态：ok
- 抓取日期：2026-01-12
- 本地缓存：.vibe/knowledge/sources/S-938/playwright_snapshot.md
- 引入原因：用户提供的“反转类蜡烛形态”参考，用于补齐形态库与确认逻辑的背景。
- 落地到本仓库：
  - 工程化落地笔记：`docs/knowledge/candlestick_pinbar_playbook.md`

### S-939 liquidityfinder.com：How to trade reversal patterns using price action

- URL：https://liquidityfinder.com/news/how-to-trade-reversal-patterns-using-price-action-c385c
- 抓取方式：MCP `playwright`
- 抓取状态：ok
- 抓取日期：2026-01-12
- 本地缓存：.vibe/knowledge/sources/S-939/playwright_snapshot.md
- 引入原因：用户提供的“流动性/止损猎取/拒绝”叙事参考，用于把 Pin Bar 解释映射到“工程化确认 + 风险预算”。
- 落地到本仓库：
  - 工程化落地笔记：`docs/knowledge/candlestick_pinbar_playbook.md`

### S-940 dailypriceaction.com：Forex pin bar trading strategy

- URL：https://dailypriceaction.com/blog/forex-pin-bar-trading-strategy/
- 抓取方式：MCP `markitdown`
- 抓取状态：ok
- 抓取状态备注：todo（待抓取）
- 抓取日期：2026-01-12
- 本地缓存：.vibe/knowledge/sources/S-940/markitdown.md
- 引入原因：用户提供的“Pin Bar 50% 回踩进场”参考，用于评估“赔率提升 vs 漏单/频率下降”的权衡。
- 落地到本仓库：
  - 工程化落地笔记：`docs/knowledge/candlestick_pinbar_playbook.md`

### S-941 baogaobox.com：西南证券 K线形态量化研究（摘要页）

- URL：https://www.baogaobox.com/insights/250527000010595.html
- 抓取方式：MCP `playwright`
- 抓取状态：ok
- 抓取日期：2026-01-12
- 本地缓存：.vibe/knowledge/sources/S-941/playwright_snapshot.md
- 引入原因：用户提供的“形态数学化 + 量价状态权重更高”的实证摘要，用于指导“评分/门控”框架而非死磕单形态。
- 落地到本仓库：
  - 工程化落地笔记：`docs/knowledge/candlestick_pinbar_playbook.md`

### S-942 reddit.com：40 years of candlestick pattern success rates（讨论帖）

- URL：https://www.reddit.com/r/Daytrading/comments/1l4nrus/40_years_of_candlestick_pattern_success_rates_127/
- 抓取方式：MCP `markitdown`
- 抓取状态：ok
- 抓取状态备注：todo（待抓取）
- 抓取日期：2026-01-12
- 本地缓存：.vibe/knowledge/sources/S-942/markitdown.md
- 引入原因：用户提供的“形态有效性随年代变化（衰退/回归）”讨论线索，用于提醒必须做成本敏感性与跨年份验证。
- 落地到本仓库：
  - 工程化落地笔记：`docs/knowledge/candlestick_pinbar_playbook.md`

### S-943 journals.kozminski.edu.pl：Zielonka et al（PDF）

- URL：https://journals.kozminski.edu.pl/system/files/Zielonka%20et%20al.pdf
- 抓取方式：MCP `playwright`
- 抓取状态：blocked（too_short，详见本地缓存 meta_playwright.json）
- 抓取状态备注：blocked（抓取失败，详见本地缓存 meta.json）
- 抓取日期：2026-01-12
- 本地缓存：.vibe/knowledge/sources/S-943/playwright_snapshot.md
- 引入原因：用户提供的“认知偏差/形态识别偏差”研究线索，用于约束主观形态在工程化时的误用风险。
- 落地到本仓库：
  - 工程化落地笔记：`docs/knowledge/candlestick_pinbar_playbook.md`

### S-944 arxiv.org：html/2501.16772v1

- URL：https://arxiv.org/html/2501.16772v1
- 抓取方式：MCP `markitdown`
- 抓取状态：ok
- 抓取状态备注：todo（待抓取）
- 抓取日期：2026-01-12
- 本地缓存：.vibe/knowledge/sources/S-944/markitdown.md
- 引入原因：用户提供的“不同时间周期下形态有效性差异”研究线索，用于校准 4h/日线/更短周期的可行边界。
- 落地到本仓库：
  - 工程化落地笔记：`docs/knowledge/candlestick_pinbar_playbook.md`

---

## O) 用户提供：流动性 / 微观结构（已提炼）

### S-945 emergentmind.com：Limit Order Book microstructure

- URL：https://www.emergentmind.com/topics/limit-order-book-microstructure
- 抓取方式：MCP `playwright`
- 抓取状态：ok
- 抓取日期：2026-01-12
- 本地缓存：.vibe/knowledge/sources/S-945/playwright_snapshot.md
- 引入原因：用户提供的 LOB 微观结构概念综述，用于对齐术语（spread/depth/slope 等）与工程化指标定义。
- 落地到本仓库：
  - 工程化落地笔记：`docs/knowledge/crypto_liquidity_microstructure_playbook.md`

### S-946 people.hec.edu：limit_RFS_2009.pdf（LOB 理论/模型）

- URL：https://people.hec.edu/rosu/wp-content/uploads/sites/43/2020/03/limit_RFS_2009.pdf
- 抓取方式：MCP `markitdown`
- 抓取状态：ok
- 抓取状态备注：todo（待抓取）
- 抓取日期：2026-01-12
- 本地缓存：.vibe/knowledge/sources/S-946/markitdown.md
- 引入原因：用户提供的 LOB 学术论文，用于理解订单簿动态与价格形成机制（理论侧对齐）。
- 落地到本仓库：
  - 工程化落地笔记：`docs/knowledge/crypto_liquidity_microstructure_playbook.md`

### S-947 pmc.ncbi.nlm.nih.gov：PMC12315853（微观结构/LOB 研究）

- URL：https://pmc.ncbi.nlm.nih.gov/articles/PMC12315853/
- 抓取方式：MCP `playwright`
- 抓取状态：ok
- 抓取日期：2026-01-12
- 本地缓存：.vibe/knowledge/sources/S-947/playwright_snapshot.md
- 引入原因：用户提供的开放论文（PMC），用于补充 LOB/微观结构实证结论与可观测变量。
- 落地到本仓库：
  - 工程化落地笔记：`docs/knowledge/crypto_liquidity_microstructure_playbook.md`

### S-948 arxiv.org：2411.08382（订单流/微观结构研究）

- URL：http://arxiv.org/pdf/2411.08382.pdf
- 抓取方式：MCP `markitdown`
- 抓取状态：ok
- 抓取状态备注：todo（待抓取）
- 抓取日期：2026-01-12
- 本地缓存：.vibe/knowledge/sources/S-948/markitdown.md
- 引入原因：用户提供的微观结构相关论文，用于校验 OFI/订单簿变量与收益/风险的统计关系。
- 落地到本仓库：
  - 工程化落地笔记：`docs/knowledge/crypto_liquidity_microstructure_playbook.md`

### S-949 pmc.ncbi.nlm.nih.gov：PMC10040314（比特币订单流/收益研究）

- URL：https://pmc.ncbi.nlm.nih.gov/articles/PMC10040314/
- 抓取方式：MCP `playwright`
- 抓取状态：ok
- 抓取日期：2026-01-12
- 本地缓存：.vibe/knowledge/sources/S-949/playwright_snapshot.md
- 引入原因：用户提供的 Bitcoin 订单流不平衡相关实证（含预测/极值风险线索），用于落地“风险预算门控”的理论支撑。
- 落地到本仓库：
  - 工程化落地笔记：`docs/knowledge/crypto_liquidity_microstructure_playbook.md`

### S-950 emergentmind.com：Order Flow Imbalance（OFI）

- URL：https://www.emergentmind.com/topics/order-flow-imbalance
- 抓取方式：MCP `markitdown`
- 抓取状态：ok
- 抓取状态备注：todo（待抓取）
- 抓取日期：2026-01-12
- 本地缓存：.vibe/knowledge/sources/S-950/markitdown.md
- 引入原因：用户提供的 OFI 概念综述，用于对齐 OFI 的定义口径（trade-based / book-based）与实现差异。
- 落地到本仓库：
  - 工程化落地笔记：`docs/knowledge/crypto_liquidity_microstructure_playbook.md`

### S-951 electronictradinghub.com：LOB imbalance 深度解读（实践向）

- URL：https://electronictradinghub.com/leveraging-limit-order-book-imbalances-for-profitable-trading-a-deep-dive-into-recent-research-and-practical-tools/
- 抓取方式：MCP `markitdown`
- 抓取状态：ok
- 抓取状态备注：todo（待抓取）
- 抓取日期：2026-01-12
- 本地缓存：.vibe/knowledge/sources/S-951/markitdown.md
- 引入原因：用户提供的实践向材料，用于提炼“制度识别 → 执行动作”的工程化流程。
- 落地到本仓库：
  - 工程化落地笔记：`docs/knowledge/crypto_liquidity_microstructure_playbook.md`

### S-952 arxiv.org：2112.04245（价格冲击/执行成本）

- URL：https://arxiv.org/pdf/2112.04245.pdf
- 抓取方式：MCP `markitdown`
- 抓取状态：ok
- 抓取状态备注：todo（待抓取）
- 抓取日期：2026-01-12
- 本地缓存：.vibe/knowledge/sources/S-952/markitdown.md
- 引入原因：用户提供的价格冲击相关研究，用于把“容量/滑点”的非线性机制工程化。
- 落地到本仓库：
  - 工程化落地笔记：`docs/knowledge/crypto_liquidity_microstructure_playbook.md`

### S-953 arxiv.org：2306.00621（微观结构/制度转换）

- URL：http://arxiv.org/pdf/2306.00621.pdf
- 抓取方式：MCP `markitdown`
- 抓取状态：ok
- 抓取状态备注：todo（待抓取）
- 抓取日期：2026-01-12
- 本地缓存：.vibe/knowledge/sources/S-953/markitdown.md
- 引入原因：用户提供的微观结构制度/状态相关研究线索，用于构建“深/薄/混乱”制度识别的可验证依据。
- 落地到本仓库：
  - 工程化落地笔记：`docs/knowledge/crypto_liquidity_microstructure_playbook.md`

### S-954 proptrader.oanda.com：Order/Position book 支阻分析

- URL：https://proptrader.oanda.com/en/lab-education/trading-knowledge/technical-analysis/support-resistance-analysis-with-order-position-book/
- 抓取方式：MCP `markitdown`
- 抓取状态：ok
- 抓取状态备注：todo（待抓取）
- 抓取日期：2026-01-12
- 本地缓存：.vibe/knowledge/sources/S-954/markitdown.md
- 引入原因：用户提供的“用订单簿解释支阻”实践向材料，用于把支阻从静态线升级为动态簇集。
- 落地到本仓库：
  - 工程化落地笔记：`docs/knowledge/crypto_liquidity_microstructure_playbook.md`

### S-955 dspace.cuni.cz：120505902.pdf（支阻/微观结构论文）

- URL：https://dspace.cuni.cz/bitstream/handle/20.500.11956/200516/120505902.pdf?sequence=1
- 抓取方式：MCP `playwright`
- 抓取状态：blocked（too_short，详见本地缓存 meta_playwright.json）
- 抓取状态备注：blocked（抓取失败，详见本地缓存 meta.json）
- 抓取日期：2026-01-12
- 本地缓存：.vibe/knowledge/sources/S-955/playwright_snapshot.md
- 引入原因：用户提供的论文线索，用于补充“支阻互换/订单簇集”相关实证结论。
- 落地到本仓库：
  - 工程化落地笔记：`docs/knowledge/crypto_liquidity_microstructure_playbook.md`

### S-956 luxalgo.com：Support/Resistance（反转交易视角）

- URL：https://www.luxalgo.com/blog/master-support-and-resistance-for-reversal-trading/
- 抓取方式：MCP `markitdown`
- 抓取状态：ok
- 抓取状态备注：todo（待抓取）
- 抓取日期：2026-01-12
- 本地缓存：.vibe/knowledge/sources/S-956/markitdown.md
- 引入原因：用户提供的实践向材料，用于对照“传统支阻 vs 流动性簇集”的叙事差异与落地边界。
- 落地到本仓库：
  - 工程化落地笔记：`docs/knowledge/crypto_liquidity_microstructure_playbook.md`

### S-957 cmcmarkets.com：Support/Resistance guide

- URL：https://www.cmcmarkets.com/en-sg/trading-guides/support-resistance
- 抓取方式：MCP `markitdown`
- 抓取状态：ok
- 抓取状态备注：todo（待抓取）
- 抓取日期：2026-01-12
- 本地缓存：.vibe/knowledge/sources/S-957/markitdown.md
- 引入原因：用户提供的支阻基础教程（作为“传统口径”对照），用于明确哪些结论需要微观结构变量才能成立。
- 落地到本仓库：
  - 工程化落地笔记：`docs/knowledge/crypto_liquidity_microstructure_playbook.md`

### S-958 acy.com：SMC 视角的支阻绘制

- URL：https://acy.com/en/market-news/education/how-to-plot-key-support-resistance-levels-the-smc-way-for-day-trading-142011/
- 抓取方式：MCP `markitdown`
- 抓取状态：ok
- 抓取状态备注：todo（待抓取）
- 抓取日期：2026-01-12
- 本地缓存：.vibe/knowledge/sources/S-958/markitdown.md
- 引入原因：用户提供的 SMC（Smart Money Concepts）视角支阻材料，用于补充“流动性猎取/止损簇集”叙事与可观测变量。
- 落地到本仓库：
  - 工程化落地笔记：`docs/knowledge/crypto_liquidity_microstructure_playbook.md`

### S-959 arxiv.org：2304.02472（订单流/高频信号）

- URL：https://arxiv.org/pdf/2304.02472.pdf
- 抓取方式：MCP `markitdown`
- 抓取状态：ok
- 抓取状态备注：todo（待抓取）
- 抓取日期：2026-01-12
- 本地缓存：.vibe/knowledge/sources/S-959/markitdown.md
- 引入原因：用户提供的订单流/信号时效研究线索，用于校准“信号半衰期 vs 交易周期”的工程结论。
- 落地到本仓库：
  - 工程化落地笔记：`docs/knowledge/crypto_liquidity_microstructure_playbook.md`

### S-960 arxiv.org：2312.16190（订单流/价格影响）

- URL：https://arxiv.org/pdf/2312.16190.pdf
- 抓取方式：MCP `markitdown`
- 抓取状态：ok
- 抓取状态备注：todo（待抓取）
- 抓取日期：2026-01-12
- 本地缓存：.vibe/knowledge/sources/S-960/markitdown.md
- 引入原因：用户提供的研究线索，用于补充“冲击分解（临时/永久）与时间衰减”的工程解释。
- 落地到本仓库：
  - 工程化落地笔记：`docs/knowledge/crypto_liquidity_microstructure_playbook.md`

### S-961 arxiv.org：2010.01241（订单簿/微观结构信号）

- URL：https://arxiv.org/pdf/2010.01241.pdf
- 抓取方式：MCP `markitdown`
- 抓取状态：ok
- 抓取状态备注：todo（待抓取）
- 抓取日期：2026-01-12
- 本地缓存：.vibe/knowledge/sources/S-961/markitdown.md
- 引入原因：用户提供的研究线索，用于对照“订单簿/订单流特征是否具有可交易边际优势”。
- 落地到本仓库：
  - 工程化落地笔记：`docs/knowledge/crypto_liquidity_microstructure_playbook.md`

### S-962 arxiv.org：2306.08157（制度/极端事件）

- URL：http://arxiv.org/pdf/2306.08157.pdf
- 抓取方式：MCP `markitdown`
- 抓取状态：ok
- 抓取状态备注：todo（待抓取）
- 抓取日期：2026-01-12
- 本地缓存：.vibe/knowledge/sources/S-962/markitdown.md
- 引入原因：用户提供的研究线索，用于补充“混乱流动性制度（事件/黑天鹅）”的识别与风险动作。
- 落地到本仓库：
  - 工程化落地笔记：`docs/knowledge/crypto_liquidity_microstructure_playbook.md`

### S-963 arxiv.org：2502.19349（波动/风险框架）

- URL：https://arxiv.org/pdf/2502.19349.pdf
- 抓取方式：MCP `playwright`
- 抓取状态：blocked（too_short，详见本地缓存 meta_playwright.json）
- 抓取状态备注：blocked（抓取失败，详见本地缓存 meta.json）
- 抓取日期：2026-01-12
- 本地缓存：.vibe/knowledge/sources/S-963/playwright_snapshot.md
- 引入原因：用户提供的研究线索，用于补充“高波动制度下的风险预算/仓位调整”方法论。
- 落地到本仓库：
  - 工程化落地笔记：`docs/knowledge/crypto_liquidity_microstructure_playbook.md`

### S-964 arxiv.org：2411.12748（加密市场/微观结构）

- URL：https://arxiv.org/pdf/2411.12748.pdf
- 抓取方式：MCP `playwright`
- 抓取状态：blocked（too_short，详见本地缓存 meta_playwright.json）
- 抓取状态备注：blocked（抓取失败，详见本地缓存 meta.json）
- 抓取日期：2026-01-12
- 本地缓存：.vibe/knowledge/sources/S-964/playwright_snapshot.md
- 引入原因：用户提供的研究线索，用于补充加密市场微观结构的实证结果与边界条件。
- 落地到本仓库：
  - 工程化落地笔记：`docs/knowledge/crypto_liquidity_microstructure_playbook.md`

### S-965 arxiv.org：2411.06327（加密订单流/微观结构）

- URL：https://arxiv.org/pdf/2411.06327.pdf
- 抓取方式：MCP `markitdown`
- 抓取状态：ok
- 抓取状态备注：todo（待抓取）
- 抓取日期：2026-01-12
- 本地缓存：.vibe/knowledge/sources/S-965/markitdown.md
- 引入原因：用户提供的研究线索，用于补充“订单流/深度变化与价格”的统计关系与可交易性评估。
- 落地到本仓库：
  - 工程化落地笔记：`docs/knowledge/crypto_liquidity_microstructure_playbook.md`

### S-966 sciencedirect.com：S0275531925004192（论文）

- URL：https://www.sciencedirect.com/science/article/pii/S0275531925004192
- 抓取方式：MCP `playwright`
- 抓取状态：blocked（检测到人机验证/风控页面（需要人工验证）；如有合法访问权限可用 --interactive）
- 抓取状态备注：blocked（抓取失败，详见本地缓存 meta.json）
- 抓取日期：2026-01-12
- 本地缓存：.vibe/knowledge/sources/S-966/playwright_snapshot.md
- 引入原因：用户提供的论文线索（可能存在付费墙），用于补充微观结构/冲击模型的实证与方法。
- 落地到本仓库：
  - 工程化落地笔记：`docs/knowledge/crypto_liquidity_microstructure_playbook.md`

### S-967 investinglive.com：Orderflow intel（案例）

- URL：https://investinglive.com/Cryptocurrency/ethereurm-price-prediction-with-orderflow-intel-by-investinglivecom-20250820/
- 抓取方式：MCP `playwright`
- 抓取状态：blocked（检测到人机验证/风控页面（需要人工验证）；如有合法访问权限可用 --interactive）
- 抓取状态备注：blocked（抓取失败，详见本地缓存 meta.json）
- 抓取日期：2026-01-12
- 本地缓存：.vibe/knowledge/sources/S-967/playwright_snapshot.md
- 引入原因：用户提供的案例向材料，用于对照“订单流指标如何在叙事层被使用”，避免把营销话术当成工程结论。
- 落地到本仓库：
  - 工程化落地笔记：`docs/knowledge/crypto_liquidity_microstructure_playbook.md`

### S-968 ieeexplore.ieee.org：10781336.pdf（论文）

- URL：https://ieeexplore.ieee.org/iel8/6287639/10380310/10781336.pdf
- 抓取方式：MCP `playwright`
- 抓取状态：blocked（too_short，详见本地缓存 meta_playwright.json）
- 抓取状态备注：blocked（抓取失败，详见本地缓存 meta.json）
- 抓取日期：2026-01-12
- 本地缓存：.vibe/knowledge/sources/S-968/playwright_snapshot.md
- 引入原因：用户提供的 IEEE 论文线索，用于补充订单簿/订单流建模与信号评估方法。
- 落地到本仓库：
  - 工程化落地笔记：`docs/knowledge/crypto_liquidity_microstructure_playbook.md`

### S-969 arxiv.org：abs/2511.20606（研究线索）

- URL：https://arxiv.org/abs/2511.20606
- 抓取方式：MCP `markitdown`
- 抓取状态：ok
- 抓取状态备注：todo（待抓取）
- 抓取日期：2026-01-12
- 本地缓存：.vibe/knowledge/sources/S-969/markitdown.md
- 引入原因：用户提供的研究线索，用于补充最新的订单流/微观结构研究方向与方法。
- 落地到本仓库：
  - 工程化落地笔记：`docs/knowledge/crypto_liquidity_microstructure_playbook.md`

### S-970 capital.com：Support/Resistance trading strategy（对照）

- URL：https://capital.com/en-int/learn/technical-analysis/support-and-resistance-trading-strategy
- 抓取方式：MCP `markitdown`
- 抓取状态：ok
- 抓取状态备注：todo（待抓取）
- 抓取日期：2026-01-12
- 本地缓存：.vibe/knowledge/sources/S-970/markitdown.md
- 引入原因：用户提供的支阻教程（传统口径对照），用于明确哪些结论在加密市场需要“流动性变量”才能稳定成立。
- 落地到本仓库：
  - 工程化落地笔记：`docs/knowledge/crypto_liquidity_microstructure_playbook.md`

### S-971 research.utwente.nl：eth_29478_02.pdf（论文）

- URL：https://research.utwente.nl/files/283902161/eth_29478_02.pdf
- 抓取方式：MCP `playwright`
- 抓取状态：blocked（检测到人机验证/风控页面（需要人工验证）；如有合法访问权限可用 --interactive）
- 抓取状态备注：blocked（抓取失败，详见本地缓存 meta.json）
- 抓取日期：2026-01-12
- 本地缓存：.vibe/knowledge/sources/S-971/playwright_snapshot.md
- 引入原因：用户提供的论文线索，用于补充执行成本/冲击模型/微观结构变量的实证与方法。
- 落地到本仓库：
  - 工程化落地笔记：`docs/knowledge/crypto_liquidity_microstructure_playbook.md`

---

## P) 加密市场风险因子（用户综述参考）

说明：

- 以下条目来自用户提供的“加密货币市场风险因子”综述的参考文献列表，用于把 URL 正式纳入仓库的“来源登记 → 可追溯抓取/落盘”流程。
- 当前仅完成登记，未执行抓取；后续可用 `scripts/tools/source_registry_fetch_sources.py` / `scripts/tools/source_registry_fetch_sources_playwright.py` 按需抓取。

### S-972 ssrn.com：abstract=3379131（三因子模型）

- URL：https://www.ssrn.com/abstract=3379131
- 抓取方式：待定（建议优先 MCP `markitdown`，必要时 `playwright`）
- 抓取状态：todo（待抓取）
- 引入原因：用户综述引用 [1]，用于三因子模型（CMKT/CSMB/CMOM）的来源登记。
- 落地到本仓库：
  - 工程化落地地图：`docs/knowledge/crypto_risk_factors_engineering_playbook.md`

### S-973 nber.org：w25882（三因子模型/定价）

- URL：https://www.nber.org/system/files/working_papers/w25882/w25882.pdf
- 抓取方式：待定（建议优先 MCP `markitdown`，必要时 `playwright`）
- 抓取状态：todo（待抓取）
- 引入原因：用户综述引用 [2]，用于三因子模型解释力与规模/流动性等定价维度的来源登记。
- 落地到本仓库：
  - 工程化落地地图：`docs/knowledge/crypto_risk_factors_engineering_playbook.md`

### S-974 journals.vsu.ru：波动/流动性风险（综述/论文）

- URL：https://journals.vsu.ru/econ/article/view/3614
- 抓取方式：待定（建议优先 MCP `markitdown`，必要时 `playwright`）
- 抓取状态：todo（待抓取）
- 引入原因：用户综述引用 [3]，用于“高波动 + 流动性不足 + 清算级联”的风险维度来源登记。
- 落地到本仓库：
  - 工程化落地地图：`docs/knowledge/crypto_risk_factors_engineering_playbook.md`

### S-975 investopedia.com：加密波动管理（科普）

- URL：https://www.investopedia.com/riding-the-wave-how-to-manage-crypto-volatility-11833947
- 抓取方式：待定（建议优先 MCP `markitdown`，必要时 `playwright`）
- 抓取状态：todo（待抓取）
- 引入原因：用户综述引用 [4]，用于“波动管理/风险控制”科普材料来源登记（需与学术/实证交叉验证）。
- 落地到本仓库：
  - 工程化落地地图：`docs/knowledge/crypto_risk_factors_engineering_playbook.md`

### S-976 moomoo.com：价格影响因素（科普/媒体）

- URL：https://www.moomoo.com/sg/hans/learn/detail-7-key-factors-that-could-impact-cryptocurrency-prices-117206-240769245
- 抓取方式：待定（建议优先 MCP `markitdown`，必要时 `playwright`）
- 抓取状态：todo（待抓取）
- 引入原因：用户综述引用 [5]，用于“情绪/社媒/宏观等综合因素”科普材料来源登记（避免把叙事当作可执行结论）。
- 落地到本仓库：
  - 工程化落地地图：`docs/knowledge/crypto_risk_factors_engineering_playbook.md`

### S-977 binance.com：2026 市场挑战（媒体/观点）

- URL：https://www.binance.com/en/square/post/01-08-2026-crypto-markets-face-key-challenges-for-growth-in-2026-34792356442450
- 抓取方式：待定（建议优先 MCP `playwright`）
- 抓取状态：todo（待抓取）
- 引入原因：用户综述引用 [6]，用于“2026 年监管/利率/机构化”等风险因子叙事线索登记（需与一手政策/数据源交叉验证）。
- 落地到本仓库：
  - 工程化落地地图：`docs/knowledge/crypto_risk_factors_engineering_playbook.md`

### S-978 proceedings.stis.ac.id：利率/收益因果关系（论文/会议）

- URL：https://proceedings.stis.ac.id/icdsos/article/view/727
- 抓取方式：待定（建议优先 MCP `markitdown`，必要时 `playwright`）
- 抓取状态：todo（待抓取）
- 引入原因：用户综述引用 [7]，用于“央行政策 → BTC/ETH 收益”的宏观维度来源登记。
- 落地到本仓库：
  - 工程化落地地图：`docs/knowledge/crypto_risk_factors_engineering_playbook.md`

### S-979 investing.com：BTC vs S&P500（市场分析/媒体）

- URL：https://www.investing.com/analysis/bitcoin-vs-sp-500--risk-reassessment-into-2026-200673050
- 抓取方式：待定（建议优先 MCP `playwright`）
- 抓取状态：todo（待抓取）
- 引入原因：用户综述引用 [8]，用于“传统金融关联/风险偏好联动”维度的市场分析线索登记。
- 落地到本仓库：
  - 工程化落地地图：`docs/knowledge/crypto_risk_factors_engineering_playbook.md`

### S-980 binance.com：宏观/项目/黑天鹅（媒体/观点）

- URL：https://www.binance.com/es-MX/square/post/23562037194689
- 抓取方式：待定（建议优先 MCP `playwright`）
- 抓取状态：todo（待抓取）
- 引入原因：用户综述引用 [9]，用于“黑天鹅/项目基本面/安全”等综合风险叙事线索登记（需与独立来源交叉验证）。
- 落地到本仓库：
  - 工程化落地地图：`docs/knowledge/crypto_risk_factors_engineering_playbook.md`

### S-981 jemaca.aks.or.id：情绪/机构化（论文/文章）

- URL：https://jemaca.aks.or.id/jemaca/article/view/23
- 抓取方式：待定（建议优先 MCP `markitdown`，必要时 `playwright`）
- 抓取状态：todo（待抓取）
- 引入原因：用户综述引用 [10]，用于“情绪驱动/机构化双刃剑”等维度来源登记。
- 落地到本仓库：
  - 工程化落地地图：`docs/knowledge/crypto_risk_factors_engineering_playbook.md`

### S-982 hde.hr：羊群效应（论文/文章）

- URL：https://www.hde.hr/sadrzaj_en.aspx?Podrucje=2034
- 抓取方式：待定（建议优先 MCP `playwright`）
- 抓取状态：todo（待抓取）
- 引入原因：用户综述引用 [11]，用于“羊群效应/行为金融”维度来源登记。
- 落地到本仓库：
  - 工程化落地地图：`docs/knowledge/crypto_risk_factors_engineering_playbook.md`

### S-983 arxiv.org：2308.08554（智能合约/安全风险）

- URL：https://arxiv.org/pdf/2308.08554.pdf
- 抓取方式：待定（建议优先 MCP `markitdown`）
- 抓取状态：todo（待抓取）
- 引入原因：用户综述引用 [12]，用于“智能合约漏洞/DeFi 安全风险”维度来源登记。
- 落地到本仓库：
  - 工程化落地地图：`docs/knowledge/crypto_risk_factors_engineering_playbook.md`

### S-984 republic.com：数字资产风险披露（科普/披露）

- URL：https://republic.com/help/what-are-the-risks-associated-with-digital-assets-blockchain-technology-utility-1
- 抓取方式：待定（建议优先 MCP `playwright`）
- 抓取状态：todo（待抓取）
- 引入原因：用户综述引用 [13]，用于“共识/预言机/交易不可逆”等技术与交易对手风险线索登记。
- 落地到本仓库：
  - 工程化落地地图：`docs/knowledge/crypto_risk_factors_engineering_playbook.md`

### S-985 taurushq.com：数字资产监管风险披露（机构/披露）

- URL：https://www.taurushq.com/legal/regulatory-risk/risks-digitalassets/
- 抓取方式：待定（建议优先 MCP `markitdown`，必要时 `playwright`）
- 抓取状态：todo（待抓取）
- 引入原因：用户综述引用 [14]，用于“监管与法律确定性”维度来源登记。
- 落地到本仓库：
  - 工程化落地地图：`docs/knowledge/crypto_risk_factors_engineering_playbook.md`

### S-986 oanda.com：交易风险（科普/平台）

- URL：https://www.oanda.com/us-en/trade-tap-blog/asset-classes/crypto/risks-of-trading-cryptocurrency/
- 抓取方式：待定（建议优先 MCP `markitdown`，必要时 `playwright`）
- 抓取状态：todo（待抓取）
- 引入原因：用户综述引用 [15]，用于“交易所/托管/合约交易风险”科普材料来源登记（需与一手规则交叉验证）。
- 落地到本仓库：
  - 工程化落地地图：`docs/knowledge/crypto_risk_factors_engineering_playbook.md`

### S-987 crypto.com：2026 关注资产（媒体/观点）

- URL：https://crypto.com/en/market-updates/top-cryptos-to-watch-in-2026
- 抓取方式：待定（建议优先 MCP `playwright`）
- 抓取状态：todo（待抓取）
- 引入原因：用户综述引用 [16]，用于“生态竞争/技术路线变化/机构化叙事”线索登记（需与数据/实证交叉验证）。
- 落地到本仓库：
  - 工程化落地地图：`docs/knowledge/crypto_risk_factors_engineering_playbook.md`

### S-988 coincub.com：波动与风险评估（科普/媒体）

- URL：https://coincub.com/risks-and-rewards-in-assessing-volatility-in-the-crypto-market/
- 抓取方式：待定（建议优先 MCP `markitdown`，必要时 `playwright`）
- 抓取状态：todo（待抓取）
- 引入原因：用户综述引用 [17]，用于“波动风险与度量”科普材料来源登记。
- 落地到本仓库：
  - 工程化落地地图：`docs/knowledge/crypto_risk_factors_engineering_playbook.md`

### S-989 mdpi.com：1911-8074/12/2/52（跨币蔓延/外溢风险）

- URL：https://www.mdpi.com/1911-8074/12/2/52/pdf
- 抓取方式：待定（建议优先 MCP `playwright` 或 `markitdown`）
- 抓取状态：todo（待抓取）
- 引入原因：用户综述引用 [18]，用于“跨币蔓延/溢出效应网络”维度来源登记。
- 落地到本仓库：
  - 工程化落地地图：`docs/knowledge/crypto_risk_factors_engineering_playbook.md`

### S-990 journal.sinergi.or.id：黑天鹅/系统性风险（论文/文章）

- URL：https://journal.sinergi.or.id/index.php/ijat/article/view/479
- 抓取方式：待定（建议优先 MCP `markitdown`，必要时 `playwright`）
- 抓取状态：todo（待抓取）
- 引入原因：用户综述引用 [19]，用于“黑天鹅事件系统性冲击”维度来源登记。
- 落地到本仓库：
  - 工程化落地地图：`docs/knowledge/crypto_risk_factors_engineering_playbook.md`

### S-991 arxiv.org：2407.15766（尾部风险/度量方法）

- URL：http://arxiv.org/pdf/2407.15766.pdf
- 抓取方式：待定（建议优先 MCP `markitdown`）
- 抓取状态：todo（待抓取）
- 引入原因：用户综述引用 [20]，用于“CVaR/尾部风险度量与方法论”维度来源登记。
- 落地到本仓库：
  - 工程化落地地图：`docs/knowledge/crypto_risk_factors_engineering_playbook.md`

### S-992 garp.org：数字资产风险（行业/机构）

- URL：https://www.garp.org/risk-intelligence/market/digital-asset-risk-241018
- 抓取方式：待定（建议优先 MCP `playwright`）
- 抓取状态：todo（待抓取）
- 引入原因：用户综述引用 [21]，用于“风险治理与行业视角”维度来源登记。
- 落地到本仓库：
  - 工程化落地地图：`docs/knowledge/crypto_risk_factors_engineering_playbook.md`

### S-993 bcg.com：数字金融资产风险与控制框架（行业框架）

- URL：https://www.bcg.com/publications/2024/a-risk-and-control-framework-for-digital-financial-assets
- 抓取方式：待定（建议优先 MCP `playwright`）
- 抓取状态：todo（待抓取）
- 引入原因：用户综述引用 [22]，用于“综合风险与控制框架（原则/控制措施）”维度来源登记。
- 落地到本仓库：
  - 工程化落地地图：`docs/knowledge/crypto_risk_factors_engineering_playbook.md`

---

## Q) 加密货币定价因子模型（五因子/动态因子）

说明：

- 本分区用于登记“横截面定价/多因子模型”相关来源，服务于五因子模型与后续研究复现。
- 其中部分因子（NET/市值/币龄）依赖外部数据源；本仓库默认约束为 OHLCV，建议先用研究层离线验证，再考虑工程落地。
- 当前项目主线为**单交易对时间序列预测/择时**；本分区内容主要用于风险语义与背景校准，后续如引入外部数据（P2）再讨论复现。

### S-994 abfer.org：Cong 等（C-5/五因子）演示稿

- URL：https://abfer.org/media/abfer-events-2022/annual-conference/slides-investfin/Lin-William-CONG-presentation.pdf
- 抓取方式：待定（建议优先 MCP `markitdown`，必要时 `playwright`）
- 抓取状态：todo（待抓取）
- 引入原因：用户综述引用 [1]，用于 C-5（MKT/SMB/VAL/NET/MOM）五因子模型的定义与实证结果口径。
- 落地到本仓库：
  - 五因子模型笔记：`docs/knowledge/crypto_pricing_five_factor_models_playbook.md`

### S-995 wp.lancs.ac.uk：Bianchi（IPCA/动态因子）演示稿

- URL：http://wp.lancs.ac.uk/fofi2022/files/2022/08/FoFI-2022-056-Daniele-Bianchi.pdf
- 抓取方式：待定（建议优先 MCP `markitdown`，必要时 `playwright`）
- 抓取状态：todo（待抓取）
- 引入原因：用户综述引用 [3]，用于 IPCA（Instrumented PCA）框架与“时变因子载荷”的实证口径。
- 落地到本仓库：
  - 五因子模型笔记：`docs/knowledge/crypto_pricing_five_factor_models_playbook.md`

### S-996 emerald.com：Fama-French 五因子在加密中的适用性（论文/文章）

- URL：http://www.emerald.com/cafr/article/25/2/145-183/14403
- 抓取方式：待定（建议优先 MCP `playwright`）
- 抓取状态：todo（待抓取）
- 引入原因：用户综述引用 [4]，用于说明传统 FF5（RMW/CMA 等）在加密中的定义与适配挑战。
- 落地到本仓库：
  - 五因子模型笔记：`docs/knowledge/crypto_pricing_five_factor_models_playbook.md`

### S-997 cambridge.org：Trend factor for the cross section of cryptocurrency returns（论文 PDF）

- URL：https://www.cambridge.org/core/services/aop-cambridge-core/content/view/4C1509ACBA33D5DCAF0AC24379148178/S0022109024000747a.pdf/trend_factor_for_the_cross_section_of_cryptocurrency_returns.pdf
- 抓取方式：待定（建议优先 MCP `markitdown`，必要时 `playwright`）
- 抓取状态：todo（待抓取）
- 引入原因：用户综述引用 [7]，用于 CTREND/趋势因子的研究线索与结果口径登记。
- 落地到本仓库：
  - 五因子模型笔记：`docs/knowledge/crypto_pricing_five_factor_models_playbook.md`

### S-998 snb.ch：Bianchi（动态因子模型）研讨会材料

- URL：https://www.snb.ch/dam/jcr:cd47611a-4261-4e74-bd69-061ab54433ce/sem_2023_05_26_bianchi.n.pdf
- 抓取方式：待定（建议优先 MCP `markitdown`，必要时 `playwright`）
- 抓取状态：todo（待抓取）
- 引入原因：用户综述引用 [12]，用于“动态因子模型/样本外表现优于固定观测因子”的证据线索登记。
- 落地到本仓库：
  - 五因子模型笔记：`docs/knowledge/crypto_pricing_five_factor_models_playbook.md`

### S-999 docs.cfbenchmarks.com：A Factor Model for Digital Assets（机构级因子模型白皮书）

- URL：https://docs.cfbenchmarks.com/A-Factor-Model-for-Digital-Assets.pdf
- 抓取方式：待定（建议优先 MCP `markitdown`，必要时 `playwright`）
- 抓取状态：todo（待抓取）
- 引入原因：用户综述引用 [55]，用于 CF Benchmarks 机构级因子模型（七因子、数据源与方法学）的来源登记。
- 落地到本仓库：
  - 因子模型生态综述：`docs/knowledge/crypto_factor_model_ecosystem_survey.md`
### S-1000 cfbenchmarks.com：introduces first institutional-grade factor model（博客）

- URL：https://www.cfbenchmarks.com/blog/cf-benchmarks-introduces-first-institutional-grade-factor-model-for-digital-assets
- 抓取方式：待定（建议优先 MCP `playwright`）
- 抓取状态：todo（待抓取）
- 引入原因：用户综述引用 [4]，用于“机构级模型发布说明/解读”的线索登记（以白皮书为主、博客为辅）。
- 落地到本仓库：
  - 因子模型生态综述：`docs/knowledge/crypto_factor_model_ecosystem_survey.md`

### S-1001 cfbenchmarks.com：CF Factor Intelligence（博客）

- URL：https://www.cfbenchmarks.com/blog/cf-benchmarks-launches-cf-factor-intelligence-enabling-actionable-insights-from-our-validated-model
- 抓取方式：待定（建议优先 MCP `playwright`）
- 抓取状态：todo（待抓取）
- 引入原因：用户综述引用 [5]，用于“模型落地产品化/因子信号服务化”的线索登记。
- 落地到本仓库：
  - 因子模型生态综述：`docs/knowledge/crypto_factor_model_ecosystem_survey.md`

### S-1002 arxiv.org：2601.07664（Giglio-Xiu 三步法/隐层因子应用线索）

- URL：https://arxiv.org/pdf/2601.07664.pdf
- 抓取方式：待定（建议优先 MCP `markitdown`）
- 抓取状态：todo（待抓取）
- 引入原因：用户综述引用 [8]，用于“隐层因子 + Giglio-Xiu 三步法”在加密定价中的应用线索登记。
- 落地到本仓库：
  - 因子模型生态综述：`docs/knowledge/crypto_factor_model_ecosystem_survey.md`

### S-1003 sciencedirect.com：pii/S1057521925004764（多因子扩展/11 因子框架线索）

- URL：https://www.sciencedirect.com/science/article/abs/pii/S1057521925004764
- 抓取方式：待定（建议优先 MCP `playwright`；可能存在付费墙/人机验证）
- 抓取状态：todo（待抓取）
- 引入原因：用户综述引用 [10]，用于“更高维度因子框架（例如 11 因子）”的研究线索登记。
- 落地到本仓库：
  - 因子模型生态综述：`docs/knowledge/crypto_factor_model_ecosystem_survey.md`

### S-1004 dl.acm.org：10.1145/3764727.3764730（观测性模型/基准线索）

- URL：https://dl.acm.org/doi/10.1145/3764727.3764730
- 抓取方式：待定（建议优先 MCP `playwright`；可能存在付费墙/登录限制）
- 抓取状态：todo（待抓取）
- 引入原因：用户综述引用 [1]，用于“基础观测性模型（CAPM/单因子等）在加密中的基准表现”的线索登记。
- 落地到本仓库：
  - 因子模型生态综述：`docs/knowledge/crypto_factor_model_ecosystem_survey.md`

### S-1005 eudl.eu：10.4108/eai.18-11-2022.2327109（四因子/反转扩展线索）

- URL：https://eudl.eu/pdf/10.4108/eai.18-11-2022.2327109
- 抓取方式：待定（建议优先 MCP `markitdown`，必要时 `playwright`）
- 抓取状态：todo（待抓取）
- 引入原因：用户综述引用 [3]，用于“Carhart 扩展（反转因子）在加密中的应用线索”的来源登记。
- 落地到本仓库：
  - 因子模型生态综述：`docs/knowledge/crypto_factor_model_ecosystem_survey.md`

---

## R) 加密资产价格预测模型（时间序列 / 深度学习）

说明：

- 本分区用于登记“价格/收益预测”模型的研究线索，服务于预测模型的工程验收与落地边界。
- 注意：预测模型不等价于横截面定价因子模型；指标口径不可混用。
- 当前项目主线为**单交易对时间序列预测/择时**；本分区为主线参考。

### S-1006 arxiv.org：N-BEATS（时间序列预测）

- URL：https://arxiv.org/pdf/1905.10437.pdf
- 抓取方式：待定（建议优先 MCP `markitdown`，必要时 `playwright`）
- 抓取状态：todo（待抓取）
- 引入原因：N-BEATS 的原始论文，用于理解模型结构、训练与评估设置，并作为“高分结果需警惕”的对照基准。
- 落地到本仓库：
  - 预测模型工程验收：`docs/knowledge/crypto_price_forecasting_models_playbook.md`

### S-1007 publications.eai.eu：N-BEATS 在加密价格预测中的应用（论文/案例）

- URL：https://publications.eai.eu/index.php/sis/article/view/9006
- 抓取方式：待定（建议优先 MCP `playwright`，必要时 `markitdown`）
- 抓取状态：todo（待抓取）
- 引入原因：用于登记“在加密场景报告的评估指标与设置”，并提示常见高分陷阱与复现要点。
- 落地到本仓库：
  - 预测模型工程验收：`docs/knowledge/crypto_price_forecasting_models_playbook.md`

### S-1008 scitepress.org：CNN-BiLSTM + 注意力（加密价格预测，论文 PDF）

- URL：https://www.scitepress.org/Papers/2024/132698/132698.pdf
- 抓取方式：待定（建议优先 MCP `markitdown`，必要时 `playwright`）
- 抓取状态：todo（待抓取）
- 引入原因：用于混合深度模型（CNN+BiLSTM+Attention）在加密预测中的结构与评估口径线索登记。
- 落地到本仓库：
  - 预测模型工程验收：`docs/knowledge/crypto_price_forecasting_models_playbook.md`

### S-1009 arxiv.org：TimeXer（Transformer 变体）时间序列预测（HTML）

- URL：https://arxiv.org/html/2512.22326v1
- 抓取方式：待定（建议优先 MCP `markitdown`，必要时 `playwright`）
- 抓取状态：todo（待抓取）
- 引入原因：用于登记 Transformer 变体在时间序列预测中的结构与多变量建模线索（含外部特征融合的工程注意事项）。
- 落地到本仓库：
  - 预测模型工程验收：`docs/knowledge/crypto_price_forecasting_models_playbook.md`

---

## S) 因子模型实现与框架集成（工程参考）

说明：

- 本分区用于登记“实现细节/数据治理/框架集成”相关来源，用于把论文口径落到本仓库的研究层与执行层。
- 若来源与结论只用于“概念对齐”，不直接参与本仓库结论，则不强制登记（避免 registry 膨胀）。
- 当前项目主线为**单交易对时间序列预测/择时**；因此这里的“因子模型实现”优先解释为：把因子语义映射到可在线计算的时间序列特征与 policy 输出，而不是横截面轮动实现。

### S-1010 artemisanalytics.com：Crypto Factor Model Analysis（实现细节/口径参考）

- URL：https://www.artemisanalytics.com/resources/crypto-factor-model-analysis
- 抓取方式：待定（建议优先 MCP `playwright`，必要时 `markitdown`）
- 抓取状态：todo（待抓取）
- 引入原因：用户材料引用 [1]，用于 SMB/VAL/MOM/NET 的构建步骤、分组口径与“成本侵蚀”风险提示的实现参考。
- 落地到本仓库：
  - 实现与集成落地：`docs/knowledge/crypto_factor_model_implementation_playbook.md`

### S-1011 qlib.readthedocs.io：Qlib 文档 PDF（v0.5.0）

- URL：https://qlib.readthedocs.io/_/downloads/en/v0.5.0/pdf/
- 抓取方式：待定（建议优先 MCP `playwright`；下载型页面可能需要渲染）
- 抓取状态：todo（待抓取）
- 引入原因：用户材料引用 [7]，用于 Qlib 工作流（数据→因子→模型→组合→回测）与研究侧组件的背景说明。
- 落地到本仓库：
  - 实现与集成落地：`docs/knowledge/crypto_factor_model_implementation_playbook.md`

### S-1012 qlib.readthedocs.io：Advanced Alpha（因子/表达式系统）

- URL：https://qlib.readthedocs.io/en/stable/advanced/alpha.html
- 抓取方式：待定（建议优先 MCP `markitdown`，必要时 `playwright`）
- 抓取状态：todo（待抓取）
- 引入原因：用户材料引用 [8]，用于 Qlib 因子表达式系统的参考入口；本仓库默认不直接复用表达式系统（避免与 factor_engine 形成第二套口径）。
- 落地到本仓库：
  - 实现与集成落地：`docs/knowledge/crypto_factor_model_implementation_playbook.md`

---

## T) 信息论 / 转移熵 / 复杂系统（单交易对时间序列）

说明：

- 本分区用于登记“熵/转移熵/复杂度/信息流网络”等信息论方法在加密市场中的研究线索。
- 当前项目主线为**单交易对时间序列预测/择时**：优先关注“熵/复杂度”作为噪声与体制特征的单币落地；跨币信息流网络仅作背景校准。

### S-1013 arxiv.org：2210.02633（加密收益的信息论/分布特性线索）

- URL：https://arxiv.org/pdf/2210.02633.pdf
- 抓取方式：待定（建议优先 MCP `markitdown`）
- 抓取状态：todo（待抓取）
- 引入原因：用户材料引用 [1]，用于 Shannon 熵与重尾分布等信息论视角的研究线索登记。
- 落地到本仓库：
  - 信息论落地笔记：`docs/knowledge/crypto_information_theory_signal_system_playbook.md`

### S-1014 mdpi.com：Entropy 24(11) 1583（重尾/非正态与信息论分析线索，PDF）

- URL：https://www.mdpi.com/1099-4300/24/11/1583/pdf?version=1667289176
- 抓取方式：待定（建议优先 MCP `markitdown`）
- 抓取状态：todo（待抓取）
- 引入原因：用户材料引用 [2]，用于“收益分布显著偏离正态、重尾拟合更优”等证据线索登记。
- 落地到本仓库：
  - 信息论落地笔记：`docs/knowledge/crypto_information_theory_signal_system_playbook.md`

### S-1015 arxiv.org：1906.05740（情绪-价格 Transfer Entropy / 信息流向）

- URL：https://arxiv.org/pdf/1906.05740.pdf
- 抓取方式：待定（建议优先 MCP `markitdown`）
- 抓取状态：todo（待抓取）
- 引入原因：用户材料引用 [3]，用于“情绪与价格的非线性有向因果（TE）强于线性因果”的研究线索登记。
- 落地到本仓库：
  - 信息论落地笔记：`docs/knowledge/crypto_information_theory_signal_system_playbook.md`

### S-1016 pmc.ncbi.nlm.nih.gov：PMC7540793（情绪/社媒与价格：非线性关系线索）

- URL：https://pmc.ncbi.nlm.nih.gov/articles/PMC7540793/
- 抓取方式：待定（建议优先 MCP `markitdown`，必要时 `playwright`）
- 抓取状态：todo（待抓取）
- 引入原因：用户材料引用 [4]，用于“社交情绪与价格非线性关系/双向耦合”的补充线索登记。
- 落地到本仓库：
  - 信息论落地笔记：`docs/knowledge/crypto_information_theory_signal_system_playbook.md`

### S-1017 mdpi.com：Entropy 27(4) 450（复杂度-熵平面/噪声类型分类线索）

- URL：https://www.mdpi.com/1099-4300/27/4/450
- 抓取方式：待定（建议优先 MCP `markitdown`，必要时 `playwright`）
- 抓取状态：todo（待抓取）
- 引入原因：用户材料引用 [7]，用于“复杂度-熵平面（CECP）分类混沌/随机/有色噪声”的研究线索登记。
- 落地到本仓库：
  - 信息论落地笔记：`docs/knowledge/crypto_information_theory_signal_system_playbook.md`

### S-1018 pmc.ncbi.nlm.nih.gov：PMC12027155（复杂度-熵平面：加密生命周期线索）

- URL：https://pmc.ncbi.nlm.nih.gov/articles/PMC12027155/
- 抓取方式：待定（建议优先 MCP `markitdown`，必要时 `playwright`）
- 抓取状态：todo（待抓取）
- 引入原因：用户材料引用 [8]，用于“按币种生命周期划分噪声类型/可预测性”的研究线索登记。
- 落地到本仓库：
  - 信息论落地笔记：`docs/knowledge/crypto_information_theory_signal_system_playbook.md`

### S-1019 nature.com：s41598-023-31618-4（市场效率量化：量子模型线索）

- URL：https://www.nature.com/articles/s41598-023-31618-4
- 抓取方式：待定（建议优先 MCP `playwright`；可能需要渲染）
- 抓取状态：todo（待抓取）
- 引入原因：用户材料引用 [9]，用于“市场效率可量化指标”的背景校准线索登记。
- 落地到本仓库：
  - 信息论落地笔记：`docs/knowledge/crypto_information_theory_signal_system_playbook.md`

### S-1020 arxiv.org：2309.04959（区块链队列系统：最大熵原理线索）

- URL：https://arxiv.org/pdf/2309.04959.pdf
- 抓取方式：待定（建议优先 MCP `markitdown`）
- 抓取状态：todo（待抓取）
- 引入原因：用户材料引用 [10]，用于“区块链系统视角（吞吐/延迟/参数约束）”的背景校准线索登记。
- 落地到本仓库：
  - 信息论落地笔记：`docs/knowledge/crypto_information_theory_signal_system_playbook.md`

### S-1021 mdpi.com：Entropy 22(7) 760（转移熵网络：风险预警线索，PDF）

- URL：https://res.mdpi.com/d_attachment/entropy/entropy-22-00760/article_deploy/entropy-22-00760.pdf
- 抓取方式：待定（建议优先 MCP `markitdown`）
- 抓取状态：todo（待抓取）
- 引入原因：用户材料引用 [11]，用于“多变量转移熵网络在动荡期的聚类/复杂度变化”线索登记（跨币网络，背景）。
- 落地到本仓库：
  - 信息论落地笔记：`docs/knowledge/crypto_information_theory_signal_system_playbook.md`

### S-1022 arxiv.org：2111.09057（信息流网络/系统风险线索）

- URL：http://arxiv.org/pdf/2111.09057.pdf
- 抓取方式：待定（建议优先 MCP `markitdown`）
- 抓取状态：todo（待抓取）
- 引入原因：用户材料引用 [12]，用于“信息流网络分析/风险预警”的补充线索登记（背景）。
- 落地到本仓库：
  - 信息论落地笔记：`docs/knowledge/crypto_information_theory_signal_system_playbook.md`

### S-1023 mdpi.com：Entropy 27(12) 1234（市场反应窗口不对称：信息熵变化线索）

- URL：https://www.mdpi.com/1099-4300/27/12/1234
- 抓取方式：待定（建议优先 MCP `markitdown`，必要时 `playwright`）
- 抓取状态：todo（待抓取）
- 引入原因：用户材料引用 [14]，用于“利好/利空反应窗口差异与信息熵变化”的背景线索登记。
- 落地到本仓库：
  - 信息论落地笔记：`docs/knowledge/crypto_information_theory_signal_system_playbook.md`

---

## U) 信号组合 / 长短腿 / 去冗余（单交易对择时映射）

说明：

- 本分区主要来自传统股票/因子研究，但这里仅取其“组合构建与评估方法论”，映射到本仓库的单交易对择时与执行。
- 重点不是横截面选币，而是：长/短方向分离评估、信号冲突处理、以及特征冗余（投影）的诊断与治理。

### S-1024 research-center.amundi.com：拆分长短腿/纯多头因子（卖空受限下的组合构建线索）

- URL：https://research-center.amundi.com/files/nuxeo/dl/64691927-6c77-4b12-b267-93cc85cd0619
- 抓取方式：待定（建议优先 MCP `markitdown`，必要时 `playwright`）
- 抓取状态：todo（待抓取）
- 引入原因：用户材料引用，用于“长短腿分离优于简单混合、卖空约束下的可实施组合构建”的证据线索登记。
- 落地到本仓库：
  - 长/短信号分离与去冗余：`docs/knowledge/factor_single_vs_multi_timing.md`

### S-1025 gsam.com：Combining Investment Signals in Long/Short Strategies（Integrated vs Sleeves 的方法论线索）

- URL：https://www.gsam.com/content/dam/gsam/pdfs/institutions/en/articles/2018/Combining_Investment_Signals_in_LongShort_Strategies.pdf
- 抓取方式：待定（建议优先 MCP `markitdown`）
- 抓取状态：todo（待抓取）
- 引入原因：用户材料引用，用于“信号组合：集成法 vs 分离法（sleeves）”的工程化对齐线索登记。
- 落地到本仓库：
  - 长/短信号分离与冲突处理：`docs/knowledge/factor_single_vs_multi_timing.md`

### S-1026 alphaarchitect.com：combine vs separate factor exposures（因子暴露混合/分离的实践讨论）

- URL：https://alphaarchitect.com/should-investors-combine-or-separate-their-factor-exposures/
- 抓取方式：待定（建议优先 MCP `markitdown`，必要时 `playwright`）
- 抓取状态：todo（待抓取）
- 引入原因：用户材料引用，用于“信号混合会引入抵消/稀释；分离更便于治理”的直觉校准线索登记。
- 落地到本仓库：
  - 长/短信号分离与组合方式：`docs/knowledge/factor_single_vs_multi_timing.md`

### S-1027 cfm.com：Equity Factors: To Short or Not To Short（空头腿的贡献、成本与可预测性不对称线索）

- URL：https://www.cfm.com/wp-content/uploads/2022/12/137-Equity-Factors-To-Short-Or-Not-To-Short-That-Is-The-Question.pdf
- 抓取方式：待定（建议优先 MCP `markitdown`）
- 抓取状态：todo（待抓取）
- 引入原因：用户材料引用，用于“空头腿是否值得纳入：预测能力阈值、分散化贡献与成本权衡”的线索登记。
- 落地到本仓库：
  - 按 side 拆开评估（长/短腿）：`docs/knowledge/factor_single_vs_multi_timing.md`

### S-1028 quantpedia.com：Long-Short vs Long-Only Implementation of Equity Factors（实施约束/成本/容量对比线索）

- URL：https://quantpedia.com/long-short-vs-long-only-implementation-of-equity-factors/
- 抓取方式：待定（建议优先 MCP `playwright`；可能存在访问限制）
- 抓取状态：todo（待抓取）
- 引入原因：用户材料引用，用于“长短 vs 纯多头在成本/容量/约束下的取舍”线索登记。
- 落地到本仓库：
  - 合约择时的成本敏感与 side 评估：`docs/knowledge/factor_single_vs_multi_timing.md`

### S-1029 nber.org：w24618（潜在因子/低维子空间与‘投影’直觉的理论背景线索）

- URL：https://www.nber.org/system/files/working_papers/w24618/w24618.pdf
- 抓取方式：待定（建议优先 MCP `markitdown`）
- 抓取状态：todo（待抓取）
- 引入原因：用户材料引用，用于“少数潜在维度张成大部分系统性信息、不同因子可能只是投影/旋转”的理论背景线索登记。
- 落地到本仓库：
  - 特征去冗余与‘本征子空间’视角：`docs/knowledge/factor_single_vs_multi_timing.md`

### S-1030 sciencedirect.com：pii/S1566014119301669（factor spanning test / 冗余因子检验线索）

- URL：https://www.sciencedirect.com/science/article/abs/pii/S1566014119301669
- 抓取方式：待定（建议优先 MCP `playwright`；可能存在付费墙/登录限制）
- 抓取状态：todo（待抓取）
- 引入原因：用户材料引用，用于“spanning test：检验新因子是否可由已有因子线性解释，从而过滤冗余”的方法论线索登记。
- 落地到本仓库：
  - 用 spanning 思路判断新特征是否新增维度：`docs/knowledge/factor_single_vs_multi_timing.md`

---

## V) 采样 / 多尺度 / 时间尺度（单交易对）

说明：

- 本分区用于登记“时间尺度不是周期、采样与混叠、以及多尺度分解/体制识别”的基础概念来源。
- 这些来源主要服务于：单交易对择时的评估口径（固定 timeframe + 跨尺度 sanity check），以及微观结构信号的半衰期/尺度错配解释。

### S-1031 en.wikipedia.org：Nyquist frequency（采样与混叠的基础定义）

- URL：https://en.wikipedia.org/wiki/Nyquist_frequency
- 抓取方式：待定（建议优先 MCP `markitdown`）
- 抓取状态：todo（待抓取）
- 引入原因：用于“timeframe=采样间隔 Δt，改变周期会改变可观测频率范围；高频结构可能混叠成低频伪规律”的概念对齐。
- 落地到本仓库：
  - timeframe 作为超参数与跨尺度复核：`docs/knowledge/factor_single_vs_multi_timing.md`
  - 半衰期错配 + aliasing 风险提示：`docs/knowledge/crypto_liquidity_microstructure_playbook.md`

### S-1032 pmc.ncbi.nlm.nih.gov：PMC4447444（Hurst 指数与自相似性的基础线索）

- URL：https://pmc.ncbi.nlm.nih.gov/articles/PMC4447444/
- 抓取方式：待定（建议优先 MCP `markitdown`）
- 抓取状态：todo（待抓取）
- 引入原因：用于“自相似/长期记忆可用 Hurst 指数刻画；且 H 会随尺度变化（multiscaling）”的概念锚点。
- 落地到本仓库：
  - 多尺度体制标签（可选增强）：`docs/knowledge/factor_single_vs_multi_timing.md`

### S-1033 hindawi.com：4024953（Wavelet/EMD 的多尺度分解线索）

- URL：https://www.hindawi.com/journals/mpe/2022/4024953/
- 抓取方式：待定（建议优先 MCP `markitdown`）
- 抓取状态：todo（待抓取）
- 引入原因：用于“别选最优周期，而是做多尺度分解（趋势/中频/高频/噪声）并按尺度融合”的方法论线索登记。
- 落地到本仓库：
  - 多尺度融合的工程化直觉（可选增强）：`docs/knowledge/factor_single_vs_multi_timing.md`

### S-1034 arxiv.org：2201.10466（rough volatility：波动的多尺度与粗糙性线索）

- URL：http://arxiv.org/pdf/2201.10466.pdf
- 抓取方式：待定（建议优先 MCP `markitdown`）
- 抓取状态：todo（待抓取）
- 引入原因：用于“波动本身具有多尺度粗糙性（H 很低）的证据线索”，提醒波动预测/风控信号要做尺度分段与样本外检验。
- 落地到本仓库：
  - 风险标签与波动门控的尺度意识：`docs/knowledge/crypto_risk_factors_engineering_playbook.md`
  - timeframe 选择与稳健性校验：`docs/knowledge/factor_single_vs_multi_timing.md`

---

## W) Koopman / 本征模态（时序预测：从“选周期”到“学算子”）

说明：

- 本分区用于登记 Koopman/DMD/EDMD 相关的参考来源（面向“非平稳时序”的动力系统视角）。
- 在本仓库的落地优先级：先跑通“可验收闭环”（额外因子 → timing_audit 体检 → policy 去冗余），再考虑引入更重的训练型模型。

### S-1035 arxiv.org：2305.18803（Koopa: Learning Non-stationary Time Series Dynamics with Koopman Predictors）

- URL：https://arxiv.org/abs/2305.18803
- 抓取方式：待定（建议优先 MCP `markitdown`）
- 抓取状态：todo（待抓取）
- 引入原因：
  - 用户提供的核心参考：用 Koopman Predictor + 时变/时不变拆分，建模非平稳时间序列动力学；
  - 其中 FourierFilter（频域拆分）与局部算子（eDMD）设计，直接启发本仓库的 Koopa-lite 原型。
- 落地到本仓库：
  - Koopa-lite 原型脚本（FFT 拆分 + rolling Koopman/DMD）：`scripts/qlib/koopman_lite.py`
  - 额外特征接入择时体检（同口径验收）：`scripts/qlib/timing_audit.py`

### S-1036 github.com：thuml/Koopa（Koopa 代码仓库）

- URL：https://github.com/thuml/Koopa
- 抓取方式：待定（建议优先 MCP `markitdown`；若 README 渲染不全再用 `playwright`）
- 抓取状态：todo（待抓取）
- 引入原因：
  - 作为“实现参照系”：FourierFilter、KPLayer（全局/局部 Koopman Predictor）、operator adaptation 的工程细节。
- 落地到本仓库：
  - 参照实现后的轻量闭环：`scripts/qlib/koopman_lite.py`
  - 本征模态/去冗余的工程化说明：`docs/knowledge/factor_single_vs_multi_timing.md`
