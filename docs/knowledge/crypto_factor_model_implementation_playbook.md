# 加密货币因子模型：实现细节、框架集成与落地指导（本仓库版）

更新日期：2026-01-15

本文目标：

1. 把 C-5（MKT/SMB/VAL/NET/MOM）与隐层/动态框架（IPCA、隐层因子控制）的“论文定义”翻译成可复现的**构建步骤与口径约束**。
2. 解释为什么“横截面因子模型”不应该直接塞进 Freqtrade 单币策略里，并给出本仓库的**正确集成路径**（研究层 → 产出 → 执行层）。
3. 给出落地闭环：数据 → 因子构建 → 体检 → 成本敏感评估 → 输出到策略/风控。

> 重要提醒：  
> - 本仓库当前特征工程默认 **OHLCV-only**（见 `04_shared/config/factors.yaml` 与 `03_integration/trading_system/infrastructure/ml/features.py`），不做跨品种横截面排名、也不引入链上/市值等外部数据。  
> - SMB/NET 等“正宗横截面因子”必须引入外部数据（P2）；在只用 OHLCV 的约束下，最多只能做弱代理（语义相近但不等价）。
> - 本项目当前主线为**单交易对时间序列预测/择时**；横截面多币分组与 long-short 因子构建暂不作为研究/落地目标。

---

## 0) 一句话结论

对本仓库而言，“因子模型”更适合作为**风险语义与特征候选池**：主线先把**单交易对时间序列预测/择时**做扎实（研究层体检 → 输出 policy → 执行层消费）；横截面因子构建细节仅作为背景知识，未来若引入 P2 外部数据再讨论复现。

---

## 1) 本项目主线：单交易对时间序列如何使用“因子语义”

因为本项目暂不做横截面轮动（多币分组/long-short 组合），更实用的做法是把因子语义映射成“单币可计算的时间序列特征”，并用本仓库既有管线做体检与落地：

- MOM（动量）→ 单币趋势/动量特征：`ret_*`、`ema_spread`、`macd*`、`roc_*`（候选池见 `04_shared/config/factors.yaml`）。
- ILLIQ（流动性）→ 成交量/冲击 proxy：`volume_z_*`、`volume_ratio`、`hl_range`（波动与流动性耦合时用于风险预算更稳健）。
- VAL（价值/便宜）→ 更像“慢变量”：长窗口回撤/收益/均值回归强度的 proxy（建议只做解释与风险预算，不做硬开关）。
- SMB（规模）/ NET（网络采用）→ 需要外部数据（市值/链上）。在 OHLCV-only 约束下暂不做“正宗复现”。

落地闭环（推荐先走本仓库已验证路径）：

1. 研究层体检（单币择时）：`scripts/qlib/timing_audit.py`（筛特征、看滚动稳定性、成本后收益）。
2. 训练与导出：`scripts/qlib/train_model.py` + `scripts/qlib/export_timing_policy.py`（把研究结论固化为可执行 policy）。
3. 执行层消费：策略/执行器读取 `04_shared/config/*.yaml`，把预测输出映射为入场门控/仓位折扣（软缩放），避免“硬方向开关”。

---

## 2) 横截面因子构建细节（背景，不作为当前主线）

以下定义均在“横截面因子收益（factor return）”语境下：在每个再平衡时点，对全币池排序分组，构造 long-short 组合的收益序列。

### 2.1 SMB（规模因子：小市值 - 大市值）

定义：小市值币组合收益减去大市值币组合收益（通常等权分组，避免被大币主导）[1]。

构建步骤（建议周频或月频再平衡）：

1. 市值口径：`market_cap = price * circulating_supply`（注意“流通量”口径与数据源版本治理）。
2. 横截面分组：常见 5 分位（Q1 最小 → Q5 最大），或简化为底部 50% vs 顶部 50%。
3. 组合收益：组内通常等权（也可做流动性约束后的风险平价，但要写死规则）。
4. 因子收益：`SMB_t = R_small_t - R_large_t`。
5. 成本处理（必须显式）：手续费/点差/冲击成本 + 做空融资/借币成本会显著侵蚀 long-short 因子收益（尤其是小币与做空腿）[2]。

工程提醒（落地常见坑）：

- 组内最小资产数：建议为每组至少 20 个，否则统计不稳且容易被极少数币驱动。
- “市值”与“可交易容量”不是一回事：许多小币市值小但深度更差，冲击成本会让因子不可执行。

