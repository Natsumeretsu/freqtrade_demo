# freqtrade_demo 常用命令（Windows / PowerShell）

## ⚠️ 核心原则：所有操作必须通过 `scripts/` 文件夹中的脚本执行

**重要：所有配置文件必须包含 `"user_data_dir": "."` 设置！**
- 项目根目录 `F:\Code\freqtrade_demo` 本身就是 user_data 目录
- 如果配置文件缺少此设置，freqtrade 会在项目根目录下创建多余的 `user_data/` 子目录

禁止直接运行底层命令（如 `freqtrade`、`uv run freqtrade` 等），否则可能导致：
- 创建多余的 `user_data/` 子目录（套娃）
- 编码问题（中文 Windows 默认 GBK）
- 路径配置不一致

仅当 `scripts/` 中没有对应脚本时，才考虑运行底层命令。

## 0) 初始化（首次克隆）
- 克隆并拉取子模块：
  - `git clone --recurse-submodules "<repo_url>"`
  - 或：`git submodule update --init --recursive`

## 1) 一键初始化（推荐）
- `& "./scripts/bootstrap.ps1"`
- 若系统限制脚本执行：
  - `powershell.exe -ExecutionPolicy Bypass -File "./scripts/bootstrap.ps1"`

## 2) 依赖与环境（uv）
- 安装固定 Python 版本（默认 3.11）：`uv python install "3.11"`
- 同步依赖（锁定）：`uv sync --frozen`
- 若遇到 Windows 文件占用导致清理失败（例如 VSCode 占用包目录）：`uv sync --frozen --inexact`

## 3) 配置模板（推荐从 `configs/` 复制）
- 通用模板 → 本地配置：`Copy-Item "configs/config.example.json" "config.json"`
- 私密模板 → 本地私密配置：`Copy-Item "configs/config-private.example.json" "config-private.json"`

## 4) 运行 Freqtrade（推荐统一入口）

**重要：禁止直接运行 `freqtrade` 命令！**
- 始终通过 `./scripts/ft.ps1` 运行，否则会在项目根目录下创建多余的 `user_data/` 子目录（套娃）
- 如果必须直接运行，必须加 `--userdir "."` 参数

- 统一入口（自动 UTF-8 + 自动补 `--userdir "."`）：
  - `./scripts/ft.ps1 --help`
  - `./scripts/ft.ps1 --version`
  - `./scripts/ft.ps1 trade --help`
  - `./scripts/ft.ps1 list-strategies`

## 5) 生成新配置（注意：`config*.json` 默认忽略，勿提交密钥）
- `./scripts/ft.ps1 new-config --config "./config.json"`

## 6) 下载数据
- 统一入口（推荐）：`./scripts/ft.ps1 download-data --config "config.json" --pairs "BTC/USDT" --timeframes "1h" --days 30`
- 或用封装脚本（支持正则 pairs / timerange / 交易模式等参数）：`powershell.exe -ExecutionPolicy Bypass -File "./scripts/data/download.ps1" -Pairs "BTC/USDT" -Timeframes "1h" -Days 30 -Config "config.json"`

## 7) 回测（示例模板）
- 通用回测：
  - `./scripts/ft.ps1 backtesting --config "config.json" --strategy "<StrategyName>" --timeframe "1h" --timerange "YYYYMMDD-YYYYMMDD"`

- FreqAI + LightGBM（本仓库示例：`configs/freqai/lgbm_trend_v1.json` / `FreqaiLGBMTrendStrategy`）：
  - 下载数据：
    - `./scripts/ft.ps1 download-data --config "configs/freqai/lgbm_trend_v1.json" --pairs "BTC/USDT" --timeframes "1h" --days 120`
  - 快速回测（14 天窗口 + 单交易对，用于验证流程跑通）：

```powershell
$end = (Get-Date).ToString('yyyyMMdd')
$start = (Get-Date).AddDays(-14).ToString('yyyyMMdd')
./scripts/ft.ps1 backtesting --config "configs/freqai/lgbm_trend_v1.json" --strategy "FreqaiLGBMTrendStrategy" --freqaimodel "LightGBMRegressor" --timeframe "1h" --timerange "$start-$end" --pairs "BTC/USDT"
```

## 8) 文档自检（freqtrade_book / freqtrade_docs）
- `uv run python "scripts/check_docs_health.py"`
- 可选：`uv run python "scripts/check_docs_health.py" --check-config-examples`

## 9) 回测结果压力测试（蒙特卡洛洗牌）
- `uv run python "scripts/analysis/stress_test.py" --zip "backtest_results/<result>.zip" --simulations 5000`
