# freqtrade_demo

这是一个“纯 userdir”的 Freqtrade 示例仓库：仓库根目录就是 userdir（策略/超参/笔记本/文档）。
`strategies_ref_docs/` 以 Git 子模块形式提供策略参考文档。

## 目录结构

- `strategies/`：策略源码
- `hyperopts/`：超参 loss 等
- `scripts/`：辅助脚本（推荐统一入口 `./scripts/ft.ps1`）
- `configs/`：可提交、可复制的配置模板（脱敏）
- `experiments/`：实验记录（命令/结论；不存训练产物）
- `freqaimodels/`：自定义 FreqAI 预测模型代码（可选）
- `notebooks/`：分析笔记本
- `freqtrade_book/`：渐进式学习手册（中文）
- `freqtrade_docs/`：离线整理的参考库（中文）
- `strategies_ref_docs/`：策略参考文档（Git 子模块）
- `.claude/CONVENTIONS.md`：项目规范文档（必读）
- `models/`：FreqAI 训练/预测产物（默认忽略，不建议手工改动）
- `artifacts/`：本地归档/历史产物（默认忽略）
- `.serena/`：Serena 项目配置与记忆（建议跨设备同步 `memories/` 与 `project.yml`；`cache/`/`logs/` 默认忽略）
- `pyproject.toml`：依赖声明（唯一来源）
- `uv.lock`：依赖锁文件（锁死传递依赖）
- `.python-version`：固定 Python 版本（uv 自动使用）
- `.venv/`：本地虚拟环境（不提交）

## 克隆（含子模块）

```bash
git clone --recurse-submodules "<your_repo_url>"
git submodule update --init --recursive
```

## 环境配置（推荐：uv 管理 `./.venv`）

```powershell
uv python install "3.11"
uv sync --frozen

.\scripts\ft.ps1 trade --help
```

### Windows 编码说明（重要）

中文 Windows 的默认编码常为 GBK，Freqtrade 在扫描 `strategies/*.py` 时可能触发 `UnicodeDecodeError`。
本仓库已提供统一入口脚本 `./scripts/ft.ps1`，会强制使用 UTF-8 模式运行 Freqtrade，建议用它替代直接运行 `uv run freqtrade ...`。

如果你希望 VSCode 的 Python 扩展（运行/调试）也默认启用 UTF-8，可复制示例环境变量文件：

```powershell
Copy-Item ".env.example" ".env"
```

说明：`.env` 默认被 git 忽略，避免误提交环境变量；请只在 `.env.example` 放非敏感内容。

也可以一键初始化（含子模块 + 依赖同步）：

```powershell
& "./scripts/bootstrap.ps1"
```

如果系统限制执行脚本，可用：

```powershell
powershell.exe -ExecutionPolicy Bypass -File "./scripts/bootstrap.ps1"
```

## Codex MCP（可选）

如果团队使用 Codex CLI，并希望启用常用 MCP（Serena / Context7 / MarkItDown / Playwright / Chrome DevTools / Wolfram），克隆后在仓库根目录执行一次：

```powershell
powershell.exe -ExecutionPolicy Bypass -File "./scripts/mcp/setup_codex.ps1"
```

更完整的同步/参数说明见：`other_doc/codex_mcp_sync.md`。

仅预览将要执行的命令（不修改本机配置）：

```powershell
./scripts/mcp/setup_codex.ps1 -WhatIf
```

如果你已经添加过同名 MCP server，但想按脚本版本覆盖：

```powershell
./scripts/mcp/setup_codex.ps1 -Force
```

前置：已安装 `codex`（Codex CLI）、`node`（含 `npx`）、`uv`（含 `uvx`）。本仓库默认使用 Wolfram 的 **Python 模式**（默认使用 `~/.codex/tools/Wolfram-MCP/`，脚本会按需克隆/更新该仓库并自动初始化其 `.venv`）；如需改用 `wolframscript` + Paclet 请使用 `-WolframMode paclet`。如需强制重建 `~/.codex/tools/Wolfram-MCP/.venv`，可加 `-BootstrapWolframPython`。如需指定 Wolfram-MCP 仓库位置/地址，可用 `-WolframMcpRepoDir` / `-WolframMcpRepoUrl`。

说明：该脚本只会写入你本机的 `~/.codex/config.toml`（Codex CLI 的用户配置），不会修改或提交仓库文件。

## 生成配置（注意：`config*.json` 默认忽略，不要提交密钥）

```powershell
uv run freqtrade --userdir "." new-config --config "./config.json"
```

## FreqAI + LightGBM 示例（滚动训练）

本仓库提供：

- 策略：`strategies/FreqaiLGBMTrendStrategy.py`（`FreqaiLGBMTrendStrategy`）
- 示例配置：`configs/freqai/lgbm_trend_v1.json`

### 开发约定（避免重复造轮子）

- 技术指标：统一用 `talib.abstract` / `technical.qtpylib`，不要手写 RSI/ATR/布林带等。
- 风控/退出：优先使用 Freqtrade 回调 `custom_roi` / `custom_stoploss`（以及配置里的 `trailing_stop` 等），不要用自定义 `custom_exit` 充当止损系统。
- FreqAI 训练产物：默认会写入 `models/<identifier>/`，该目录已在 `.gitignore` 中忽略，避免误提交。

回测示例：

```powershell
.\scripts\ft.ps1 backtesting `
  --config "configs/freqai/lgbm_trend_v1.json" `
  --strategy "FreqaiLGBMTrendStrategy" `
  --freqaimodel "LightGBMRegressor" `
  --timeframe "1h" `
  --timerange "20250101-20270101"
```

扫参示例（跨多个窗口评估阈值稳健性）：

```powershell
uv run python "scripts/analysis/param_sweep.py" --configs "configs/freqai/lgbm_trend_v1_eval.json" --pairs "BTC/USDT" --timeframe-detail "5m" --fee 0.0015
```

提示：扫参脚本也支持把入场过滤参数一起纳入网格（用于提升“熊市/暴跌窗口”的抗性），详见 `scripts/analysis/param_sweep.py --help`。

## 市场仪表盘（大盘均值/相对强弱）

如果你希望从**最早数据到最新**，查看“交易对等权大盘”的归一化走势，以及每个交易对相对大盘的**强弱/排名变化**：

```powershell
uv run python "scripts/data/dashboard.py" `
  --config "configs/config_moonshot.json" `
  --datadir "data/okx" `
  --timeframe "1h" `
  --resample "1D" `
  --benchmark "rebalanced" `
  --anchor "pair" `
  --heatmap-resample "1W" `
  --out "plot/market_dashboard_moonshot.html"
```

周期同步更新（适合 Dry Run / Live 前的“实盘节奏”监控）：

```powershell
powershell.exe -ExecutionPolicy Bypass -File "./scripts/data/update_dashboard.ps1" `
  -Config "configs/config_moonshot.json" `
  -Days 10 `
  -Timeframes @("1h") `
  -Out "plot/market_dashboard_moonshot.html"
```
