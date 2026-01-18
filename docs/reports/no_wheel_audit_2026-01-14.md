# 不造轮子审计（2026-01-14）

更新日期：2026-01-14



> **⚠️ 历史文档说明（2026-01-17）**：
> 本文档中提及的 vbrain、vharvest、local_rag、in_memoria 等系统已于 2026-01-17 完全移除。
> 当前项目采用 Docker MCP ToolKit 的 `memory` 工具（知识图谱）+ 实时获取（fetch/playwright/context7/duckduckgo）方案。
> 本文档保留作为历史记录，文中相关内容仅供参考，不再适用于当前架构。


> 能不造轮子就不要造轮子。  
> 能不造轮子就不要造轮子。  
> 能不造轮子就不要造轮子。

本文用于：在“人生苦短，我用 Python”的前提下，尽量把时间花在顶层设计与验证闭环上，而不是重复实现/重复维护。

---

## 1) 已确认的“造轮子/重复实现”点（以及已做的减法）

### 1.1 训练侧概率校准（已减法）

- 位置：`scripts/qlib/train_model.py`
- 原问题：自研 sigmoid 校准逻辑（属于 sklearn 已有成熟能力的重复实现）
- 处理：改用 `sklearn.calibration.CalibratedClassifierCV(method="sigmoid", cv=TimeSeriesSplit, ensemble=False)`  
  - 仍保留 `metrics.base` / `metrics.calibrated` 输出口径，供 `scripts/qlib/ablation.ps1` 汇总使用

### 1.2 横截面 RankIC 计算（已减法）

- 位置：`03_integration/trading_system/application/factor_audit.py`
- 原问题：自研 Spearman RankIC 的逐行向量化实现（本质是相关系数计算的重复实现）
- 处理：改用 Qlib 现成实现 `qlib.contrib.eva.alpha.calc_ic(...).ric`（并保留“每期至少 3 个点才计算”的旧口径）

---

## 2) 仍在违反铁律的疑似点（需要你先确认/帮忙找“不要造轮子”的替代方案）

### 2.1 MCP/JSON-RPC 客户端（✅ 已收口：官方 MCP Python SDK）

现状（已修复）：此前以下脚本内各自实现了 `_LineReader/_mcp_call`（Windows pipe 超时读取、JSON-RPC 2.0 stdio 协议等），属于明显的“重复造轮子 + 重复拷贝”维护风险。

处理：已引入官方 MCP Python SDK（`mcp`），并新增统一封装 `scripts/tools/mcp_stdio_client.py`；下述脚本已迁移，重复协议代码已删除（约 600 行）。

迁移清单（已完成）：

- `scripts/tools/in_memoria_seed_vibe_insights.py`
- `scripts/tools/local_rag_cleanup_ingested_files.py`
- `scripts/tools/local_rag_eval_models.py`
- `scripts/tools/local_rag_ingest_project_docs.py`
- `scripts/tools/local_rag_ingest_sources.py`
- `scripts/tools/source_registry_fetch_sources.py`
- `scripts/tools/source_registry_fetch_sources_playwright.py`
- `scripts/tools/vbrain.py`

更新（2026-01-15）：替代方案与迁移建议已形成完整技术债报告，见：`docs/reports/tech_debt_review_2026-01-15_v1.0.md`。

### 2.2 因子/择时体检指标口径（是否可完全用 Qlib 替代？）

现状：`scripts/qlib/factor_audit.py`、`scripts/qlib/timing_audit.py` 仍包含本仓库自定义的指标口径（成本后收益/换手/滚动稳定性等）。  
Qlib 提供了 IC/RankIC 等基础能力，但是否能覆盖“成本/换手/滚动稳定性”这一整套口径，需要你确认是否有更成熟的库/模块（例如 Qlib 的 report/evaluate/backtest 体系，或其它专用库）。

更新（2026-01-15）：Qlib 迁移覆盖度与建议已落盘，见：`docs/reports/tech_debt_review_2026-01-15_v1.0.md`。

我需要你确认/寻找的“非自研”替代方案需求（若要推进全量替换，可作为验收清单使用）：

- **目标**：给定（factor 值、future return、成本参数、滚动窗口定义），输出：
  - IC/RankIC（按日/按窗口）
  - 分位组合收益（top/bottom/long-short）
  - 换手与成本后收益（明确成本模型）
  - 滚动稳定性摘要（P10/median/max_drawdown 等）
- **约束**：适配本仓库数据口径（OHLCV→pkl），最好能直接吃 pandas 数据。

---

## 3) 建议的“减负清单”（需要你确认后才会做危险操作）

⚠️ 删除目录/文件属于高风险操作，需要你明确确认后我才会执行：

- 根目录的 `strategies_ref_docs/`：这是误创建的独立 clone（不是子模块路径），建议删除以减小仓库体积，只保留 `docs/archive/strategies_ref_docs/` 子模块。
  - 状态：已删除（2026-01-15）
