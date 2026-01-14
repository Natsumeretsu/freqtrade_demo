from __future__ import annotations

"""
drift.py - 特征分布基线与概念漂移检测（轻量版）

设计目标：
- 训练阶段导出特征分布“基线”（用于跨设备/跨时间对齐）
- 评估阶段对比“当前窗口”与基线，输出漂移信号（PSI/均值漂移/缺失率等）

说明：
- 本模块不引入重型因果/统计依赖（如 DoWhy / econml / scipy），保证可移植、可复现。
- 这里的漂移指标主要用于“风险降级/告警/复盘”，不直接等价于交易信号。
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import numpy as np
import pandas as pd


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _to_float_or_none(x: Any) -> float | None:
    try:
        v = float(x)
    except Exception:
        return None
    return v if np.isfinite(v) else None


def _ensure_1d_finite(values: pd.Series | np.ndarray) -> np.ndarray:
    if isinstance(values, pd.Series):
        arr = values.to_numpy(dtype="float64", copy=False)
    else:
        arr = np.asarray(values, dtype="float64")

    if arr.size <= 0:
        return np.asarray([], dtype="float64")

    arr = np.where(np.isfinite(arr), arr, np.nan)
    return arr[np.isfinite(arr)]


def _unique_sorted_edges(edges: np.ndarray) -> np.ndarray:
    e = np.asarray(edges, dtype="float64")
    e = e[np.isfinite(e)]
    if e.size <= 0:
        return np.asarray([], dtype="float64")
    e = np.unique(e)
    e.sort()
    return e


def _fallback_edges(arr: np.ndarray) -> np.ndarray:
    if arr.size <= 0:
        return np.asarray([], dtype="float64")
    v = float(arr[-1])
    # 退化情况下给一个宽松区间，避免 PSI 分箱为 0
    return np.asarray([v - 1.0, v + 1.0], dtype="float64")


def _hist_proportions(arr: np.ndarray, *, edges: np.ndarray) -> list[float]:
    if arr.size <= 0 or edges.size < 2:
        return []
    counts, _ = np.histogram(arr, bins=edges)
    total = float(np.sum(counts))
    if total <= 0:
        return [0.0 for _ in range(int(edges.size - 1))]
    return [float(c) / total for c in counts]


def _psi(p: list[float], q: list[float], *, eps: float) -> float:
    if not p or not q or len(p) != len(q):
        return float("nan")
    p_arr = np.asarray(p, dtype="float64")
    q_arr = np.asarray(q, dtype="float64")
    p_arr = np.clip(p_arr, eps, 1.0)
    q_arr = np.clip(q_arr, eps, 1.0)
    return float(np.sum((p_arr - q_arr) * np.log(p_arr / q_arr)))


@dataclass(frozen=True)
class DriftThresholds:
    """漂移阈值（经验值，可按资产/周期调参）。"""

    psi_warn: float = 0.20
    psi_crit: float = 0.50
    mean_z_warn: float = 3.0
    mean_z_crit: float = 6.0
    missing_warn: float = 0.05
    missing_crit: float = 0.20


def build_feature_baseline(
    X: pd.DataFrame,
    *,
    quantile_bins: int = 10,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    构建特征分布基线（用于后续漂移对比）。

    - quantile_bins: PSI 分箱数量（默认 10，即 deciles）
    - metadata: 额外元信息（例如 feature_set、训练区间、rows_train 等）
    """
    if X is None or X.empty:
        raise ValueError("X 为空，无法构建基线")

    if int(quantile_bins) < 2:
        raise ValueError("quantile_bins 必须 >= 2")

    q = np.linspace(0.0, 1.0, int(quantile_bins) + 1, dtype="float64")

    features: dict[str, Any] = {}
    for col in list(X.columns):
        s = X[col]
        arr = _ensure_1d_finite(s)
        if arr.size <= 0:
            features[str(col)] = {
                "count": 0,
                "mean": None,
                "std": None,
                "min": None,
                "max": None,
                "psi_bins": [],
                "psi_ref": [],
            }
            continue

        edges = _unique_sorted_edges(np.quantile(arr, q))
        if edges.size < 2:
            edges = _fallback_edges(arr)

        ref = _hist_proportions(arr, edges=edges)
        features[str(col)] = {
            "count": int(arr.size),
            "mean": _to_float_or_none(np.mean(arr)),
            "std": _to_float_or_none(np.std(arr, ddof=0)),
            "min": _to_float_or_none(np.min(arr)),
            "max": _to_float_or_none(np.max(arr)),
            "psi_bins": [float(x) for x in edges],
            "psi_ref": ref,
        }

    return {
        "version": 1,
        "created_at": _utc_now_iso(),
        "quantile_bins": int(quantile_bins),
        "metadata": dict(metadata or {}),
        "features": features,
    }