### 2.2 VAL（价值因子：便宜 - 昂贵）

加密缺少统一的“账面价值”，常见替代做法是用长周期回撤/收益做代理，例如 52 周收益（Ret52W）[1][2]。

构建步骤（示例口径）：

1. 指标：`ret_52w = price_now / price_52w_ago - 1`。
2. 排序：按 ret_52w 升序（更低的过去收益被视为“更便宜”）。
3. 分组：Q1（最便宜）vs Q5（最贵），等权计算组收益。
4. 因子收益：`VAL_t = R_Q1_t - R_Q5_t`。

工程提醒：

- VAL 很容易与“均值回归/反转”混淆：它是横截面定价语境下的慢变量，不建议直接用作短周期信号开关。
- 若要引入链上代理（例如市值/日活跃地址），必须先完成链上数据对齐与缺失治理（P2）。

### 2.3 MOM（动量因子：赢家 - 输家）

定义：短期赢家组合收益减去输家组合收益（横截面）[2]。

构建要点：

1. 回看期：常见 2 周（10 个交易日）或 4 周；实践中会加入“skip window”（例如跳过最近 3 天）以降低短期反转噪声 [2]。
2. 排序：按过去窗口收益排序，Q5（赢家）vs Q1（输家）。
3. 因子收益：`MOM_t = R_winner_t - R_loser_t`。

工程提醒：

- 横截面 MOM ≠ 单币趋势：本仓库的 `ret_* / ema_spread / macd` 等更像“时间序列动量”，与赢家-输家口径不同（不要混用评估指标）。
- 论文常报告“大币正动量、小币反向”的异质性结论，但落地必须用你的币池/窗口复核 [2]。

### 2.4 NET（网络采用因子：高增长 - 低增长）

定义：网络采用指标增长更快的币，未来收益更高（加密原生因子）[2]。

常见指标（示例）：

- 具有余额的地址数增长、活跃地址增长、交易数增长等（具体口径强依赖数据源）。

构建步骤（示例口径）：

1. 获取链上指标序列（外部数据，P2）。
2. 计算增长率（例如同比/52 周对比）。
3. 横截面排序分组：Q5（高增长）vs Q1（低增长）。
4. 因子收益：`NET_t = R_high_growth_t - R_low_growth_t`。

工程提醒：

- 新币/上线未满一年：同比指标不可用，需要单独处理（过滤或改用更短窗口）。
- 链上数据字段会变更、缺失会频繁出现：必须做版本治理与“缺失/漂移 → 动作”的闭环，否则无法审计。

---

## 3) 隐层/动态因子模型的实现机制（研究口径）

### 3.1 IPCA（动态因子载荷）

核心思想：允许资产的因子暴露（β）随时间与特征变化，而不是固定常数；更适合制度切换快的市场 [3][4]。

工程化理解（落地时你真正要解决的问题）：

- 输入不仅是收益矩阵 `R_{i,t}`，还需要“资产特征矩阵” `Z_{i,t}`（例如流动性、规模、波动、反转等）。
- 关键难点是：特征口径一致、缺失治理、样本外评估，以及成本/做空约束。

### 3.2 隐层因子控制（三步法思路）

三步法/隐层因子控制的常见用途是：降低遗漏变量偏误，让风险溢价估计更稳健 [5]。

工程提醒：

- 这类方法更偏“解释与估计”而非“直接可执行策略”；落地时应该把它当作风险语义/稳健性校验，而不是直接驱动高频轮动。

---

## 4) 如何在本仓库落地：Qlib（研究）→ 输出 → Freqtrade（执行）

### 4.1 现状约束（必须先认清）

本仓库当前特征工程与体检脚本的设计取舍是：

- 特征 SSOT：`04_shared/config/factors.yaml` 声明因子名集合；实现集中在 `03_integration/trading_system/infrastructure/factor_engines/`。
- 特征仅依赖 OHLCV：`03_integration/trading_system/infrastructure/ml/features.py` 会拒绝不受支持的列（例如 market_cap、active_addresses）。

因此：

- 你现在就能做：用 OHLCV 特征做横截面排序体检（例如把 `ret_12 / vol_12 / volume_z_72` 当作因子候选），并做成本敏感评估（`scripts/qlib/factor_audit.py`）。
- 你暂时做不了：在不引入外部数据的前提下“正宗复现 SMB/NET”。

