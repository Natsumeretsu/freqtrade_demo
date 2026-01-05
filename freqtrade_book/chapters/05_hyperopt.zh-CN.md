# 超参优化（Hyperopt）：让策略“可量化地变好”

[返回目录](../SUMMARY.zh-CN.md) | [上一章](./04_strategy_development.zh-CN.md) | [下一章](./06_live_risk.zh-CN.md)

## 本章目标

- 你能跑一次 hyperopt，并知道它在优化什么、输出怎么看。
- 你能在需要时写自定义 loss，并避免把 hyperopt 跑得很慢。

## 本章完成标准（学完你应该能做到）

- [ ] 能用小 `--epochs` 跑通一次 hyperopt（先求可用，再求最优）
- [ ] 会用 `hyperopt-show` 查看最优解或指定 epoch 的详细信息
- [ ] 知道用不同 `--timerange` 做 sanity check，避免过拟合
- [ ] 明白自定义 loss 需要高性能（避免把 hyperopt 拖成“永动机”）

---

## 0) 最小命令模板（先跑一个小实验）

```powershell
uv run freqtrade hyperopt --userdir "." --config "config.json" --strategy "SimpleTrendFollowV6" --timerange 20240101- --epochs 50
uv run freqtrade hyperopt-show --userdir "." --best -n -1 --print-json --no-header
```

### 0.1 关键输出检查点

- `hyperopt`：会生成 `hyperopt_results/` 下的结果文件（并在终端显示进度/最优解摘要）。
- `hyperopt-show`：能输出 JSON（代表成功读取并解析最新/最优结果）。

---

## 1) hyperopt 什么时候用？

当你已经有一个“能跑通回测、逻辑稳定”的策略后，才适合做超参优化：

- 先解决逻辑错误/信号缺陷
- 再用 hyperopt 调参（参数空间越大越慢，越容易过拟合）

---

## 2) 最小 hyperopt 模板

```powershell
uv run freqtrade hyperopt --userdir "." --config "config.json" --strategy "SimpleTrendFollowV6"
```

建议固定：

- `--timerange`：避免不同时段的市场状态导致结果不可比
- `--timeframe`：与策略一致

---

## 3) 如何看结果（最小读法）

先记住这条：hyperopt 输出的是“在某一段历史行情里，某套参数的表现”，它不是未来保证。

建议先看三类信息：

- 收益与回撤：不要只看收益率，至少配合一个回撤指标一起看。
- 稳定性：换一段 `--timerange` 跑同样的参数，结果是否还能站得住。
- 参数是否合理：例如止损/ROI 是否极端（极端往往意味着过拟合）。

你可以用 `hyperopt-show` 快速查看结果文件里的某个 epoch 或最优解（默认读取最新结果文件）：

```powershell
uv run freqtrade hyperopt-show --userdir "." -n 168
uv run freqtrade hyperopt-show --userdir "." --best -n -1 --print-json --no-header
```

---

## 4) 自定义 loss：性能第一

loss 每个 epoch 都会被调用一次，写得慢会把 hyperopt 拖成“永动机”。

原则：

- 只用必要字段
- 避免复杂循环/重计算
- 把可预计算的东西挪到外面

---

## 5) 练习：让 hyperopt 跑得“可控且可复现”

目标：你能在小样本上快速迭代，并避免一次跑到天荒地老。

1. 固定时间范围 + 少量 epochs 先跑通：

```powershell
uv run freqtrade hyperopt --userdir "." --config "config.json" --strategy "SimpleTrendFollowV6" --timerange 20240101- --epochs 50
```

2. 再把 `--timerange` 换一段（例如更早/更晚）做 sanity check，看看最优解是否“只在某段行情里好看”。

---

## 6) 排错速查（hyperopt 慢/结果奇怪）

- 跑得太慢：先缩小参数空间（spaces/自定义参数数量）、减少 `--timerange`、降低 `--epochs`；确认 loss 没写成 O(n²)。
- 结果特别“夸张”：优先怀疑过拟合或前视偏差；先做 `lookahead-analysis`，再继续调参。

---

## 延伸阅读（参考库）

- hyperopt：[`freqtrade_docs/hyperopt.zh-CN.md`](../../freqtrade_docs/hyperopt.zh-CN.md)
- hyperopt（高级）：[`freqtrade_docs/advanced_hyperopt.zh-CN.md`](../../freqtrade_docs/advanced_hyperopt.zh-CN.md)

---

[返回目录](../SUMMARY.zh-CN.md) | [上一章](./04_strategy_development.zh-CN.md) | [下一章](./06_live_risk.zh-CN.md)
