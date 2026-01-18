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
from trading_system.infrastructure.koopman_lite import compute_koopman_lite_features
from trading_system.infrastructure.factor_engines.factor_cache import FactorCache, FactorCacheKey


def _calc_entropy(arr: np.ndarray) -> float:
    """计算离散序列的 Shannon 熵（归一化到 [0, 1]）"""
    if len(arr) == 0:
        return np.nan
    # 统计各状态频率
    unique, counts = np.unique(arr[~np.isnan(arr)], return_counts=True)
    if len(unique) <= 1:
        return 0.0
    probs = counts / counts.sum()
    # Shannon 熵
    entropy = -np.sum(probs * np.log(probs + 1e-10))
    # 归一化（最大熵 = log(状态数)）
    max_entropy = np.log(len(unique))
    return entropy / max_entropy if max_entropy > 0 else 0.0


def _discretize_to_state(arr: np.ndarray) -> float:
    """将最后一个值离散化为 3 个状态（低=0/中=1/高=2）"""
    if len(arr) == 0 or np.all(np.isnan(arr)):
        return np.nan
    val = arr[-1]
    if np.isnan(val):
        return np.nan
    q33 = np.nanpercentile(arr, 33)
    q67 = np.nanpercentile(arr, 67)
    if val <= q33:
        return 0.0
    elif val <= q67:
        return 1.0
    else:
        return 2.0


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
_KOOP_PRED_RET_RE = re.compile(r"^koop_pred_ret_h(\d+)$", re.IGNORECASE)
_KOOP_MODE_RE = re.compile(r"^koop_mode_(\d+)_(amp|freq|decay)$", re.IGNORECASE)

# 新增：市场制度/流动性/熵因子
_VOL_OF_VOL_RE = re.compile(r"^vol_of_vol_(\d+)$", re.IGNORECASE)
_RET_VOL_RATIO_RE = re.compile(r"^ret_vol_ratio_(\d+)$", re.IGNORECASE)
_REL_VOL_RE = re.compile(r"^rel_vol_(\d+)$", re.IGNORECASE)
_DIR_ENTROPY_RE = re.compile(r"^dir_entropy_(\d+)$", re.IGNORECASE)
_VOL_STATE_ENTROPY_RE = re.compile(r"^vol_state_entropy_(\d+)$", re.IGNORECASE)

# 新增：信息论/风险/流动性因子（来源：docs/knowledge）
_BUCKET_ENTROPY_RE = re.compile(r"^bucket_entropy_(\d+)$", re.IGNORECASE)
_HURST_RE = re.compile(r"^hurst_(\d+)$", re.IGNORECASE)
_GAP_RE = re.compile(r"^gap_(\d+)$", re.IGNORECASE)
_TAIL_RATIO_RE = re.compile(r"^tail_ratio_(\d+)$", re.IGNORECASE)
_PRICE_IMPACT_RE = re.compile(r"^price_impact_(\d+)$", re.IGNORECASE)

# 新增：反转因子（Reversal Factors）
_REVERSAL_RE = re.compile(r"^reversal_(\d+)$", re.IGNORECASE)
_ZSCORE_CLOSE_RE = re.compile(r"^zscore_close_(\d+)$", re.IGNORECASE)

# 新增：价格动量因子（Price Momentum）
_EMA_SPREAD_RE = re.compile(r"^ema_spread_(\d+)_(\d+)$", re.IGNORECASE)
_PRICE_TO_HIGH_RE = re.compile(r"^price_to_high_(\d+)$", re.IGNORECASE)
_PRICE_TO_LOW_RE = re.compile(r"^price_to_low_(\d+)$", re.IGNORECASE)

# 新增：风险因子（Risk Factors）
_VAR_RE = re.compile(r"^var_(\d+)_(\d+)$", re.IGNORECASE)
_ES_RE = re.compile(r"^es_(\d+)_(\d+)$", re.IGNORECASE)
_DOWNSIDE_VOL_RE = re.compile(r"^downside_vol_(\d+)$", re.IGNORECASE)

# 新增：流动性因子（Liquidity Factors）
_AMIHUD_RE = re.compile(r"^amihud_(\d+)$", re.IGNORECASE)
_OBV_SLOPE_RE = re.compile(r"^obv_slope_(\d+)$", re.IGNORECASE)


