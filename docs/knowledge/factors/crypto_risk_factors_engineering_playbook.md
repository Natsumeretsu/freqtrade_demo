# 加密市场风险因子：工程化落地地图（本仓库版）

更新日期：2026-01-15

本文目标：

1. 把“风险因子/因子模型”的学术叙事，翻译成**可观测指标 → 可执行动作 → 可复现证据**。
2. 明确哪些风险维度可以在“仅 OHLCV”的数据约束下落地，哪些必须引入外部数据（链上/市值/盘口/宏观/情绪）。
3. 给出本仓库的最短路径：先做 **P0（无外部数据）**，再按 ROI 逐步升级到 **P1/P2**。

适用上下文（本仓库当前约束，默认口径）：

- 标的：`BTC/USDT:USDT`、`ETH/USDT:USDT`
- 市场：加密合约（含杠杆/资金费率维度）
- 周期：`4h`（信号层/风控层）
- 数据：研究层以 `02_qlib_research/qlib_data/.../*.pkl` 为主（OHLCV）
- 工程底座：`factors.yaml`（特征单一来源）+ `features.py`（离线/在线一致）+ `auto_risk`（漂移/制度 → 动作闭环）

当前研究主线（重要）：本项目暂时以**单交易对时间序列预测/择时**为主；横截面多币因子（SMB/NET/C-5 等）仅作为风险语义与背景知识。

---

## 0) 一句话结论

加密市场的风险不是“一个指标能解释的”，而是**多维度、高相关、快切换**：工程上最稳健的做法是把它拆成几类可控开关：

- **硬过滤（Hard）**：禁新开仓/强制减仓/停策略（应对外生黑天鹅、数据/交易不可用、结构性崩坏）
- **软过滤（Soft）**：仓位/杠杆/开仓频率缩放（应对高波动、流动性枯竭、制度逆风、概念漂移）
- **证据落盘（Evidence）**：每次触发都落盘，便于复盘与阈值校准（否则永远靠感觉调参）

---

## 1) 因子模型（学术）与风险因子（工程）的“正确位置”

你提供的三因子/五因子/IPCA 等框架，本质上大多属于：

- **横截面定价/风险暴露解释**：解释“为什么不同币的预期收益不同”（需要很多币种与外部属性数据）
- **而不是**：单一币对的入场/出场规则（择时/CTA）

对本仓库而言，更合理的落地方式是：

1. **把因子模型当作“风险语义层”**：告诉我们应该关心哪些风险维度（规模、动量、流动性、网络采用、下行风险、相关性外溢等）。
2. **把策略当作“执行层”**：仍然做单币（或少币）择时，但在上层叠加“风险预算/禁开仓/降杠杆”的闭环。
3. **把可获得数据决定的部分先做完**：先用 OHLCV 代理（P0），再引入外部数据把关键缺口补齐（P1/P2）。

### 1.1 三因子模型（CMKT / CSMB / CMOM）：把“解释力”翻译成“工程语义”

学术叙事（常见口径）：

- **CMKT（市场因子）**：所有代币按市值加权的整体市场收益（market-wide risk）。
- **CSMB（规模因子）**：小盘组合收益 - 大盘组合收益（size）。
- **CMOM（动量因子）**：赢家组合收益 - 输家组合收益（momentum）。

工程解读（对本仓库更有用的部分）：

- 这类模型主要解释“跨币种的预期收益差异”（横截面），不是单币择时规则。
- 你提供的综述引用指出：三因子模型对加密横截面收益的解释力可达 **50%~80%** [2]；规模效应可能为负（小币相对大币超额收益约 **-3.4%~-4.1%/周**）[2]；动量溢价为正（赢家-输家约 **+2.5%~+4.1%/周**）[1]。这些数字强依赖样本与时间窗，落地前必须用本仓库的币池与数据口径复核。
- 在本仓库的 P0 约束下：
  - CMKT → 用 BTC 作为 market proxy（见 2.1 / `auto_risk.market_context`）。
  - CSMB → 需要市值数据与更大的 universe（P2），否则不建议硬做（见 2.4）。
  - CMOM → 先用 `ret_*`/`ema_spread` 做单币时间序列动量；再决定是否扩展到横截面赢家-输家（见 2.5）。

