# 业界成熟做法的正确性与支撑：本项目对标与证据链

更新日期：2026-01-14

本文回答两个问题：

1. 为什么“因子/特征中心化 + 离线/在线一致 + 硬过滤+软过滤 + 组件化 + 流水线与可追溯”是业界成熟做法？
2. 本仓库是否真的按这些做法落地了？落地在哪里？如何验收？

> 结论先行：这些原则在 **MLOps** 与 **量化交易系统工程化** 中属于高共识做法。  
> 本仓库选择“**轻量但可扩展**”的落地方式：优先把 **口径与复用** 做成单一来源（SSOT），并通过脚本/清单/测试把链路固定下来，避免“写很多策略但每个都在重复造轮子”。

---

## 1) 因子/特征中心化（SSOT）的正确性

### 1.1 业界为什么要中心化

核心原因不是“好看”，而是**成本与风险最小化**：

- **避免重复造轮子**：同一特征被不同人/不同策略重复实现，后期维护成本指数增长。
- **避免口径漂移**：同名因子在不同地方计算细节不同，训练与实盘看似同列名但实际含义已变。
- **更容易协作与审计**：当结果变差时，能快速定位“因子定义变了/输入变了/实现变了”。

### 1.2 本仓库怎么落地（映射）

- 因子集声明（单一来源）：`04_shared/config/factors.yaml`
  - `factor_sets.<name>` 定义“需要哪些因子”，支持 `@` 复用（例如 `cta_core`）。
- 因子计算实现（单一来源）：`03_integration/trading_system/infrastructure/factor_engines/`
  - 当前默认引擎：`talib_engine.py`
- 因子集装配/校验入口：`03_integration/trading_system/application/factor_usecase.py`
- 因子集选择（策略/训练复用）：`03_integration/trading_system/application/factor_sets.py`

### 1.3 如何验收（最小）

- 单测：`uv run python -X utf8 -m unittest -q`（覆盖 factor_sets 与 features 相关测试）
- 策略识别：`./scripts/ft.ps1 list-strategies --config "01_freqtrade/config.json"`

---

## 2) 离线/在线一致性（Offline-Online Parity）

### 2.1 业界为什么强调一致性

生产系统里最常见、最隐蔽的失败模式之一：**训练效果很好，上线后效果大幅下降**。  
原因往往不是模型本身，而是“训练用的特征”与“上线实时计算的特征”并不一致（口径/对齐/缺失值处理/窗口边界/数据泄漏等）。

### 2.2 本仓库怎么落地（映射）

关键策略：**训练与预测使用同一条特征链路**（同一份实现、同一组列名）。

- 统一特征工程（训练/预测共用）：`03_integration/trading_system/infrastructure/ml/features.py`
  - 默认特征集：`ml_core`（在 `04_shared/config/factors.yaml` 声明）
- 模型训练导出：`scripts/qlib/train_model.py`
  - 导出 `model.pkl` + `features.json` + `model_info.json`，固定“模型需要哪些列”
- 数据集转换：`scripts/qlib/convert_freqtrade_to_qlib.py`
  - 将 Freqtrade 数据转换为研究层可训练格式，并生成 manifest（可追溯）

### 2.3 如何验收（关键点）

- 看 `features.json`：模型训练时使用的列集合应来自 `ml_core`，且与在线计算一致。
- 对齐检查：在策略启用模型过滤时，若缺列/列名变化，应显式报错或按配置 fail-open（本仓库默认 fail-open，避免因模型缺失阻断交易）。

---

## 3) “硬过滤 + 软过滤”的组合（风控红线 + 连续缩放）

### 3.1 业界为什么用组合

- **硬过滤（Hard Filter）**：风控红线 / 保险丝  
  典型如：最大回撤保护、仓位/杠杆上限、极端波动不交易、流动性不足不交易。  
  目标是“宁可少赚，也不踩雷”。

- **软过滤（Soft Filter / Soft Scaling）**：强度映射 / 风险折扣  
  不直接否决交易，而是把“风险/信号强度”映射到仓位/杠杆等连续变量：  
  目标是“在可交易集合里做连续优化”，提升风险调整后收益与稳定性。

组合的合理性在于：**先保证不做明显错误的交易（硬），再在剩余空间做平滑优化（软）**。

### 3.2 本仓库怎么落地（映射）

