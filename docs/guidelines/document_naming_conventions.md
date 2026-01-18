# 文档命名规范

更新日期：2026-01-17

## 1. 通用规则

**基本原则**：
- 使用英文小写字母
- 单词间使用下划线 `_` 分隔
- 避免使用特殊字符（如 `?`、`!`、空格等）
- 文件名应简洁明了，能够反映内容主题

**日期格式**：
- 使用 ISO 8601 格式：`YYYY-MM-DD`
- 示例：`2026-01-17`

---

## 2. 各目录命名规范

### 2.1 evaluation/ (评估报告)

**格式**：`<主题>_<日期>.md`

**示例**：
- `factor_quality_analysis_2026-01-16.md`
- `strategy_optimization_verification_report_2026-01-16.md`
- `parameter_optimization_comparison_2026-01-16.md`

### 2.2 research/ (研究笔记)

**格式**：`<主题>_research.md` 或 `<主题>_research_<日期>.md`

**示例**：
- `qlib_freqtrade_factors_research.md`
- `industry_factor_strategy_separation_research.md`
- `cta_factors_series_crypto_research.md`

### 2.3 reports/ (技术报告)

**格式**：`<类型>_<主题>_<日期>_<版本>.md`

**类型**：
- `change_summary` - 变更摘要
- `plan` - 计划文档
- `review` - 审查报告
- `guide` - 指南文档

**示例**：
- `change_summary_2026-01-15.md`
- `tech_debt_review_2026-01-15_v1.0.md`
- `quant_trading_full_stack_guide_2026-01-15_v1.0.md`

### 2.4 knowledge/ (知识库)

**格式**：`<主题>_<子主题>_playbook.md` 或 `<主题>_<子主题>.md`

**示例**：
- `crypto_exchange_strategy_deep_dive.md`
- `crypto_factor_model_implementation_playbook.md`
- `mcp_knowledge_memory_landscape.md`

### 2.5 guidelines/ (规范指南)

**格式**：`<主题>_<类型>.md`

**类型**：
- `standard` - 标准
- `policy` - 政策
- `guide` - 指南

**示例**：
- `backtest_reporting_standard.md`
- `refactor_policy.md`
- `archive_policy.md`

---

## 3. 版本号规范

**格式**：`v<major>.<minor>`

**说明**：
- `major`：主版本号（重大变更）
- `minor`：次版本号（小幅更新）

**示例**：
- `v1.0` - 初始版本
- `v1.1` - 小幅更新
- `v2.0` - 重大变更

---

## 4. 特殊情况处理

**多部分文档**：
- 使用 `_part1`、`_part2` 后缀
- 示例：`industry_factor_strategy_separation_research_part2.md`

**临时文档**：
- 使用 `temp_` 前缀
- 完成后应删除或重命名
- 示例：`temp_analysis_draft.md`

**草稿文档**：
- 使用 `draft_` 前缀
- 完成后应删除前缀
- 示例：`draft_new_strategy_proposal.md`

---

## 5. 重命名指南

**何时重命名**：
- 文件名不符合规范
- 文件内容发生重大变更
- 文件用途发生改变

**重命名流程**：
1. 确认新文件名符合规范
2. 检查是否有其他文件引用此文件
3. 更新所有引用
4. 执行重命名操作
5. 提交 Git 变更

**Git 重命名命令**：
```bash
git mv old_name.md new_name.md
```

---

## 6. 检查清单

在创建或重命名文件时，请检查：

- [ ] 文件名使用英文小写字母
- [ ] 单词间使用下划线分隔
- [ ] 包含日期（如适用）
- [ ] 包含版本号（如适用）
- [ ] 文件名简洁明了
- [ ] 符合所在目录的命名规范
- [ ] 无特殊字符（除 `_`、`-`、`.` 外）