@dataclass(frozen=True)
class TalibEngineParams:
    adx_period: int = 14
    atr_period: int = 14
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9
    volume_ratio_lookback: int = 72
    # Koopa-lite（Koopman/本征模态）参数：默认按 15m/1h 的经验取值
    koop_window: int = 512
    koop_embed_dim: int = 16
    koop_stride: int = 10
    koop_ridge: float = 1e-3
    fft_window: int = 512
    fft_topk: int = 8


class TalibFactorEngine(IFactorEngine):
    def __init__(
        self,
        params: TalibEngineParams | None = None,
        cache: FactorCache | None = None,
        parallel_config=None
    ) -> None:
        self._p = params or TalibEngineParams()

        # 初始化缓存（如果未提供，创建默认缓存）
        if cache is None:
            cache = FactorCache(max_size=1000)
        self._cache = cache

        self._current_pair: str | None = None
        self._current_timeframe: str | None = None

        # 初始化并行计算器
        from trading_system.infrastructure.factor_engines.parallel_computer import (
            ParallelConfig,
            ParallelFactorComputer,
        )
        if parallel_config is None:
            parallel_config = ParallelConfig(
                enabled=True,
                max_workers=4,
                use_processes=True,
                min_factors_for_parallel=10,  # 提高阈值，避免小任务开销
                min_rows_for_processes=5000,  # 小数据集自动切换到线程
            )
        self._parallel_computer = ParallelFactorComputer(parallel_config)

        # 初始化批量优化器
        from trading_system.infrastructure.factor_engines.batch_optimizer import BatchFactorComputer
        self._batch_computer = BatchFactorComputer()

        # 初始化因子计算器注册表
        from trading_system.infrastructure.factor_engines.factor_computer import FactorComputerRegistry
        from trading_system.infrastructure.factor_engines.ema_computer import EMAFactorComputer
        from trading_system.infrastructure.factor_engines.momentum_computer import MomentumFactorComputer
        from trading_system.infrastructure.factor_engines.volatility_computer import VolatilityFactorComputer
        from trading_system.infrastructure.factor_engines.technical_computer import TechnicalFactorComputer
        from trading_system.infrastructure.factor_engines.bollinger_computer import BollingerFactorComputer
        from trading_system.infrastructure.factor_engines.stochastic_computer import StochasticFactorComputer
        from trading_system.infrastructure.factor_engines.adx_atr_computer import AdxAtrFactorComputer
        from trading_system.infrastructure.factor_engines.macd_computer import MacdFactorComputer
        from trading_system.infrastructure.factor_engines.volume_computer import VolumeFactorComputer
        from trading_system.infrastructure.factor_engines.risk_computer import RiskFactorComputer
        from trading_system.infrastructure.factor_engines.liquidity_computer import LiquidityFactorComputer
        from trading_system.infrastructure.factor_engines.reversal_computer import ReversalFactorComputer
        from trading_system.infrastructure.factor_engines.price_momentum_computer import PriceMomentumFactorComputer
        from trading_system.infrastructure.factor_engines.entropy_computer import EntropyFactorComputer
        from trading_system.infrastructure.factor_engines.hurst_computer import HurstFactorComputer
        from trading_system.infrastructure.factor_engines.special_computer import SpecialFactorComputer
        
        self._registry = FactorComputerRegistry()
        self._registry.register(EMAFactorComputer())
        self._registry.register(MomentumFactorComputer())
        self._registry.register(VolatilityFactorComputer())
        self._registry.register(TechnicalFactorComputer())
        self._registry.register(BollingerFactorComputer())
        self._registry.register(StochasticFactorComputer())
        self._registry.register(AdxAtrFactorComputer(self._p.adx_period, self._p.atr_period))
        self._registry.register(MacdFactorComputer(self._p.macd_fast, self._p.macd_slow, self._p.macd_signal))
        self._registry.register(VolumeFactorComputer(self._p.volume_ratio_lookback))
        self._registry.register(RiskFactorComputer())
        self._registry.register(LiquidityFactorComputer())
        self._registry.register(ReversalFactorComputer())
        self._registry.register(PriceMomentumFactorComputer())
        self._registry.register(EntropyFactorComputer())
        self._registry.register(HurstFactorComputer())
        self._registry.register(SpecialFactorComputer())

    def set_context(self, pair: str | None = None, timeframe: str | None = None) -> None:
        """设置当前交易对和时间周期（用于缓存键生成）

        Args:
            pair: 交易对名称（如 'BTC/USDT'）
            timeframe: 时间周期（如 '1h', '5m'）
        """
        if pair is not None:
            self._current_pair = pair
        if timeframe is not None:
            self._current_timeframe = timeframe

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
            # Koopman 本征模态因子
            "koop_spectral_radius",
            "koop_reconstruction_error",
        }:
            return True
        if _KOOP_PRED_RET_RE.match(name):
            return True
        if _KOOP_MODE_RE.match(name):
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
        # 新增：市场制度/流动性/熵因子
        if _VOL_OF_VOL_RE.match(name) or _RET_VOL_RATIO_RE.match(name) or _REL_VOL_RE.match(name):
            return True
        if _DIR_ENTROPY_RE.match(name) or _VOL_STATE_ENTROPY_RE.match(name):
            return True
        # 新增：信息论/风险/流动性因子
        if _BUCKET_ENTROPY_RE.match(name) or _HURST_RE.match(name) or _GAP_RE.match(name):
            return True
        if _TAIL_RATIO_RE.match(name) or _PRICE_IMPACT_RE.match(name):
            return True
        # 新增：反转因子
        if _REVERSAL_RE.match(name) or _ZSCORE_CLOSE_RE.match(name):
            return True
        # 新增：价格动量因子
        if _EMA_SPREAD_RE.match(name) or _PRICE_TO_HIGH_RE.match(name) or _PRICE_TO_LOW_RE.match(name):
            return True
        # 新增：风险因子
        if _VAR_RE.match(name) or _ES_RE.match(name) or _DOWNSIDE_VOL_RE.match(name):
            return True
        # 新增：流动性因子
        if _AMIHUD_RE.match(name) or _OBV_SLOPE_RE.match(name):
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

        # 如果启用了缓存，先检查缓存
        if self._cache is not None:
            # 获取数据的结束时间戳
            end_timestamp = int(data.index[-1].timestamp()) if hasattr(data.index[-1], 'timestamp') else 0

            # 检查每个因子是否在缓存中
            factors_to_compute = []
            for factor_name in factor_names:
                cache_key = FactorCacheKey(
                    pair=self._current_pair or "UNKNOWN",
                    timeframe=self._current_timeframe or "1h",
                    factor_name=factor_name,
                    end_timestamp=end_timestamp
                )
                cached_value = self._cache.get(cache_key)
                if cached_value is not None:
                    out[factor_name] = cached_value
                else:
                    factors_to_compute.append(factor_name)

            # 如果所有因子都在缓存中，直接返回
            if not factors_to_compute:
                return pd.DataFrame(out, index=data.index)

            # 只计算未缓存的因子
            factor_names = factors_to_compute

        # 使用并行计算处理因子
        results = self._parallel_computer.compute_parallel(
            data, factor_names, self._compute_single_factor
        )

        # 分离成功计算的因子和需要回退的因子
        remaining_factors = []
        for factor_name in factor_names:
            if factor_name in results and results[factor_name] is not None:
                out[factor_name] = results[factor_name]
            else:
                remaining_factors.append(factor_name)

        # 如果所有因子都已通过计算器处理，直接返回
        if not remaining_factors:
            # 将新计算的因子存入缓存
            if self._cache is not None:
                end_timestamp = int(data.index[-1].timestamp()) if hasattr(data.index[-1], 'timestamp') else 0
                for factor_name, factor_value in out.items():
                    cache_key = FactorCacheKey(
                        pair=self._current_pair or "UNKNOWN",
                        timeframe=self._current_timeframe or "1h",
                        factor_name=factor_name,
                        end_timestamp=end_timestamp
                    )
                    self._cache.set(cache_key, factor_value)

            if not out:
                return pd.DataFrame(index=data.index)
            df = pd.DataFrame(out, index=data.index)
            return df.replace([np.inf, -np.inf], np.nan)

        # 对于剩余因子，使用原始实现（主要是 Koopman 等复杂因子）
        factor_names = remaining_factors

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

        # --- 新增：市场制度/流动性/熵因子 ---

        # vol_of_vol_<n>：波动的波动（滚动波动率的变化率）
        for name in factor_names:
            m = _VOL_OF_VOL_RE.match(name)
            if m is None:
                continue
            n = int(m.group(1))
            if n <= 1:
                continue
            # 先计算滚动波动率，再计算其变化率
            vol_series = ret1.rolling(n).std() if ret1 is not None else close.pct_change(1).rolling(n).std()
            out[name] = vol_series.pct_change(n)

        # ret_vol_ratio_<n>：|ret|/volume（单位成交量的价格变化，流动性冲击代理）
        for name in factor_names:
            m = _RET_VOL_RATIO_RE.match(name)
            if m is None:
                continue
            n = int(m.group(1))
            if n <= 0:
                continue
            abs_ret = close.pct_change(1).abs().rolling(n).mean()
            vol_mean = volume.rolling(n).mean().replace(0, np.nan)
            out[name] = abs_ret / vol_mean

        # rel_vol_<n>：相对成交量（volume / sma(volume, n)）
        for name in factor_names:
            m = _REL_VOL_RE.match(name)
            if m is None:
                continue
            n = int(m.group(1))
            if n <= 0:
                continue
            mean = volume.rolling(n).mean().replace(0, np.nan)
            out[name] = volume / mean

        # dir_entropy_<n>：方向熵（sign(ret) 的熵）
        for name in factor_names:
            m = _DIR_ENTROPY_RE.match(name)
            if m is None:
                continue
            n = int(m.group(1))
            if n <= 2:
                continue
            ret_sign = np.sign(close.pct_change(1))
            out[name] = ret_sign.rolling(n).apply(_calc_entropy, raw=True)

        # vol_state_entropy_<n>：波动状态熵（波动率分位离散化后的熵）
        for name in factor_names:
            m = _VOL_STATE_ENTROPY_RE.match(name)
            if m is None:
                continue
            n = int(m.group(1))
            if n <= 2:
                continue
            vol_series = ret1.rolling(n).std() if ret1 is not None else close.pct_change(1).rolling(n).std()
            # 将波动率离散化为 3 个状态（低/中/高）
            vol_state = vol_series.rolling(n).apply(lambda x: _discretize_to_state(x), raw=True)
            out[name] = vol_state.rolling(n).apply(_calc_entropy, raw=True)

        # --- 新增：信息论/风险/流动性因子（来源：docs/knowledge） ---

        # bucket_entropy_<n>：分桶收益熵（比 dir_entropy 信息量更高）
        # 来源：crypto_information_theory_signal_system_playbook.md
        for name in factor_names:
            m = _BUCKET_ENTROPY_RE.match(name)
            if m is None:
                continue
            n = int(m.group(1))
            if n <= 4:
                continue
            ret_series = close.pct_change(1)
            # 将收益分成 5 个分位桶
            def _bucket_entropy(arr: np.ndarray) -> float:
                if len(arr) < 5 or np.all(np.isnan(arr)):
                    return np.nan
                valid = arr[~np.isnan(arr)]
                if len(valid) < 5:
                    return np.nan
                # 使用分位数分桶
                try:
                    buckets = pd.qcut(valid, q=5, labels=False, duplicates="drop")
                except ValueError:
                    return np.nan
                return _calc_entropy(buckets)
            out[name] = ret_series.rolling(n).apply(_bucket_entropy, raw=True)

        # hurst_<n>：Hurst 指数（趋势/均值回归体制标签）
        # 来源：factor_single_vs_multi_timing.md
        # H > 0.5 趋势/持久性，H < 0.5 均值回归/反持久性
        for name in factor_names:
            m = _HURST_RE.match(name)
            if m is None:
                continue
            n = int(m.group(1))
            if n < 20:
                continue
            def _hurst(arr: np.ndarray) -> float:
                if len(arr) < 20 or np.all(np.isnan(arr)):
                    return np.nan
                valid = arr[~np.isnan(arr)]
                if len(valid) < 20:
                    return np.nan
                # R/S 分析法估计 Hurst 指数
                mean = np.mean(valid)
                deviations = valid - mean
                cumsum = np.cumsum(deviations)
                R = np.max(cumsum) - np.min(cumsum)
                S = np.std(valid, ddof=1)
                if S == 0:
                    return np.nan
                RS = R / S
                if RS <= 0:
                    return np.nan
                # H = log(R/S) / log(n)
                return np.log(RS) / np.log(len(valid))
            out[name] = close.rolling(n).apply(_hurst, raw=True)

        # gap_<n>：跳空缺口（开盘价与前收盘价差异的滚动均值）
        # 来源：crypto_risk_factors_engineering_playbook.md
        if "open" in data.columns:
            open_price = data["open"].astype("float64")
            for name in factor_names:
                m = _GAP_RE.match(name)
                if m is None:
                    continue
                n = int(m.group(1))
                if n <= 0:
                    continue
                gap = (open_price - close.shift(1)) / close.shift(1).replace(0, np.nan)
                out[name] = gap.rolling(n).mean()

        # tail_ratio_<n>：尾部比率（上尾/下尾风险不对称）
        # 来源：crypto_risk_factors_engineering_playbook.md
        for name in factor_names:
            m = _TAIL_RATIO_RE.match(name)
            if m is None:
                continue
            n = int(m.group(1))
            if n < 10:
                continue
            ret_series = close.pct_change(1)
            def _tail_ratio(arr: np.ndarray) -> float:
                if len(arr) < 10 or np.all(np.isnan(arr)):
                    return np.nan
                valid = arr[~np.isnan(arr)]
                if len(valid) < 10:
                    return np.nan
                q95 = np.percentile(valid, 95)
                q05 = np.percentile(valid, 5)
                if q05 == 0:
                    return np.nan
                return abs(q95 / q05) if q05 != 0 else np.nan
            out[name] = ret_series.rolling(n).apply(_tail_ratio, raw=True)

        # price_impact_<n>：价格冲击代理（|ret|/sqrt(volume)）
        # 来源：crypto_liquidity_microstructure_playbook.md
        for name in factor_names:
            m = _PRICE_IMPACT_RE.match(name)
            if m is None:
                continue
            n = int(m.group(1))
            if n <= 0:
                continue
            abs_ret = close.pct_change(1).abs()
            sqrt_vol = np.sqrt(volume.replace(0, np.nan))
            impact = abs_ret / sqrt_vol
            out[name] = impact.rolling(n).mean()

        # --- 反转因子（Reversal Factors） ---
        # 来源：学术研究表明短期反转 Sharpe 4.58

        # reversal_<n>：n日反转信号（-ret_n，即过去n日收益的负值）
        for name in factor_names:
            m = _REVERSAL_RE.match(name)
            if m is None:
                continue
            n = int(m.group(1))
            if n <= 0:
                continue
            out[name] = -close.pct_change(n)

        # zscore_close_<n>：n日价格 Z-score（均值回归信号）
        for name in factor_names:
            m = _ZSCORE_CLOSE_RE.match(name)
            if m is None:
                continue
            n = int(m.group(1))
            if n <= 1:
                continue
            mean = close.rolling(n).mean()
            std = close.rolling(n).std().replace(0, np.nan)
            out[name] = (close - mean) / std

        # --- 价格动量因子（Price Momentum） ---

        # ema_spread_<short>_<long>：EMA(short)/EMA(long) - 1
        for name in factor_names:
            m = _EMA_SPREAD_RE.match(name)
            if m is None:
                continue
            short_period = int(m.group(1))
            long_period = int(m.group(2))
            if short_period <= 0 or long_period <= 0:
                continue
            ema_short = ta.EMA(data, timeperiod=short_period)
            ema_long = ta.EMA(data, timeperiod=long_period)
            if not isinstance(ema_short, pd.Series):
                ema_short = pd.Series(ema_short, index=data.index)
            if not isinstance(ema_long, pd.Series):
                ema_long = pd.Series(ema_long, index=data.index)
            out[name] = (ema_short / ema_long.replace(0, np.nan)) - 1.0

        # price_to_high_<n>：close / highest(n) - 1
        for name in factor_names:
            m = _PRICE_TO_HIGH_RE.match(name)
            if m is None:
                continue
            n = int(m.group(1))
            if n <= 0:
                continue
            highest = high.rolling(n).max().replace(0, np.nan)
            out[name] = (close / highest) - 1.0

        # price_to_low_<n>：close / lowest(n) - 1
        for name in factor_names:
            m = _PRICE_TO_LOW_RE.match(name)
            if m is None:
                continue
            n = int(m.group(1))
            if n <= 0:
                continue
            lowest = low.rolling(n).min().replace(0, np.nan)
            out[name] = (close / lowest) - 1.0

        # --- 风险因子（Risk Factors） ---

        # var_<pct>_<n>：n日 pct% VaR（历史分布的下行分位）
        for name in factor_names:
            m = _VAR_RE.match(name)
            if m is None:
                continue
            pct = int(m.group(1))
            n = int(m.group(2))
            if pct <= 0 or pct >= 100 or n <= 1:
                continue
            ret_series = close.pct_change(1)
            out[name] = ret_series.rolling(n).quantile(pct / 100.0)

        # es_<pct>_<n>：n日 pct% ES（Expected Shortfall，条件VaR）
        for name in factor_names:
            m = _ES_RE.match(name)
            if m is None:
                continue
            pct = int(m.group(1))
            n = int(m.group(2))
            if pct <= 0 or pct >= 100 or n <= 1:
                continue
            ret_series = close.pct_change(1)
            def _es(arr: np.ndarray) -> float:
                if len(arr) < 5 or np.all(np.isnan(arr)):
                    return np.nan
                valid = arr[~np.isnan(arr)]
                if len(valid) < 5:
                    return np.nan
                threshold = np.percentile(valid, pct)
                tail = valid[valid <= threshold]
                return np.mean(tail) if len(tail) > 0 else np.nan
            out[name] = ret_series.rolling(n).apply(_es, raw=True)

        # downside_vol_<n>：n日下行波动率（仅计算负收益的标准差）
        for name in factor_names:
            m = _DOWNSIDE_VOL_RE.match(name)
            if m is None:
                continue
            n = int(m.group(1))
            if n <= 1:
                continue
            ret_series = close.pct_change(1)
            def _downside_vol(arr: np.ndarray) -> float:
                if len(arr) < 3 or np.all(np.isnan(arr)):
                    return np.nan
                valid = arr[~np.isnan(arr)]
                negative = valid[valid < 0]
                return np.std(negative, ddof=1) if len(negative) > 1 else np.nan
            out[name] = ret_series.rolling(n).apply(_downside_vol, raw=True)

        # --- 流动性因子（Liquidity Factors） ---

        # amihud_<n>：Amihud 非流动性比率（|ret|/volume 的滚动均值）
        for name in factor_names:
            m = _AMIHUD_RE.match(name)
            if m is None:
                continue
            n = int(m.group(1))
            if n <= 0:
                continue
            abs_ret = close.pct_change(1).abs()
            vol_safe = volume.replace(0, np.nan)
            amihud = abs_ret / vol_safe
            out[name] = amihud.rolling(n).mean()

        # obv_slope_<n>：OBV 斜率（n日 OBV 的线性回归斜率）
        for name in factor_names:
            m = _OBV_SLOPE_RE.match(name)
            if m is None:
                continue
            n = int(m.group(1))
            if n <= 2:
                continue
            obv = ta.OBV(data)
            if not isinstance(obv, pd.Series):
                obv = pd.Series(obv, index=data.index)
            def _slope(arr: np.ndarray) -> float:
                if len(arr) < 3 or np.all(np.isnan(arr)):
                    return np.nan
                valid = arr[~np.isnan(arr)]
                if len(valid) < 3:
                    return np.nan
                x = np.arange(len(valid))
                return np.polyfit(x, valid, 1)[0]
            out[name] = obv.rolling(n).apply(_slope, raw=True)

        # --- Koopman 本征模态因子 ---
        need_koop_core = any(n in {"koop_spectral_radius", "koop_reconstruction_error"} for n in factor_names)
        need_koop_modes = any(_KOOP_MODE_RE.match(str(n)) for n in factor_names)
        pred_horizons: set[int] = set()
        for n in factor_names:
            mm = _KOOP_PRED_RET_RE.match(str(n))
            if mm is not None:
                try:
                    hh = int(mm.group(1))
                    if hh > 0:
                        pred_horizons.add(hh)
                except Exception:
                    pass

        if need_koop_core or need_koop_modes or pred_horizons:
            feats = compute_koopman_lite_features(
                close=close,
                window=int(self._p.koop_window),
                embed_dim=int(self._p.koop_embed_dim),
                stride=int(self._p.koop_stride),
                ridge=float(self._p.koop_ridge),
                pred_horizons=sorted(pred_horizons),
                fft_window=0,  # 不再使用独立 FFT
                fft_topk=0,
            )

            for col in feats.columns:
                if col in set(factor_names):
                    out[col] = feats[col]

        if not out:
            return pd.DataFrame(index=data.index)

        # 将新计算的因子存入缓存
        if self._cache is not None:
            end_timestamp = int(data.index[-1].timestamp()) if hasattr(data.index[-1], 'timestamp') else 0
            for factor_name, factor_value in out.items():
                cache_key = FactorCacheKey(
                    pair=self._current_pair or "UNKNOWN",
                    timeframe=self._current_timeframe or "1h",
                    factor_name=factor_name,
                    end_timestamp=end_timestamp
                )
                self._cache.set(cache_key, factor_value)

        df = pd.DataFrame(out, index=data.index)
        return df.replace([np.inf, -np.inf], np.nan)

    def _compute_single_factor(self, data: pd.DataFrame, factor_name: str) -> pd.Series:
        """计算单个因子（用于并行计算）"""
        computer = self._registry.get_computer(factor_name)
        if computer is not None:
            try:
                return computer.compute(data, factor_name)
            except Exception:
                # 如果计算器失败，返回 None，稍后回退到原始实现
                return None
        return None