### 4.2 研究层（Qlib 风格）推荐路径

建议用本仓库已有入口完成闭环：

1. 下载数据：用 `./scripts/data/download.ps1`（避免自行用 ccxt 造数据口径）。
2. 转换到研究数据：`scripts/qlib/convert_freqtrade_to_qlib.py` → `02_qlib_research/qlib_data/.../*.pkl`。
3. 因子体检（横截面排序 + 成本后评估）：`scripts/qlib/factor_audit.py`。
4. 择时体检（单币）：`scripts/qlib/timing_audit.py`。
5. 产出策略可消费的“policy”（例如择时执行器 YAML）：`scripts/qlib/export_timing_policy.py`（同类模式也适用于“因子策略权重/币池输出”）。

> 说明：本仓库引入 Qlib（pyqlib）主要用于研究层数据组织与训练接口；因子计算仍以本仓库的 factor_engine 为准，避免形成第二套特征口径。
> 若你希望了解 Qlib 原生 workflow 与因子/表达式系统的设计，可参考 Qlib 文档 [7][8]（本仓库不直接复用其表达式系统）。

### 4.3 执行层（Freqtrade）正确集成方式

不要把“跨币横截面排序”硬塞进 `populate_indicators()`：Freqtrade 策略的 dataframe 天然是“单交易对视角”，跨币协同不仅难做，还很容易在回测/实盘出现口径漂移。

本仓库更推荐的集成方式：

1. 在研究层生成“每日/每周 policy”（币池、权重、风控开关、禁新开窗口等），落到 `04_shared/config/`。
2. 策略侧通过 `03_integration/trading_system` 读取 policy，并映射为：
   - 入场门控（Gate）
   - 仓位/杠杆缩放（Soft risk scaling）
   - 极端情况禁新开（Hard stop / risk-off）

执行命令（本仓库强制入口）：

- 回测与运行必须通过 `./scripts/ft.ps1`，不要直接运行 `freqtrade`（避免生成意外 user_data 目录、避免编码问题），详见 `README.md` 与 `AGENTS.md`。
- 如需参考 Freqtrade 回测/策略接口的官方说明，见 [6]。

---

## 5) 选择建议：什么时候用因子模型，什么时候别用

更适合因子模型的场景：

- 你有一个相对稳定的 universe（Top N 流动性/市值），并且能治理外部数据（市值/链上/币龄）。
- 你愿意把交易成本与可执行性作为硬约束，而不是只看论文的 R²/Sharpe。

不适合强上因子模型的场景：

- 你只有单币/少币执行需求，且只拥有 OHLCV；此时更稳健的做法是做“时间序列择时 + 风险闭环”（见风险因子地图与择时体检管线）。

---

## 6) 参考入口与来源

知识库入口：

- 风险因子工程化地图（P0→P2）：`docs/knowledge/crypto_risk_factors_engineering_playbook.md`
- 五因子/IPCA/Trend 落地边界：`docs/knowledge/crypto_pricing_five_factor_models_playbook.md`
- 因子模型生态与指标口径：`docs/knowledge/crypto_factor_model_ecosystem_survey.md`
- 价格预测模型工程验收：`docs/knowledge/crypto_price_forecasting_models_playbook.md`

来源（已登记到 `docs/knowledge/source_registry.md`）：

- [1] https://www.artemisanalytics.com/resources/crypto-factor-model-analysis（S-1010）
- [2] https://abfer.org/media/abfer-events-2022/annual-conference/slides-investfin/Lin-William-CONG-presentation.pdf（S-994）
- [3] http://wp.lancs.ac.uk/fofi2022/files/2022/08/FoFI-2022-056-Daniele-Bianchi.pdf（S-995）
- [4] https://www.snb.ch/dam/jcr:cd47611a-4261-4e74-bd69-061ab54433ce/sem_2023_05_26_bianchi.n.pdf（S-998）
- [5] https://arxiv.org/pdf/2601.07664.pdf（S-1002）
- [6] https://www.freqtrade.io/en/stable/backtesting/（S-917）
- [7] https://qlib.readthedocs.io/_/downloads/en/v0.5.0/pdf/（S-1011）
- [8] https://qlib.readthedocs.io/en/stable/advanced/alpha.html（S-1012）
