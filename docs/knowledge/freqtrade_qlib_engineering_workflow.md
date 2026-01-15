# Freqtrade + Qlib 工程化落地（本仓库版）

本文将 `docs/remp_research/Freqtrade + Qlib 工程改造/` 的设计思路，按“**业界常见分层结构**”落地到本仓库：

- `01_freqtrade/`：Freqtrade userdir（策略/配置/数据/回测产物）
- `02_qlib_research/`：研究层（数据集/模型/Notebook）
- `03_integration/`：集成层（研究层 ↔ 策略侧的桥接代码）
- `04_shared/`：共享配置（可提交的 YAML/模板）

如果你关心“为什么这样做是业界成熟方案、以及如何验收做没做对”，建议配套阅读：`docs/knowledge/industry_best_practices_support_analysis.md`。

如果你希望继续走向“制度自适应 + 概念漂移监控”等进阶方向（在行业标准之上继续提升），建议配套阅读：`docs/knowledge/industry_best_practices_improvement_space.md`。

---

## 1) 目录与配置约定

### ✅ 可提交配置（权威）

- `04_shared/config/paths.yaml`：路径约定（Freqtrade 数据根、研究数据根、模型根）
- `04_shared/config/symbols.yaml`：交易对与研究符号映射（注意 futures 的 `:` 必须加引号）
- `04_shared/config/symbols_research_okx_futures_top40.yaml`：研究币池（Top40，偏流动性；不影响默认 symbols.yaml）
- `04_shared/config/factors.yaml`：因子集声明（策略/研究共用，避免重复造轮子）

### ✅ 运行期产物（默认 gitignore，可重建）

- 研究层数据：`02_qlib_research/qlib_data/<exchange>/<timeframe>/<symbol>.pkl`
- 研究层模型：`02_qlib_research/models/qlib/<version>/<exchange>/<timeframe>/<symbol>/`
  - `model.pkl`
  - `features.json`
  - `model_info.json`

### ✅ 代码入口

- 配置加载：`03_integration/trading_system/infrastructure/config_loader.py`
- 因子集（声明式依赖）：`03_integration/trading_system/application/factor_sets.py`
- 因子引擎（实现）：`03_integration/trading_system/infrastructure/factor_engines/talib_engine.py`
- 因子引擎工厂（配置驱动）：`03_integration/trading_system/infrastructure/factor_engines/factory.py`
- 因子编排用例（统一校验/合并）：`03_integration/trading_system/application/factor_usecase.py`
- 入场门控组件（可复用 Gate）：`03_integration/trading_system/application/entry_gates.py`
- 序列信号算子（cross/reentry/bull/bear）：`03_integration/trading_system/application/signal_ops.py`
- Gate 漏斗统计（通过率/卡口贡献）：`03_integration/trading_system/application/gate_pipeline.py`
- 风险缩放工具（硬过滤/软缩放复用）：`03_integration/trading_system/application/risk_scaling.py`
- 模型加载：`03_integration/trading_system/infrastructure/ml/model_loader.py`
- 特征工程：`03_integration/trading_system/infrastructure/ml/features.py`（训练/预测共用）
- Freqtrade 数据适配（含宏观 informative 构造）：`03_integration/trading_system/infrastructure/freqtrade_data.py`
- 交易对映射：`03_integration/trading_system/domain/symbols.py`
- 脚本：
  - `scripts/qlib/convert_freqtrade_to_qlib.py`
  - `scripts/qlib/train_model.py`
  - `scripts/qlib/pipeline.ps1`
  - `scripts/qlib/factor_audit.py`
  - `scripts/qlib/factor_audit.ps1`
  - `scripts/qlib/timing_audit.py`
  - `scripts/qlib/export_timing_policy.py`

---

## 2) 快速上手（PowerShell）

### 2.1 初始化依赖

```powershell
./scripts/bootstrap.ps1
```

### 2.2 将 Freqtrade feather 转为研究层数据集

默认读取 `04_shared/config/symbols.yaml` 的 pairs：

```powershell
uv run python -X utf8 "scripts/qlib/convert_freqtrade_to_qlib.py" --timeframe "4h"
```

输出目录示例：
- `02_qlib_research/qlib_data/okx/4h/manifest.json`
- `02_qlib_research/qlib_data/okx/4h/BTC_USDT.pkl`

### 2.3 训练模型并导出为策略可加载格式

```powershell
uv run python -X utf8 "scripts/qlib/train_model.py" --pair "BTC/USDT:USDT" --timeframe "4h"
```