### 1.2 五因子/动态因子模型：更适合研究层落地

如需进一步了解 C-5、IPCA、Trend factor 等“横截面定价”研究与落地边界，见：`docs/knowledge/crypto_pricing_five_factor_models_playbook.md`。
更宏观的因子模型生态地图与指标口径见：`docs/knowledge/crypto_factor_model_ecosystem_survey.md`。
因子模型实现与集成落地（研究→执行）见：`docs/knowledge/crypto_factor_model_implementation_playbook.md`。
价格预测模型的工程验收（避免“高分但不可交易”）见：`docs/knowledge/crypto_price_forecasting_models_playbook.md`。
信息论视角下的“熵/转移熵/复杂度”特征与风险含义见：`docs/knowledge/crypto_information_theory_signal_system_playbook.md`。

---

## 2) 风险维度清单：从“概念”到“可观测/可执行”

下面按你给出的内容逐类拆解，并标注“本仓库能否落地”与建议动作类型。

### 2.1 市场因子（CMKT / MKT）：整体风险偏好的代理

工程含义：市场下跌/风险偏好下降时，大多数资产都会同步变差，尤其在压力期相关性会上升。

- P0（仅 OHLCV）可做：
  - 用 **BTC 收益/波动**作为市场代理（对 ETH 更有意义：`ETH 的走势很大程度受 BTC 解释`）。
  - 用“市场危机制度”触发降风险（本仓库已做：`auto_risk.regime.crisis`）。
- 建议动作：
  - Soft：波动/危机时降低仓位与杠杆；
  - Hard：极端异常时禁新开仓（可选，谨慎）。
- 本仓库落地点（建议）：
  - 已实现 `market_context`（BTC 作为 market proxy），当前仅汇总为额外风险折扣（软缩放，不新增禁新开）。

### 2.2 波动性与清算级联：加密的第一风险（P0 必做）

工程含义：加密的尾部与杠杆效应会让“波动上升 → 强制平仓/流动性枯竭 → 更高波动”形成正反馈。

- P0（仅 OHLCV）可做：
  - 实现波动率/区间波动/跳跃（`vol_*`、`hl_range`、gap 等）
  - “波动的波动”（滚动波动率的变化率）
  - 量价异常：`volume_z_*` 与 `|ret|` 同时异常（风险放大期）
- P1（交易所数据）建议补齐：
  - 资金费率、未平仓量（OI）、爆仓数据（若可得）
- 建议动作：
  - Soft：波动上升时降低杠杆/仓位；
  - Hard：疑似清算级联（波动+成交量异常）时禁新开仓，保留退出。
- 本仓库现状：
  - `ml_core` 已含 `vol_12`、`hl_range`、`volume_z_72`；
  - `auto_risk.regime` 已有 crisis 折扣，属于正确方向。

### 2.3 流动性风险与成交量溢价：决定“能不能成交/成本是否爆表”

工程含义：低流动性会导致滑点、冲击成本、无法退出；压力期更会出现“价格发现失真”。

- P0（仅 OHLCV）可做（弱代理）：
  - `volume_z_*`、成交量长期分位数、`|ret|/volume`（单位成交量的价格变化）
  - 低成交量 + 大波动：视作流动性枯竭预警
- P1（盘口/点差）补齐后更可靠：
  - 点差（spread）、深度（depth）、订单簿不平衡（OBI）、成交失败率等
- 建议动作：
  - Soft：流动性下降时降低单笔仓位、降低杠杆；
  - Hard：数据/成交不可用时禁新开仓（只允许退出）。
- 进一步阅读（微观结构/执行层）：`docs/knowledge/crypto_liquidity_microstructure_playbook.md`

### 2.4 规模因子（CSMB / SMB）：横截面因子，当前数据约束下不建议硬做

