# 新设备快速对接指南（Windows + uv）

本文目标：在**另一台电脑**上把本仓库从 `git clone` 到“可回测/可跑脚本/可用 vbrain”一次性跑通，避免因目录约定、配置分层和本地缓存导致的反复踩坑。

适用场景：

- ✅ 全新电脑：第一次克隆本仓库
- ✅ 已有克隆：只是从远端拉取了最新重构版本，需要把本机环境/配置对齐
- ✅ 双设备切换：希望保持“结论层一致、缓存层可重建”

> 重要变化：本仓库不再把 repo root 当作 userdir。Freqtrade `userdir` 固定在：`01_freqtrade/`。  
> **所有 Freqtrade 命令必须通过** `./scripts/ft.ps1` 执行（避免生成意外 `user_data/` 目录）。

---

## 0) 你需要准备什么（最小前置）

必需：

- Windows 10/11
- Git（用于 clone / submodule）
- `uv`（管理 Python 与虚拟环境，虚拟环境位于 `./.venv/`）

可选（建议）：

- PowerShell 7（`pwsh`）：用于 MCP 一键脚本（PowerShell 5.1 对 UTF-8 无 BOM 支持不佳）
- Node.js 18+：用于 In‑Memoria / Local RAG（vbrain core）
- Chrome/Chromium：用于 Playwright/Chrome DevTools MCP（如你需要网页自动化）

---

## 1) 克隆仓库（含子模块）

全新电脑直接执行：

```powershell
git clone --recurse-submodules "<your_repo_url>" "freqtrade_demo"
Set-Location "freqtrade_demo"
git submodule update --init --recursive
```

如果你已经 clone 过（只需要拉取更新）：

```powershell
git pull --ff-only
git submodule update --init --recursive
```

---

## 2) 一键初始化（推荐）

在仓库根目录运行：

```powershell
./scripts/bootstrap.ps1
```

如果系统限制执行脚本（ExecutionPolicy）：

```powershell
powershell.exe -ExecutionPolicy Bypass -File "./scripts/bootstrap.ps1"
```

说明：

- `bootstrap.ps1` 会按 `.python-version` 安装对应 Python，并执行 `uv sync --frozen`（以 `uv.lock` 为准）。
- 你也可以把 MCP 初始化一起做掉（需要 PowerShell 7 / `pwsh`）：

```powershell
./scripts/bootstrap.ps1 -SetupCodex
# 或
./scripts/bootstrap.ps1 -SetupClaude
```

更详细的 MCP 同步文档：

- Codex：`docs/setup/codex_mcp_sync.md`
- Claude：`docs/setup/claude_mcp_sync.md`

---

## 3) 生成本机运行配置（必须）

### 3.1 `.env`（本机环境变量）

```powershell
Copy-Item ".env.example" ".env"
```

> `.env` 默认 gitignore：只放本机差异项（例如代理、Token、本机路径覆盖等），不要提交密钥。

### 3.2 `01_freqtrade/config.json`（可提交，但必须“脱敏”）

```powershell
Copy-Item "04_shared/configs/config.example.json" "01_freqtrade/config.json"
```

要求：

- 允许随 Git 同步，但**禁止写入任何密钥/Token/password**  
  （密钥放到 `.env` 或 `01_freqtrade/config-private.json`）。

### 3.3 `01_freqtrade/config-private.json`（本机私密覆盖）

```powershell
Copy-Item "04_shared/configs/config-private.example.json" "01_freqtrade/config-private.json"
```

> `01_freqtrade/config-private.json` 默认 gitignore：只放交易所 key/secret、代理、私密 endpoint 等。

---

## 4) 最小验收（不依赖市场数据）

### 4.1 验证策略能被识别（最关键）

```powershell
./scripts/ft.ps1 list-strategies --config "01_freqtrade/config.json"
```

期望：

- 能看到 `SmallAccountTrendFilteredV1`、`SmallAccountFuturesTrendV1` 等主线策略
- 不应在仓库根目录生成 `user_data/`（若出现，说明你绕过了 `./scripts/ft.ps1`）