def evaluate_feature_drift(
    X_window: pd.DataFrame,
    *,
    baseline: dict[str, Any],
    thresholds: DriftThresholds | None = None,
    psi_eps: float = 1e-6,
) -> dict[str, Any]:
    """
    对比“当前窗口”与基线，输出漂移报告。

    返回结构适合直接 json.dump（内部已转为 Python 原生类型）。
    """
    if X_window is None or X_window.empty:
        raise ValueError("X_window 为空，无法评估漂移")

    th = thresholds or DriftThresholds()
    base_features = (baseline or {}).get("features") or {}
    if not isinstance(base_features, dict) or not base_features:
        raise ValueError("baseline.features 为空或格式错误")

    rows = int(len(X_window))
    feature_reports: dict[str, Any] = {}
    worst_level = "ok"

    for name, b in base_features.items():
        if not isinstance(b, dict):
            continue

        if name not in X_window.columns:
            feature_reports[name] = {"status": "missing_column"}
            worst_level = "crit"
            continue

        raw = X_window[name].astype("float64").replace([np.inf, -np.inf], np.nan)
        missing_rate = float(raw.isna().mean()) if rows > 0 else 1.0
        arr = _ensure_1d_finite(raw)

        edges = np.asarray(b.get("psi_bins") or [], dtype="float64")
        ref = b.get("psi_ref") or []
        cur = _hist_proportions(arr, edges=edges) if edges.size >= 2 else []
        psi_val = _psi(cur, ref, eps=float(psi_eps))

        mean_ref = _to_float_or_none(b.get("mean"))
        std_ref = _to_float_or_none(b.get("std"))
        mean_cur = _to_float_or_none(np.mean(arr)) if arr.size > 0 else None
        std_cur = _to_float_or_none(np.std(arr, ddof=0)) if arr.size > 0 else None

        mean_z = None
        std_ratio = None
        if mean_ref is not None and std_ref is not None and std_ref > 0 and mean_cur is not None:
            mean_z = float((mean_cur - mean_ref) / std_ref)
        if std_ref is not None and std_ref > 0 and std_cur is not None:
            std_ratio = float(std_cur / std_ref)

        # 判定状态：优先缺失，其次 PSI，再均值漂移
        status = "ok"
        if missing_rate >= float(th.missing_crit):
            status = "crit"
        elif missing_rate >= float(th.missing_warn):
            status = "warn"

        if np.isfinite(psi_val):
            if psi_val >= float(th.psi_crit):
                status = "crit"
            elif psi_val >= float(th.psi_warn) and status != "crit":
                status = "warn"

        if mean_z is not None and np.isfinite(mean_z):
            if abs(mean_z) >= float(th.mean_z_crit):
                status = "crit"
            elif abs(mean_z) >= float(th.mean_z_warn) and status != "crit":
                status = "warn"

        if status == "crit":
            worst_level = "crit"
        elif status == "warn" and worst_level != "crit":
            worst_level = "warn"

        feature_reports[name] = {
            "status": status,
            "missing_rate": float(missing_rate),
            "psi": _to_float_or_none(psi_val),
            "mean_ref": mean_ref,
            "mean_cur": mean_cur,
            "mean_z": _to_float_or_none(mean_z),
            "std_ref": std_ref,
            "std_cur": std_cur,
            "std_ratio": _to_float_or_none(std_ratio),
        }

    return {
        "version": 1,
        "evaluated_at": _utc_now_iso(),
        "rows": rows,
        "status": worst_level,
        "thresholds": {
            "psi_warn": float(th.psi_warn),
            "psi_crit": float(th.psi_crit),
            "mean_z_warn": float(th.mean_z_warn),
            "mean_z_crit": float(th.mean_z_crit),
            "missing_warn": float(th.missing_warn),
            "missing_crit": float(th.missing_crit),
        },
        "features": feature_reports,
    }