工程含义：规模效应在加密中可能表现为“溢价”也可能表现为“折价”，但它需要**大量币种**与**市值数据**构造长短组合。

- P0（仅 BTC/ETH + OHLCV）现实情况：
  - 无法形成稳健的“大小盘分组”，做出来很容易是噪声。
- 你提供的摘要中提到：
  - 小币相对大币的超额收益约 **-3.4%~-4.1%/周**（示例口径）。这意味着规模效应可能为负；但仍需按本地币池与样本期复核。
- 建议落地方式（如果未来扩展到 Top50）：
  - P2：引入市值数据（CoinMarketCap/交易所/第三方），构建稳定 universe，再做 SMB。
- 本仓库建议：
  - 暂时把“规模”当作**资产选择与交易成本约束**的问题（先把 universe 扩大后再做）。

### 2.5 动量因子（CMOM / MOM）：可以落地，但要区分“择时信号”与“风险折扣”

工程含义：趋势/动量在加密中很强，但不同币、不同市值段可能表现不同（小币甚至会反向）。

- P0（仅 OHLCV）可做：
  - **时间序列动量（单币）**：直接用 `ret_*`/`ema_spread` 等作为趋势强弱（本仓库已有）
  - **横截面动量（赢家-输家）**：需要足够币池 + 定期再平衡；更适合先在研究层做离线复核，再决定是否接入执行层
- 你提供的摘要中提到：
  - 赢家相对输家的超额收益约 **+2.5%~+4.1%/周**（示例口径）。落地时更重要的是“在不同制度/不同币池是否稳定”，而不是数字本身。
- 建议动作：
  - Soft：顺势方向降低风险折扣（against_trend 降低）；
  - Hard：不要用“动量反向”直接停机（更适合当信号层/策略层）。
- 本仓库现状：
  - `auto_risk.regime.scale.against_trend` 已体现“顺势/逆势差异”。

### 2.6 价值因子（VAL）：加密版“价值”难定义，P0 不建议做硬信号

工程含义：学术里常用“过去 52 周收益”做价值代理，但其经济学解释与加密基本面并不总一致。

- P0 可做（但更适合研究，不适合实盘硬开关）：
  - 长周期回撤/均值回复强度的 proxy（需要更长历史与更严谨验证）
- P2（链上/基本面）更合理的“价值代理”：
  - MVRV、Realized Cap、活跃地址/交易额等

### 2.7 网络采用因子（NET）：高价值，但必须引入链上数据

工程含义：这是加密特有的“基本面”，但本仓库当前 OHLCV 数据无法表达。

- P2（链上数据）建议路线：
  - 先从 BTC/ETH 的可得指标做最小集（活跃地址、交易数、交易所净流入/流出）
  - 再扩展到多币（成本与维护会显著上升）
- 工程提醒：
  - 链上指标也会漂移，需要同样的“基线 + 漂移 + 动作”闭环。

### 2.8 宏观/监管风险：外生冲击，正确做法是“预案化开关”

工程含义：监管/政策/利率冲击通常不是 OHLCV 能提前稳定识别的；硬做会导致“拟合解释而非可执行预测”。

- 建议落地方式：
  - 手动/日历型的风险开关（重大事件窗口禁新开/降杠杆）
  - 保持证据落盘（事件→动作→收益/回撤影响）
- 2026 年度重点（示例，不构成预测）：
  - 监管确定性变化（例如美国监管框架立法进展、欧盟 MiCA 落地节奏等）
  - 利率路径与风险偏好（央行政策转向、资金流变化）
  - 机构化带来的相关性变化（例如 ETF 资金流与“更像风险资产”的联动增强）
- 未来可选（P2+）：
  - 引入宏观指标与新闻情绪，但要有严格的回测验证与数据对齐。

### 2.9 情绪/羊群/FOMO：可做弱代理，但更适合“风险预算”而非信号

工程含义：情绪数据通常来自外部；若没有外部源，可以用“价格+量的极端形态”做弱代理。

