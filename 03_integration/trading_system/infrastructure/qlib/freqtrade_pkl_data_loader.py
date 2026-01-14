from __future__ import annotations

"""
freqtrade_pkl_data_loader.py - Qlib DataLoader：从本仓库的 pkl 数据集加载并构造 (feature,label) 数据

设计取舍：
- Qlib 原生推荐使用 provider_uri + LocalProvider（二进制）来驱动 DataHandler（例如 Alpha158）。
- 但本仓库的“权威数据源”是 Freqtrade 下载的 OHLCV（feather），研究层目前固化为 pkl：
  02_qlib_research/qlib_data/<exchange>/<timeframe>/<symbol>.pkl
- 为避免引入第二套数据存储与口径漂移，本模块用 Qlib 的 DataLoader 接口直接读取上述 pkl，
  并输出 Qlib 模型训练通用的列结构：columns level0 = ["feature","label"]。

注意：
- 这是研究层数据组织方式，不影响执行层（Freqtrade）的运行方式。
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from qlib.data.dataset.loader import DataLoader

from trading_system.application.factor_sets import get_factor_templates, render_factor_names
from trading_system.infrastructure.ml.features import compute_features


@dataclass(frozen=True)
class FreqtradePklDataLoaderConfig:
    data_root: Path
    exchange: str
    timeframe: str
    feature_set: str
    feature_vars: dict[str, Any]
    horizon: int
    threshold: float
    drop_na: bool = True
    label_name: str = "LABEL0"


def _ensure_datetime_index(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()

    work = df.copy()
    if "date" in work.columns:
        ts = pd.to_datetime(work["date"], utc=True, errors="coerce")
        work["date"] = ts
        work = work.dropna(subset=["date"]).copy()
        # Qlib 默认把 datetime 当作“无时区”的时间轴；这里显式转为 UTC 的 naive timestamp
        work.index = work["date"].dt.tz_localize(None)
        work = work.drop(columns=["date"])
    else:
        work.index = pd.to_datetime(work.index, utc=True, errors="coerce").tz_localize(None)

    work = work.sort_index()
    work = work[~work.index.isna()]
    return work


def _parse_time(x: Any) -> pd.Timestamp | None:
    if x is None:
        return None
    s = str(x).strip()
    if not s:
        return None
    try:
        return pd.Timestamp(s)
    except Exception:
        return None


def _filter_time(df: pd.DataFrame, start_time: Any, end_time: Any) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    st = _parse_time(start_time)
    et = _parse_time(end_time)
    if st is None and et is None:
        return df
    if st is None:
        return df.loc[:et]
    if et is None:
        return df.loc[st:]
    return df.loc[st:et]


def _compute_binary_label(close: pd.Series, *, horizon: int, threshold: float) -> pd.Series:
    """
    二分类标签：future_return > threshold 视为 1，否则 0。

    关键点：最后 horizon 根 K 线没有未来收益，必须置为 NaN 并在训练阶段丢弃，避免未来信息泄露。
    """
    h = int(horizon)
    if h <= 0:
        raise ValueError("horizon 必须为正整数")

    c = close.astype("float64")
    future_ret = c.shift(-h) / c - 1.0
    y = (future_ret > float(threshold)).astype("float64")
    y[~np.isfinite(future_ret.to_numpy(dtype="float64", copy=False))] = np.nan
    return y


def _resolve_instruments(instruments: Any) -> list[str]:
    if instruments is None:
        return []
    if isinstance(instruments, str):
        s = instruments.strip()
        if not s:
            return []
        return [s]
    if isinstance(instruments, (list, tuple, set)):
        out: list[str] = []
        for x in instruments:
            sx = str(x).strip()
            if sx:
                out.append(sx)
        return out
    return [str(instruments).strip()] if str(instruments).strip() else []


def _build_feature_columns(*, feature_set: str, variables: dict[str, Any]) -> list[str]:
    name = str(feature_set or "").strip()
    if not name:
        raise ValueError("feature_set 不能为空")

    templates = get_factor_templates(name)
    cols = render_factor_names(templates, dict(variables or {}))
    cols = [str(c).strip() for c in cols if str(c).strip()]
    if not cols:
        raise ValueError(f"feature_set 渲染后为空：{name}")
    return cols


class FreqtradePklDataLoader(DataLoader):
    """
    Qlib DataLoader：从 pkl 数据集加载，并生成 (feature,label) 的 multi-index columns。
    """

    def __init__(
        self,
        *,
        data_root: str | Path,
        exchange: str,
        timeframe: str,
        feature_set: str = "ml_core",
        feature_vars: dict[str, Any] | None = None,
        horizon: int = 1,
        threshold: float = 0.0,
        drop_na: bool = True,
        label_name: str = "LABEL0",
    ) -> None:
        self._cfg = FreqtradePklDataLoaderConfig(
            data_root=Path(data_root).expanduser().resolve(),
            exchange=str(exchange).strip(),
            timeframe=str(timeframe).strip(),
            feature_set=str(feature_set).strip() or "ml_core",
            feature_vars=dict(feature_vars or {}),
            horizon=int(horizon),
            threshold=float(threshold),
            drop_na=bool(drop_na),
            label_name=str(label_name).strip() or "LABEL0",
        )

    def _data_path(self, symbol: str) -> Path:
        return (self._cfg.data_root / self._cfg.exchange / self._cfg.timeframe / f"{symbol}.pkl").resolve()

    def load(self, instruments, start_time=None, end_time=None) -> pd.DataFrame:
        symbols = _resolve_instruments(instruments)
        if not symbols:
            # 允许 instruments=None：自动扫描目录
            base = (self._cfg.data_root / self._cfg.exchange / self._cfg.timeframe).resolve()
            if base.is_dir():
                symbols = [p.stem for p in base.glob("*.pkl") if p.is_file()]

        symbols = [s for s in symbols if s]
        if not symbols:
            return pd.DataFrame()

        feature_cols = _build_feature_columns(feature_set=self._cfg.feature_set, variables=self._cfg.feature_vars)

        frames: list[pd.DataFrame] = []
        for sym in symbols:
            path = self._data_path(sym)
            if not path.is_file():
                continue

            raw = pd.read_pickle(path)
            raw = _ensure_datetime_index(raw)
            raw = _filter_time(raw, start_time, end_time)
            if raw.empty:
                continue

            feats = compute_features(raw, feature_cols=feature_cols)
            if feats is None or feats.empty:
                continue

            y = _compute_binary_label(raw["close"], horizon=self._cfg.horizon, threshold=self._cfg.threshold)
            y_df = y.to_frame(name=self._cfg.label_name)

            # 对齐并（可选）清理缺失
            Xy = feats.join(y_df, how="inner")
            if bool(self._cfg.drop_na):
                Xy = Xy.replace([np.inf, -np.inf], np.nan).dropna(axis=0, how="any")
            if Xy.empty:
                continue

            # MultiIndex columns：feature / label
            feat_part = Xy[feats.columns].copy()
            feat_part.columns = pd.MultiIndex.from_product([["feature"], list(feat_part.columns)])
            label_part = Xy[[self._cfg.label_name]].copy()
            label_part.columns = pd.MultiIndex.from_product([["label"], [self._cfg.label_name]])
            out = pd.concat([feat_part, label_part], axis=1)

            # MultiIndex index：datetime / instrument
            out["instrument"] = sym
            out = out.set_index("instrument", append=True)
            out.index = out.index.set_names(["datetime", "instrument"])
            frames.append(out)

        if not frames:
            return pd.DataFrame()

        data = pd.concat(frames, axis=0).sort_index()
        # 轻量断言：避免把非法值带入训练
        if ("label", self._cfg.label_name) in data.columns:
            yy = data[("label", self._cfg.label_name)]
            bad = yy.notna() & (~yy.isin([0.0, 1.0]))
            if bool(bad.any()):
                raise ValueError("label 存在非 0/1 的值，请检查 threshold/horizon 或数据源。")
        return data
