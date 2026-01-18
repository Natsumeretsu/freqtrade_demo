# 目录结构：Freqtrade + Qlib（工程化分层）

本仓库采用“运行层 / 研究层 / 集成层 / 共享配置”分层，目标是：

- 把 Freqtrade 的实盘/回测与研究（因子/模型/验证）解耦
- 让路径与产物位置稳定、可复现、可追溯
- 对小资金场景优先“减少意外目录与工程噪声”（尤其是 Windows 环境）

---

## 1) 顶层分层（repo root）

```
freqtrade_demo/
├── 01_freqtrade/                 # Freqtrade userdir（运行层：回测/实盘都指向这里）
│   ├── strategies/               # 策略（*.py）与参数文件（*.json，可选）
│   ├── hyperopts/                # Hyperopt loss / 目标函数（源码）
│   ├── freqaimodels/             # 自定义 FreqAI 模型（可选）
│   ├── config.json               # 运行配置（可同步，但禁止写入密钥）
│   ├── config-private.json       # 私密覆盖配置（不要提交）
│   ├── data/                     # 市场数据（默认 gitignore）
│   ├── logs/                     # 运行日志（默认 gitignore）
│   ├── backtest_results/         # 回测产物（默认 gitignore）
│   ├── hyperopt_results/         # 超参产物（默认 gitignore）
│   └── plot/                     # 报表/图（默认 gitignore）
│
├── 02_qlib_research/             # 研究层：Notebook/实验记录（可复现、可对比）
│   ├── notebooks/
│   ├── experiments/
│   ├── qlib_data/                # Qlib 风格数据（默认 gitignore）
│   └── models/                   # 研究层模型（默认 gitignore）
│
├── 03_integration/               # 集成层：桥接代码（策略侧可 import）
│   └── trading_system/
│
├── 04_shared/                    # 共享配置（可提交）
│   ├── configs/                  # Freqtrade JSON 配置模板（脱敏）
│   └── config/                   # YAML（Qlib 路径/交易对/符号映射）
│
├── scripts/                      # 统一脚本入口（强制使用）
├── docs/                         # 权威文档（设计/知识/流程）
└── artifacts/                    # 本地 benchmark 产物（默认 gitignore）
```

---

## 2) 关键约定（避免路径与产物混乱）

1. **Freqtrade 只能通过脚本运行**：使用 `./scripts/ft.ps1 <命令> ...`  
   - 脚本会自动补 `--userdir "./01_freqtrade"`  
   - 禁止直接运行 `freqtrade` 或 `uv run freqtrade`，否则容易生成意外的 `user_data/` 子目录
2. **大体积产物默认不进 Git**：`01_freqtrade/data/`、`01_freqtrade/backtest_results/`、`01_freqtrade/models/`、`02_qlib_research/qlib_data/`、`02_qlib_research/models/` 等默认 gitignore
3. **共享配置一处维护**：  
   - JSON 模板：`04_shared/configs/`（可复制到 `01_freqtrade/` 作为运行配置）  
   - YAML（Qlib 相关）：`04_shared/config/`（供 `03_integration/trading_system` 与 `scripts/qlib/*` 读取）

---

## 3) 文件放哪里（最常见问题）

- 新策略：`01_freqtrade/strategies/<Strategy>.py`  
  - 若需要固定默认参数：同名 `01_freqtrade/strategies/<Strategy>.json`
- 运行配置：`01_freqtrade/config.json`（可同步，但禁止写入密钥）
- 私密配置：`01_freqtrade/config-private.json`（不要提交）
- Qlib 数据输出：`02_qlib_research/qlib_data/<exchange>/<timeframe>/<symbol>.pkl`
- Qlib 模型输出：`02_qlib_research/models/qlib/<version>/<exchange>/<timeframe>/<symbol>/`
- 工具/脚本：统一放 `scripts/`
- 文档与结论：统一放 `docs/`（大量参考资料可归档到 `docs/archive/`）
