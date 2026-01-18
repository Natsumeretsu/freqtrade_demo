"""技术指标因子

包含基于技术分析的因子实现。
"""

from __future__ import annotations

import pandas as pd

from integration.factor_library.base import BaseFactor
from integration.factor_library.registry import register_factor


@register_factor
class MomentumFactor(BaseFactor):
    """动量因子

    计算指定窗口期的价格变化率。
    """

    def __init__(self, window: int = 96):
        """初始化动量因子

        Args:
            window: 回看窗口（K线数量），默认96（8小时@5m）
        """
        self.window = window
        super().__init__(window=window)

    @property
    def name(self) -> str:
        return f"momentum_{self.window // 12}h"

    @property
    def description(self) -> str:
        return f"{self.window // 12}小时动量因子（价格变化率）"

    @property
    def category(self) -> str:
        return "technical"

    def calculate(self, df: pd.DataFrame) -> pd.Series:
        """计算动量因子

        Args:
            df: OHLCV 数据框

        Returns:
            动量因子值（价格变化率）
        """
        return df["close"].pct_change(self.window)

    def _validate_params(self) -> None:
        """验证参数"""
        if self.window <= 0:
            msg = f"window 必须大于0，当前值: {self.window}"
            raise ValueError(msg)


@register_factor
class VolatilityFactor(BaseFactor):
    """波动率因子

    计算指定窗口期的价格波动率（标准差）。
    """

    def __init__(self, window: int = 288):
        """初始化波动率因子

        Args:
            window: 回看窗口（K线数量），默认288（24小时@5m）
        """
        self.window = window
        super().__init__(window=window)

    @property
    def name(self) -> str:
        return f"volatility_{self.window // 12}h"

    @property
    def description(self) -> str:
        return f"{self.window // 12}小时波动率因子（收益率标准差）"

    @property
    def category(self) -> str:
        return "technical"

    def calculate(self, df: pd.DataFrame) -> pd.Series:
        """计算波动率因子

        Args:
            df: OHLCV 数据框

        Returns:
            波动率因子值（收益率标准差）
        """
        returns = df["close"].pct_change()
        return returns.rolling(window=self.window).std()

    def _validate_params(self) -> None:
        """验证参数"""
        if self.window <= 1:
            msg = f"window 必须大于1，当前值: {self.window}"
            raise ValueError(msg)


@register_factor
class VolumeSurgeFactor(BaseFactor):
    """成交量激增因子

    检测成交量相对于历史均值的激增程度。
    """

    def __init__(self, window: int = 96, threshold: float = 2.0):
        """初始化成交量激增因子

        Args:
            window: 回看窗口（K线数量），默认96（8小时@5m）
            threshold: 激增阈值（倍数），默认2.0
        """
        self.window = window
        self.threshold = threshold
        super().__init__(window=window, threshold=threshold)

    @property
    def name(self) -> str:
        return "volume_surge"

    @property
    def description(self) -> str:
        return f"成交量激增因子（当前成交量 / {self.window}期均值）"

    @property
    def category(self) -> str:
        return "volume"

    def calculate(self, df: pd.DataFrame) -> pd.Series:
        """计算成交量激增因子

        Args:
            df: OHLCV 数据框

        Returns:
            成交量激增因子值（当前成交量 / 历史均值）
        """
        volume_ma = df["volume"].rolling(window=self.window).mean()
        return df["volume"] / volume_ma

    def _validate_params(self) -> None:
        """验证参数"""
        if self.window <= 0:
            msg = f"window 必须大于0，当前值: {self.window}"
            raise ValueError(msg)
        if self.threshold <= 0:
            msg = f"threshold 必须大于0，当前值: {self.threshold}"
            raise ValueError(msg)


@register_factor
class SMAFactor(BaseFactor):
    """简单移动平均线因子"""

    def __init__(self, window: int = 20):
        self.window = window
        super().__init__(window=window)

    @property
    def name(self) -> str:
        return "sma_20"

    @property
    def description(self) -> str:
        return "简单移动平均线"

    @property
    def category(self) -> str:
        return "technical"

    def calculate(self, df: pd.DataFrame) -> pd.Series:
        return df["close"].rolling(self.window).mean()

    def _validate_params(self) -> None:
        if self.window <= 0:
            msg = f"window 必须大于0，当前值: {self.window}"
            raise ValueError(msg)


