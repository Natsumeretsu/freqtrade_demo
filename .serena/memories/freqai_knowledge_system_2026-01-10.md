# Freqtrade_demo：项目固有知识结构（MCP 抓取 → 登记 → 回灌）

更新日期：2026-01-10

> ⚠️ 快照归档：本文件从 2026-01-10 起仅作为里程碑快照，不再持续更新。
> 
> 最新主干请以分类记忆为准：
> - `freqai_index`
> - `freqai_methodology`
> - `freqai_ops_environment`
> - `freqai_sources_policy`

## 0) 当前环境状态（浏览器与抓取）
- 若缺少 Chrome 导致 `playwright_mcp` / `chrome_devtools_mcp` 不可用：运行 `./scripts/tools/fix_chrome_for_mcp.ps1`（无需管理员权限；等价手动步骤见 `project_docs/setup/codex_mcp_sync.md`）。
- 修复后：遇到需要 JS 的页面优先用 `playwright_mcp` 抓取；失败再登记为 blocked。



## 1) 文档结构（已迁移）
- 原 `other_doc/` 已迁移为 `project_docs/`，并按职责分层：
  - `project_docs/design/`：策略赛道与策略设计文档（含“策略类唯一基底”）
  - `project_docs/guidelines/`：工程规范（例如回测输出标准）
  - `project_docs/setup/`：工具/环境同步（Claude/Codex 等）
  - `project_docs/knowledge/`：外部来源登记与可持续知识沉淀

## 2) 策略文档规则（强制）
- “一类策略（一个 `IStrategy` 子类）→ 一份唯一基底文档”。
- 唯一入口索引：`project_docs/freqai_core_strategy_guide.md`。
- 策略细节只写在该策略对应的基底文档，索引文件只挂链接，避免多源冲突。

## 3) 回测输出标准（强制）
- 规范：`project_docs/guidelines/backtest_reporting_standard.md`。
- 关键要求：每次回测至少输出 1 份“逐交易对 vs Market change”报表（HTML 优先，其次 CSV）。
- 报表工具：`scripts/analysis/pair_report.py`。
- 运行约定：Freqtrade 命令统一通过 `./scripts/ft.ps1`（避免生成多余 `user_data/`）。

## 4) 项目知识沉淀机制（主入口）
- 知识索引：`project_docs/knowledge/index.md`。
- 来源登记（权威清单）：`project_docs/knowledge/source_registry.md`（URL/抓取方式/状态/可复用要点/落地映射）。

### 4.1 标准流程（持续迭代）
1. 把外部链接登记到 `source_registry.md`（给唯一 ID：S-xxx，并标注类别）。
2. 用 MCP 抓取：优先 `markitdown`；若遇到 JS/反爬再尝试 `playwright`；失败则标注 blocked（403/robot/js-required/406/460）。
3. 只沉淀“可复用要点”（概念、风险、关键参数/变量、适用边界），避免粘贴整篇原文。
4. 将已验证要点回灌到对应设计文档/策略基底文档，并在 `project_docs/freqai_core_strategy_guide.md` 挂入口。

## 5) 已抓取来源（按类别，详情以登记表为准）
> 完整列表与抓取状态以 `project_docs/knowledge/source_registry.md` 为准。

### A) 网格 / 均值回归（震荡赛道）
- S-001 TradingView（Mean Reverse Grid Algorithm）：ok；invite-only（源码不可见）；分层网格/分批建仓/逐层止盈思想。
- S-002 Cryptohopper（What is Grid Trading?）：ok；区间适配性与趋势风险提示。
- S-003 QuantifiedStrategies：blocked（robot）。
- S-004 Antier Solutions：ok；落地重点在参数/风控/执行与回测验证。
- S-005 WunderTrading：blocked（403）。

### B) 套利（低风险收益赛道，偏工程/执行）
- S-101 Gemini：ok；套利类型与主要风险（延迟/滑点/费用/提现/规则）。
- S-102 Crypto.com：ok；套利成本核算与自动化工具要点。
- S-103 Highstrike：blocked（403）。
- S-104 CoinMarketCap（DeFi Arbitrage）：ok；DeFi 套利类型拆分与合约/Gas/价格风险。
- S-105 TastyCrypto：blocked（403）。
- S-106 Quidax：blocked（403）。

### C) 期货交易系统 / 风控（通用参考）
- S-201 Bitunix：ok；系统化流程（设计→验证→优化→风控），强调杠杆/保证金/止损纪律。
- S-202 MetroTrade：blocked（403）。

### D) 机构视角 / 基金策略框架（宏观与工程参考）
- S-301 CryptoResearchReport：ok；体制识别 + 对冲工具 + 执行风险。
- S-302 XBTO：ok；主动管理与“利用错定价”的工具箱（均值回归/统计套利等）。

