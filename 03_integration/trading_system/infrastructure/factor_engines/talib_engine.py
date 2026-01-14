from __future__ import annotations

"""
talib_engine.py - 基于 talib.abstract 的因子引擎实现

约定（支持的因子名，兼容现有策略字段）：
- EMA：ema_<n> / ema_short_<n> / ema_long_<n>
- ADX：adx / adx_<n>
- ATR：atr / atr_<n>
- ATR%：atr_pct / atr_pct_<n>（= atr / close）
- MACD：macd / macdsignal / macdhist（使用配置中的 fast/slow/signal）
- volume_ratio：volume_ratio / volume_ratio_<n>（= volume / rolling_mean(volume,n)）
- ret：ret_<n>（= close.pct_change(n)）
- vol：vol_<n>（= std(ret_1, n)）
- skew：skew_<n>（= skew(ret_1, n)）
- kurt：kurt_<n>（= kurt(ret_1, n)，pandas 口径为 excess kurtosis）
- volume_z：volume_z_<n>（= zscore(volume,n)）
- hl_range：hl_range（= high/low - 1）
- ema_spread：ema_spread（= EMA(close,10)/EMA(close,50) - 1）

增强技术指标（用于研究/建模候选池，仍保持 OHLCV 可在线计算）：
- RSI：rsi_<n>
- CCI：cci_<n>
- MFI：mfi_<n>
- ROC：roc_<n>
- WILLR：willr_<n>
- 布林宽度/百分位：bb_width_<n>_<k> / bb_percent_b_<n>_<k>（k 为整数，通常 2）
- 随机指标：stoch_k_<k>_<d>_<smooth> / stoch_d_<k>_<d>_<smooth>
"""

import re
from dataclasses import dataclass

import numpy as np
import pandas as pd
import talib.abstract as ta

from trading_system.domain.factor_engine import IFactorEngine


_EMA_RE = re.compile(r"^(ema|ema_short|ema_long)_(\d+)$", re.IGNORECASE)
_ADX_RE = re.compile(r"^adx_(\d+)$", re.IGNORECASE)
_ATR_RE = re.compile(r"^atr_(\d+)$", re.IGNORECASE)
_ATR_PCT_RE = re.compile(r"^atr_pct_(\d+)$", re.IGNORECASE)
_VOL_RATIO_RE = re.compile(r"^volume_ratio_(\d+)$", re.IGNORECASE)
_RET_RE = re.compile(r"^ret_(\d+)$", re.IGNORECASE)
_VOL_RE = re.compile(r"^vol_(\d+)$", re.IGNORECASE)
_SKEW_RE = re.compile(r"^skew_(\d+)$", re.IGNORECASE)
_KURT_RE = re.compile(r"^kurt_(\d+)$", re.IGNORECASE)
_VOLUME_Z_RE = re.compile(r"^volume_z_(\d+)$", re.IGNORECASE)
_RSI_RE = re.compile(r"^rsi_(\d+)$", re.IGNORECASE)
_CCI_RE = re.compile(r"^cci_(\d+)$", re.IGNORECASE)
_MFI_RE = re.compile(r"^mfi_(\d+)$", re.IGNORECASE)
_ROC_RE = re.compile(r"^roc_(\d+)$", re.IGNORECASE)
_WILLR_RE = re.compile(r"^willr_(\d+)$", re.IGNORECASE)
_BB_WIDTH_RE = re.compile(r"^bb_width_(\d+)_(\d+)$", re.IGNORECASE)
_BB_PCTB_RE = re.compile(r"^bb_percent_b_(\d+)_(\d+)$", re.IGNORECASE)
_STOCH_K_RE = re.compile(r"^stoch_k_(\d+)_(\d+)_(\d+)$", re.IGNORECASE)
_STOCH_D_RE = re.compile(r"^stoch_d_(\d+)_(\d+)_(\d+)$", re.IGNORECASE)


@dataclass(frozen=True)
class TalibEngineParams:
    adx_period: int = 14
    atr_period: int = 14
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9
    volume_ratio_lookback: int = 72