@register_factor
class EMAFactor(BaseFactor):
    """指数移动平均线因子"""

    def __init__(self, window: int = 20):
        self.window = window
        super().__init__(window=window)

    @property
    def name(self) -> str:
        return "ema_20"

    @property
    def description(self) -> str:
        return "指数移动平均线"

    @property
    def category(self) -> str:
        return "technical"

    def calculate(self, df: pd.DataFrame) -> pd.Series:
        return df["close"].ewm(span=self.window, adjust=False).mean()

    def _validate_params(self) -> None:
        if self.window <= 0:
            msg = f"window 必须大于0，当前值: {self.window}"
            raise ValueError(msg)


@register_factor
class MACrossoverFactor(BaseFactor):
    """均线交叉信号因子"""

    def __init__(self, fast_window: int = 5, slow_window: int = 20):
        self.fast_window = fast_window
        self.slow_window = slow_window
        super().__init__(fast_window=fast_window, slow_window=slow_window)

    @property
    def name(self) -> str:
        return "ma_cross_5_20"

    @property
    def description(self) -> str:
        return "均线交叉信号"

    @property
    def category(self) -> str:
        return "technical"

    def calculate(self, df: pd.DataFrame) -> pd.Series:
        fast_ma = df["close"].rolling(self.fast_window).mean()
        slow_ma = df["close"].rolling(self.slow_window).mean()
        return (fast_ma - slow_ma) / slow_ma

    def _validate_params(self) -> None:
        if self.fast_window <= 0:
            msg = f"fast_window 必须大于0，当前值: {self.fast_window}"
            raise ValueError(msg)
        if self.slow_window <= 0:
            msg = f"slow_window 必须大于0，当前值: {self.slow_window}"
            raise ValueError(msg)
        if self.fast_window >= self.slow_window:
            msg = "fast_window 必须小于 slow_window"
            raise ValueError(msg)


@register_factor
class PriceToSMAFactor(BaseFactor):
    """价格相对 SMA 的偏离度因子"""

    def __init__(self, window: int = 20):
        self.window = window
        super().__init__(window=window)

    @property
    def name(self) -> str:
        return "price_to_sma_20"

    @property
    def description(self) -> str:
        return "价格相对简单移动平均线的偏离度"

    @property
    def category(self) -> str:
        return "technical"

    def calculate(self, df: pd.DataFrame) -> pd.Series:
        sma = df["close"].rolling(self.window).mean()
        return (df["close"] - sma) / sma

    def _validate_params(self) -> None:
        if self.window <= 0:
            msg = f"window 必须大于0，当前值: {self.window}"
            raise ValueError(msg)


@register_factor
class SMADistanceFactor(BaseFactor):
    """快慢均线距离因子"""

    def __init__(self, fast_window: int = 5, slow_window: int = 20):
        self.fast_window = fast_window
        self.slow_window = slow_window
        super().__init__(fast_window=fast_window, slow_window=slow_window)

    @property
    def name(self) -> str:
        return "sma_distance_5_20"

    @property
    def description(self) -> str:
        return "快慢均线距离"

    @property
    def category(self) -> str:
        return "technical"

    def calculate(self, df: pd.DataFrame) -> pd.Series:
        fast_sma = df["close"].rolling(self.fast_window).mean()
        slow_sma = df["close"].rolling(self.slow_window).mean()
        return (fast_sma - slow_sma) / slow_sma

    def _validate_params(self) -> None:
        if self.fast_window <= 0:
            msg = f"fast_window 必须大于0，当前值: {self.fast_window}"
            raise ValueError(msg)
        if self.slow_window <= 0:
            msg = f"slow_window 必须大于0，当前值: {self.slow_window}"
            raise ValueError(msg)
        if self.fast_window >= self.slow_window:
            msg = "fast_window 必须小于 slow_window"
            raise ValueError(msg)


@register_factor
class RSIFactor(BaseFactor):
    """相对强弱指标因子"""

    def __init__(self, window: int = 14):
        self.window = window
        super().__init__(window=window)

    @property
    def name(self) -> str:
        return "rsi_14"

    @property
    def description(self) -> str:
        return "相对强弱指标"

    @property
    def category(self) -> str:
        return "technical"

    def calculate(self, df: pd.DataFrame) -> pd.Series:
        delta = df["close"].diff()
        gain = (delta.where(delta > 0, 0)).rolling(self.window).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(self.window).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))

    def _validate_params(self) -> None:
        if self.window <= 0:
            msg = f"window 必须大于0，当前值: {self.window}"
            raise ValueError(msg)


