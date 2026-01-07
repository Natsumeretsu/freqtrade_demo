# 任务完成检查清单（建议）

## 环境/依赖
- 依赖同步：`uv sync --frozen`
- 若遇到 Windows 文件占用导致清理失败（例如 VSCode 占用包目录）：`uv sync --frozen --inexact`

## 策略/超参相关改动
- 基础导入检查：`uv run python -m compileall "strategies" "hyperopts"`
- 策略可见性/加载检查：`./scripts/ft.ps1 list-strategies`
- 行为验证（按需，可能较慢）：使用对应配置跑一次 `backtesting`。

## 脚本相关改动（scripts/）
- 基础运行检查：`uv run python -m compileall "scripts"`

## 文档相关改动（freqtrade_book/ / freqtrade_docs/）
- 必跑自检：`uv run python "scripts/check_docs_health.py"`
- 如涉及配置示例：可加跑 `uv run python "scripts/check_docs_health.py" --check-config-examples`（需要依赖已安装）。

## 通用安全复核
- 确认未引入/提交 `config.json` 等敏感文件与密钥。
- `git status` 确认变更范围符合预期。
