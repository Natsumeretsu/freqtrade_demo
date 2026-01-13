# 自定义 FreqAI 预测模型（freqaimodels/）

本目录用于存放**自定义 FreqAI 预测模型**（Python 代码），供 Freqtrade 通过 `--freqaimodel` 加载。

要点：

- 训练/回测产物（模型文件、预测数据等）会自动写入 `01_freqtrade/models/<identifier>/`，不要放在这里。
- 自定义模型通常需要继承 Freqtrade 的 `IFreqaiModel`，并按需重写 `fit()` / `train()` / `predict()` 等方法。

## 0) 如何使用

1. 新建一个 `*.py` 文件，并在其中定义模型类（类名将作为 `--freqaimodel` 的值）。
2. 运行时指定模型类名：

```powershell
./scripts/ft.ps1 backtesting --config "04_shared/configs/archive/freqai/lgbm_trend_v1.json" --strategy-path "01_freqtrade/strategies_archive" --strategy "FreqaiLGBMTrendStrategy" --freqaimodel "<YourModelClassName>"
```

参考：

- `docs/archive/freqtrade_docs/freqai_configuration.zh-CN.md`（自定义模型放置位置与加载方式）
- `docs/archive/freqtrade_docs/freqai_developers.zh-CN.md`（FreqAI 文件结构与开发说明）