@register_factor
class MACDFactor(BaseFactor):
    """MACD 指标因子"""

    def __init__(self, fast: int = 12, slow: int = 26, signal: int = 9):
        self.fast = fast
        self.slow = slow
        self.signal = signal
        super().__init__(fast=fast, slow=slow, signal=signal)

    @property
    def name(self) -> str:
        return "macd_12_26_9"

    @property
    def description(self) -> str:
        return "MACD 指标"

    @property
    def category(self) -> str:
        return "technical"

    def calculate(self, df: pd.DataFrame) -> pd.Series:
        ema_fast = df["close"].ewm(span=self.fast, adjust=False).mean()
        ema_slow = df["close"].ewm(span=self.slow, adjust=False).mean()
        macd = ema_fast - ema_slow
        signal_line = macd.ewm(span=self.signal, adjust=False).mean()
        return macd - signal_line

    def _validate_params(self) -> None:
        if self.fast <= 0:
            msg = f"fast 必须大于0，当前值: {self.fast}"
            raise ValueError(msg)
        if self.slow <= 0:
            msg = f"slow 必须大于0，当前值: {self.slow}"
            raise ValueError(msg)
        if self.signal <= 0:
            msg = f"signal 必须大于0，当前值: {self.signal}"
            raise ValueError(msg)


@register_factor
class ROCFactor(BaseFactor):
    """变化率指标因子"""

    def __init__(self, window: int = 12):
        self.window = window
        super().__init__(window=window)

    @property
    def name(self) -> str:
        return "roc_12"

    @property
    def description(self) -> str:
        return "变化率指标"

    @property
    def category(self) -> str:
        return "technical"

    def calculate(self, df: pd.DataFrame) -> pd.Series:
        return ((df["close"] - df["close"].shift(self.window)) / df["close"].shift(self.window)) * 100

    def _validate_params(self) -> None:
        if self.window <= 0:
            msg = f"window 必须大于0，当前值: {self.window}"
            raise ValueError(msg)


@register_factor
class StochRSIFactor(BaseFactor):
    """随机 RSI 因子"""

    def __init__(self, window: int = 14, smooth_k: int = 3, smooth_d: int = 3):
        self.window = window
        self.smooth_k = smooth_k
        self.smooth_d = smooth_d
        super().__init__(window=window, smooth_k=smooth_k, smooth_d=smooth_d)

    @property
    def name(self) -> str:
        return "stoch_rsi_14"

    @property
    def description(self) -> str:
        return "随机 RSI"

    @property
    def category(self) -> str:
        return "technical"

    def calculate(self, df: pd.DataFrame) -> pd.Series:
        # 先计算 RSI
        delta = df["close"].diff()
        gain = (delta.where(delta > 0, 0)).rolling(self.window).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(self.window).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))

        # 计算 Stochastic RSI
        rsi_min = rsi.rolling(self.window).min()
        rsi_max = rsi.rolling(self.window).max()
        stoch_rsi = (rsi - rsi_min) / (rsi_max - rsi_min)

        # K 线平滑
        k = stoch_rsi.rolling(self.smooth_k).mean()
        return k

    def _validate_params(self) -> None:
        if self.window <= 0:
            msg = f"window 必须大于0，当前值: {self.window}"
            raise ValueError(msg)
        if self.smooth_k <= 0:
            msg = f"smooth_k 必须大于0，当前值: {self.smooth_k}"
            raise ValueError(msg)
        if self.smooth_d <= 0:
            msg = f"smooth_d 必须大于0，当前值: {self.smooth_d}"
            raise ValueError(msg)


@register_factor
class WilliamsRFactor(BaseFactor):
    """威廉指标因子"""

    def __init__(self, window: int = 14):
        self.window = window
        super().__init__(window=window)

    @property
    def name(self) -> str:
        return "williams_r_14"

    @property
    def description(self) -> str:
        return "威廉指标"

    @property
    def category(self) -> str:
        return "technical"

    def calculate(self, df: pd.DataFrame) -> pd.Series:
        highest_high = df["high"].rolling(self.window).max()
        lowest_low = df["low"].rolling(self.window).min()
        return ((highest_high - df["close"]) / (highest_high - lowest_low)) * -100

    def _validate_params(self) -> None:
        if self.window <= 0:
            msg = f"window 必须大于0，当前值: {self.window}"
            raise ValueError(msg)


@register_factor
class ATRFactor(BaseFactor):
    """平均真实波幅因子"""

    def __init__(self, window: int = 14):
        self.window = window
        super().__init__(window=window)

    @property
    def name(self) -> str:
        return "atr_14"

    @property
    def description(self) -> str:
        return "平均真实波幅"

    @property
    def category(self) -> str:
        return "technical"

    def calculate(self, df: pd.DataFrame) -> pd.Series:
        high_low = df["high"] - df["low"]
        high_close = (df["high"] - df["close"].shift()).abs()
        low_close = (df["low"] - df["close"].shift()).abs()
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        return tr.rolling(self.window).mean()

    def _validate_params(self) -> None:
        if self.window <= 0:
            msg = f"window 必须大于0，当前值: {self.window}"
            raise ValueError(msg)


