# 代码风格与约定（freqtrade_demo）

## 语言与沟通
- 产出（说明/分析/结论）统一使用简体中文。
- 代码注释与文档优先使用中文（必要时保留关键英文术语/参数名/命令名）。

## 环境与编码（重要）
- Windows 中文环境可能默认 GBK，Freqtrade 扫描 `strategies/*.py` 时可能触发 `UnicodeDecodeError`。
- 推荐统一用 `./scripts/ft.ps1`（内部设置 `PYTHONUTF8=1`/`PYTHONIOENCODING=utf-8`，并用 `python -X utf8` 启动）。
- VSCode 工作区 `.vscode/settings.json` 也会为集成终端设置上述环境变量。

## 依赖与运行方式
- 使用 `uv` 管理虚拟环境（`./.venv/`）与依赖（`uv sync --frozen` 以 `uv.lock` 为准）。
- 运行命令优先：`uv run ...`；Freqtrade 子命令建议显式带 `--userdir "."`。

## 策略/超参代码习惯
- 策略实现遵循 Freqtrade `IStrategy`（示例 `SampleStrategy`：`INTERFACE_VERSION = 3`）。
- 常见依赖：`pandas`/`numpy`，指标优先使用 `talib.abstract` 与 `technical.qtpylib`。
- README 建议：风控/退出优先用 `custom_roi` / `custom_stoploss` 与配置项（如 `trailing_stop`），避免用 `custom_exit` 充当止损系统。

## 安全与仓库约定
- `config*.json` 默认忽略（防止密钥泄露）；提交前务必 `git status` 复核。
- 危险操作（删除/批量改动/覆盖历史等）需要用户明确确认。

## 文档目录额外约束
- `freqtrade_book/`、`freqtrade_docs/` 各自有目录级 `AGENTS.md`：写文档需按其模板与自检要求执行。
- 文档提交前建议运行：`uv run python "scripts/check_docs_health.py"`。
