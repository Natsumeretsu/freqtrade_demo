# freqtrade_demo

这是一个“纯 userdir”的 Freqtrade 示例仓库：仓库根目录就是 userdir（策略/超参/笔记本/文档）。
`strategies_ref_docs/` 以 Git 子模块形式提供策略参考文档。

## 目录结构

- `strategies/`：策略源码
- `hyperopts/`：超参 loss 等
- `notebooks/`：分析笔记本
- `docs/`：补充文档（中文）
- `strategies_ref_docs/`：策略参考文档（Git 子模块）
- `requirements.txt`：Freqtrade 依赖（固定到 Git commit）
- `.venv/`：本地虚拟环境（不提交）

## 克隆（含子模块）

```bash
git clone --recurse-submodules "<your_repo_url>"
git submodule update --init --recursive
```

## 环境配置（推荐：uv 管理 `./.venv`）

```powershell
uv python install "3.11"
uv venv --python "3.11" "./.venv"
uv pip install --python "./.venv/Scripts/python.exe" -r "./requirements.txt"

& "./.venv/Scripts/freqtrade.exe" --userdir "." --help
```

## 生成配置（注意：`config*.json` 默认忽略，不要提交密钥）

```powershell
& "./.venv/Scripts/freqtrade.exe" --userdir "." new-config --config "./config.json"
```