@register_factor
class BollingerBandWidthFactor(BaseFactor):
    """布林带宽度因子"""

    def __init__(self, window: int = 20, num_std: float = 2.0):
        self.window = window
        self.num_std = num_std
        super().__init__(window=window, num_std=num_std)

    @property
    def name(self) -> str:
        return "bb_width_20"

    @property
    def description(self) -> str:
        return "布林带宽度"

    @property
    def category(self) -> str:
        return "technical"

    def calculate(self, df: pd.DataFrame) -> pd.Series:
        sma = df["close"].rolling(self.window).mean()
        std = df["close"].rolling(self.window).std()
        upper_band = sma + (std * self.num_std)
        lower_band = sma - (std * self.num_std)
        return (upper_band - lower_band) / sma

    def _validate_params(self) -> None:
        if self.window <= 0:
            msg = f"window 必须大于0，当前值: {self.window}"
            raise ValueError(msg)
        if self.num_std <= 0:
            msg = f"num_std 必须大于0，当前值: {self.num_std}"
            raise ValueError(msg)


@register_factor
class BollingerBandPositionFactor(BaseFactor):
    """价格在布林带中的位置因子"""

    def __init__(self, window: int = 20, num_std: float = 2.0):
        self.window = window
        self.num_std = num_std
        super().__init__(window=window, num_std=num_std)

    @property
    def name(self) -> str:
        return "bb_position_20"

    @property
    def description(self) -> str:
        return "价格在布林带中的位置"

    @property
    def category(self) -> str:
        return "technical"

    def calculate(self, df: pd.DataFrame) -> pd.Series:
        sma = df["close"].rolling(self.window).mean()
        std = df["close"].rolling(self.window).std()
        upper_band = sma + (std * self.num_std)
        lower_band = sma - (std * self.num_std)
        return (df["close"] - lower_band) / (upper_band - lower_band)

    def _validate_params(self) -> None:
        if self.window <= 0:
            msg = f"window 必须大于0，当前值: {self.window}"
            raise ValueError(msg)
        if self.num_std <= 0:
            msg = f"num_std 必须大于0，当前值: {self.num_std}"
            raise ValueError(msg)


@register_factor
class KeltnerChannelWidthFactor(BaseFactor):
    """Keltner 通道宽度因子"""

    def __init__(self, window: int = 20, atr_window: int = 10, multiplier: float = 2.0):
        self.window = window
        self.atr_window = atr_window
        self.multiplier = multiplier
        super().__init__(window=window, atr_window=atr_window, multiplier=multiplier)

    @property
    def name(self) -> str:
        return "keltner_width_20"

    @property
    def description(self) -> str:
        return "Keltner 通道宽度"

    @property
    def category(self) -> str:
        return "technical"

    def calculate(self, df: pd.DataFrame) -> pd.Series:
        ema = df["close"].ewm(span=self.window, adjust=False).mean()

        # 计算 ATR
        high_low = df["high"] - df["low"]
        high_close = (df["high"] - df["close"].shift()).abs()
        low_close = (df["low"] - df["close"].shift()).abs()
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr = tr.rolling(self.atr_window).mean()

        upper_band = ema + (atr * self.multiplier)
        lower_band = ema - (atr * self.multiplier)
        return (upper_band - lower_band) / ema

    def _validate_params(self) -> None:
        if self.window <= 0:
            msg = f"window 必须大于0，当前值: {self.window}"
            raise ValueError(msg)
        if self.atr_window <= 0:
            msg = f"atr_window 必须大于0，当前值: {self.atr_window}"
            raise ValueError(msg)
        if self.multiplier <= 0:
            msg = f"multiplier 必须大于0，当前值: {self.multiplier}"
            raise ValueError(msg)


@register_factor
class HistoricalVolatilityFactor(BaseFactor):
    """历史波动率因子"""

    def __init__(self, window: int = 20):
        self.window = window
        super().__init__(window=window)

    @property
    def name(self) -> str:
        return "hist_vol_20"

    @property
    def description(self) -> str:
        return "历史波动率"

    @property
    def category(self) -> str:
        return "technical"

    def calculate(self, df: pd.DataFrame) -> pd.Series:
        import numpy as np
        log_returns = np.log(df["close"] / df["close"].shift())
        return log_returns.rolling(self.window).std() * (252 ** 0.5)

    def _validate_params(self) -> None:
        if self.window <= 0:
            msg = f"window 必须大于0，当前值: {self.window}"
            raise ValueError(msg)