默认输出目录示例：
- `02_qlib_research/models/qlib/v1/okx/4h/BTC_USDT/model.pkl`
- `02_qlib_research/models/qlib/v1/okx/4h/BTC_USDT/features.json`
- `02_qlib_research/models/qlib/v1/okx/4h/BTC_USDT/model_info.json`
- `02_qlib_research/models/qlib/v1/okx/4h/BTC_USDT/feature_baseline.json`（训练特征分布基线，用于漂移检测）

> 说明：训练脚本使用真实 Qlib（pyqlib）的 `DatasetH/DataHandler` 组织数据，并通过本仓库的 `FreqtradePklDataLoader` 直接读取 pkl（保持数据口径单一）。  
> 同时会对概率做时间序列校准（TimeSeriesSplit + sigmoid），更适合后续做“连续权重”。

### 2.4 一键流水线（推荐）

把转换 + 逐交易对训练合并为一个动作（默认读取 `04_shared/config/symbols.yaml` 的 pairs）：

```powershell
./scripts/qlib/pipeline.ps1 -Timeframe "4h" -ModelVersion "v2_cal"
```

你也可以用 `-SymbolsYaml` 指定更大的研究币池（转换与训练都会使用同一批 pairs）：

```powershell
./scripts/qlib/pipeline.ps1 -Timeframe "15m" -SymbolsYaml "04_shared/config/symbols_research_okx_futures_top40.yaml" -ModelVersion "v2_cal"
```

如果你希望把“数据下载 → 研究训练 → 因子体检 → 回测报告”也一并收口成**单一入口**，使用：

```powershell
# 先预览将执行的步骤（不真正运行）
./scripts/workflows/quant_e2e.ps1 -All -WhatIf

# 全量闭环（示例：15m 合约择时执行器）
./scripts/workflows/quant_e2e.ps1 -All -Download `
  -TradingMode "futures" `
  -Pairs "BTC/USDT:USDT" `
  -Timeframe "15m" `
  -DownloadDays 120 `
  -BacktestConfig "04_shared/configs/small_account/config_small_futures_timing_15m.json" `
  -Strategy "SmallAccountFuturesTimingExecV1" `
  -BacktestTimerange "20251215-20260114"
