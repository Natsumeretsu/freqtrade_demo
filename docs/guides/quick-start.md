# 快速开始指南

本指南帮助你快速搭建环境并运行第一个回测。

---

## 环境要求

- **操作系统**: Windows 10/11
- **Python**: 3.11+
- **工具**: uv（Python 包管理器）、PowerShell 7+

---

## 1. 环境初始化

运行初始化脚本，自动安装依赖：

```powershell
./scripts/bootstrap.ps1
```

该脚本会：
- 检查 Python 版本
- 使用 uv 同步依赖
- 验证环境配置

---

## 2. 下载数据

下载 ETH/USDT 历史数据（示例）：

```powershell
./scripts/data/download.ps1 `
  -Pairs "ETH/USDT:USDT" `
  -Timeframes "5m" `
  -TradingMode "futures" `
  -Timerange "20230101-"
```

---

## 3. 运行回测

### 单策略回测

```powershell
./scripts/ft.ps1 backtesting `
  --strategy SimpleMVPStrategy `
  --config ft_userdir/config.json
```

### 批量回测

```powershell
./scripts/backtest.ps1 -Strategies "SimpleMVPStrategy,ETHHighFreqStrategy"
```

回测结果将保存到 `docs/reports/backtest/` 目录。

---

## 4. 查看结果

回测完成后，查看生成的报告：

```powershell
# 查看 Markdown 报告
cat docs/reports/backtest/latest/report.md

# 或在浏览器中打开
start docs/reports/backtest/latest/report.md
```

---

## 5. 下一步

- [因子开发指南](factor-development.md) - 学习如何开发自定义因子
- [回测指南](backtesting-guide.md) - 深入了解回测流程
- [策略开发指南](strategy-development.md) - 开发自己的交易策略

---

## 常见问题

### Q: 如何查看可用策略？

```powershell
./scripts/ft.ps1 list-strategies
```

### Q: 如何修改回测参数？

编辑配置文件 `ft_userdir/config.json`，修改以下参数：
- `stake_amount`: 每次交易金额
- `max_open_trades`: 最大持仓数量
- `timeframe`: K线周期

### Q: 回测失败怎么办？

1. 检查数据是否下载完整
2. 查看错误日志
3. 确认策略文件语法正确

---

**最后更新**: 2026-01-19
