# 更新 Freqtrade（How to update）

这份文档由 Freqtrade 官方页面离线保存后整理为便于“vibe coding 查阅使用”的 Markdown。

- 来源：https://www.freqtrade.io/en/stable/updating/
- 离线保存时间：Mon Jan 05 2026 11:45:52 GMT+0800 (中国标准时间)

## 0) 本仓库的推荐运行方式（Windows + uv）

本仓库使用 `uv` 管理环境，且仓库根目录就是 Freqtrade 的 `userdir`，建议命令统一写成：

```bash
uv run freqtrade <命令> --userdir "." <参数...>
```

下文若出现 `freqtrade ...` 的官方示例，你可以直接在前面加上 `uv run`，并补上 `--userdir "."`。

---

## 1) 目录速览（H2）

下面列出原文的一级小节标题（H2），便于你快速定位内容：

- Docker
- Installation via setup script
- Plain native installation

---

## 2) 原文（自动 Markdown 化，便于搜索与复制）

To update your freqtrade installation, please use one of the below methods, corresponding to your installation method.

Tracking changes

Breaking changes / changed behavior will be documented in the changelog that is posted alongside every release.
For the develop branch, please follow PR's to avoid being surprised by changes.

### Docker

Legacy installations using the `master` image

We're switching from master to stable for the release Images - please adjust your docker-file and replace `freqtradeorg/freqtrade:master` with `freqtradeorg/freqtrade:stable`

```text
docker compose pull
docker compose up -d
```

### Installation via setup script

```text
./setup.sh --update
```

Note

Make sure to run this command with your virtual environment disabled!

### Plain native installation

Please ensure that you're also updating dependencies - otherwise things might break without you noticing.

```bash
git pull
pip install -U -r requirements.txt
pip install -e .

# Ensure freqUI is at the latest version
freqtrade install-ui
```

#### Problems updating

Update-problems usually come missing dependencies (you didn't follow the above instructions) - or from updated dependencies, which fail to install (for example TA-lib).
Please refer to the corresponding installation sections (common problems linked below)