class TalibFactorEngine(IFactorEngine):
    def __init__(self, params: TalibEngineParams | None = None) -> None:
        self._p = params or TalibEngineParams()

    def supports(self, factor_name: str) -> bool:
        name = str(factor_name or "").strip()
        if not name:
            return False

        if name in {
            "adx",
            "atr",
            "atr_pct",
            "macd",
            "macdsignal",
            "macdhist",
            "volume_ratio",
            "hl_range",
            "ema_spread",
        }:
            return True

        if _EMA_RE.match(name):
            return True
        if _ADX_RE.match(name) or _ATR_RE.match(name) or _ATR_PCT_RE.match(name):
            return True
        if _VOL_RATIO_RE.match(name):
            return True
        if _RET_RE.match(name) or _VOL_RE.match(name) or _SKEW_RE.match(name) or _KURT_RE.match(name) or _VOLUME_Z_RE.match(name):
            return True
        if _RSI_RE.match(name) or _CCI_RE.match(name) or _MFI_RE.match(name) or _ROC_RE.match(name) or _WILLR_RE.match(name):
            return True
        if _BB_WIDTH_RE.match(name) or _BB_PCTB_RE.match(name):
            return True
        if _STOCH_K_RE.match(name) or _STOCH_D_RE.match(name):
            return True
        return False

    def compute(self, data: pd.DataFrame, factor_names: list[str]) -> pd.DataFrame:
        if data is None or data.empty:
            return pd.DataFrame()

        required = {"close", "high", "low", "volume"}
        missing = [c for c in required if c not in data.columns]
        if missing:
            raise ValueError(f"缺少必要列：{missing}")

        out: dict[str, pd.Series] = {}

        close = data["close"].astype("float64")
        high = data["high"].astype("float64")
        low = data["low"].astype("float64")
        volume = data["volume"].astype("float64")

        # EMA（支持多个 period）
        for name in factor_names:
            m = _EMA_RE.match(name)
            if not m:
                continue
            period = int(m.group(2))
            if period <= 0:
                continue
            out[name] = ta.EMA(data, timeperiod=period)

        # ema_spread：默认口径（10/50），用于 ML/研究侧的“趋势结构”特征
        if "ema_spread" in factor_names:
            # 复用已算出的 EMA（如果刚好请求过），否则自行计算
            ema10 = out.get("ema_10")
            if ema10 is None:
                ema10 = out.get("ema_short_10")
            if ema10 is None:
                ema10 = out.get("ema_long_10")
            if ema10 is None:
                ema10 = ta.EMA(data, timeperiod=10)

            ema50 = out.get("ema_50")
            if ema50 is None:
                ema50 = out.get("ema_short_50")
            if ema50 is None:
                ema50 = out.get("ema_long_50")
            if ema50 is None:
                ema50 = ta.EMA(data, timeperiod=50)

            if not isinstance(ema10, pd.Series):
                ema10 = pd.Series(ema10, index=data.index)
            if not isinstance(ema50, pd.Series):
                ema50 = pd.Series(ema50, index=data.index)

            out["ema_spread"] = (ema10 / ema50.replace(0, np.nan)) - 1.0

        # hl_range
        if "hl_range" in factor_names:
            out["hl_range"] = (high / low.replace(0, np.nan)) - 1.0

        # ret_*
        for name in factor_names:
            m = _RET_RE.match(name)
            if m is None:
                continue
            n = int(m.group(1))
            if n <= 0:
                continue
            out[name] = close.pct_change(n)

        # vol_* / skew_* / kurt_*：复用 ret_1
        need_ret1 = any((_VOL_RE.match(n) or _SKEW_RE.match(n) or _KURT_RE.match(n)) for n in factor_names)
        ret1 = close.pct_change(1) if need_ret1 else None

        for name in factor_names:
            if (m := _VOL_RE.match(name)) is not None:
                n = int(m.group(1))
                if n > 0 and ret1 is not None:
                    out[name] = ret1.rolling(n).std()
                continue
            if (m := _SKEW_RE.match(name)) is not None:
                n = int(m.group(1))
                if n > 0 and ret1 is not None:
                    out[name] = ret1.rolling(n).skew()
                continue
            if (m := _KURT_RE.match(name)) is not None:
                n = int(m.group(1))
                if n > 0 and ret1 is not None:
                    out[name] = ret1.rolling(n).kurt()
                continue

        # volume_z_*
        for name in factor_names:
            m = _VOLUME_Z_RE.match(name)
            if m is None:
                continue
            n = int(m.group(1))
            if n <= 1:
                continue
            mean = volume.rolling(n).mean()
            std = volume.rolling(n).std()
            out[name] = (volume - mean) / std.replace(0, np.nan)

        # RSI / CCI / MFI / ROC / WILLR
        for name in factor_names:
            if (m := _RSI_RE.match(name)) is not None:
                n = int(m.group(1))
                if n > 0:
                    out[name] = ta.RSI(data, timeperiod=n)
                continue
            if (m := _CCI_RE.match(name)) is not None:
                n = int(m.group(1))
                if n > 0:
                    out[name] = ta.CCI(data, timeperiod=n)
                continue
            if (m := _MFI_RE.match(name)) is not None:
                n = int(m.group(1))
                if n > 0:
                    out[name] = ta.MFI(data, timeperiod=n)
                continue
            if (m := _ROC_RE.match(name)) is not None:
                n = int(m.group(1))
                if n > 0:
                    out[name] = ta.ROC(data, timeperiod=n)
                continue
            if (m := _WILLR_RE.match(name)) is not None:
                n = int(m.group(1))
                if n > 0:
                    out[name] = ta.WILLR(data, timeperiod=n)
                continue

        # 布林宽度 / percent_b（用 close 默认输入）
        bb_params: set[tuple[int, int]] = set()
        for name in factor_names:
            if (m := _BB_WIDTH_RE.match(name)) is not None:
                bb_params.add((int(m.group(1)), int(m.group(2))))
            if (m := _BB_PCTB_RE.match(name)) is not None:
                bb_params.add((int(m.group(1)), int(m.group(2))))

        for period, dev in sorted(bb_params):
            if period <= 1 or dev <= 0:
                continue
            bb = ta.BBANDS(data, timeperiod=int(period), nbdevup=float(dev), nbdevdn=float(dev), matype=0)
            upper = bb["upperband"].astype("float64")
            middle = bb["middleband"].astype("float64")
            lower = bb["lowerband"].astype("float64")

            width_name = f"bb_width_{period}_{dev}"
            if width_name in factor_names:
                out[width_name] = (upper / lower.replace(0, np.nan)) - 1.0

            pctb_name = f"bb_percent_b_{period}_{dev}"
            if pctb_name in factor_names:
                denom = (upper - lower).replace(0, np.nan)
                out[pctb_name] = (close - lower) / denom

        # 随机指标 STOCH（slowk/slowd）
        stoch_params: set[tuple[int, int, int]] = set()
        for name in factor_names:
            if (m := _STOCH_K_RE.match(name)) is not None:
                stoch_params.add((int(m.group(1)), int(m.group(2)), int(m.group(3))))
            if (m := _STOCH_D_RE.match(name)) is not None:
                stoch_params.add((int(m.group(1)), int(m.group(2)), int(m.group(3))))

        for k_period, d_period, smooth_k in sorted(stoch_params):
            if k_period <= 1 or d_period <= 0 or smooth_k <= 0:
                continue
            st = ta.STOCH(
                data,
                fastk_period=int(k_period),
                slowk_period=int(smooth_k),
                slowk_matype=0,
                slowd_period=int(d_period),
                slowd_matype=0,
            )

            k_name = f"stoch_k_{k_period}_{d_period}_{smooth_k}"
            d_name = f"stoch_d_{k_period}_{d_period}_{smooth_k}"
            if k_name in factor_names:
                out[k_name] = st["slowk"].astype("float64")
            if d_name in factor_names:
                out[d_name] = st["slowd"].astype("float64")

        # ADX / ATR（支持默认与带后缀两种）
        adx_periods: dict[str, int] = {}
        atr_periods: dict[str, int] = {}
        atr_pct_periods: dict[str, int] = {}

        for name in factor_names:
            if name == "adx":
                adx_periods["adx"] = int(self._p.adx_period)
                continue
            if name == "atr":
                atr_periods["atr"] = int(self._p.atr_period)
                continue
            if name == "atr_pct":
                atr_pct_periods["atr_pct"] = int(self._p.atr_period)
                continue

            if (m := _ADX_RE.match(name)) is not None:
                adx_periods[name] = int(m.group(1))
            if (m := _ATR_RE.match(name)) is not None:
                atr_periods[name] = int(m.group(1))
            if (m := _ATR_PCT_RE.match(name)) is not None:
                atr_pct_periods[name] = int(m.group(1))

        for col, period in adx_periods.items():
            if period > 0:
                out[col] = ta.ADX(data, timeperiod=period)
        for col, period in atr_periods.items():
            if period > 0:
                out[col] = ta.ATR(data, timeperiod=period)

        # atr_pct：优先复用已计算的 atr；否则再算一次
        for col, period in atr_pct_periods.items():
            if period <= 0:
                continue

            atr_col = "atr" if col == "atr_pct" else f"atr_{period}"
            atr_series = out.get(atr_col)
            if atr_series is None:
                atr_series = ta.ATR(data, timeperiod=period)
            out[col] = atr_series / close.replace(0, np.nan)

        # MACD：只要任一 MACD 相关列被请求，就计算一次并输出三列
        if any(n in {"macd", "macdsignal", "macdhist"} for n in factor_names):
            macd = ta.MACD(
                data,
                fastperiod=int(self._p.macd_fast),
                slowperiod=int(self._p.macd_slow),
                signalperiod=int(self._p.macd_signal),
            )
            out["macd"] = macd["macd"]
            out["macdsignal"] = macd["macdsignal"]
            out["macdhist"] = macd["macdhist"]

        # volume_ratio：支持默认与带后缀 lookback（统一输出列名：volume_ratio）
        vr_items: dict[str, int] = {}
        for name in factor_names:
            if name == "volume_ratio":
                vr_items["volume_ratio"] = int(self._p.volume_ratio_lookback)
                continue
            m = _VOL_RATIO_RE.match(name)
            if m is not None:
                vr_items["volume_ratio"] = int(m.group(1))

        for col, lb in vr_items.items():
            if lb <= 0:
                continue
            mean = volume.rolling(lb).mean().replace(0, np.nan)
            out[col] = volume / mean

        if not out:
            return pd.DataFrame(index=data.index)

        df = pd.DataFrame(out, index=data.index)
        return df.replace([np.inf, -np.inf], np.nan)
