# freqtrade_demo 项目概览

## 项目目的
- 这是一个“纯 userdir”的 Freqtrade 示例仓库：仓库根目录就是 userdir（策略/超参/笔记本/文档）。
- `strategies_ref_docs/` 以 Git 子模块形式提供策略参考文档。

## 技术栈
- OS：Windows（PowerShell 5.1）。
- Python：`3.11`（见 `.python-version`）。
- 依赖管理：`uv`（虚拟环境 `./.venv/`，锁文件 `uv.lock`）。
- 核心依赖：`freqtrade[freqai,hyperopt]`（通过 `pyproject.toml` pin 到指定 git rev）。

## 目录结构（高层）
- `strategies/`：策略源码（Freqtrade `IStrategy`）。
- `hyperopts/`：Hyperopt loss 等。
- `scripts/`：PowerShell / Python 辅助脚本（推荐统一入口 `ft.ps1`）。
- `configs/`：可提交、可复制的配置模板（脱敏）；本地私密配置仍建议落到根目录 `config*.json`（默认忽略）。
- `freqaimodels/`：自定义 FreqAI 预测模型代码目录（可选，供 `--freqaimodel` 加载）。
- `models/<identifier>/`：FreqAI 训练/预测产物目录（自动生成，默认忽略，尽量不要手工改）。
- `experiments/`：实验记录（只记录配置/命令/结论，不存放训练产物）。
- `notebooks/`：分析/研究笔记本。
- `freqtrade_book/`：渐进式学习手册（中文）。
- `freqtrade_docs/`：离线整理的参考库（中文）。
- `strategies_ref_docs/`：策略参考文档（子模块）。
- `artifacts/`：本地归档/历史产物（默认忽略）。
