# 变更摘要（2026-01-15）

更新日期：2026-01-15



> **⚠️ 历史文档说明（2026-01-17）**：
> 本文档中提及的 vbrain、vharvest、local_rag、in_memoria 等系统已于 2026-01-17 完全移除。
> 当前项目采用 Docker MCP ToolKit 的 `memory` 工具（知识图谱）+ 实时获取（fetch/playwright/context7/duckduckgo）方案。
> 本文档保留作为历史记录，文中相关内容仅供参考，不再适用于当前架构。


## 背景与目标

- 目标 1：彻底消灭 MCP/JSON-RPC 客户端“重复实现 + 复制粘贴”，把协议与超时等复杂性转交给官方 SDK，降低维护成本。
- 目标 2：把“完整量化交易生态”的顶层地图补齐为可执行、可追溯的仓库文档，避免拍脑袋堆框架。
- 目标 3：把“脚本控制平面”收口到单一入口，让日常闭环（训练/体检/回测）一键可复现。

---

## 关键决策（可追溯）

- **铁律：能不造轮子就不造轮子**：MCP 客户端不再自研协议层，统一使用官方 `mcp` Python SDK，并封装为仓库内可复用薄层。
- **默认轻量闭环**：编排优先“脚本 + 文件落盘”，不默认引入 Dagster/Airflow/TSDB/监控平台；只有在 24/7、多策略、多币种的阶段才升级。
- **危险操作显式触发**：端到端工作流默认不下载数据；需要显式传 `-Download` 才会调用下载脚本，避免误触发大规模网络/数据操作。

---

## 关键变更

- MCP 客户端收口（减少重复造轮子）：
  - 新增 `scripts/tools/mcp_stdio_client.py`：基于官方 `mcp` SDK 的 stdio 客户端封装。
  - `scripts/tools/` 下涉及 MCP 调用的脚本统一迁移至该封装（移除 `_LineReader/_mcp_call` 等重复实现）。

- 生态与选型文档补全（顶层地图 + 可追溯）：
  - 新增 `docs/reports/quant_trading_full_stack_guide_2026-01-15_v1.0.md`：以本仓库真实基座（Freqtrade + Qlib + vbrain）为中心的全栈分层指南。
  - 新增/更新评估报告：`docs/reports/tech_debt_review_2026-01-15_v1.0.md`、`docs/reports/local_vector_db_review_2026-01-15_v1.0.md`、`docs/reports/crypto_trading_framework_review_2026-01-15_v1.0.md`，并互相链接到全栈指南。

- 脚本控制平面收口（单一入口）：
  - 新增 `scripts/workflows/quant_e2e.ps1`：串起“下载（可选）→Qlib 训练→因子体检→基准回测报告”的端到端编排脚本，支持 `-WhatIf` 预览。
  - `README.md` 与 `docs/knowledge/freqtrade_qlib_engineering_workflow.md` 增加该统一入口的使用方式与示例参数。

---

## 复现命令（PowerShell）

- 预览将执行的步骤（不真正运行）：
  - `./scripts/workflows/quant_e2e.ps1 -All -WhatIf`
- 全量闭环（包含下载，示例：15m 合约择时执行器）：
  - `./scripts/workflows/quant_e2e.ps1 -All -Download -TradingMode "futures" -Pairs "BTC/USDT:USDT" -Timeframe "15m" -DownloadDays 120 -BacktestConfig "04_shared/configs/small_account/config_small_futures_timing_15m.json" -Strategy "SmallAccountFuturesTimingExecV1" -BacktestTimerange "20251215-20260114"`

