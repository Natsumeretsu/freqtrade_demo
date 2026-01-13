# Freqtrade 项目规范

> 本文档固化 freqtrade 官方规范和本项目的约定，所有开发者和 AI 助手必须遵守。

## 1. 目录结构规范

### 1.1 Freqtrade 标准目录（位于 userdir：`01_freqtrade/`）

说明：下表中的目录均指 **userdir 内的相对路径**，本仓库实际位置为：`01_freqtrade/<目录>/`。

| 目录 | 用途 | 官方要求 |
|------|------|----------|
| `strategies/` | 策略源码 | 文件名必须与类名一致（PascalCase） |
| `hyperopts/` | 自定义 loss 函数 | 文件名必须与类名一致 |
| `freqaimodels/` | 自定义 FreqAI 模型 | 文件名必须与类名一致 |
| `data/` | 历史数据 | 按交易所分子目录：`data/{exchange}/` |
| `backtest_results/` | 回测结果 | 自动生成，可清理 |
| `hyperopt_results/` | 超参优化结果 | `.fthypt` 文件带时间戳 |
| `models/` | FreqAI 训练产物 | 自动生成，已忽略 |
| `notebooks/` | Jupyter 分析笔记本 | 可选 |
| `plot/` | 图表输出 | 可再生成，建议定期清理 |
| `logs/` | 运行日志 | 已忽略 |

### 1.2 本项目自定义目录（本仓库分层结构）

| 目录 | 用途 | 说明 |
|------|------|------|
| `04_shared/configs/` | 配置模板 | 脱敏配置，可提交 |
| `04_shared/config/` | Qlib YAML 配置 | paths/symbols 等共享配置 |
| `scripts/` | 辅助脚本 | 强制入口（`./scripts/ft.ps1` 等） |
| `02_qlib_research/experiments/` | 实验记录 | 命令/结论，不存产物 |
| `02_qlib_research/notebooks/` | 分析笔记本 | 可复现研究 |
| `03_integration/trading_system/` | 桥接代码 | 策略侧可导入（因子/模型分离的接入点） |
| `docs/` | 权威文档 | 设计/知识/流程 |
| `docs/archive/freqtrade_book/` | 学习手册 | 中文文档 |
| `docs/archive/freqtrade_docs/` | 参考文档 | 离线整理（raw_html 默认不提交） |
| `docs/archive/strategies_ref_docs/` | 策略参考 | Git 子模块 |
| `artifacts/` | 本地产物 | 默认忽略 |

---

## 2. 文件命名规范

### 2.1 策略文件（strategies/）

```
✅ 正确：FreqaiLGBMTrendStrategy.py  → class FreqaiLGBMTrendStrategy
✅ 正确：TheQuantumFlux.py           → class TheQuantumFlux
❌ 错误：freqai_lgbm_trend_strategy.py（snake_case 不符合规范）
```

**规则**：
- 文件名 = 类名 + `.py`
- 使用 PascalCase
- 参数文件：`{StrategyName}.json`（与策略同名）

### 2.2 Hyperopt Loss 文件（hyperopts/）

```
✅ 正确：CompounderCalmarSortinoLoss.py → class CompounderCalmarSortinoLoss
❌ 错误：compounder_calmar_sortino_loss.py
```

### 2.3 FreqAI 模型文件（freqaimodels/）

```
✅ 正确：MyCustomRegressor.py → class MyCustomRegressor
```

**注意**：避免与内置模型重名（LightGBMRegressor、XGBoost 等）

---

## 3. 配置文件规范

### 3.1 配置文件位置

```
# 共享模板（可提交）
04_shared/configs/
├── config.example.json                 # 示例配置（可提交）
├── config-private.example.json         # 私密覆盖示例（仅占位符）
├── config_{name}.json                  # 策略/用途专用配置
├── pairs_{name}.txt                    # 交易对列表
└── freqai/
    └── lgbm_{name}_v1.json             # FreqAI 配置

# 运行期配置（userdir：01_freqtrade/）
01_freqtrade/
├── config.json                         # 可提交但禁止写入密钥
└── config-private.json                 # 私密覆盖（不要提交）
```

