# 脚本目录说明

本目录包含项目自动化脚本，按功能分类组织。

---

## 📁 目录结构

```
scripts/
├── bootstrap.ps1           # 环境初始化脚本
├── ft.ps1                  # Freqtrade 命令包装器
├── data/                   # 数据相关脚本
│   ├── download.ps1        # 数据下载
│   └── dashboard.py        # 数据仪表板
├── lib/                    # 公共库
│   ├── common.ps1          # PowerShell 公共函数
│   ├── backtest_utils.py   # 回测工具
│   └── format_utils.py     # 格式化工具
├── mcp/                    # MCP 配置脚本
│   ├── setup_claude.ps1    # Claude MCP 配置
│   └── setup_codex.ps1     # Codex MCP 配置
└── tools/                  # 开发工具
    └── vbrain_mcp_server.py # vbrain MCP 服务器
```

---

## 🚀 核心脚本

### bootstrap.ps1
**用途**：一键初始化项目环境

**功能**：
- 安装 Python 3.11
- 同步依赖（uv sync）
- 验证环境配置

**使用**：
```powershell
./scripts/bootstrap.ps1
```

---

### ft.ps1
**用途**：Freqtrade 命令包装器

**功能**：
- 自动设置 `--userdir "./ft_userdir"`
- 注入 `PYTHONPATH=integration`
- 统一命令入口

**使用**：
```powershell
# 查看策略列表
./scripts/ft.ps1 list-strategies

# 回测
./scripts/ft.ps1 backtesting --strategy SimpleMVPStrategy --config ft_userdir/config.json

# 超参优化
./scripts/ft.ps1 hyperopt --strategy SimpleMVPStrategy --hyperopt-loss SharpeHyperOptLoss
```

---

## 📊 数据脚本

### data/download.ps1
**用途**：下载交易所历史数据

**使用**：
```powershell
./scripts/data/download.ps1 `
  -Pairs "BTC/USDT:USDT" `
  -Timeframes "15m" `
  -TradingMode "futures" `
  -Timerange "20200101-"
```

---

## 🔧 开发工具

### tools/vbrain_mcp_server.py
**用途**：vbrain MCP 服务器（工作流编排）

**功能**：
- 统一入口
- 闭环自动化
- 任务编排

---

## ⚠️ 重要约定

1. **禁止直接运行 freqtrade**：必须通过 `./scripts/ft.ps1` 执行
2. **路径规范**：所有脚本使用相对路径，从项目根目录执行
3. **编码规范**：PowerShell 脚本使用 UTF-8 BOM，Python 脚本使用 UTF-8

---

**最后更新**：2026-01-18
