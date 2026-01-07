# freqtrade_demo

这是一个“纯 userdir”的 Freqtrade 示例仓库：仓库根目录就是 userdir（策略/超参/笔记本/文档）。
`strategies_ref_docs/` 以 Git 子模块形式提供策略参考文档。

## 目录结构

- `strategies/`：策略源码
- `hyperopts/`：超参 loss 等
- `notebooks/`：分析笔记本
- `docs/`：补充文档（中文）
- `strategies_ref_docs/`：策略参考文档（Git 子模块）
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

## KNNTrendWindow 示例（严格样本外）

训练用 `2018-2024`，回测/评估用 `2025-2026`（避免“训练集标签跨到测试期”的隐性泄露），并且按“典型持仓几小时”将默认 `horizon` 调整为 6。

### 1) 训练模型（2018-2024 训练，2025-2026 测试）

```powershell
uv run python -X utf8 "scripts/train_knn_trend_window.py" `
  --filter-trend `
  --datadir "data/okx" `
  --pair "BTC/USDT" `
  --timeframe "1h" `
  --train-timerange "20180101-20250101" `
  --test-timerange "20250101-20270101"
```

训练结束会打印“阈值扫描（用于选 buy_proba_min）”。如果需要手动固定参数，可在策略同名参数文件中配置：`strategies/knn_trend_window_strategy.json`

```json
{
  "strategy_name": "KNNTrendWindowStrategy",
  "params": {
    "buy": {
      "buy_adx_min": 10,
      "buy_proba_min": 0.35
    }
  }
}
```

### 2) 回测策略（2025-2026 严格样本外）

```powershell
.\scripts\ft.ps1 backtesting `
  --config "config.json" `
  --strategy "KNNTrendWindowStrategy" `
  --timeframe "1h" `
  --timerange "20250101-20270101"
```
