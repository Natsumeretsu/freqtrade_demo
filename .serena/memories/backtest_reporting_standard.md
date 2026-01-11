# 回测输出标准（强制）

## 一、回测摘要格式（CLI 输出必须包含）

### 表1: 基本信息

| 字段 | 值 | 路径 |
|------|-----|------|
| 策略名称 | FreqaiMoonshotStandalone | strategies/FreqaiMoonshotStandalone.py |
| 配置文件 | lgbm_moonshot_futures_v1 | configs/freqai/lgbm_moonshot_futures_v1.json |
| ML 模型 | LightGBMRegressor | (freqtrade 内置) |
| Freqtrade 版本 | 2026.1-dev-xxxxxx | - |
| 交易所 | OKX (futures) | - |
| 回测区间 | 2025-12-11 → 2026-01-09 (**29天**) | - |
| 训练窗口 | 2024-12-11 → 2025-12-10 (365天) | - |
| 时间周期 | 1h | - |

### 表2: 综合绩效表

纵轴=交易对，横轴=核心指标，最后一行为 **TOTAL**

| 交易对 | 交易数 | 胜/平/负 | 胜率 | 收益率 | 回撤 | PF | 平均持仓 |
|--------|--------|----------|------|--------|------|-----|----------|
| BTC/USDT:USDT | 5 | 4/0/1 | 80% | +2.3% | 1.2% | 2.1 | 8h |
| ETH/USDT:USDT | 3 | 2/0/1 | 67% | +1.1% | 0.8% | 1.8 | 6h |
| **TOTAL** | **8** | **6/0/2** | **75%** | **+3.4%** | **1.5%** | **2.0** | **7h** |

**补充指标**（单行）：
- 起始/最终资金、CAGR、日均收益、总交易量
- 最大回撤金额+百分比+持续时间+起止日期
- Sortino、最佳/最差交易

### 表3: 入场/出场明细（按交易对分组）

```
BTC/USDT:USDT:
| Enter Tag | Exit Reason | 次数 | 胜率 | 平均收益 |
|-----------|-------------|------|------|----------|
| FREQAI_LONG | ROI | 3 | 100% | +1.5% |
| FREQAI_LONG | STOPLOSS | 1 | 0% | -5.0% |

ETH/USDT:USDT:
| Enter Tag | Exit Reason | 次数 | 胜率 | 平均收益 |
|-----------|-------------|------|------|----------|
| FREQAI_LONG | FREQAI_SMART_EXIT | 2 | 100% | +1.1% |
```

### 问题分析（可选）

当结果异常时（如交易过少、胜率过低、回撤过大），需附带可能原因分析

---

- 样本窗口：默认使用当前数据目录中“最早~最新”的完整周期（覆盖上涨/下跌/震荡）；若做 Train/Val/Test 或分年拆分，每个区间同样输出完整报表。
- 输出形式：必须提供表格报表，优先 HTML，其次 CSV；纵轴=交易对，横轴=指标；并包含与 Market change 的对比。
- Market change 口径：逐交易对用本地 OHLCV 计算 `close_end/close_start-1`（%），区间使用回测结果 JSON 的 `backtest_start/backtest_end`（已含 startup_candle_count 偏移）以保证对齐。
- 工具/脚本：统一使用 `scripts/backtest_pair_report.py` 从回测 zip 生成 `plot/<Strategy>_per_pair_report_<YYYYMMDD>_<YYYYMMDD>.html` + `.csv`。
- 注意：避免最小下单伪影（必要时提高 `dry_run_wallet` 或合理设置 `max_open_trades/stake_amount`），否则会出现“0 交易”污染结论。