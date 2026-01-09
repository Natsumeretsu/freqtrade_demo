# 回测输出标准（强制）

- 样本窗口：默认使用当前数据目录中“最早~最新”的完整周期（覆盖上涨/下跌/震荡）；若做 Train/Val/Test 或分年拆分，每个区间同样输出完整报表。
- 输出形式：必须提供表格报表，优先 HTML，其次 CSV；纵轴=交易对，横轴=指标；并包含与 Market change 的对比。
- Market change 口径：逐交易对用本地 OHLCV 计算 `close_end/close_start-1`（%），区间使用回测结果 JSON 的 `backtest_start/backtest_end`（已含 startup_candle_count 偏移）以保证对齐。
- 工具/脚本：统一使用 `scripts/backtest_pair_report.py` 从回测 zip 生成 `plot/<Strategy>_per_pair_report_<YYYYMMDD>_<YYYYMMDD>.html` + `.csv`。
- 注意：避免最小下单伪影（必要时提高 `dry_run_wallet` 或合理设置 `max_open_trades/stake_amount`），否则会出现“0 交易”污染结论。