- P0（仅 OHLCV）可做：
  - 极端上涨/下跌 + 放量（FOMO/恐慌 proxy）
  - 尾部形态（skew/kurt）用于解释（不建议单独触发硬禁开）
- P2（外部数据）更合理：
  - 恐惧贪婪指数、社媒热度/KOL 事件、资金净流等，更适合作为“风险预算/降档”而非信号层硬规则

### 2.10 技术/安全/交易对手风险：OHLCV 无法提前预测，但可以快速止损/停机

工程含义：合约漏洞、交易所风险、数据中断属于“系统性不可控”，工程上要把它们当作**停机条件**。

- P0 可做（本地可观测）：
  - 数据缺失/时间戳跳变/成交量异常为 0（数据或交易不可用）
- P1 可做（交易所状态）：
  - 获取交易所维护/异常公告（若可自动化），或人工开关
- 工程提醒：
  - 智能合约漏洞/共识攻击/交易所破产等事件往往无法提前量化预测，但会通过“波动+流动性”渠道迅速传导；应优先保证硬停机与退出路径可靠

### 2.11 外溢/传染（BTC 主导、跨币相关性断裂）：P0 也能做，ROI 很高

工程含义：当相关结构变化（相关性断裂/β 跳变）时，原来的“对冲/分散”假设会失效。

- P0（仅 BTC/ETH OHLCV）可做：
  - `corr(ret_BTC, ret_ETH)` 的滚动监控
  - `beta_ETH_to_BTC` 的滚动估计（简化线性回归即可）
- 建议动作：
  - Soft：相关性下降/结构变化时降低杠杆或缩小仓位上限；
  - Hard：当相关性断裂 + 高波动同时出现，可短期禁新开（可选）。

### 2.12 项目基本面与竞争风险：更适合 universe 管理，而不是信号层

工程含义：tokenomics、解锁计划、生态竞争（L1/L2、AppChain/Rollup 等）会带来中长期“生存/归零”风险，但短周期 OHLCV 难以提前稳定识别。

- P0（无需外部数据）建议做法：
  - 把这类风险当作“标的选择”问题：白名单/黑名单、最小上市时间、最小流动性门槛（避免薄盘与操纵型标的）
- P2（第三方/链上/基本面）可做：
  - 供应与解锁、持仓集中度、TVL/活跃用户、开发活跃度等，作为 universe 打分或仓位上限
- 工程提醒：
  - 这类指标更适合“慢变量”（周/月级更新），避免高频切换导致过拟合与执行噪声

### 2.13 风险衡量与管理：VaR 不够，用尾部视角做复盘与校准

工程含义：加密收益分布厚尾、跳跃、极端归零事件更多，传统正态 VaR 往往低估尾部。

- 建议把尾部风险主要放在“离线评估/报告”层：
  - 用 CVaR/Expected Shortfall、极值理论（EVT）等衡量极端损失
  - 配合成本敏感性与压力测试做稳健性验收
- 与本仓库的对齐：
  - 这类度量更适合作为 `scripts/analysis/*` 的报告指标，而不是策略实时硬开关（否则容易误触）

---

## 3) 本仓库的 P0 落地建议（不引入外部数据）

在“只有 BTC/ETH、只有 OHLCV”的约束下，最值得做的三件事：

1. **Market Proxy（CMKT 的工程版本）**：用 BTC 作为市场代理，对 ETH 的风控/仓位缩放更有效。
2. **相关性断裂监控（外溢风险）**：滚动相关性/β 作为额外风险折扣输入（属于风控层，不是信号层）。
3. **流动性枯竭代理增强**：在已有 `volume_z_72` 基础上增加 “`|ret|/volume`” 一类指标，用于识别“薄盘冲击”。

落地方式建议（与本仓库架构对齐）：

