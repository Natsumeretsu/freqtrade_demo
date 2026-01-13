# 环境准备（Windows + uv）与启动方式

[返回目录](../SUMMARY.zh-CN.md) | [上一章](./00_reading_guide.zh-CN.md) | [下一章](./02_configuration.zh-CN.md)

## 本章目标

- 你能在本仓库完成依赖安装，并能跑起 `freqtrade` 命令。
- 你能根据场景选择“本地安装 / Docker / 仅回测”路径。

## 本章完成标准（学完你应该能做到）

- [ ] 能成功执行 `uv sync --frozen`
- [ ] 能运行 `uv run freqtrade --version` 并输出版本
- [ ] 能运行 `uv run freqtrade --help` 并看到常见子命令（`download-data` / `backtesting` 等）
- [ ] 能运行 `uv run freqtrade show-config --userdir "." --config "config.json"`（或已用 `new-config` 生成配置）

---

## 0) 最小命令模板（本仓库）

```powershell
uv sync --frozen
uv run freqtrade --version
```

### 0.1 关键输出检查点

- `uv sync --frozen`：无报错退出（第一次跑会下载/安装依赖，耗时更长）。
- `uv run freqtrade --version`：能输出类似 `freqtrade <版本号>` 的版本信息。

---

## 1) 本仓库默认约束（先记住这三条）

1. Windows 环境，PowerShell 5.1。
2. 统一用 `uv` 管理虚拟环境（默认在 `./.venv/`）。
3. 依赖安装统一用 `uv sync --frozen`（以 `uv.lock` 为准）。

---

## 2) 一键初始化（推荐）

如果你想最省事，优先用仓库脚本：

```powershell
./scripts/bootstrap.ps1
```

---

## 3) 手动初始化（你需要知道发生了什么）

```powershell
uv sync --frozen
uv run freqtrade --version
```

如果 `uv run freqtrade --version` 能输出版本号，说明环境 OK。

---

## 4) 常见踩坑（Windows）

### 4.1 编译依赖（Visual C++ Build Tools）

某些依赖需要编译工具链（你会看到类似 “Microsoft Visual C++ 14.0 is required”）。
遇到这种情况不要硬猜，先按报错提示安装 Build Tools，再重跑 `uv sync --frozen`。

### 4.2 不同安装方式怎么选？

- 你只想回测/超参：本地安装即可（最快）。
- 你想跑 UI/做运维：Docker 往往更省心（隔离依赖，环境更一致）。

---

## 5) 练习：确认你真的能“跑命令”

1. 先确认命令列表（能看到 `download-data` / `backtesting` 等子命令就对了）：

```powershell
uv run freqtrade --help
```

2. 再确认 userdir 与配置能被识别（本仓库根目录就是 userdir）：

```powershell
uv run freqtrade show-config --userdir "." --config "config.json"
```

如果你还没有 `config.json`，可以先生成一份示例再回到本手册继续：

```powershell
uv run freqtrade new-config --userdir "."
```

你应该看到：

- `--help`：输出子命令列表（应包含 `download-data` / `backtesting` / `list-strategies` 等）。
- `show-config`：输出中包含 `Your combined configuration is:`（若没有 `config.json` 会报错，这是正常的）。
- `new-config`：进入交互式配置生成流程（会询问交易所/交易对/策略等）。

---

## 6) 排错速查（按出现频率）

- `uv` 找不到：先安装 uv，并确保在当前 PowerShell 会话可用。
- `uv sync` 编译失败：按报错提示安装 Visual C++ Build Tools，再重跑 `uv sync --frozen`。
- Python 版本不匹配：以 `.python-version` 为准，让 `uv` 自动切换。
- `freqtrade` 运行时报缺依赖：优先确认是否执行过 `uv sync --frozen`，不要用 `pip install` 乱装依赖。

---

## 延伸阅读（参考库）

- Windows 安装：[`freqtrade_docs/windows_installation.zh-CN.md`](../../freqtrade_docs/windows_installation.zh-CN.md)
- Linux/macOS/Raspberry 安装：[`freqtrade_docs/installation.zh-CN.md`](../../freqtrade_docs/installation.zh-CN.md)
- Docker 快速开始：[`freqtrade_docs/docker_quickstart.zh-CN.md`](../../freqtrade_docs/docker_quickstart.zh-CN.md)
- 高级安装后任务：[`freqtrade_docs/advanced_setup.zh-CN.md`](../../freqtrade_docs/advanced_setup.zh-CN.md)
- 更新 Freqtrade：[`freqtrade_docs/updating.zh-CN.md`](../../freqtrade_docs/updating.zh-CN.md)

---

[返回目录](../SUMMARY.zh-CN.md) | [上一章](./00_reading_guide.zh-CN.md) | [下一章](./02_configuration.zh-CN.md)