### 3.2 敏感信息处理

```
❌ 禁止提交：
- 任何含 exchange.key/secret/password/token 的文件
- `*.env`（环境变量）
- `01_freqtrade/config-private*.json`（私密覆盖）
- `config*.local.json` / `config*.secrets.json` / `config*.private.json`（本地覆盖）

✅ 可以提交：
- `04_shared/configs/*.json`（脱敏模板）
- `01_freqtrade/config.json`（仅占位符/空密钥版本）
- `.env.example`（示例）
```

---

## 4. 数据目录规范

### 4.1 历史数据结构

```
01_freqtrade/data/
└── okx/
    ├── BTC_USDT-4h.feather
    └── futures/
        └── BTC_USDT_USDT-4h-futures.feather
```

### 4.2 数据格式

- 默认格式：`feather`（Apache Arrow）
- 文件命名：`{pair}-{timeframe}.{format}`
- 期货命名：`{base}_{quote}_{settle}-{timeframe}.feather`

---

## 5. 代码规范

### 5.1 技术指标

```python
# ✅ 正确：使用 talib.abstract 或 qtpylib
from talib.abstract import RSI, ATR, BBANDS
import freqtrade.vendor.qtpylib.indicators as qtpylib

# ❌ 错误：手写指标
def my_rsi(close, period):  # 不要这样做
    ...
```

### 5.2 风控/退出

```python
# ✅ 正确：使用 Freqtrade 回调
def custom_stoploss(self, ...) -> float:
    return -0.10

# ❌ 错误：在 custom_exit 中实现止损逻辑
def custom_exit(self, ...):
    if profit < -0.10:  # 不要这样做
        return "my_stoploss"
```

### 5.3 FreqAI 特殊要求

- 不能使用动态 `VolumePairList`（会在运行时增删交易对）
- 所有训练数据必须预先下载
- 模型产物写入 `01_freqtrade/models/{identifier}/`

---

## 6. Git 规范

### 6.1 .gitignore 必须包含

```gitignore
# 私钥/个人配置（不要提交）
/*.env
/01_freqtrade/config-private*.json
/config*.local.json
/config*.secrets.json
/config*.private.json

# 运行期数据/日志/产物（默认不提交）
/01_freqtrade/data/
/01_freqtrade/logs/
/01_freqtrade/backtest_results/
/01_freqtrade/hyperopt_results/
/01_freqtrade/plot/
/*.sqlite*
/*.log

# FreqAI 模型（可再生成，避免误提交）
/01_freqtrade/models/*/

# Qlib 研究层数据/模型（可再生成，默认不提交）
/02_qlib_research/qlib_data/
/02_qlib_research/models/

# 本地产物（可再生成）
/artifacts/

# Python
**/__pycache__/
*.py[cod]
.venv/
```

### 6.2 提交前检查

1. 确保无敏感信息
2. 策略文件名与类名一致
3. 删除无用的缓存文件

---

## 7. 清理规范

### 7.1 可安全删除

| 目录/文件 | 说明 |
|-----------|------|
| `01_freqtrade/plot/*.html` | 图表可再生成 |
| `01_freqtrade/hyperopt_results/*.pkl` | 缓存数据 |
| `01_freqtrade/backtest_results/` 旧文件 | 保留最新即可 |
| `__pycache__/` | Python 缓存 |
| `*.sqlite-shm`, `*.sqlite-wal` | SQLite 临时文件 |

### 7.2 定期清理建议

```powershell
# 清理 Python 缓存
Get-ChildItem -Recurse -Directory -Name "__pycache__" | Remove-Item -Recurse

# 清理 plot 文件夹
Remove-Item 01_freqtrade/plot/* -Recurse
```

---

## 8. 参考链接

- [Freqtrade 官方文档](https://www.freqtrade.io/en/stable/)
- [FreqAI 配置](https://www.freqtrade.io/en/stable/freqai-configuration/)
- [Hyperopt 文档](https://www.freqtrade.io/en/stable/hyperopt/)
- [策略自定义](https://www.freqtrade.io/en/stable/strategy-customization/)

---

*最后更新：2026-01-09*
