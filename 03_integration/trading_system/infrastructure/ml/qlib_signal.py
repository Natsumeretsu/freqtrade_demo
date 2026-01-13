from __future__ import annotations

"""
qlib_signal.py - 研究层模型信号服务（在线预测 + 缓存）

职责：
- 按项目约定目录加载模型，并为“当前时刻”输出上涨概率（predict_proba 的正类概率）
- 复用与训练一致的特征构造（trading_system.infrastructure.ml.features）
- 提供 side_proba / soft_scale / hard_fuse 等通用映射函数，便于策略侧复用

说明：
- 本模块不依赖真实 Qlib；仅复用本仓库的模型导出约定（model.pkl + features.json）。
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from trading_system.domain.symbols import freqtrade_pair_to_symbol
from trading_system.infrastructure.config_loader import ConfigManager, get_config
from trading_system.infrastructure.freqtrade_data import get_analyzed_dataframe_upto_time, get_last_candle_timestamp
from trading_system.infrastructure.ml.features import build_last_row_features
from trading_system.infrastructure.ml.model_loader import ModelCache

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class QlibSignalParams:
    """服务侧参数（策略参数不在这里定义，避免强耦合）。"""

    min_history_rows: int = 100


class QlibSignalService:
    """
    Qlib 风格“方向概率”服务：
    - entry_proba_up：返回“未来上涨概率”
    - 内置轻量缓存：同一交易对、同一根 K 线只算一次
    """

    def __init__(
        self,
        *,
        cfg: ConfigManager | None = None,
        model_cache: ModelCache | None = None,
        params: QlibSignalParams | None = None,
    ) -> None:
        self._cfg = cfg or get_config()
        self._cache = model_cache or ModelCache()
        self._p = params or QlibSignalParams()

        # (pair,timeframe) -> (candle_ts, proba)
        self._proba_cache: dict[tuple[str, str], tuple[pd.Timestamp, float]] = {}
        self._warned_model_dirs: set[str] = set()

    def model_dir(self, *, pair: str, timeframe: str) -> Path:
        """
        约定的模型目录：
        02_qlib_research/models/qlib/<version>/<exchange>/<timeframe>/<symbol>/
        """
        version = str(self._cfg.model_version).strip() or "v1"
        exchange = str(self._cfg.freqtrade_exchange).strip() or "okx"
        symbol = freqtrade_pair_to_symbol(pair)
        return (self._cfg.qlib_model_dir / version / exchange / str(timeframe) / str(symbol)).resolve()

    def entry_proba_up(
        self,
        *,
        dp: Any,
        pair: str,
        timeframe: str,
        current_time: datetime,
    ) -> float | None:
        """
        计算当前时刻的“未来上涨概率”（来自研究层模型）。

        约定：
        - 使用 dp.get_analyzed_dataframe 获取到当前为止的历史 K 线
        - 用与训练脚本一致的轻量特征构造
        - 仅返回最后一行的 proba（正类概率）
        """
        df = get_analyzed_dataframe_upto_time(dp, pair=str(pair), timeframe=str(timeframe), current_time=current_time)
        if df is None or df.empty:
            return None
        if int(len(df)) < int(self._p.min_history_rows):
            return None

        candle_ts = get_last_candle_timestamp(df)
        cache_key = (str(pair), str(timeframe))
        if candle_ts is not None:
            cached = self._proba_cache.get(cache_key)
            if (
                isinstance(cached, tuple)
                and len(cached) == 2
                and isinstance(cached[0], pd.Timestamp)
                and cached[0] == candle_ts
                and np.isfinite(cached[1])
            ):
                return float(cached[1])

        model_dir = self.model_dir(pair=str(pair), timeframe=str(timeframe))
        try:
            loader = self._cache.get(model_dir)
        except Exception as e:
            key = model_dir.as_posix()
            if key not in self._warned_model_dirs:
                logger.warning("Qlib 模型加载失败：%s (%s)", key, e)
                self._warned_model_dirs.add(key)
            return None

        try:
            last = build_last_row_features(df, feature_cols=(loader.features if loader.features else None))
        except Exception:
            return None
        if last is None or last.empty:
            return None

        try:
            proba = loader.predict_proba(last)
        except Exception:
            return None

        if not (hasattr(proba, "ndim") and hasattr(proba, "shape")):
            return None
        if int(proba.ndim) != 2 or int(proba.shape[1]) < 2:
            return None

        try:
            v = float(proba[0, 1])
        except Exception:
            return None
        if not np.isfinite(v):
            return None

        if candle_ts is not None:
            self._proba_cache[cache_key] = (candle_ts, float(v))
        return float(v)

    @staticmethod
    def side_proba(*, proba_up: float, side: str) -> float | None:
        """
        将“上涨概率”转换为“做该方向的胜率概率”：
        - long：使用 proba_up
        - short：使用 1 - proba_up
        """
        if not np.isfinite(proba_up):
            return None
        side_l = str(side or "").strip().lower()
        if side_l == "long":
            return float(proba_up)
        if side_l == "short":
            return float(1.0 - float(proba_up))
        return None

    @staticmethod
    def soft_scale(*, side_proba: float, floor: float, threshold: float) -> float:
        """
        将概率映射为 0~1 的风险折扣（越低越保守）：
        - side_proba <= 0.5：返回 floor
        - side_proba >= threshold：返回 1.0
        - 中间线性插值
        """
        floor_v = float(floor) if np.isfinite(floor) else 0.0
        floor_v = float(max(0.0, min(1.0, floor_v)))

        thr = float(threshold)
        thr = float(max(0.5, min(0.99, thr))) if np.isfinite(thr) else 0.55

        p = float(side_proba)
        if not np.isfinite(p):
            return 1.0
        if p <= 0.5:
            return floor_v
        if p >= thr:
            return 1.0
        return float(floor_v + (1.0 - floor_v) * ((p - 0.5) / (thr - 0.5)))

    @staticmethod
    def hard_fuse_block(*, side_proba: float, enabled: bool, min_proba: float) -> bool:
        """
        硬保险丝：模型强烈反向时拒绝入场（避免在明显逆风方向硬扛）。
        """
        if not bool(enabled):
            return False
        if not np.isfinite(side_proba):
            return False
        fuse_min = float(min_proba)
        if not np.isfinite(fuse_min):
            return False
        fuse_min = float(max(0.0, min(0.49, fuse_min)))
        return float(side_proba) < fuse_min