- 软缩放/硬阈值工具：`03_integration/trading_system/application/risk_scaling.py`
- 入场门控（布尔 gate）：`03_integration/trading_system/application/entry_gates.py`
- 信号算子（cross/reentry 等事件）：`03_integration/trading_system/application/signal_ops.py`
- 可观测性（漏斗统计）：`03_integration/trading_system/application/gate_pipeline.py`
  - 策略侧可通过 `buy_debug_gate_stats` 输出漏斗摘要并缓存 `_gate_funnel_cache`

### 3.3 如何验收（调参/消融友好）

- 打开 `buy_debug_gate_stats`，观察“最终存活率 + top bottlenecks”
- 做因子消融（建议按清单）：`docs/knowledge/factor_ablation_checklist_smallaccount_futures.md`

---

## 4) 策略组件化（Signal / Risk / Execution / Monitoring）

### 4.1 业界为什么组件化

量化系统的复杂度主要来自“变化频繁”，而不是“单个策略逻辑复杂”。  
组件化的目标是把变化拆开：

- 信号怎么来（Signal）
- 风险怎么控（Risk）
- 订单怎么下（Execution）
- 怎么观测与复盘（Monitoring）

当你想替换其中一块（比如风险门控或因子实现）时，不应该被迫重写整个策略。

### 4.2 本仓库怎么落地（映射）

本仓库采用接近 DDD 的分层（domain/application/infrastructure），并让策略文件更像“装配层”：

- domain（接口/领域对象）：`03_integration/trading_system/domain/`
- application（用例/编排）：`03_integration/trading_system/application/`
- infrastructure（具体实现）：`03_integration/trading_system/infrastructure/`

策略侧主要做两件事：

1) 声明需要哪些因子/门控/参数  
2) 调用集成层用例完成计算与门控，避免策略内重复实现

---

## 5) 流水线化与可追溯（Pipeline + Manifest + 版本锁定）

### 5.1 业界为什么强调可追溯

当你问“为什么这次表现变差”，你真正需要的是一条可追溯链路：

- 用了哪份数据？哪个时间范围？
- 用了哪些特征/因子定义？代码版本是什么？
- 用了哪个模型？训练参数是什么？
- 当时的环境依赖版本是什么？

没有这些，复盘会变成“猜”，团队协作会变成“口口相传”。

### 5.2 本仓库怎么落地（映射）

- 依赖锁定：`uv.lock`（配合 `uv sync --frozen`）
- 一键流水线：`scripts/qlib/pipeline.ps1`
- 研究数据 manifest：`02_qlib_research/qlib_data/<exchange>/<timeframe>/manifest.json`
- vbrain 控制平面 manifest：`docs/tools/vbrain/manifest.json`

---

## 6) 你如何判断“我们做对了”（建议验收顺序）

1) 环境一致性：`uv sync --frozen`
2) 策略入口一致：`./scripts/ft.ps1 list-strategies --config "01_freqtrade/config.json"`
3) 单测锁口径：`uv run python -X utf8 -m unittest -q`
4) vbrain 状态（可选）：`python -X utf8 scripts/tools/vbrain.py status`
5) 回测/训练链路（按需）：`./scripts/analysis/*`、`./scripts/qlib/pipeline.ps1`

---

## 7) 进一步“更像业界”的增强（可选，不是必须）

如果你后续希望更接近“Feature Store”的体验，可以考虑逐步增强（按收益/复杂度排序）：

1. 为 `factors.yaml` 补充元数据（描述/用途/输入依赖/owner/标签），并在工具层导出为文档索引。
2. 为关键因子与门控增加更细粒度的单测（窗口边界、缺失值、极端值）。
3. 引入更强的可观测性（例如把 gate 漏斗统计写入回测报告产物，便于横向对比）。

---

## 附录：用户草稿（外部引用链接清单）

说明：以下链接为“外部参考线索”，**未逐条核验可用性与相关性**。  
若你希望将其纳入本仓库的可追溯体系，建议逐条登记到 `docs/knowledge/source_registry.md` 并分配 `S-xxx`。

原始草稿与链接清单已归档在：

- `docs/knowledge/cache/industry_best_practices_support_analysis_draft.md`

---

## 8) 进阶方向（在行业标准之上继续提升）

如果你希望把系统从“标准答案”继续升级到“制度自适应 + 漂移监控 + 更强治理”的层级，见：

- `docs/knowledge/industry_best_practices_improvement_space.md`
