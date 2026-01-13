# freqtrade_demo

这是一个面向 Windows + `uv` 的 **Freqtrade（回测/实盘）+ Qlib 风格研究（因子/模型）** 的工程化仓库。

> 重要变化：本仓库不再把 repo root 当作 userdir。Freqtrade `userdir` 固定在：`01_freqtrade/`。

---

## 目录结构（最重要）

- `01_freqtrade/`：Freqtrade userdir（策略/运行配置/数据/回测产物）
- `02_qlib_research/`：研究层（notebooks/experiments；`qlib_data/` 与 `models/` 默认不提交）
- `03_integration/`：集成层（桥接代码：`trading_system/`，策略侧可 `import`）
- `04_shared/`：共享配置  
  - `04_shared/configs/`：Freqtrade JSON 配置模板（脱敏、可提交）  
  - `04_shared/config/`：Qlib 相关 YAML（路径/交易对/符号映射，可提交）
- `scripts/`：统一脚本入口（强制使用）
- `docs/`：权威文档；`docs/archive/`：离线参考与归档（含子模块 `docs/archive/strategies_ref_docs/`）
- `artifacts/`：本地 benchmark 产物（默认不提交）

---

## 克隆（含子模块）

```bash
git clone --recurse-submodules "<your_repo_url>"
git submodule update --init --recursive
```

---

## 环境配置（推荐：uv 管理 `./.venv`）

```powershell
uv python install "3.11"
uv sync --frozen

./scripts/ft.ps1 --help
```

也可以一键初始化（含依赖同步）：

```powershell
./scripts/bootstrap.ps1
```

若系统限制执行脚本：

```powershell
powershell.exe -ExecutionPolicy Bypass -File "./scripts/bootstrap.ps1"
```

---

## 关键约定（避免路径与产物混乱）

- **所有 Freqtrade 命令必须用** `./scripts/ft.ps1 <命令> ...`  
  - 脚本会自动补 `--userdir "./01_freqtrade"`  
  - 禁止直接运行 `freqtrade` / `uv run freqtrade`（容易生成意外 `user_data/` 子目录）
- 私密信息只放 `.env` 或 `01_freqtrade/config-private.json`（默认 gitignore）
- 市场数据/回测产物/训练模型默认不随 Git 同步（见：`docs/setup/git_sync_policy.md`）

### Windows 编码说明（重要）

中文 Windows 默认编码常为 GBK，Freqtrade 在扫描 `01_freqtrade/strategies/*.py` 时可能触发 `UnicodeDecodeError`。  
本仓库脚本入口会强制 UTF-8 模式运行，建议始终用 `./scripts/ft.ps1`。

如需让 IDE/调试也统一 UTF-8，可复制：

```powershell
Copy-Item ".env.example" ".env"
```

---

## Quickstart（最小可跑通）

### 1) 生成运行配置

```powershell
Copy-Item "04_shared/configs/config.example.json" "01_freqtrade/config.json"
Copy-Item "04_shared/configs/config-private.example.json" "01_freqtrade/config-private.json"
```

### 2) 验证策略能被识别

```powershell
./scripts/ft.ps1 list-strategies --config "01_freqtrade/config.json"
```

### 3) 下载数据（示例：OKX 永续，4h + 1d）

```powershell
./scripts/data/download.ps1 `
  -Pairs "BTC/USDT:USDT" `
  -Timeframes "4h","1d" `
  -TradingMode "futures" `
  -Timerange "20200101-"
```

### 4) 回测（示例：小资金合约趋势）

```powershell
./scripts/analysis/small_account_backtest.ps1 `
  -Config "04_shared/configs/small_account/config_small_futures_base.json" `
  -Strategy "SmallAccountFuturesTrendV1" `
  -Pairs "BTC/USDT:USDT" `
  -Timeframe "4h" `
  -TradingMode "futures" `
  -Timerange "20200101-20251231"
```

（可选）### 5) 研究层：一键转换 + 训练（Qlib 风格）

```powershell
./scripts/qlib/pipeline.ps1 -Timeframe "4h" -ModelVersion "v1"
```

---

## 典型入口（策略/示例）

- 小资金现货主线：`01_freqtrade/strategies/SmallAccountTrendFilteredV1.py`
- 小资金合约趋势：`01_freqtrade/strategies/SmallAccountFuturesTrendV1.py`
- 其它历史/实验策略（含 FreqAI）已归档：`01_freqtrade/strategies_archive/`（配置示例见：`04_shared/configs/archive/`）

---

## Codex MCP（可选）

如需一键写入本机 Codex CLI 配置（Serena / Context7 / MarkItDown / Playwright / Chrome DevTools / Wolfram 等）：

```powershell
powershell.exe -ExecutionPolicy Bypass -File "./scripts/mcp/setup_codex.ps1"
```

更完整的说明见：`docs/setup/codex_mcp_sync.md`。
