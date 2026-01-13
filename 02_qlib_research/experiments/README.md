# 实验记录（experiments/）

本目录用于存放“可复现、可对比”的实验记录（不存放训练产物）。

建议每个实验一个子目录，目录名与 `freqai.identifier` 对齐，例如：`experiments/lgbm_trend_v1/`。

每次实验至少记录：

- 配置文件路径（例如 `04_shared/configs/archive/freqai/lgbm_trend_v1.json`）
- 策略文件/策略类名
- 固定的 `--timerange` / `--timeframe` / 交易对列表
- 本次改动点（只改一个因素）
- 结论与下一步

注意：训练/回测产物会写入 `01_freqtrade/models/<identifier>/`，该目录默认被 git 忽略。