### E) 学术 / 研究（方法论与市场结构）
- S-401 arXiv 2212.06888：ok；永续合约/资金费率机制与无套利定价边界。
- S-402 arXiv 2102.04591：ok；强平/杠杆/最优保证金，尾部风险主导“生存性”。
- S-403 arXiv 2210.00883：ok；方向预测提升有限，更适合做门控/过滤。
- S-404 arXiv 2101.01261：ok；对冲需同时最小化方差与强平概率。
- S-405 arXiv 2201.12893：ok；估值/体制参考（不宜当短线入场信号）。
- S-406 VilniusTech 2025：ok；策略综述与风控重要性（偏框架）。
- S-407 Notas Económicas（因子模型）：ok；提示“市场结构因子”对横截面解释的重要性。
- S-408 MDPI 1551：blocked（不稳定/超时）。
- S-409 MDPI 278：blocked（403）。
- S-410 IJIRIS：blocked（邮箱墙）。

### F) 框架 / 参数文档（Freqtrade/FreqAI/LightGBM）
- S-501 Freqtrade：FreqAI Introduction：ok；框架定位与常见坑（动态 pairlist 不兼容）。
- S-502 Freqtrade：FreqAI Configuration：ok；分类器需设置 `self.freqai.class_names`，保证推理概率列稳定。
- S-503 Freqtrade：FreqAI Parameter Table：ok；freqai 配置字段权威口径（train/backtest 窗口、feature/model 参数树）。
- S-504 Freqtrade：Running FreqAI：ok；滚动训练机制与 Hyperopt 重点（阈值/门控优先）。
- S-505 LightGBM：Parameters：ok；`is_unbalance`/`scale_pos_weight` 二选一，且会影响概率估计质量。

### G) Triple Barrier / Meta-Labeling（方法论与开源实现）
- S-601 mlfinpy：Labelling：ok；分类优先、TB+Meta-Labeling、Trend Scanning（可做体制与样本权重）。
- S-602 GitHub triple_barrier：ok；交易级 TB 标注范式（入场事件列 + O/H/L/C + TP/SL/时间障碍）。
- S-603 Hudson & Thames：Meta-Labeling：blocked（406）。

### H) 性能 / 向量化（实现策略的工程约束）
- S-701 Python⇒Speed：Pandas vectorization：ok；向量化可能更慢/更耗内存，必须测量。
- S-702 Investopedia：Trailing Stop/Stop-Loss Combo：blocked（460）。

### I) 模型实践参考（可借鉴但不直接复用）
- S-801 GitHub freqAI-LSTM：ok；阈值 + 加权聚合评分 + 控制信号稀疏度（结果样本期短，注意过拟合）。

## 6) 可复用结论（直接指导策略/配置）

### 6.1 目标类型：优先分类，避免“回归目标喂给分类器”
- 研究与开源实现一致强调：金融短周期回归（连续收益）难度更高，分类（离散标签）更现实（S-601）。
- FreqAI 分类器实践要点：在 `set_freqai_targets()` 设置 `self.freqai.class_names`，并保持标签/类名稳定（S-502）。

### 6.2 目标与执行一致：TB 标签必须与实盘生命周期同口径
- 训练标签如果只看固定 horizon 收盘涨跌，会与“路径依赖止损/止盈”产生错位；TB/Meta-Labeling 的价值在于把执行约束提前写入标签（S-601/S-602）。
- 本仓库策略文档已明确：入场/出场应对齐同一个 `label_period_candles` 与同一套 barrier 口径（见 `project_docs/design/freqai_cta_trend_v3.md`）。

### 6.3 样本不平衡：先解决“标签稀缺 → 过度保守”
- LightGBM 的不平衡处理二选一：`is_unbalance` 或 `scale_pos_weight`（S-505）。
- 文档提醒：不平衡权重会影响概率估计质量；因此在策略层应把概率更多当作“排序/优势”而非绝对校准值，并用 `enter_prob + prob_margin` 结构降低抖动（见 `project_docs/design/freqai_cta_trend_v3.md`）。

### 6.4 性能重构：避免“为了向量化而向量化”
- 未来窗口矩阵（N×L）会显著放大内存；向量化未必更快，必须以 profiling 为准（S-701）。
- 更优方向：半向量化/分块计算/只对事件点计算（事件驱动标签），减少不必要的扫描（S-602）。

### 6.5 超参优化：优先阈值/门控，而非特征/目标
- Freqtrade 官方建议：Hyperopt 重点放在入场/出场阈值与门控条件，不要在 `feature_engineering_*()` 与 `set_freqai_targets()` 内做超参搜索（S-504）。

## 7) 已回灌位置（入口一致）
- 赛道总览：`project_docs/design/crypto_futures_strategy_options.md`。
- 策略唯一入口索引：`project_docs/freqai_core_strategy_guide.md`。
- 知识索引/来源登记：`project_docs/knowledge/index.md` / `project_docs/knowledge/source_registry.md`。
