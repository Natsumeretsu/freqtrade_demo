# FreqAI：机器学习工作流（先理解，再上手）

[返回目录](../SUMMARY.zh-CN.md) | [上一章](./07_ops_monitoring.zh-CN.md) | [下一章](./09_end_to_end_workflow.zh-CN.md)

## 本章目标

- 你能理解 FreqAI 的训练/推理/回测重训节奏，以及核心配置项。
- 你能判断“现在是否值得用 FreqAI”，避免盲目上模型导致过拟合。

## 本章完成标准（学完你应该能做到）

- [ ] 能解释 `train_period_days` / `backtest_period_days` / `identifier` 的作用与关系
- [ ] 能用 `identifier` 做实验隔离，并固定时间窗口让结果可对比、可复现
- [ ] 知道先跑通纯策略流程（数据→回测→迭代→风控）再引入 FreqAI
- [ ] 能用参数表/特征工程文档做“字典式查阅”，每次只改少量因素

---

## 0) 最小命令模板（先确认工具链可用）

```powershell
uv run freqtrade list-freqaimodels --userdir "."
```

如果你连“纯策略”流程还没跑顺（数据→回测→迭代→风控），建议先完成前面章节，再回来上 FreqAI。

### 0.1 关键输出检查点

- `list-freqaimodels`：能输出可用模型列表（证明 FreqAI 相关命令可用）。
- 若报 “command not found”/依赖问题：先回到“环境准备”章节把环境跑通。

---

## 1) 什么时候用 FreqAI？

FreqAI 会显著增加复杂度（数据、特征、训练、推理、版本管理）。

建议：

- 先把“纯策略”流程跑顺：数据 → 回测 → 迭代 → 风控
- 再把 FreqAI 当作增强模块引入（否则你很难定位问题来自哪里）

---

## 2) 你必须先搞懂的三个配置概念

- `train_period_days`：训练窗口长度（滑动窗口）
- `backtest_period_days`：训练一次后，用多少天做推理再重训（回测时的重训节奏）
- `identifier`：模型唯一标识（关系到模型复用与落盘路径）

---

## 3) 特征工程与参数表：把它当成字典用

FreqAI 的参数非常多，建议两种用法：

1. 先按官方示例跑通（少改参数）
2. 再对照参数表逐项理解（每次只改少量，便于归因）

---

## 4) 练习：把一次训练/推理流程做成“可复现实验”

目标：你能用 `identifier` 把每次实验隔离开，并能复现同一套配置的结果。

1. 先从官方示例配置起步（少改参数），设置一个明确的 `identifier`（例如 `my_first_freqai`）。
2. 固定训练与回测窗口（例如：固定 `train_period_days` 与 `backtest_period_days`），避免“你以为改了模型，其实是换了行情区间”。
3. 每次只改一个因素（一个特征、一个模型参数或一个标签定义），并记录结果与结论。

提示：本仓库已准备 `freqaimodels/` 目录用于落盘模型；`identifier` 变化会影响模型复用与路径。

---

## 5) 排错速查（FreqAI 常见卡点）

- 训练很慢：先减少特征数量与训练窗口，再谈更复杂的模型；优先保证“能跑通”。
- 结果不稳定：先怀疑过拟合；把 `identifier` 与时间窗口固定，再做对比实验。
- 模型复用混乱：确保 `identifier` 唯一且语义清晰（不要复用同名做不同实验）。

---

## 延伸阅读（参考库）

- FreqAI 介绍：[`freqtrade_docs/freqai.zh-CN.md`](../../freqtrade_docs/freqai.zh-CN.md)
- FreqAI 配置：[`freqtrade_docs/freqai_configuration.zh-CN.md`](../../freqtrade_docs/freqai_configuration.zh-CN.md)
- 运行 FreqAI：[`freqtrade_docs/freqai_running.zh-CN.md`](../../freqtrade_docs/freqai_running.zh-CN.md)
- 特征工程：[`freqtrade_docs/freqai_feature_engineering.zh-CN.md`](../../freqtrade_docs/freqai_feature_engineering.zh-CN.md)
- 参数表：[`freqtrade_docs/freqai_parameter_table.zh-CN.md`](../../freqtrade_docs/freqai_parameter_table.zh-CN.md)
- 强化学习：[`freqtrade_docs/freqai_reinforcement_learning.zh-CN.md`](../../freqtrade_docs/freqai_reinforcement_learning.zh-CN.md)
- 开发者指南：[`freqtrade_docs/freqai_developers.zh-CN.md`](../../freqtrade_docs/freqai_developers.zh-CN.md)

---

[返回目录](../SUMMARY.zh-CN.md) | [上一章](./07_ops_monitoring.zh-CN.md) | [下一章](./09_end_to_end_workflow.zh-CN.md)
