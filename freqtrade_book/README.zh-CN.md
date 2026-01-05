# Freqtrade 学习手册（本仓库整理版）

这是一套把 `freqtrade_docs/` 参考库“整理成册”的学习手册：按**渐进式学习路线**组织内容，同时提供“随查随用”的参考索引，方便你在写策略/跑回测/做运维时快速定位答案。

## 如何使用

- 想系统学习：按 [目录](SUMMARY.zh-CN.md) 从上往下读。
- 想快速查：先看 [关键词索引](chapters/91_keyword_index.zh-CN.md) 或 [快速速查](chapters/99_quick_reference.zh-CN.md)，再跳到对应的 `freqtrade_docs/*.zh-CN.md` 原文附录做全文搜索。
- 想“边做边学”：每章都给出可直接运行的命令模板（统一使用 `uv run` + `--userdir "."`）。

## 与 freqtrade_docs 的关系

- `freqtrade_docs/`：参考库（每页包含“原文自动 Markdown 化”，适合全文搜索与复制示例）。
- `freqtrade_book/`：手册（中文讲“怎么用/怎么查/怎么排错”，并把参考库串成学习路径）。

## 快速入口

- 目录：[`freqtrade_book/SUMMARY.zh-CN.md`](SUMMARY.zh-CN.md)
- 阅读指南：[`freqtrade_book/chapters/00_reading_guide.zh-CN.md`](chapters/00_reading_guide.zh-CN.md)
- 关键词索引：[`freqtrade_book/chapters/91_keyword_index.zh-CN.md`](chapters/91_keyword_index.zh-CN.md)
- 快速速查：[`freqtrade_book/chapters/99_quick_reference.zh-CN.md`](chapters/99_quick_reference.zh-CN.md)
- 参考库索引：[`freqtrade_book/chapters/90_reference_library.zh-CN.md`](chapters/90_reference_library.zh-CN.md)

## 维护自检（可选）

校验 `freqtrade_book/` 与 `freqtrade_docs/` 的本地链接是否断链，并检查手册是否误写入敏感 Token：

```bash
uv run python "scripts/check_docs_health.py"
```