@register_factor
class OBVFactor(BaseFactor):
    """能量潮指标因子"""

    def __init__(self):
        super().__init__()

    @property
    def name(self) -> str:
        return "obv"

    @property
    def description(self) -> str:
        return "能量潮指标"

    @property
    def category(self) -> str:
        return "volume"

    def calculate(self, df: pd.DataFrame) -> pd.Series:
        obv = (df["volume"] * ((df["close"] - df["close"].shift()) > 0).astype(int) -
               df["volume"] * ((df["close"] - df["close"].shift()) < 0).astype(int)).cumsum()
        return obv

    def _validate_params(self) -> None:
        pass


@register_factor
class CMFFactor(BaseFactor):
    """资金流量指标因子"""

    def __init__(self, window: int = 20):
        self.window = window
        super().__init__(window=window)

    @property
    def name(self) -> str:
        return "cmf_20"

    @property
    def description(self) -> str:
        return "资金流量指标"

    @property
    def category(self) -> str:
        return "volume"

    def calculate(self, df: pd.DataFrame) -> pd.Series:
        mf_multiplier = ((df["close"] - df["low"]) - (df["high"] - df["close"])) / (df["high"] - df["low"])
        mf_volume = mf_multiplier * df["volume"]
        cmf = mf_volume.rolling(self.window).sum() / df["volume"].rolling(self.window).sum()
        return cmf

    def _validate_params(self) -> None:
        if self.window <= 0:
            msg = f"window 必须大于0，当前值: {self.window}"
            raise ValueError(msg)


@register_factor
class VWAPFactor(BaseFactor):
    """成交量加权平均价因子"""

    def __init__(self, window: int = 20):
        self.window = window
        super().__init__(window=window)

    @property
    def name(self) -> str:
        return "vwap_20"

    @property
    def description(self) -> str:
        return "成交量加权平均价"

    @property
    def category(self) -> str:
        return "volume"

    def calculate(self, df: pd.DataFrame) -> pd.Series:
        typical_price = (df["high"] + df["low"] + df["close"]) / 3
        vwap = (typical_price * df["volume"]).rolling(self.window).sum() / df["volume"].rolling(self.window).sum()
        return (df["close"] - vwap) / vwap

    def _validate_params(self) -> None:
        if self.window <= 0:
            msg = f"window 必须大于0，当前值: {self.window}"
            raise ValueError(msg)


@register_factor
class VolumeWeightedMomentumFactor(BaseFactor):
    """成交量加权动量因子"""

    def __init__(self, window: int = 20):
        self.window = window
        super().__init__(window=window)

    @property
    def name(self) -> str:
        return "vol_weighted_mom_20"

    @property
    def description(self) -> str:
        return "成交量加权动量"

    @property
    def category(self) -> str:
        return "volume"

    def calculate(self, df: pd.DataFrame) -> pd.Series:
        returns = df["close"].pct_change()
        volume_weight = df["volume"] / df["volume"].rolling(self.window).mean()
        return (returns * volume_weight).rolling(self.window).sum()

    def _validate_params(self) -> None:
        if self.window <= 0:
            msg = f"window 必须大于0，当前值: {self.window}"
            raise ValueError(msg)


@register_factor
class TrendStrengthFactor(BaseFactor):
    """趋势强度因子"""

    def __init__(self, window: int = 20):
        self.window = window
        super().__init__(window=window)

    @property
    def name(self) -> str:
        return "trend_strength_20"

    @property
    def description(self) -> str:
        return "趋势强度"

    @property
    def category(self) -> str:
        return "technical"

    def calculate(self, df: pd.DataFrame) -> pd.Series:
        # 使用线性回归斜率衡量趋势强度
        import numpy as np

        def calc_slope(series):
            if len(series) < 2:
                return np.nan
            x = np.arange(len(series))
            y = series.values
            if np.all(np.isnan(y)):
                return np.nan
            valid_mask = ~np.isnan(y)
            if valid_mask.sum() < 2:
                return np.nan
            slope = np.polyfit(x[valid_mask], y[valid_mask], 1)[0]
            return slope

        return df["close"].rolling(self.window).apply(calc_slope, raw=False)

    def _validate_params(self) -> None:
        if self.window <= 0:
            msg = f"window 必须大于0，当前值: {self.window}"
            raise ValueError(msg)

