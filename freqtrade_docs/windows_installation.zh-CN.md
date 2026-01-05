# Windows installation（Windows installation）

这份文档由 Freqtrade 官方页面离线保存后整理为便于“vibe coding 查阅使用”的 Markdown。

- 来源：https://www.freqtrade.io/en/stable/windows_installation/
- 离线保存时间：Mon Jan 05 2026 11:35:13 GMT+0800 (中国标准时间)

## 0) 本仓库的推荐运行方式（Windows + uv）

本仓库使用 `uv` 管理环境，且仓库根目录就是 Freqtrade 的 `userdir`，建议命令统一写成：

```bash
uv run freqtrade <命令> --userdir "." <参数...>
```

下文若出现 `freqtrade ...` 的官方示例，你可以直接在前面加上 `uv run`，并补上 `--userdir "."`。

---

## 1) 目录速览（H2）

下面列出原文的一级小节标题（H2），便于你快速定位内容：

- Clone the git repository
- Install freqtrade automatically
- Install freqtrade manually

---

## 2) 原文（自动 Markdown 化，便于搜索与复制）

We **strongly** recommend that Windows users use [Docker](https://www.freqtrade.io/en/stable/docker_quickstart/) as this will work much easier and smoother (also more secure).

If that is not possible, try using the Windows Linux subsystem (WSL) - for which the Ubuntu instructions should work.
Otherwise, please follow the instructions below.

All instructions assume that python 3.11+ is installed and available.

### Clone the git repository

First of all clone the repository by running:

```text
git clone https://github.com/freqtrade/freqtrade.git
```

Now, choose your installation method, either automatically via script (recommended) or manually following the corresponding instructions.

### Install freqtrade automatically

#### Run the installation script

The script will ask you a few questions to determine which parts should be installed.

```text
Set-ExecutionPolicy -ExecutionPolicy Bypass
cd freqtrade
. .\setup.ps1
```

### Install freqtrade manually

64bit Python version

Please make sure to use 64bit Windows and 64bit Python to avoid problems with backtesting or hyperopt due to the memory constraints 32bit applications have under Windows.
32bit python versions are no longer supported under Windows.

Hint

Using the [Anaconda Distribution](https://www.anaconda.com/distribution/) under Windows can greatly help with installation problems. Check out the [Anaconda installation section](https://www.freqtrade.io/en/stable/installation/#installation-with-conda) in the documentation for more information.

#### Error during installation on Windows

```text
error: Microsoft Visual C++ 14.0 is required. Get it with "Microsoft Visual C++ Build Tools": http://landinghub.visualstudio.com/visual-cpp-build-tools
```

Unfortunately, many packages requiring compilation don't provide a pre-built wheel. It is therefore mandatory to have a C/C++ compiler installed and available for your python environment to use.

You can download the Visual C++ build tools from [here](https://visualstudio.microsoft.com/visual-cpp-build-tools/) and install "Desktop development with C++" in it's default configuration. Unfortunately, this is a heavy download / dependency so you might want to consider WSL2 or [docker compose](https://www.freqtrade.io/en/stable/docker_quickstart/) first.

