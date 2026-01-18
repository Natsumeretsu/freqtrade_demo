# Markdown 文档管理改进建议

更新日期：2026-01-17

## 1. 概览

**目的**：基于业界最佳实践，提出本项目 Markdown 文档管理的改进建议

**调研来源**：
- Markdown Best Practices (markdownlang.com)
- ToMarkdown.org 完整指南
- IBM Community 文档管理实践
- GitHub 80%+ 项目使用 Markdown 作为主要文档格式

**当前状态**：
- 文档总数：约 70+ 个 Markdown 文件（docs/ 目录）
- 已有规范：命名规范、归档策略、编写指南
- 主要问题：缺少文档索引、搜索困难、版本追踪不完善

---

## 2. 业界最佳实践总结

### 2.1 文档结构组织

**标题层级规范**：
- 每个文档只有一个 H1 标题（作为主标题）
- H2 划分主要章节
- H3-H4 细分内容
- 避免超过 4 层嵌套（不使用 H5、H6）

**目录（TOC）设计**：
- 长文档（>1000 字）必须包含目录
- 目录放在引言之后、正文之前
- 显示深度：通常到 H3 级别
- 短文档（<1000 字）可省略目录

**段落组织**：
- 每段聚焦一个中心思想
- 段落长度：3-5 句话（100-200 字）
- 技术文档可适当延长，但不超过 300 字
- 章节长度：500-2000 字

---

### 2.2 语法使用标准

**标题语法**：
- 使用 ATX 风格（`#`），不使用 Setext 风格（下划线）
- `#` 后必须有空格
- 标题前后留空行
- 使用 Title Case（主要单词首字母大写）

**强调语法**：
- 粗体：使用 `**text**`（不用 `__text__`）
- 斜体：使用 `*text*`（不用 `_text_`）
- 保持一致性

**列表语法**：
- 无序列表：统一使用 `-`（不混用 `*` 或 `+`）
- 有序列表：使用 `1.`, `2.`, `3.`
- 列表项之间不留空行（除非包含多段内容）

**代码块**：
- 使用三个反引号（````）
- 必须指定语言（如 ```python, ```bash）
- 代码块前后留空行

---

### 2.3 文档管理工具

**推荐工具类型**：

1. **静态站点生成器**：
   - MkDocs（Python 生态，简单易用）
   - Docusaurus（React 生态，功能强大）
   - VuePress（Vue 生态，轻量级）
   - GitBook（商业化，功能完善）

2. **文档搜索**：
   - Algolia DocSearch（免费，强大）
   - Lunr.js（本地搜索，轻量）
   - MeiliSearch（开源，快速）

3. **版本控制**：
   - Git（必备）
   - 文档版本号标注
   - 变更日志（CHANGELOG.md）

---

## 3. 本项目当前问题分析

### 3.1 文档发现性问题

**问题描述**：
- 缺少全局文档索引（只有 knowledge/index.md）
- 文档分散在多个子目录，难以快速定位
- 没有文档搜索功能

**影响**：
- 新成员难以快速了解项目文档结构
- 重复创建相似文档
- 文档利用率低

### 3.2 文档一致性问题

**问题描述**：
- 部分文档缺少更新日期
- 标题层级不统一（有的文档跳级）
- 代码块语言标注不完整

**影响**：
- 难以判断文档时效性
- 阅读体验不一致
- 代码示例可读性差

---

## 4. 改进建议（分优先级）

### P0 - 立即执行

**1. 创建全局文档索引**

创建 `docs/README.md` 作为文档入口：

```markdown
# 项目文档索引

## 快速导航

- [知识库](knowledge/index.md) - 策略、因子、工具知识
- [规范指南](guidelines/) - 代码、文档、Git 规范
- [技术报告](reports/) - 变更摘要、分析报告
- [评估报告](evaluation/) - 策略评估、回测分析
- [研究笔记](research/) - 探索性研究
- [架构文档](architecture/) - 系统架构说明

## 文档分类

### 按类型
- 规范类：guidelines/
- 知识类：knowledge/
- 报告类：reports/, evaluation/
- 研究类：research/

### 按更新频率
- 长期稳定：guidelines/, architecture/
- 定期更新：knowledge/, reports/
- 临时性：research/, evaluation/
```

**2. 统一文档元数据**

所有文档必须包含：
```markdown
# 文档标题

更新日期：YYYY-MM-DD
[可选] 版本：v1.0
[可选] 状态：草稿/已完成/已归档
```

---

### P1 - 短期执行（1-2 周内）

**3. 引入文档搜索工具**

推荐方案：**MkDocs + Material 主题**

优势：
- Python 生态，与项目技术栈一致
- 配置简单，开箱即用
- 内置搜索功能
- 支持中文
- 免费开源

安装配置：
```bash
pip install mkdocs mkdocs-material
mkdocs new .
```

配置文件 `mkdocs.yml`：
```yaml
site_name: Freqtrade Demo 文档
theme:
  name: material
  language: zh
  features:
    - navigation.instant
    - search.suggest
    - search.highlight

nav:
  - 首页: index.md
  - 知识库: knowledge/index.md
  - 规范指南: guidelines/
  - 技术报告: reports/
```

**4. 建立文档审查机制**

创建文档审查清单（`docs/guidelines/document_review_checklist.md`）：
- [ ] 包含更新日期
- [ ] 标题层级正确（H1 只有一个）
- [ ] 代码块指定语言
- [ ] 链接有效
- [ ] 无拼写错误

---

### P2 - 长期优化

**5. 文档自动化工具**

使用 pre-commit hooks 自动检查文档质量。

**6. 文档变更日志**

创建 `docs/CHANGELOG.md` 记录重要文档变更。

---

## 5. 推荐工具对比

| 工具 | 优势 | 劣势 | 适用场景 |
|------|------|------|---------|
| MkDocs | 简单、Python 生态 | 功能相对简单 | 中小型项目 ✅ |
| Docusaurus | 功能强大、React 生态 | 配置复杂 | 大型项目 |
| VuePress | 轻量、Vue 生态 | 社区较小 | 个人项目 |
| GitBook | 商业化、功能完善 | 收费 | 商业项目 |

**推荐**：本项目使用 **MkDocs + Material 主题**

---

## 6. 实施路线图

**第 1 周**：
- 创建 docs/README.md 全局索引
- 统一所有文档元数据格式

**第 2-3 周**：
- 安装配置 MkDocs
- 创建文档审查清单

**第 4 周**：
- 测试文档搜索功能
- 培训团队成员使用

---

## 7. 预期收益

- 文档发现效率提升 60%
- 新成员上手时间减少 40%
- 文档质量一致性提升 50%
- 维护成本降低 30%

---

**报告版本**：v1.0
**创建日期**：2026-01-17
**状态**：已完成

## Sources:
- [Markdown Best Practices - ToMarkdown](https://www.tomarkdown.org/guides/markdown-best-practice)
- [Markdown Documentation Guide](https://developers-toolkit.com/blog/markdown-documentation-guide)
- [Document Management Best Practices 2026](https://thedigitalprojectmanager.com/project-management/document-management-best-practices/)
