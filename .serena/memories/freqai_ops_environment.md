# FreqAI 工程与环境主干（Windows / scripts 约定 / MCP / 浏览器 / 回测输出）

更新日期：2026-01-10

---

## 1) 命令与环境约定（强制）

- Windows 环境（PowerShell 5.1 为主）。
- 依赖/虚拟环境：统一使用 `uv`，虚拟环境位于 `./.venv/`。
- **禁止直接运行 `freqtrade`**：所有 freqtrade 命令必须通过 `./scripts/ft.ps1`（避免生成多余 `user_data/` 子目录）。
- 路径：命令中尽量使用双引号包裹路径，优先使用 `/` 作为分隔符。

---

## 2) 回测输出与分析（强制）

- 回测汇报标准：`.serena/memories/backtest_reporting_standard.md`（文档侧：`project_docs/guidelines/backtest_reporting_standard.md`）。
- 每次回测至少输出“逐交易对 vs Market change”的报表（HTML 优先，其次 CSV）。

---

## 3) MCP 工具优先级（默认）

- 代码检索/精确编辑：优先 `serena`（符号级），纯文本检索再用 `rg`。
- 资料抓取：`markitdown`（静态）→ `playwright_mcp`（JS/交互）→ 失败则登记 blocked。

---

## 4) Chrome / Playwright / DevTools 可用性（按需修复）

- 若 `playwright_mcp` / `chrome_devtools_mcp` 因缺少 `chrome.exe` 不可用：运行脚本（无需管理员权限）：
  - `./scripts/tools/fix_chrome_for_mcp.ps1`
- 手动等价步骤见：`project_docs/setup/codex_mcp_sync.md`

---

## 5) 已知小坑

- 仓库根目录可能出现名为 `nul` 的文件，Windows 下 `rg` 可能报错；本仓库已在 `.gitignore` 忽略该文件名以避免扫描异常。
