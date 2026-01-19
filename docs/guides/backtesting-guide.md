# 回测指南

本指南介绍如何进行策略回测和结果分析。

---

## 回测流程

```
数据准备 → 配置策略 → 执行回测 → 分析结果 → 优化参数
```

---

## 1. 数据准备

### 下载历史数据

```powershell
./scripts/data/download.ps1 `
  -Pairs "ETH/USDT:USDT" `
  -Timeframes "5m" `
  -TradingMode "futures" `
  -Timerange "20230101-20231231"
```

### 验证数据完整性

```powershell
./scripts/ft.ps1 list-data
```

---

## 2. 配置策略

编辑 `ft_userdir/config.json`：

```json
{
  "stake_currency": "USDT",
  "stake_amount": 100,
  "max_open_trades": 3,
  "timeframe": "5m",
  "dry_run": true
}
```

---

## 3. 执行回测

### 单策略回测

```powershell
./scripts/ft.ps1 backtesting `
  --strategy SimpleMVPStrategy `
  --config ft_userdir/config.json `
  --timerange 20230101-20231231
```

### 批量回测

```powershell
./scripts/backtest.ps1 `
  -Strategies "SimpleMVPStrategy,ETHHighFreqStrategy" `
  -Timerange "20230101-20231231"
```

---

## 4. 分析结果

### 关键指标

- **总交易次数**: 交易频率
- **胜率**: 盈利交易占比
- **总收益率**: 累计收益
- **最大回撤**: 最大亏损幅度
- **夏普比率**: 风险调整后收益
- **索提诺比率**: 下行风险调整后收益

### 查看报告

```powershell
# 查看 Markdown 报告
cat docs/reports/backtest/latest/report.md
```

---

## 5. 参数优化

使用 Hyperopt 进行参数优化：

```powershell
./scripts/ft.ps1 hyperopt `
  --strategy SimpleMVPStrategy `
  --hyperopt-loss SharpeHyperOptLoss `
  --epochs 100
```

---

## 最佳实践

### 1. 避免过拟合
- 使用样本外数据验证
- 限制参数数量
- 交叉验证

### 2. 考虑交易成本
- 手续费
- 滑点
- 资金费率

### 3. 风险管理
- 设置止损
- 控制仓位
- 分散投资

---

**最后更新**: 2026-01-19
