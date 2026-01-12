# 变更摘要（2026-01-13）

## 背景与目标

- 目标 1：补齐 OKX 现货 2020-2022 历史数据，并验证可回测。
- 目标 2：为 `SmallAccountTrendFilteredV1` 增加可回测的风险开关因子（高阶趋势/波动率/流动性代理）与“软风险折扣”（仅调仓位，不改信号）。
- 目标 3：做一轮小范围参数邻域 + 多损失函数搜索，输出“收益-回撤-交易数”候选点集，并判断是否存在明确的无损改进。
- 目标 4：更新 vbrain（local_rag）向量索引，确保 `project_docs` 文档可检索。

## 关键变更

- 策略增强（现货）：
  - `strategies/SmallAccountTrendFilteredV1.py` 增加：
    - 高阶趋势门控（宏观 SMA + 斜率门槛）：`buy_use_macro_trend_filter` 等；
    - 波动率上限门控（`atr_pct`）：`buy_use_atr_pct_max_filter` 等；
    - 流动性代理门控（`volume_ratio`）：`buy_use_volume_ratio_filter` 等；
    - “软风险折扣”（不改信号，只改仓位）：`buy_use_*_stake_scale` 系列；
    - `informative_pairs` 追加日线（默认 `BTC/USDT 1d`）以支持宏观过滤；
    - `custom_stake_amount` 引入软折扣计算。
  - `strategies/SmallAccountTrendFilteredV1.json` 同步新增参数默认值。

- 搜索脚本（可复用）：
  - `scripts/analysis/pareto_neighborhood_search.ps1`：对参数 JSON 做小邻域随机扰动，重复回测并抽取指标，输出候选集与帕累托前沿。
  - `scripts/analysis/walk_forward_search.ps1`：先训练集搜索，再验证集复测，降低过拟合风险。

- 压力测试：
  - `scripts/analysis/stress_test.py`：补齐/增强蒙特卡洛压力测试能力（支持 `--slippage` 与 `--mode policy` 等）。

- 数据：
  - 通过 `scripts/data/download.ps1` 拉取 OKX 现货 `BTC/USDT` 的 `4h/1d` 数据并回填到 2020（`--prepend`）。

- vbrain（local_rag）：
  - 已将 `project_docs/**/*.md` 全部写入向量索引，便于后续检索与问答。

## 回测结论（OKX 现货，BTC/USDT，4h）

### baseline（当前 `SmallAccountTrendFilteredV1.json` 参数）

- 2020-2022（`20200101-20221231`）：
  - 总收益：`+116.05%`
  - 最大回撤（相对）：`19.04%`
  - 交易数：`54`

- 2020-2026（`20200101-20260108`，实际数据到 2026-01-04）：
  - 总收益：`+424.64%`（10 → 52.46 USDT，回测口径）
  - CAGR：`32.41%`
  - 最大回撤（相对）：`15.23%`
  - 交易数：`90`

- 2025（`20250101-20251231`）：
  - 总收益：`+15.91%`
  - 最大回撤（相对）：`4.03%`
  - 交易数：`5`

### 帕累托/邻域结论

- `pareto_neighborhood_search.ps1`（2020-2022，30 次邻域采样）：
  - 未发现“收益≥、回撤≤、交易数≥”三目标同时支配 baseline 的无损改进点。
  - baseline 在该目标定义下呈现“局部非支配”特征（不等价于全局最优）。

- `walk_forward_search.ps1`（训练 2020-2021，验证 2022，40 次邻域采样）：
  - baseline 在 2022 单年验证集上：`-0.97%`（交易数 8）
  - 在当前邻域与样本规模下，验证集未出现盈利候选点（按脚本的最小交易数约束）。
  - 解释：该策略框架偏“顺趋势做多”，在 2022 这类熊段环境下缺少稳定优势；更现实的处理是“风险关机/空仓”，或转合约体系加入做空能力。

### 压力测试（实盘含义的保守刻画）

- 对 2020-2026 回测结果做压力测试（`--mode policy --slippage 0.0005`，单边 0.05% 滑点假设）：
  - 回测口径下的最终权益会随滑点下降（示例：10 → 50.47 USDT）
  - 路径风险明显高于单一路径回测：最大回撤的中位数约 `27%`，最差 5% 情景约 `40%`

## 复现命令（PowerShell）

- 下载数据（回填 2020-2022，现货）：
  - `./scripts/data/download.ps1 -Pairs "BTC/USDT" -Timeframes "4h","1d" -Config "configs/small_account/config_small_spot_base.json" -TradingMode "spot" -Timerange "20200101-20221231" -Prepend`
- baseline 回测：
  - `./scripts/analysis/small_account_backtest.ps1 -Config "configs/small_account/config_small_spot_base.json" -Strategy "SmallAccountTrendFilteredV1" -Pairs "BTC/USDT" -Timeframe "4h" -Timerange "20200101-20260108"`
- 邻域帕累托搜索：
  - `./scripts/analysis/pareto_neighborhood_search.ps1 -Timerange "20200101-20221231" -Trials 30 -Seed 42`
- Walk-forward 搜索：
  - `./scripts/analysis/walk_forward_search.ps1 -TrainTimerange "20200101-20211231" -TestTimerange "20220101-20221231" -Trials 40 -Seed 42`
- 压力测试（示例）：
  - `uv run python -X utf8 "scripts/analysis/stress_test.py" --zip "backtest_results/bench_spot_small10_SmallAccountTrendFilteredV1_4h_2020_2026/backtest-result-2026-01-13_02-35-15.zip" --mode policy --simulations 2000 --seed 42 --slippage 0.0005 --json`