### 4.2 跑单元测试（推荐）

```powershell
uv run python -X utf8 -m unittest -q
```

---

## 5) 需要回测/下载数据时怎么做

### 5.1 下载市场数据（示例：OKX 永续，4h + 1d）

```powershell
./scripts/data/download.ps1 `
  -Pairs "BTC/USDT:USDT" `
  -Timeframes "4h","1d" `
  -TradingMode "futures" `
  -Timerange "20200101-"
```

### 5.2 跑主线回测（示例：小资金合约趋势）

```powershell
./scripts/analysis/small_account_backtest.ps1 `
  -Config "04_shared/configs/small_account/config_small_futures_base.json" `
  -Strategy "SmallAccountFuturesTrendV1" `
  -Pairs "BTC/USDT:USDT" `
  -Timeframe "4h" `
  -TradingMode "futures" `
  -Timerange "20200101-20251231"
```

---

## 6) vbrain / Local RAG：跨设备建议 SOP（强烈建议）

vbrain 的跨设备原则：**同步“结论层”，重建“加速层”**。

- 结论层（必须同步）：`docs/`、`.serena/memories/`
- 主脑层（建议同步）：`in-memoria.db`（可写 DB，避免双设备并发写入）
- 加速层（默认不同步）：`.vibe/`（Local RAG 向量库/缓存，可重建）

### 6.1 切换设备的推荐顺序（避免冲突）

1) 设备 A：`git pull --ff-only` → 工作 → `git commit` → `git push`  
2) 设备 B：`git pull --ff-only` → `uv sync --frozen` → 预热索引

> 不建议两台设备同时改动并提交 `in-memoria.db`，因为它是二进制 DB，无法可靠合并。

### 6.2 预热 vbrain（重建 docs 索引 + 显示进度）

```powershell
python -X utf8 scripts/tools/vbrain.py preheat --rebuild-docs
```

查看 vbrain 状态（路径/缓存/索引状态）：

```powershell
python -X utf8 scripts/tools/vbrain.py status
```

更完整的工作流与模型选型结论见：

- `docs/setup/vibe_brain_workflow.md`
- `docs/tools/vbrain/README.md`

---

## 7) 归档内容怎么启用（可选）

历史/实验策略（含 FreqAI）已归档到：`01_freqtrade/strategies_archive/`。  
需要使用时，显式追加 `--strategy-path`：

```powershell
./scripts/ft.ps1 list-strategies --config "01_freqtrade/config.json" --strategy-path "01_freqtrade/strategies_archive"
```

归档配置模板位于：`04_shared/configs/archive/`（按需复制到 `01_freqtrade/` 使用）。

---

## 8) 常见问题（排障速查）

### 8.1 PowerShell 执行策略报错

优先用：

```powershell
powershell.exe -ExecutionPolicy Bypass -File "./scripts/bootstrap.ps1"
```

### 8.2 Windows 中文编码导致 `UnicodeDecodeError`

结论：尽量始终使用 `./scripts/ft.ps1`（脚本入口会以 UTF‑8 模式运行）。  
相关说明见：`README.md` 的 “Windows 编码说明”。

### 8.3 不小心生成了 `user_data/` 目录

原因：绕过了 `./scripts/ft.ps1`，直接运行了 `freqtrade` / `uv run freqtrade`。  
处理：之后只使用 `./scripts/ft.ps1`；历史遗留的 `user_data/` 可按需手动清理（不影响本仓库主流程）。

---

## 9) 最终验收清单（建议打勾）

- [ ] `uv sync --frozen` 成功，`./.venv/` 已创建
- [ ] 已生成 `.env`、`01_freqtrade/config.json`、`01_freqtrade/config-private.json`
- [ ] `./scripts/ft.ps1 list-strategies --config "01_freqtrade/config.json"` 正常输出
- [ ] `uv run python -X utf8 -m unittest -q` 通过
- [ ] （可选）已下载数据并完成一次回测
- [ ] （可选）已运行 `python -X utf8 scripts/tools/vbrain.py preheat --rebuild-docs`