- 指标声明：优先走 `04_shared/config/factors.yaml`（特征单一来源）
- 计算实现：优先复用 `03_integration/trading_system/infrastructure/factor_engines/*`
- 风控动作：集中在 `03_integration/trading_system/infrastructure/auto_risk.py`
- 阈值校准：用 `scripts/analysis/auto_risk_replay.py` 做离线回放，避免靠直觉调参

---

## 4) P1/P2 升级路线（引入外部数据后再做）

### P1（交易所可得，ROI 高）

- 资金费率（funding）：作为“拥挤度/杠杆偏向”的代理
- OI（未平仓量）与爆仓（liquidations）：更直接的清算级联信号
- 点差/深度：执行质量与流动性制度

### P2（链上/第三方，ROI 中等但成本高）

- 市值/流通量：用于 SMB（规模）与 universe 构建
- 活跃地址/交易额/交易所净流：用于 NET（网络采用）与“资金迁移”风险
- 稳定币供给/赎回：宏观流动性 proxy（需要严格数据对齐）

工程提醒：

- 外部数据必须解决三件事：**时间对齐**、**缺失处理**、**漂移/版本治理**。
- 引入外部数据后，要把它们也纳入漂移与证据落盘体系（否则越做越不可控）。

---

## 5) 与本仓库现有模块的对齐（避免重复造轮子）

- 特征声明（单一来源）：`04_shared/config/factors.yaml`
- 特征计算（实现唯一）：`03_integration/trading_system/infrastructure/factor_engines/*`（当前为 talib）
- 训练/导出（包含基线）：`scripts/qlib/train_model.py` → `feature_baseline.json`
- 漂移体检（诊断视角）：`scripts/qlib/check_drift.py`
- 自动闭环（执行视角）：`03_integration/trading_system/infrastructure/auto_risk.py`
- 阈值校准（统计视角）：`scripts/analysis/auto_risk_replay.py`

---

## 6) 你现在最可能遇到的三个“落地误区”

1. **把横截面因子当成择时信号**：会导致大量“理论正确但回测/实盘无效”的实现。
2. **用单一指标触发硬停机**：加密天然非平稳，阈值会频繁误触；硬动作应尽量只对“确凿不可交易/不可控风险”生效。
3. **不做证据落盘与离线校准**：没有回放统计，所有阈值讨论都会变成“主观争论”。

---

## 7) 来源（用户摘要，待登记/抓取）

说明：

- 为保持仓库工具链兼容性，source registry 的 S-ID 使用 `S-<至少 3 位数字>`（相关抓取/ingest 脚本依赖该格式）。因此本次仅将正文引用到的核心来源 [1]~[22] 登记为 `S-972`~`S-993`。
- [23]~[52] 为扩展阅读，暂未逐条登记；如后续需要抓取与落盘，可从中挑选关键条目补录。

### 7.1 核心来源（已登记到 `docs/knowledge/source_registry.md`）

- [1] https://www.ssrn.com/abstract=3379131（S-972）
- [2] https://www.nber.org/system/files/working_papers/w25882/w25882.pdf（S-973）
- [3] https://journals.vsu.ru/econ/article/view/3614（S-974）
- [4] https://www.investopedia.com/riding-the-wave-how-to-manage-crypto-volatility-11833947（S-975）
- [5] https://www.moomoo.com/sg/hans/learn/detail-7-key-factors-that-could-impact-cryptocurrency-prices-117206-240769245（S-976）
- [6] https://www.binance.com/en/square/post/01-08-2026-crypto-markets-face-key-challenges-for-growth-in-2026-34792356442450（S-977）
- [7] https://proceedings.stis.ac.id/icdsos/article/view/727（S-978）
- [8] https://www.investing.com/analysis/bitcoin-vs-sp-500--risk-reassessment-into-2026-200673050（S-979）
- [9] https://www.binance.com/es-MX/square/post/23562037194689（S-980）
- [10] https://jemaca.aks.or.id/jemaca/article/view/23（S-981）
- [11] https://www.hde.hr/sadrzaj_en.aspx?Podrucje=2034（S-982）
- [12] https://arxiv.org/pdf/2308.08554.pdf（S-983）
- [13] https://republic.com/help/what-are-the-risks-associated-with-digital-assets-blockchain-technology-utility-1（S-984）
- [14] https://www.taurushq.com/legal/regulatory-risk/risks-digitalassets/（S-985）
- [15] https://www.oanda.com/us-en/trade-tap-blog/asset-classes/crypto/risks-of-trading-cryptocurrency/（S-986）
- [16] https://crypto.com/en/market-updates/top-cryptos-to-watch-in-2026（S-987）
- [17] https://coincub.com/risks-and-rewards-in-assessing-volatility-in-the-crypto-market/（S-988）
- [18] https://www.mdpi.com/1911-8074/12/2/52/pdf（S-989）
- [19] https://journal.sinergi.or.id/index.php/ijat/article/view/479（S-990）
- [20] http://arxiv.org/pdf/2407.15766.pdf（S-991）
- [21] https://www.garp.org/risk-intelligence/market/digital-asset-risk-241018（S-992）
- [22] https://www.bcg.com/publications/2024/a-risk-and-control-framework-for-digital-financial-assets（S-993）

