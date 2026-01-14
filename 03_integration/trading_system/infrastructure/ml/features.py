from __future__ import annotations

"""
features.py - 研究层/实盘共用的特征工程（保证训练与预测一致）

设计目标：
- 只依赖 OHLCV 的“可在线计算”特征（避免未来泄露）
- 训练脚本与策略侧复用同一套特征函数
- 输出特征列名稳定，可用 `features.json` 固化并在实盘严格对齐
- 特征本身复用 factor_engine（避免重复造轮子/口径漂移）

位置说明：
- 本模块属于基础设施层（infrastructure/ml），供策略适配层与训练脚本共同复用。
"""

import re
from typing import Iterable

import numpy as np
import pandas as pd

from trading_system.application.factor_sets import get_factor_templates, render_factor_names
from trading_system.domain.factor_engine import IFactorEngine
from trading_system.infrastructure.factor_engines.factory import create_factor_engine

DEFAULT_FEATURE_SET_NAME = "ml_core"

_VOL_RATIO_ALIAS_RE = re.compile(r"^volume_ratio_(\d+)$")

_ENGINE: IFactorEngine | None = None


def _default_feature_columns() -> list[str]:
    templates = get_factor_templates(DEFAULT_FEATURE_SET_NAME)
    cols = render_factor_names(templates, {})
    cols = [str(c).strip() for c in cols if str(c).strip()]
    if not cols:
        raise ValueError(f"默认特征集为空或不存在：{DEFAULT_FEATURE_SET_NAME}")
    return cols


DEFAULT_FEATURE_COLUMNS: list[str] = _default_feature_columns()


def _get_engine() -> IFactorEngine:
    global _ENGINE
    if _ENGINE is None:
        _ENGINE = create_factor_engine()
    return _ENGINE


def _dedupe_keep_order(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for x in items:
        s = str(x).strip()
        if not s or s in seen:
            continue
        seen.add(s)
        out.append(s)
    return out


def compute_features(df: pd.DataFrame, *, feature_cols: Iterable[str] | None = None) -> pd.DataFrame:
    """
    从 OHLCV 计算特征矩阵（不包含标签）。

    依赖列：close/high/low/volume
    """
    if df is None or df.empty:
        return pd.DataFrame()

    required = ("close", "high", "low", "volume")
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"缺少必要列：{missing}")

    cols = list(feature_cols) if feature_cols is not None else list(DEFAULT_FEATURE_COLUMNS)
    cols = _dedupe_keep_order(cols)
    if not cols:
        return pd.DataFrame(index=df.index)

    engine = _get_engine()
    unsupported = [c for c in cols if not engine.supports(c)]
    if unsupported:
        raise ValueError(f"不支持的特征列（因子名）：{unsupported}")

    feats = engine.compute(df, cols)
    if feats is None or feats.empty:
        return pd.DataFrame(index=df.index)

    # volume_ratio 特殊处理：
    # - 因子引擎会把 volume_ratio_<n> 视为“参数化输入”，但统一输出列名为 volume_ratio
    # - 为保证训练/预测/体检的“列名严格对齐”，这里为请求的 volume_ratio_<n> 补一个别名列
    vr_aliases = [c for c in cols if _VOL_RATIO_ALIAS_RE.match(str(c))]
    if vr_aliases:
        uniq = sorted(set(vr_aliases))
        if len(uniq) > 1:
            raise ValueError(f"volume_ratio_<n> 暂不支持同时请求多个窗口：{uniq}")
        if "volume_ratio" in feats.columns and uniq[0] not in feats.columns:
            feats[uniq[0]] = feats["volume_ratio"]

    return feats.replace([np.inf, -np.inf], np.nan)


def compute_target(close: pd.Series, *, horizon: int, threshold: float) -> pd.Series:
    """
    计算二分类标签（未来收益是否超过阈值）。

    - horizon: 未来第 N 根 K 线收益
    - threshold: 未来收益阈值（例如覆盖手续费的最小收益）
    """
    h = int(horizon)
    if h <= 0:
        raise ValueError("horizon 必须为正整数")

    c = close.astype("float64")
    future_ret = c.shift(-h) / c - 1.0
    return (future_ret > float(threshold)).astype("int64")


def select_feature_columns(df: pd.DataFrame, feature_cols: Iterable[str] | None = None) -> list[str]:
    cols = list(feature_cols) if feature_cols is not None else list(DEFAULT_FEATURE_COLUMNS)
    cols = [str(c).strip() for c in cols if str(c).strip()]
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise ValueError(f"特征列缺失：{missing}")
    return cols


def build_supervised_dataset(
    df: pd.DataFrame,
    *,
    horizon: int,
    threshold: float,
    feature_cols: Iterable[str] | None = None,
) -> tuple[pd.DataFrame, pd.Series, list[str]]:
    """
    从 OHLCV 构建监督学习数据集（X, y）。
    """
    if df is None or df.empty:
        raise ValueError("数据为空")

    feats = compute_features(df, feature_cols=feature_cols)
    cols = select_feature_columns(feats, feature_cols)

    y = compute_target(df["close"], horizon=int(horizon), threshold=float(threshold))
    work = feats[cols].copy()
    work["target"] = y
    work = work.replace([np.inf, -np.inf], np.nan).dropna()
    if work.empty:
        raise ValueError("有效样本为空：请检查数据长度/特征窗口/阈值设置")

    X = work[cols].astype("float64")
    y2 = work["target"].astype("int64")
    return X, y2, cols


def build_last_row_features(
    df: pd.DataFrame,
    *,
    feature_cols: Iterable[str] | None = None,
) -> pd.DataFrame:
    """
    为“当前时刻”构建一行特征（用于在线预测）。
    """
    feats = compute_features(df, feature_cols=feature_cols)
    if feats.empty:
        return feats
    cols = select_feature_columns(feats, feature_cols)
    last = feats[cols].iloc[[-1]].replace([np.inf, -np.inf], np.nan)
    if last.isna().any(axis=None):
        return pd.DataFrame()
    return last
