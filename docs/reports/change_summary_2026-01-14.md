# 变更摘要（2026-01-14）

更新日期：2026-01-14


## 背景与目标

- 目标 1：建立“离线策略参考库”作为策略灵感与对照语料，保证断网也可查阅与全文检索。
- 目标 2：检查研究/训练侧是否存在“造轮子”，并在不破坏执行层（Freqtrade）约束的前提下**拥抱真实 Qlib（pyqlib）**。
- 目标 3：把“设计/架构级变更一次性到位、禁止长期双轨”内化为项目规范，避免半迁移导致不可控复杂度。

---

## 关键决策（可追溯）

- **单一数据口径**：研究数据仍以本仓库 Freqtrade 下载的 OHLCV 为权威来源；研究侧用 pkl 作为中间形态（`02_qlib_research/qlib_data/...`）。
- **Qlib 作为研究框架**：引入 pyqlib 的 `DatasetH/DataHandler` 组织训练数据，但不引入第二套 provider 数据存储，避免“研究/执行口径漂移”。
- **策略参考库采用子模块**：用 git submodule 引入 `docs/archive/strategies_ref_docs/`，保证离线可用且不污染主仓库历史。
- **一次性到位重构规范**：涉及主流程/核心模块切换时，要求同一个变更中完成代码/脚本/配置/文档/测试的全量收口。

---

## 关键变更

- 规范与文档：
  - `AGENTS.md` 增加“架构与重构规范（一次性到位）”。
  - 新增 `docs/guidelines/refactor_policy.md` 作为可执行的重构方法论文档。
  - 新增 `docs/archive/strategies_ref_docs_guide.md`：离线策略参考库的使用指南。
  - `docs/knowledge/freqtrade_qlib_engineering_workflow.md` 补充“真实 Qlib（pyqlib）组织数据”的说明。

- 离线策略参考库：
  - `docs/archive/strategies_ref_docs` 作为子模块（见 `.gitmodules`）。
  - 新增 `scripts/docs/search_strategies_ref_docs.ps1`：统一 UTF-8 输出的搜索封装（优先 rg）。
  - `.gitignore` 忽略根目录误创建的 `strategies_ref_docs/`（避免与子模块路径混淆）。

- 拥抱 Qlib（研究/训练侧）：
  - `pyproject.toml` 增加 `pyqlib>=0.9.0`、`lightgbm>=4.0.0`，并将 `numpy` 限制为 `<2.4.0`（避免 yanked 版本导致锁定不稳定）。
  - 新增 `03_integration/trading_system/infrastructure/qlib/freqtrade_pkl_data_loader.py`：
    - 以 Qlib `DataLoader` 形式直接读取 `02_qlib_research/qlib_data/.../*.pkl`；
    - 特征计算复用 `trading_system.infrastructure.ml.features.compute_features`，保证训练/在线一致；
    - 输出 Qlib 训练可用的 multi-index columns（feature/label）与 index（datetime/instrument）。
  - `scripts/qlib/train_model.py` 重写为真实 Qlib 数据组织方式：
    - `DatasetH + DataHandler + FreqtradePklDataLoader`；
    - LightGBM 二分类训练；
    - 时间序列概率校准（TimeSeriesSplit + sigmoid）并导出可被策略侧加载的 `model.pkl/features.json/model_info.json/feature_baseline.json`。
  - `scripts/qlib/ablation.ps1` 文案更新以反映训练脚本依赖 pyqlib。

---

## 复现命令（PowerShell）

- 初始化依赖：
  - `uv sync --frozen`
- （可选）补齐子模块：
  - `git submodule update --init --recursive`
- 转换研究数据（feather → pkl）：
  - `uv run python -X utf8 "scripts/qlib/convert_freqtrade_to_qlib.py" --timeframe "4h"`
- 训练并导出模型：
  - `uv run python -X utf8 "scripts/qlib/train_model.py" --pair "BTC/USDT:USDT" --timeframe "4h"`