### 7.2 扩展阅读（未逐条登记）

- [23] https://link.springer.com/10.1007/s43546-023-00577-3
- [24] https://link.springer.com/10.1007/s10614-025-10888-2
- [25] https://dinastires.org/JAFM/article/view/2379
- [26] https://www.emerald.com/insight/content/doi/10.1108/JCMS-07-2024-0038/full/html
- [27] https://arxiv.org/pdf/1912.05228.pdf
- [28] https://downloads.hindawi.com/journals/complexity/2021/5581843.pdf
- [29] http://arxiv.org/pdf/2406.19401.pdf
- [30] https://www.mdpi.com/1911-8074/15/11/532/pdf?version=1668428001
- [31] https://arxiv.org/pdf/2411.09676.pdf
- [32] https://pmc.ncbi.nlm.nih.gov/articles/PMC8996802/
- [33] https://www.sciencedirect.com/science/article/abs/pii/S1057521925004764
- [34] https://www.straitsfinancial.com/insights/manage-digital-assets-effectively
- [35] https://onlinelibrary.wiley.com/doi/full/10.1002/fut.22425
- [36] https://finance.yahoo.com/news/why-crypto-today-january-13-142615613.html
- [37] https://www.ey.com/en_us/insights/financial-services/token-due-diligence-a-structured-approach-to-digital-asset-risk
- [38] https://www.sciencedirect.com/science/article/abs/pii/S095219762400808X
- [39] https://www.weforum.org/stories/2026/01/digital-economy-inflection-point-what-to-expect-for-digital-assets-in-2026/
- [40] https://wmi.edu.sg/programmes/asset-management/digital-assets-strategies-risks-regulations/
- [41] https://www.semanticscholar.org/paper/ca0baff8a87e52442f88822989bd02fb5a2a5ee3
- [42] https://rbes.fa.ru/jour/article/download/94/94
- [43] http://arxiv.org/pdf/2411.13615.pdf
- [44] https://journals.sagepub.com/doi/pdf/10.1177/21582440231193600
- [45] https://zodia-custody.com/digital-asset-risk-disclosures/
- [46] https://www.cmcmarkets.com/zh-nz/cfd/learn/cfd-asset-classes/crypto-risks
- [47] https://www.osl.com/hk-en/academy/article/cryptocurrency-price-movements-key-factors-that-drive-volatility
- [48] http://gaoli.ruc.edu.cn/jrkjqy/ea0f47a83317449bb963e7f24932d0f1.htm
- [49] https://www.cftc.gov/sites/default/files/2022-09/DigitalAssetRisks.pdf
- [50] https://www.kroll.com/zh-cn/publications/navigating-the-crypto-maze-mitigating-risks-maximizing-opportunities
- [51] https://www.blackrock.com/us/financial-professionals/insights/exploring-crypto-volatility
- [52] https://www.moneysense.gov.sg/risks-of-trading-payment-token-derivatives/