```

### 2.4.1 概念漂移体检（推荐）

当你怀疑模型/因子“静默衰减”（制度切换、数据质量变化、特征口径变化）时，建议对比最近窗口特征分布 vs 训练基线：

```powershell
uv run python -X utf8 "scripts/qlib/check_drift.py" --pair "BTC/USDT:USDT" --timeframe "4h" --window 500
```

输出说明（两种口径）：
- `status`：对所有特征取最坏值（更严格，用于排查哪个特征最异常）
- `auto_risk_status`：按 `trading_system.yaml` 的 `gate_features + aggregate` 聚合（更贴近实盘可执行动作）

### 2.4.2 自动降风险闭环（从可观测到可执行）

仅“能看见漂移”还不够，业界更常见的是把漂移/制度映射为可执行动作：**warn 降风险、crit 禁新开**，并把证据落盘，便于复盘与重训决策。

本仓库已提供最小闭环实现：

- 配置入口：`04_shared/config/trading_system.yaml` → `auto_risk`
- 开关覆盖（推荐放到 `.env`，避免改动可提交配置）：
  - `AUTO_RISK_ENABLED=true`
- 触发动作（默认策略侧行为）：
  - drift=`warn`：对新开仓做仓位/杠杆风险折扣（默认 ×0.85）
  - drift=`crit`：禁止新开仓（默认启用）+ 强降风险（默认 ×0.30）
  - market_context：以 BTC 作为市场代理，监控相关性/β 断裂，仅做“软缩放”（不新增禁新开；默认下限 0.85）
  - 恢复滞回：从 `crit` 恢复到允许新开仓，需要连续 `ok` 达到 `recover_ok_checks`（默认 3 次）
- 漂移判定（避免误触的关键）：
  - `drift.gate_features`：仅这些特征参与“整体漂移判定”（其余特征更偏监控/解释）
  - `drift.aggregate`：用“crit/warn 特征数量或占比”聚合整体状态，避免单一噪声特征长期把整体打到 `crit`
  - 推荐校准目标（以 okx/BTC/4h 为例，可用回放自定义你的偏好）：`ok>=50%`、`crit<=5%`、`crit_streak_p95<=6`
- 证据落盘（gitignore，可重建）：`artifacts/auto_risk/*.json`

> 注意：自动闭环只能影响“新开仓”的 stake/leverage，无法改变已开的仓位（交易系统通用限制）。  
> 若模型目录不存在或缺少 `feature_baseline.json`，默认 **fail-open**（不阻断交易，只记录原因）。

### 2.4.3 离线回放评估（阈值校准，推荐）

当你发现 `crit` 触发过多（0 trades / 过度保守）或触发过少（缺少保护）时，建议用离线回放脚本对 `auto_risk` 做“可量化校准”：

```powershell
uv run python -X utf8 "scripts/analysis/auto_risk_replay.py" --pair "BTC/USDT:USDT" --exchange "okx" --timeframe "4h" --start "2022-01-01" --end "2024-01-01"
```

输出要点：
- `drift_rate`：ok/warn/crit 占比（越接近你的风险偏好越好）
- `market_context_rate`：ok/warn/crit 占比 + `mean_scale`（评估相关性/β 断裂触发频率与缩放强度）
- `blocked_entries_rate`：被“禁新开仓”的比例（crit 触发后会变高）
- `crit_streak`：连续 crit 的最大/分位数（用于决定 `recover_ok_checks` 是否需要调整）

脚本会将报告写入 `artifacts/auto_risk_replay/*.json`，并在报告里记录本次使用的 `auto_risk` 配置（含 gate_features/aggregate/thresholds），方便跨设备复现结论。

### 2.5 在策略中启用模型（软过滤 + 硬保险丝）

`01_freqtrade/strategies/SmallAccountFuturesTrendV1.py` 已增加参数：
- `buy_use_qlib_model_filter`（默认 `false`）
- `buy_qlib_soft_scale_enabled`（默认 `true`）
- `buy_qlib_soft_scale_floor`（默认 `0.30`）
- `buy_qlib_proba_threshold`（默认 `0.55`，达到该概率视为满风险，其下线性插值）
- `buy_qlib_hard_fuse_enabled`（默认 `true`）
- `buy_qlib_hard_fuse_min_proba`（默认 `0.45`，模型强烈反向时拒绝入场）
- `buy_qlib_fail_open`（默认 `true`，模型缺失/不可用时不阻断交易）

启用方式示例：编辑 `01_freqtrade/strategies/SmallAccountFuturesTrendV1.json` 的 `params.buy`，将
`buy_use_qlib_model_filter` 设为 `true`。

> 行为解释（业界常见范式）：
> - **软过滤**：不改入场信号，只根据模型概率对仓位/杠杆做风险折扣（默认只作用于仓位）。
> - **硬保险丝**：仅当模型概率明显反向时，拒绝入场，避免逆风硬扛。

### 2.4.2 因子体检（短周期：15m/1h，推荐）

在进入“训练模型/策略重构”前，先用研究层口径对因子做体检：
- RankIC（Spearman）
- 分位组合收益（top/bottom/long-short）
- 成本后收益（按换手 × round-trip 成本的简化口径）
- 30/60 天滚动窗口稳定性（中位数/分位数/最差）

示例（推荐用 Top40 研究币池跑 15m + 1h 两个频率）：

```powershell
./scripts/qlib/factor_audit.ps1 `
  -Timeframes "15m","1h" `
  -SymbolsYaml "04_shared/config/symbols_research_okx_futures_top40.yaml" `
  -FeatureSet "cta_core" `
  -Horizons 1,4 `
  -Fee 0.0006 `
  -RollingDays 30,60
```

若你想体检“某个策略的因子集合”（例如带 EMA 占位符的集合），可以传入策略参数 JSON 让占位符自动填充：

```powershell
./scripts/qlib/factor_audit.ps1 `
  -Timeframes "15m","1h" `
  -SymbolsYaml "04_shared/config/symbols_research_okx_futures_top40.yaml" `
  -FeatureSet "SmallAccountFuturesTrendV1" `
  -StrategyParams "01_freqtrade/strategies/SmallAccountFuturesTrendV1.json"
```

输出目录位于：`artifacts/factor_audit/.../`（`factor_summary.csv` + `summary.md`）。

### 2.4.3 择时体检（单币） + 通用执行器（15m 主信号 + 1h 复核）

你如果更关心“单币择时”而不是“截面选强弱”，推荐使用 `timing_audit`：
- 每个币、每个因子、每个 horizon：自动选方向（pos/neg）
- 每个币、每个因子、每个 horizon：自动选长短腿模式（`side=both/long/short`），避免“长腿赚钱但短腿拖后腿”
- 用滚动分位阈值构造极简择时（多/空/空仓）
- 扣手续费/滑点，输出 30/60 天滚动稳定性
- 强制报告对 BTC 的超额（若基准数据可用）

示例（推荐先用 Top40 研究币池跑 15m + 1h）：

```powershell
uv run python -X utf8 "scripts/qlib/timing_audit.py" `
  --exchange okx `
  --timeframe 15m `
  --symbols-yaml "04_shared/config/symbols_research_okx_futures_top40.yaml" `
  --feature-set timing_pool_v1 `
  --horizons 1 4 `
  --lookback-days 30 `
  --rolling-days 30 60 `
  --fee 0.0006 `
  --export-series

uv run python -X utf8 "scripts/qlib/timing_audit.py" `
  --exchange okx `
  --timeframe 1h `
  --symbols-yaml "04_shared/config/symbols_research_okx_futures_top40.yaml" `
  --feature-set timing_pool_v1 `
  --horizons 1 4 `
  --lookback-days 30 `
  --rolling-days 30 60 `
  --fee 0.0006 `
  --export-series
```

输出目录位于：`artifacts/timing_audit/.../`（`timing_summary.csv` + `summary.md`）。

把 15m（主）与 1h（复核）的结果合成一个“策略可读”的 policy YAML：

```powershell
uv run python -X utf8 "scripts/qlib/export_timing_policy.py" `
  --main-csv "artifacts/timing_audit/<15m_run>/timing_summary.csv" `
  --confirm-csv "artifacts/timing_audit/<1h_run>/timing_summary.csv" `
  --out "04_shared/config/timing_policy_okx_futures_15m_1h.yaml" `
  --topk 3 `
  --allow-watch

> 注意：`export_timing_policy.py` 默认会按择时序列（`pos`）做相关性去冗余（逼近“少数模态张成”）；因此需要上一步 `timing_audit.py` 带 `--export-series` 输出序列文件。若你临时只想复现旧行为，可传 `--dedupe-method none`。
```

### 2.4.4 Koopa-lite（Koopman/本征模态）额外因子：生成 → 体检 → 导出 policy

如果你想把“多尺度/本征模态”的想法落到可执行闭环，推荐先用 `koopman_lite.py` 生成一批额外因子，再交给 `timing_audit.py` 用同口径验收。

1) 生成 Koopa-lite 额外因子（输出为 pkl：每个 pair 一张特征表）：

```powershell
uv run python -X utf8 "scripts/qlib/koopman_lite.py" `
  --exchange okx `
  --timeframe 15m `
  --symbols-yaml "04_shared/config/symbols_research_okx_futures_top40.yaml" `
  --window 512 `
  --embed-dim 16 `
  --stride 10 `
  --pred-horizons 1 4 `
  --fft-window 512 `
  --fft-topk 8
```

2) 只体检这些额外因子（忽略 feature-set）：

```powershell
uv run python -X utf8 "scripts/qlib/timing_audit.py" `
  --exchange okx `
  --timeframe 15m `
  --symbols-yaml "04_shared/config/symbols_research_okx_futures_top40.yaml" `
  --only-extra-factors `
  --extra-features "artifacts/koopman_lite/<run>.pkl" `
  --extra-factors koop_pred_ret_h1 koop_pred_ret_h4 fft_hp_logp `
  --horizons 1 4 `
  --lookback-days 30 `
  --rolling-days 30 60 `
  --fee 0.0006 `
  --export-series
```

3) 与常规流程一致：用 `export_timing_policy.py` 把 `timing_summary.csv` 合成 YAML，再交给执行器策略回测/实盘。

生成的 policy 中，每个因子条目包含：
- `name`：因子名
- `direction`：`pos/neg`（因子值越大/越小越偏多）
- `side`：`both/long/short`（多空都做/只做多/只做空）

然后用通用执行器策略做回测（30/60 天）：

```powershell
./scripts/analysis/small_account_backtest.ps1 `
  -Config "04_shared/configs/small_account/config_small_futures_timing_15m.json" `
  -Strategy "SmallAccountFuturesTimingExecV1" `
  -Pairs "BTC/USDT:USDT" `
  -Timeframe "15m" `
  -TradingMode "futures" `
  -Timerange "20251215-20260114"
```

> 提示：如果你还没下载 15m/1h 的 futures 数据，先跑：  
> `./scripts/data/download.ps1 -Pairs "BTC/USDT:USDT" -Timeframes "15m","1h" -TradingMode "futures" -Days 120`

---

## 3) 路径覆盖（.env）

仓库根目录的 `.env` 会被自动读取（默认 gitignore）。你可以从 `.env.example` 复制生成：

```powershell
Copy-Item ".env.example" ".env"
```

常用覆盖项：
- `FREQTRADE_EXCHANGE`
- `FREQTRADE_DATA_DIR`
- `QLIB_DATA_DIR`
- `QLIB_MODEL_DIR`
- `QLIB_MODEL_VERSION`

---

## 4) 常见问题

1. **转换脚本提示找不到 feather 数据**
   - 检查 `04_shared/config/paths.yaml` 的 `freqtrade.data_root` 与实际数据目录是否一致；
   - 也可以直接传 `--datadir "01_freqtrade/data/okx"` 指向包含 `.feather` 的目录。

2. **启用模型过滤后 0 trades**
   - 先确认模型目录是否存在（`02_qlib_research/models/qlib/...`）；
   - 若开启了硬保险丝：适当降低 `buy_qlib_hard_fuse_min_proba`（例如 0.45 → 0.42）；
   - 若只是交易变少/仓位变小：检查 `buy_qlib_soft_scale_floor` 是否过低。

---

## 5) 因子/特征的“单一来源”（强制约定）

本仓库把“因子”视为策略与研究的共同依赖：**必须只在一个地方定义与实现**，否则会出现口径漂移（同名因子在不同模块计算方式不同）。

约定如下：

- **声明在哪**：`04_shared/config/factors.yaml`（`factor_sets.<name>`）
- **实现在哪**：`03_integration/trading_system/infrastructure/factor_engines/*`（当前默认：`talib_engine.py`）
- **策略怎么用**：策略只负责声明“需要哪些因子”，再用 `get_container().factor_usecase().execute(df, factor_names)` 补齐列
- **训练/预测怎么用**：`03_integration/trading_system/infrastructure/ml/features.py` 也复用同一套因子引擎，默认特征集为 `ml_core`

新增/修改因子的推荐流程：

1. 在 `04_shared/config/factors.yaml` 增加/调整因子名（或模板）
2. 在因子引擎中补齐 `supports()` + `compute()`（必要时增加参数解析）
3. 补一条单测锁住：因子可计算、无 inf、且训练/预测使用同一列名

---

## 6) 门控/风控的“单一来源”（推荐约定）

除了因子口径，策略最容易“悄悄漂移”的另一块是**门控/风控逻辑**（尤其是软缩放的插值公式）。

本仓库推荐把可复用门控沉淀为纯函数，策略只做“装配与参数选择”：

- **软缩放/硬门槛**：统一放在 `03_integration/trading_system/application/risk_scaling.py`
  - 例如：`linear_scale_up/linear_scale_down/step_min/step_max/macro_sma_soft_scale`
- **入场门控（布尔 Gate）**：统一放在 `03_integration/trading_system/application/entry_gates.py`
  - 例如：`macro_sma_regime_ok/atr_pct_range_ok/ema_trend_ok/volume_ratio_min_ok`
- **交叉/再入等事件算子**：统一放在 `03_integration/trading_system/application/signal_ops.py`
  - 例如：`crossed_above/crossed_below/reentry_event/bull_mode/bear_mode`
- **门控漏斗统计（可观测性）**：统一放在 `03_integration/trading_system/application/gate_pipeline.py`
  - 例如：`gate_funnel/top_bottlenecks`（用于定位哪个 gate 最“卡”）
- **宏观 informative 构造**：统一放在 `03_integration/trading_system/infrastructure/freqtrade_data.py`
  - 例如：`build_macro_sma_informative_dataframe`（策略侧仍负责 merge）

### 启用“门控漏斗统计”（用于调参/消融）

两条 SmallAccount 策略都提供了 `buy_debug_gate_stats`（默认关闭）：

- 打开后，会在首次计算时输出一条“漏斗摘要”（final 存活率 + top bottlenecks）。
- 同时把完整漏斗结果缓存到 `self._gate_funnel_cache[(pair, side)]`（futures 包含 `long/short`，spot 只有 `long`），便于你在调试器里做更深的归因分析。

这样做的好处：

1. 两条策略用同一套公式，避免“看起来一样但细节不同”的隐性 bug  
2. 单测更容易写：对输入→输出做断言即可，不依赖回测环境  
3. 后续要换实现（例如更复杂的风险模型）时，替换面更小、更可控
