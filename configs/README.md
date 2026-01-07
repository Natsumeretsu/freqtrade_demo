# 配置模板（configs/）

本目录用于存放**可提交、可复制**的配置模板（均为脱敏示例）。

- 通用模板：`configs/config.example.json`
- 私密模板：`configs/config-private.example.json`（示例仅占位符；真实密钥请只放到你自己的 `config-private.json`）
- FreqAI 示例：`configs/freqai/lgbm_trend_v1.json`

## 0) 最小使用方式

```powershell
Copy-Item "configs/config.example.json" "config.json"
Copy-Item "configs/config-private.example.json" "config-private.json"

./scripts/ft.ps1 show-config --config "config.json" --config "config-private.json"
```

说明：

- `config.json` / `config-private.json` 放在仓库根目录，默认会被 git 忽略（避免误提交密钥）。
- FreqAI 训练/预测产物会自动写入 `models/<identifier>/`，也默认被 git 忽略。
