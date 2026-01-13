# Freqtrade + Qlib 工程化落地（本仓库版）

本文将 `docs/remp_research/Freqtrade + Qlib 工程改造/` 的设计思路，按“**业界常见分层结构**”落地到本仓库：

- `01_freqtrade/`：Freqtrade userdir（策略/配置/数据/回测产物）
- `02_qlib_research/`：研究层（数据集/模型/Notebook）
- `03_integration/`：集成层（研究层 ↔ 策略侧的桥接代码）
- `04_shared/`：共享配置（可提交的 YAML/模板）

---

## 1) 目录与配置约定

### ✅ 可提交配置（权威）

- `04_shared/config/paths.yaml`：路径约定（Freqtrade 数据根、研究数据根、模型根）
- `04_shared/config/symbols.yaml`：交易对与研究符号映射（注意 futures 的 `:` 必须加引号）
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

> 说明：训练脚本会对概率做时间序列校准（TimeSeriesSplit + sigmoid），更适合后续做“连续权重”。

### 2.4 一键流水线（推荐）

把转换 + 逐交易对训练合并为一个动作（默认读取 `04_shared/config/symbols.yaml` 的 pairs）：

```powershell
./scripts/qlib/pipeline.ps1 -Timeframe "4h" -ModelVersion "v2_cal"
```

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
