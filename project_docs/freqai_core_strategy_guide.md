# FreqAI 策略文档索引（唯一入口）

更新日期：2026-01-10

本仓库采用“一类策略一一对应一份唯一基底文档”的规则：

- 每个策略类（`IStrategy` 子类）只允许有 1 份权威指南
- 本文件只做索引，不承载策略细节（避免出现多源冲突）

---

## 策略一一对应文档映射

- `FreqaiMetaLabel`（v1，已被 v2 替代）：`project_docs/design/freqai_meta_label_v1.md`
- `FreqaiMetaLabelV2`：`project_docs/design/freqai_meta_label_v2.md`
- `FreqaiTripleBarrierV2`：`project_docs/design/freqai_triple_barrier_v2.md`
- `FreqaiTripleBarrierV3`：`project_docs/design/freqai_triple_barrier_v3.md`
- `FreqaiCTATrendV3`：`project_docs/design/freqai_cta_trend_v3.md`
- `FreqaiVolatilityGridV1`：`project_docs/design/freqai_volatility_grid_v1.md`

---

## 共用工程约定（全仓库通用）

- 命令统一通过 `./scripts/ft.ps1` 执行（避免生成多余的 `user_data/` 目录）
- 回测结果汇报标准：`project_docs/guidelines/backtest_reporting_standard.md`
- 私密配置 `config*.json` 默认忽略，避免误提交密钥

---

## 文档维护规则（强制）

- 新增一个策略类（新增一个 `IStrategy` 子类） → 必须新增 1 份对应的基底文档，并在本索引登记
- 同一个策略类的调参/修复 → 只更新该策略的基底文档，不在其它文件重复描述

---

## 赛道参考（非策略类文档）

- 加密货币期货三赛道选型（网格 / 均值回归 / 套利）：`project_docs/design/crypto_futures_strategy_options.md`

---

## 知识结构（项目固有知识）

- 项目固有知识索引（含外部来源登记）：`project_docs/knowledge/index.md`
