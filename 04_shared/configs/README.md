# 配置模板（`04_shared/configs/`）

更新日期：2026-01-17

本目录用于存放**可提交、可复制**的配置模板（均为脱敏示例）。

- 通用模板：`04_shared/configs/config.example.json`
- 私密模板：`04_shared/configs/config-private.example.json`（示例仅占位符；真实密钥请只放到你自己的 `config-private.json`）
- FreqAI 示例（已归档）：`04_shared/configs/archive/freqai/lgbm_trend_v1.json`
- Qlib 研究/集成（YAML 配置）：`04_shared/config/paths.yaml`、`04_shared/config/symbols.yaml`

## 0) 最小使用方式

```powershell
Copy-Item "04_shared/configs/config.example.json" "01_freqtrade/config.json"
Copy-Item "04_shared/configs/config-private.example.json" "01_freqtrade/config-private.json"

./scripts/ft.ps1 show-config --config "01_freqtrade/config.json" --config "01_freqtrade/config-private.json"
```

说明：

- `01_freqtrade/config.json` / `01_freqtrade/config-private.json` 是运行期配置；请确保私密信息只写入 `*-private*` 文件（并保持 gitignore）。
- FreqAI 训练/预测产物会自动写入 `01_freqtrade/models/<identifier>/`，默认被 gitignore。
- Qlib 相关脚本默认读取 `04_shared/config/*.yaml`，并允许用 `.env` 覆盖路径（例如 `QLIB_DATA_DIR`）。
