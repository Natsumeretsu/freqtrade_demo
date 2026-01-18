# 项目目录结构说明

更新日期：2026-01-17

## 1. 概览

本文档详细说明 freqtrade_demo 项目的目录结构、各目录用途和使用规范。

**核心原则**：
- 4 层架构：01_freqtrade（执行层）、02_qlib_research（研究层）、03_integration（集成层）、04_shared（共享配置）
- 根目录保持整洁，避免临时文件污染
- 实际工作目录在各层级子目录中

---

## 2. 根目录结构

```
freqtrade_demo/
├── 01_freqtrade/          # Freqtrade 执行层（userdir）
├── 02_qlib_research/      # Qlib 研究层
├── 03_integration/        # 集成层（桥接代码）
├── 04_shared/             # 共享配置
├── scripts/               # 统一脚本入口
├── docs/                  # 权威文档
├── artifacts/             # 本地产物（不提交）
├── tests/                 # 测试代码
├── .claude/               # Claude Code 配置
├── .serena/               # Serena 配置
├── .venv/                 # Python 虚拟环境
├── CLAUDE.md              # Claude 工作指南
├── AGENTS.md              # 自动化助手指南
├── README.md              # 项目说明
├── pyproject.toml         # Python 项目配置
└── uv.lock                # 依赖锁定文件
```

---

## 3. 各层级详细说明

### 3.1 01_freqtrade/ - Freqtrade 执行层

**用途**：Freqtrade userdir，包含策略、配置、数据、回测产物

**目录结构**：
```
01_freqtrade/
├── strategies/            # 策略文件（.py）
├── strategies_archive/    # 策略归档
├── config.json            # Freqtrade 配置
├── data/                  # 市场数据（OHLCV）
├── backtest_results/      # 回测结果
├── hyperopt_results/      # 超参优化结果
├── hyperopts/             # 超参优化配置
├── freqaimodels/          # FreqAI 模型
├── logs/                  # 日志文件
├── plot/                  # 图表输出
├── notebooks/             # Jupyter 笔记本
└── archive/               # 历史归档
```

**使用规范**：
- 所有策略开发在此目录进行
- 使用 `scripts/ft.ps1` 脚本执行 Freqtrade 命令
- 数据和日志默认不提交（见 .gitignore）

---

### 3.2 02_qlib_research/ - Qlib 研究层

**用途**：因子研究、模型训练、实验分析

**目录结构**：
```
02_qlib_research/
├── experiments/           # 实验代码
├── notebooks/             # Jupyter 笔记本
├── qlib_data/             # Qlib 数据（不提交）
└── models/                # 训练模型（不提交）
```

**使用规范**：
- 因子研究和模型训练在此目录进行
- 数据和模型默认不提交（体积大且可再生成）
- 研究结论提炼后移动到 `docs/knowledge/`

---

### 3.3 03_integration/ - 集成层

**用途**：桥接 Freqtrade 和 Qlib，提供共享代码

**目录结构**：
```
03_integration/
└── trading_system/        # 桥接代码（可被策略 import）
```

**使用规范**：
- 策略侧可以 `import` 此目录的代码
- 提供因子计算、信号生成等共享功能

---

### 3.4 04_shared/ - 共享配置

**用途**：存放可提交的配置模板

**目录结构**：
```
04_shared/
├── configs/               # Freqtrade JSON 配置模板
└── config/                # Qlib YAML 配置
```

**使用规范**：
- 配置文件脱敏后可提交
- 私密配置使用 `.local.json` 后缀（不提交）

---

### 3.5 scripts/ - 统一脚本入口

**用途**：所有脚本统一入口，强制使用

**目录结构**：
```
scripts/
├── ft.ps1                 # Freqtrade 命令封装
├── bootstrap.ps1          # 环境初始化
├── data/                  # 数据处理脚本
├── analysis/              # 分析脚本
├── evaluation/            # 评估脚本
├── qlib/                  # Qlib 相关脚本
├── workflows/             # 工作流脚本
├── tools/                 # 工具脚本
├── mcp/                   # MCP 相关脚本
└── archive/               # 归档脚本
    ├── cleanup/           # 清理脚本归档
    └── analysis/          # 分析脚本归档
```

**使用规范**：
- 所有脚本必须通过 `scripts/` 目录执行
- 临时脚本执行完成后移动到 `scripts/archive/`
- 不要在根目录直接创建脚本文件

---

### 3.6 docs/ - 权威文档

**用途**：项目文档、知识库、技术报告

**目录结构**：
```
docs/
├── knowledge/             # 知识库
│   ├── strategies/        # 策略相关知识
│   ├── factors/           # 因子相关知识
│   └── tools/             # 工具相关知识
├── guidelines/            # 规范指南
├── reports/               # 技术报告
├── evaluation/            # 评估报告
├── research/              # 研究笔记
├── setup/                 # 环境配置
└── archive/               # 归档文档
```

**使用规范**：
- 所有文档使用 Markdown 格式
- 遵循文档命名规范（见 `docs/guidelines/document_naming_conventions.md`）
- 过时文档定期归档到 `docs/archive/`

---

### 3.7 artifacts/ - 本地产物

**用途**：本地实验产物、临时文件（不提交）

**目录结构**：
```
artifacts/
└── temp/                  # 临时文件存放位置
```

**使用规范**：
- 所有临时数据文件存放到 `artifacts/temp/`
- 每月第一周清理过期文件
- 整个 `artifacts/` 目录不提交到 Git

---

## 4. 临时文件管理规范

### 4.1 临时文件类型

**临时数据文件**：
- CSV 数据文件（factor_data*.csv）
- 数据库文件（*.db）
- 日志文件（*.log、*.txt）

**临时脚本文件**：
- 检查脚本（check_*.py）
- 分析脚本（analyze_*.py）
- 准备脚本（prepare_*.py）

### 4.2 存放位置

| 文件类型 | 存放位置 | 清理策略 |
|---------|---------|---------|
| 临时数据文件 | `artifacts/temp/` | 每月第一周清理 |
| 临时脚本文件 | `scripts/archive/` | 执行完成后归档 |
| 根目录临时文件 | ❌ 禁止 | 立即移动或删除 |

### 4.3 .gitignore 规则

已配置的忽略规则：
```gitignore
# 临时数据文件
factor_data*.csv
*.db
export_log.txt

check_*.py
analyze_*.py
prepare_*.py
```

---

## 5. 常见问题

### 5.1 为什么根目录不能有临时文件？

**原因**：
- 根目录是项目的门面，应保持整洁
- 临时文件污染会降低项目可维护性
- 容易误提交到 Git

**解决方案**：
- 临时数据文件 → `artifacts/temp/`
- 临时脚本文件 → `scripts/archive/`

### 5.2 策略文件应该放在哪里？

**答案**：`01_freqtrade/strategies/`

**原因**：
- 这是 Freqtrade 的 userdir
- 所有策略开发统一在此目录
- 根目录的 `strategies/` 已删除

### 5.3 如何清理过期文件？

**定期清理**（每月第一周）：
```bash
# 清理临时数据文件
rm -rf artifacts/temp/*

# 检查归档脚本
ls scripts/archive/
```

---

## 6. 参考资源

- 文档命名规范：`docs/guidelines/document_naming_conventions.md`
- 归档策略：`docs/guidelines/archive_policy.md`
- 项目结构分析报告：`docs/reports/project_structure_analysis_2026-01-17.md`

---

**文档版本**：v1.0
**创建日期**：2026-01-17
**状态**：已完成
