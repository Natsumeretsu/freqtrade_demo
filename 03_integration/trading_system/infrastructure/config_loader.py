from __future__ import annotations

"""
config_loader.py - 统一的配置加载工具（YAML + .env）

设计原则：
- “可复现”：默认配置写入仓库可提交目录（04_shared/config/）
- “可覆盖”：本地差异通过 .env 覆盖（.env 默认 gitignore）
"""

import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv


class ConfigManager:
    """配置管理器：加载 04_shared/config/*.yaml，并读取 .env 覆盖。"""

    def __init__(
        self,
        *,
        config_dir: str | Path | None = None,
        env_file: str | Path = ".env",
        repo_root: str | Path | None = None,
    ) -> None:
        # __file__ = 03_integration/trading_system/infrastructure/config_loader.py
        # repo_root = .../freqtrade_demo
        self.repo_root = Path(repo_root).resolve() if repo_root else Path(__file__).resolve().parents[3]
        self.config_dir = (
            (self.repo_root / "04_shared/config") if config_dir is None else (self.repo_root / Path(config_dir))
        ).resolve()

        # 先加载 .env（只读、非强制），用于覆盖路径/开关等
        env_path = (self.repo_root / Path(env_file)).resolve()
        if env_path.is_file():
            load_dotenv(dotenv_path=env_path, override=False)

        self.configs: dict[str, Any] = {}
        self._load_all_yaml()

    def _load_all_yaml(self) -> None:
        if not self.config_dir.is_dir():
            raise FileNotFoundError(f"配置目录不存在：{self.config_dir.as_posix()}")

        yaml_files = sorted(self.config_dir.glob("*.yaml")) + sorted(self.config_dir.glob("*.yml"))
        if not yaml_files:
            raise FileNotFoundError(f"配置目录下未找到任何 .yaml/.yml：{self.config_dir.as_posix()}")

        for path in yaml_files:
            name = path.stem
            with path.open("r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            if not isinstance(data, dict):
                raise ValueError(f"配置文件必须为 YAML dict：{path.as_posix()}")
            self.configs[name] = data

    def get(self, key: str, default: Any = None) -> Any:
        """获取配置值，支持点号分隔的嵌套查询（例如 symbols.pairs）。"""
        parts = [p for p in str(key or "").split(".") if p]
        if not parts:
            return default

        value: Any = self.configs
        for part in parts:
            if not isinstance(value, dict):
                return default
            value = value.get(part)
            if value is None:
                return default
        return value

    def get_env(self, key: str, default: Any = None) -> Any:
        v = os.getenv(str(key or "").strip(), "")
        return v if v != "" else default

    @property
    def freqtrade_exchange(self) -> str:
        return str(self.get_env("FREQTRADE_EXCHANGE", self.get("paths.freqtrade.exchange", "okx"))).strip()

    @property
    def freqtrade_data_dir(self) -> Path:
        """
        Freqtrade 数据根目录（优先 env：FREQTRADE_DATA_DIR，其次 YAML：paths.freqtrade.data_root）。
        注意：多数脚本会在其下拼接 exchange 子目录（如 01_freqtrade/data/okx）。
        """
        raw = self.get_env("FREQTRADE_DATA_DIR", self.get("paths.freqtrade.data_root", "01_freqtrade/data"))
        return (self.repo_root / Path(str(raw))).resolve()

    @property
    def qlib_data_dir(self) -> Path:
        raw = self.get_env("QLIB_DATA_DIR", self.get("paths.qlib.data_root", "02_qlib_research/qlib_data"))
        return (self.repo_root / Path(str(raw))).resolve()

    @property
    def qlib_model_dir(self) -> Path:
        raw = self.get_env("QLIB_MODEL_DIR", self.get("paths.qlib.model_root", "02_qlib_research/models/qlib"))
        return (self.repo_root / Path(str(raw))).resolve()

    @property
    def model_version(self) -> str:
        return str(self.get_env("QLIB_MODEL_VERSION", "v1")).strip() or "v1"

    def pairs(self) -> list[str]:
        pairs = self.get("symbols.pairs", []) or []
        return [str(p).strip() for p in pairs if str(p).strip()]

    def qlib_symbols(self) -> list[str]:
        syms = self.get("symbols.qlib_symbols", []) or []
        return [str(s).strip() for s in syms if str(s).strip()]

    def koopman_config(self) -> dict:
        """获取 Koopman 配置（带默认值）"""
        defaults = {
            "window": 512,
            "embed_dim": 16,
            "stride": 10,
            "ridge": 0.001,
            "pred_horizons": [1, 4],
            "fft_window": 512,
            "fft_topk": 8,
        }
        raw = self.get("trading_system.koopman", {}) or {}
        return {**defaults, **raw}

    def display(self) -> str:
        """返回可打印的配置摘要（不直接 print，便于脚本复用）。"""
        lines = [
            "=== trading_system 配置摘要 ===",
            f"- repo_root: {self.repo_root.as_posix()}",
            f"- config_dir: {self.config_dir.as_posix()}",
            f"- freqtrade_exchange: {self.freqtrade_exchange}",
            f"- freqtrade_data_dir: {self.freqtrade_data_dir.as_posix()}",
            f"- qlib_data_dir: {self.qlib_data_dir.as_posix()}",
            f"- qlib_model_dir: {self.qlib_model_dir.as_posix()}",
            f"- model_version: {self.model_version}",
            f"- pairs: {self.pairs()}",
            f"- qlib_symbols: {self.qlib_symbols()}",
            "===========================",
        ]
        return "\n".join(lines)


_CONFIG: ConfigManager | None = None


def get_config() -> ConfigManager:
    """获取全局配置单例。"""
    global _CONFIG
    if _CONFIG is None:
        _CONFIG = ConfigManager()
    return _CONFIG


if __name__ == "__main__":
    cfg = get_config()
    print(cfg.display())
