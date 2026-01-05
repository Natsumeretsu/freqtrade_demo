# freqtrade_book 目录 - AGENTS 指南

本文件用于给 Codex/自动化助手提供 `freqtrade_book/` 目录树范围内的工作约束与最佳实践。

## 1) 目标（强制）

- 把 `freqtrade_docs/` 参考库内容“整理成册”：形成一条**渐进式学习路线**（从 0 到能回测/能跑 dry-run/能上实盘），同时保留“随查随用”的参考索引。
- 面向“vibe coding 查阅使用”：内容要可搜索、可复制、可复用，尽量用清晰的小节、清单与命令模板表达。

## 2) 文档风格（强制）

- 只使用简体中文撰写（必要时保留关键英文术语、参数名、命令名）。
- 不做逐句翻译搬运；优先写“怎么用/怎么查/怎么排错”的结构化内容。
- 每章都要给出：
  - 本章目标（你学完能做什么）
  - 最小可运行命令模板（与本仓库一致：`uv run freqtrade ... --userdir "."`）
  - 延伸阅读：链接到 `freqtrade_docs/*.zh-CN.md` 参考库

## 3) 目录结构约定

- `freqtrade_book/README.zh-CN.md`：入口与总览。
- `freqtrade_book/SUMMARY.zh-CN.md`：目录（按学习顺序）。
- `freqtrade_book/chapters/*.zh-CN.md`：章节正文（用数字前缀保证顺序）。

## 4) 引用与链接规范

- 章节间链接：优先使用相对路径（例如 `./03_data_backtest.zh-CN.md`）。
- 引用参考库：从章节文件链接到 `../../freqtrade_docs/<file>.zh-CN.md`。
- 命令统一使用本仓库推荐形式：

```powershell
uv run freqtrade <命令> --userdir "." <参数...>
```

## 5) 安全（强制）

- 禁止在文档中写入真实密钥/Token/密码/JWT secret。
- 示例统一使用占位符：`<yourExchangeKey>`、`<telegramToken>`、`<strong_password>` 等。

## 6) 章节骨架（强制）

学习章节（`00_` ~ `09_`）建议固定骨架，便于读者快速定位与复用：

1. 标题（`# ...`）
2. 顶部导航：`[返回目录] | [上一章] | [下一章]`
3. `## 本章目标`
4. `## 本章完成标准`
5. `---`
6. `## 0) 最小命令模板` + `### 0.1 关键输出检查点`（让读者知道“跑完应该看到什么”）
7. 正文按“任务/问题”编号组织（`## 1) ...`、`## 2) ...`）
8. `## 延伸阅读（参考库）`：链接到 `../../freqtrade_docs/*.zh-CN.md`
9. 底部导航：同顶部

代码块语言约定：

- 命令行：`powershell`
- 配置片段：`json`
- 日志/输出：`text`

## 7) 提交前自检（强制）

在提交前运行自检脚本，避免断链/泄露/结构退化：

```powershell
uv run python "scripts/check_docs_health.py"
```

可选：同时校验 `config.example.json` 是否能通过 `show-config`/`list-strategies`：

```powershell
uv run python "scripts/check_docs_health.py" --check-config-examples
```
