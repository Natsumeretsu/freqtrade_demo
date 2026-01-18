# 文档归档指南

更新日期：2026-01-17

## 1. 归档原则

**何时归档**：
- 评估报告：完成后 3 个月未更新
- 研究笔记：提炼完成并移到 knowledge/ 后
- 技术报告：内容已过时或被新报告替代
- 变更摘要：完成后 6 个月

**归档位置**：
- 评估报告 → `archive/evaluation/`
- 研究笔记 → `archive/research/`
- 技术报告 → `archive/reports/`

---

## 2. 归档流程

### 2.1 手动归档

**步骤**：
1. 确认文档已过时或完成提炼
2. 移动文件到对应归档目录
3. 更新索引文件（如 knowledge/index.md）

**示例**：
```bash
# 归档评估报告
mv docs/evaluation/old_report.md docs/archive/evaluation/

# 归档研究笔记
mv docs/research/old_research.md docs/archive/research/
```

### 2.2 定期审查

**频率**：每月第一周

**检查清单**：
- [ ] 检查 evaluation/ 目录，归档 3 个月未更新的文件
- [ ] 检查 research/ 目录，归档已提炼完成的文件
- [ ] 检查 reports/ 目录，归档 6 个月前的变更摘要
- [ ] 更新相关索引文件

---

## 3. 归档后处理

**保持可追溯**：
- 归档文件保持原文件名
- 在原目录的索引中添加归档说明
- 必要时在归档文件开头添加归档日期

**示例**：
```markdown
> **归档说明**：本文档已于 2026-01-17 归档，内容可能已过时。
```

---

## 4. 不归档的文档

**永久保留**：
- 规范与指南（guidelines/）
- 知识库核心文档（knowledge/）
- 索引文件（index.md、source_registry.md）
- 最新的技术报告和评估报告

---

## 5. 归档目录结构

```
docs/archive/
├── evaluation/      # 归档的评估报告
├── research/        # 归档的研究笔记
├── reports/         # 归档的技术报告
└── strategies_ref_docs/  # Git 子模块（Freqtrade 策略参考）
```
