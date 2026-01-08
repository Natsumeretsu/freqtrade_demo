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

## 生成配置（注意：`config*.json` 默认忽略，不要提交密钥）

```powershell
uv run freqtrade --userdir "." new-config --config "./config.json"
```

## FreqAI + LightGBM 示例（滚动训练）

本仓库提供：

- 策略：`strategies/freqai_lgbm_trend_strategy.py`（`FreqaiLGBMTrendStrategy`）
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
uv run python "scripts/sweep_freqai_params.py" --configs "configs/freqai/lgbm_trend_v1_eval.json" --pairs "BTC/USDT" --timeframe-detail "5m" --fee 0.0015
```

提示：扫参脚本也支持把入场过滤参数一起纳入网格（用于提升“熊市/暴跌窗口”的抗性），详见 `scripts/sweep_freqai_params.py --help`。
