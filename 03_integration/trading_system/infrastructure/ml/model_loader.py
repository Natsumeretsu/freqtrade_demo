from __future__ import annotations

"""
model_loader.py - 研究层模型加载与预测封装

对齐 docs/remp_research/Freqtrade + Qlib 工程改造 的导出格式约定：
- model.pkl            : joblib 保存的模型对象
- features.json        : {"features": [...]} 或 {"feature_columns": [...]}
- model_info.json      : 可选，训练元信息
"""

import json
import logging
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from joblib import load

logger = logging.getLogger(__name__)


class QlibModelLoader:
    """模型加载器：加载模型与特征清单，并提供 predict/predict_proba。"""

    def __init__(self, model_dir: str | Path) -> None:
        self.model_dir = Path(model_dir).expanduser().resolve()
        self.model: Any | None = None
        self.features: list[str] = []
        self.model_info: dict[str, Any] = {}

        self._load_model()
        self._load_features()
        self._load_model_info()

    def _load_model(self) -> None:
        model_file = self.model_dir / "model.pkl"
        if not model_file.is_file():
            raise FileNotFoundError(f"模型文件不存在：{model_file.as_posix()}")
        self.model = load(model_file)

    def _load_features(self) -> None:
        features_file = self.model_dir / "features.json"
        if not features_file.is_file():
            self.features = []
            return

        try:
            data = json.loads(features_file.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning("features.json 解析失败：%s (%s)", features_file.as_posix(), e)
            self.features = []
            return

        feats = data.get("features") or data.get("feature_columns") or []
        if not isinstance(feats, list):
            self.features = []
            return

        self.features = [str(f).strip() for f in feats if str(f).strip()]

    def _load_model_info(self) -> None:
        info_file = self.model_dir / "model_info.json"
        if not info_file.is_file():
            self.model_info = {}
            return

        try:
            self.model_info = json.loads(info_file.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning("model_info.json 解析失败：%s (%s)", info_file.as_posix(), e)
            self.model_info = {}

    def _prepare_X(self, X: pd.DataFrame | np.ndarray) -> np.ndarray:
        if isinstance(X, pd.DataFrame):
            if self.features:
                missing = [f for f in self.features if f not in X.columns]
                if missing:
                    raise ValueError(f"输入缺少必要特征列：{missing}")
                X = X[self.features]
            arr = X.values
        else:
            arr = X
        return np.asarray(arr, dtype="float64")

    def predict(self, X: pd.DataFrame | np.ndarray) -> np.ndarray:
        if self.model is None:
            raise RuntimeError("模型未加载")
        arr = self._prepare_X(X)
        return np.asarray(self.model.predict(arr))

    def predict_proba(self, X: pd.DataFrame | np.ndarray) -> np.ndarray:
        if self.model is None:
            raise RuntimeError("模型未加载")
        arr = self._prepare_X(X)
        if hasattr(self.model, "predict_proba"):
            return np.asarray(self.model.predict_proba(arr))
        raise AttributeError("模型不支持 predict_proba")

    def validate_features(self, dataframe: pd.DataFrame) -> bool:
        if not self.features:
            return True
        missing = set(self.features) - set(dataframe.columns)
        return len(missing) == 0

    def get_model_info(self) -> dict[str, Any]:
        return {
            "model_type": type(self.model).__name__ if self.model is not None else "unknown",
            "features": self.features,
            "info": self.model_info,
            "model_dir": self.model_dir.as_posix(),
        }


class ModelCache:
    """进程内模型缓存（避免每次入场都重复反序列化）。"""

    def __init__(self) -> None:
        self._loaders: dict[str, QlibModelLoader] = {}

    def get(self, model_dir: str | Path) -> QlibModelLoader:
        key = str(Path(model_dir).expanduser().resolve())
        loader = self._loaders.get(key)
        if loader is None:
            loader = QlibModelLoader(key)
            self._loaders[key] = loader
        return loader

    def clear(self) -> None:
        self._loaders.clear()
