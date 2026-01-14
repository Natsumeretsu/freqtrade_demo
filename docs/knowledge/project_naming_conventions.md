# 项目统一命名规范（v1）

目标：让“代码/配置/文档”对同一件事使用同一套名字，避免出现「名称看不出是现货还是合约」「执行器/规则策略混在一起」这种长期维护成本。

---

## 1) 核心对象的命名规则

### 1.1 Freqtrade 策略（类名/文件名）

**统一格式：**

`SmallAccount{Market}{Style}{Variant}V{N}`

- `SmallAccount`：账户规模定位（当前仓库主线都是 small account）
- `Market`：市场类型（二选一）
  - `Spot`：现货
  - `Futures`：合约（USDT 本位永续为主）
- `Style`：策略风格/交易范式（例如 `Trend` / `Reversion` / `Timing`）
- `Variant`：该风格下的变体或角色（例如 `Filtered` / `Hybrid` / `Sma200` / `Exec`）
- `V{N}`：版本号（只增不减，避免历史复现被覆盖）

**约定：**
- 策略文件名与类名一致（例如 `SmallAccountSpotTrendFilteredV1.py` 内部类名同名）。
- 如该策略有参数文件（Freqtrade parameter file），文件名同样与策略名一致：`<StrategyName>.json`。

---

## 2) 配置文件命名规则（Freqtrade JSON）

**统一格式：**

`config_small_{market}_{purpose}_{timeframe}.json`

- `market`：`spot` / `futures`
- `purpose`：用途（例如 `base` / `profit_first` / `timing_exec`）
- `timeframe`：该配置默认用于的策略主周期（例如 `4h` / `15m`）

> 说明：配置名要能一眼看出“跑什么市场/什么目标/什么频率”，避免打开文件才知道。

---

## 3) 择时执行器的 policy（YAML）

**统一格式：**

`timing_policy_{exchange}_{market}_{main_tf}_{confirm_tf}.yaml`

示例：`timing_policy_okx_futures_15m_1h.yaml`

---

## 4) 旧 → 新命名映射（本仓库已统一）

| 旧策略名 | 新策略名 | 说明 |
| --- | --- | --- |
| `SmallAccountTrendFilteredV1` | `SmallAccountSpotTrendFilteredV1` | 补齐 `Spot` 语义 |
| `SmallAccountTrendHybridV1` | `SmallAccountSpotTrendHybridV1` | 补齐 `Spot` 语义 |
| `SmallAccountSma200TrendV1` | `SmallAccountSpotSma200TrendV1` | 补齐 `Spot` 语义 |
| `SmallAccountReversionV1` | `SmallAccountSpotReversionV1` | 补齐 `Spot` 语义 |
| `SmallAccountFuturesTimingV1` | `SmallAccountFuturesTimingExecV1` | 明确是“policy 驱动的通用执行器” |

---

## 5) 落地要求（强制）

1. 新增策略/配置/文档引用时，必须使用新命名；禁止混用旧名。
2. 策略名发生变化时，必须同步更新：
   - `01_freqtrade/strategies/<StrategyName>.py`
   - `01_freqtrade/strategies/<StrategyName>.json`（如存在）
   - `04_shared/configs/**` 中引用到的默认策略名（如有）
   - `docs/**`、`scripts/**` 中的复现命令与路径说明

