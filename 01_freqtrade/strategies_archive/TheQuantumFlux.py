from __future__ import annotations

from datetime import datetime, timedelta
from functools import reduce

import numpy as np
import talib.abstract as ta
from pandas import DataFrame, Series

from freqtrade.persistence import Trade
from freqtrade.strategy import IStrategy, merge_informative_pair
from freqtrade.strategy.strategy_helper import stoploss_from_absolute


class TheQuantumFlux(IStrategy):
    """
    The Quantum Flux（量子通量）——多因子融合自适应振荡器（QFC）策略（期货，多/空）。

    设计目标：
    - 把趋势（ADX）、动量（RSI）、波动（ATR）、量能（CMF）归一化后做自适应融合；
    - 用 1h EMA200 做宏观门控：牛市只做多，熊市只做空；
    - 风控使用 ATR（1:2 风险收益）+ 时间超时退出，不依赖 minimal_roi。
    """

    INTERFACE_VERSION = 3

    timeframe = "5m"
    can_short = True
    process_only_new_candles = True

    # 用户指定：滚动归一化需要较长窗口
    startup_candle_count: int = 200

    use_exit_signal = True
    use_custom_stoploss = True

    # 禁用 ROI（由 custom_exit 主导出场），设置极高阈值仅作兜底
    minimal_roi = {"0": 1.0}
    stoploss = -0.25

    # --- 指标参数（加密偏快设置）---
    rsi_period = 12
    adx_period = 10
    atr_period = 10
    cmf_period = 14

    norm_window = 100

    # --- 权重（基础 + 趋势增强）---
    weight_trend_base = 0.2
    weight_mom = 0.3
    weight_vol_base = 0.3
    weight_volu = 0.2
    adx_strong_trend_threshold = 25.0
    weight_trend_strong = 0.4
    weight_vol_strong = 0.1

    # --- QFC 动态阈值（“布林逻辑”）---
    qfc_std_window = 20
    qfc_std_mult = 1.8

    # --- 宏观门控（1h EMA200）---
    macro_timeframe = "1h"
    macro_ema_period = 200

    # --- 风控（ATR）---
    stoploss_atr_mult = 2.5  # 放宽止损，避免被震出
    takeprofit_atr_mult = 5.0  # 保持 1:2 风险收益
    timeout = timedelta(minutes=180)  # 延长超时到 3 小时
    timeout_min_profit = 0.002  # 0.2%
    timeout_loss = timedelta(minutes=90)  # 亏损单 90 分钟退出（原 30 太激进）

    # --- 保护机制（宽松版）---
    protections = [
        {"method": "CooldownPeriod", "stop_duration_candles": 1},
    ]

    # 执行层：默认用市价以减少"信号失真/错过成交"
    order_types = {
        "entry": "market",
        "exit": "market",
        "stoploss": "market",
        "stoploss_on_exchange": False,
    }
    order_time_in_force = {"entry": "GTC", "exit": "GTC"}

    def informative_pairs(self):
        """
        为每个交易对增加 1h 信息周期，用于计算 EMA200 宏观门控。
        """
        dp = getattr(self, "dp", None)
        if dp is None:
            return []

        try:
            pairs = dp.current_whitelist()
        except Exception:
            return []

        inf_tf = str(getattr(self, "macro_timeframe", "1h"))
        return list(dict.fromkeys((pair, inf_tf) for pair in pairs))

    @staticmethod
    def _minmax_norm(series: Series, window: int) -> Series:
        w = int(max(2, window))
        roll_min = series.rolling(window=w, min_periods=w).min()
        roll_max = series.rolling(window=w, min_periods=w).max()
        denom = (roll_max - roll_min).replace(0, np.nan)
        out = (series - roll_min) / denom
        return out.clip(lower=0.0, upper=1.0)

    @staticmethod
    def _calc_cmf(dataframe: DataFrame, period: int) -> Series:
        """
        CMF(Chaikin Money Flow) 手工实现：
        Sum(MFM * Vol, n) / Sum(Vol, n)
        其中 MFM = ((Close-Low) - (High-Close)) / (High-Low)
        """
        p = int(max(2, period))
        high = dataframe["high"].astype("float64")
        low = dataframe["low"].astype("float64")
        close = dataframe["close"].astype("float64")
        vol = dataframe["volume"].astype("float64")

        hl = (high - low).astype("float64")
        mfm = np.where(hl != 0.0, ((close - low) - (high - close)) / hl, 0.0)
        mfv = (mfm * vol).astype("float64")

        vol_sum = vol.rolling(window=p, min_periods=p).sum().replace(0, np.nan)
        mfv_sum = mfv.rolling(window=p, min_periods=p).sum()
        cmf = mfv_sum / vol_sum
        return cmf.replace([np.inf, -np.inf], np.nan)

    @staticmethod
    def _calc_hma(close: Series, period: int) -> Series:
        """
        HMA（Hull Moving Average）：
        HMA(n) = WMA( 2*WMA(price, n/2) - WMA(price, n), sqrt(n) )
        """
        p = int(max(2, period))
        half = int(max(1, p // 2))
        sqrt_p = int(max(1, int(np.sqrt(p))))

        # talib.abstract 在传入 Series 时可能返回 ndarray，这里统一使用 DataFrame 输入以保证返回 Series
        wma_half = ta.WMA(close.to_frame("close"), timeperiod=half)
        wma_full = ta.WMA(close.to_frame("close"), timeperiod=p)
        raw = (2.0 * wma_half) - wma_full
        hma = ta.WMA(raw.to_frame("close"), timeperiod=sqrt_p)
        return hma.replace([np.inf, -np.inf], np.nan)

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        df = dataframe.copy()

        # --- Raw Indicators ---
        df["rsi_12"] = ta.RSI(df, timeperiod=int(self.rsi_period))
        df["adx_10"] = ta.ADX(df, timeperiod=int(self.adx_period))
        df["atr_10"] = ta.ATR(df, timeperiod=int(self.atr_period))
        df["cmf_14"] = self._calc_cmf(df, int(self.cmf_period))

        # --- Normalization (0~1) ---
        df["rsi_n"] = self._minmax_norm(df["rsi_12"], int(self.norm_window))
        df["adx_n"] = self._minmax_norm(df["adx_10"], int(self.norm_window))
        df["atr_n"] = self._minmax_norm(df["atr_10"], int(self.norm_window))
        df["cmf_n"] = self._minmax_norm(df["cmf_14"], int(self.norm_window))

        # --- Simplified QFC: RSI + CMF only (方向一致的指标) ---
        # RSI 低 + CMF 低 = 超卖（做多）
        # RSI 高 + CMF 高 = 超买（做空）
        df["qfc_value"] = ((df["rsi_n"] * 0.6) + (df["cmf_n"] * 0.4)) * 100.0
        df["qfc_value"] = df["qfc_value"].clip(lower=0.0, upper=100.0)

        # --- Dynamic Thresholds (Bollinger-style) ---
        std = df["qfc_value"].rolling(window=int(self.qfc_std_window), min_periods=int(self.qfc_std_window)).std(ddof=0)
        df["qfc_std"] = std
        mult = float(self.qfc_std_mult)
        df["qfc_upper"] = 50.0 + (std * mult)
        df["qfc_lower"] = 50.0 - (std * mult)

        # --- Macro Filter (1h EMA200) ---
        dp = getattr(self, "dp", None)
        if dp is not None:
            inf_tf = str(getattr(self, "macro_timeframe", "1h"))
            try:
                informative = dp.get_pair_dataframe(pair=metadata["pair"], timeframe=inf_tf)
            except Exception:
                informative = None

            if informative is not None and not informative.empty:
                inf = informative.copy()
                inf["ema_200"] = ta.EMA(inf, timeperiod=int(self.macro_ema_period))
                inf_small = inf[["date", "ema_200"]].copy().replace([np.inf, -np.inf], np.nan)
                df = merge_informative_pair(df, inf_small, self.timeframe, inf_tf, ffill=True)

        return df.replace([np.inf, -np.inf], np.nan)

    def populate_entry_trend(self, df: DataFrame, metadata: dict) -> DataFrame:
        inf_tf = str(getattr(self, "macro_timeframe", "1h"))
        ema_col = f"ema_200_{inf_tf}"

        if ema_col not in df.columns:
            # 缺少宏观门控数据时不交易（避免误判）
            df["enter_long"] = 0
            df["enter_short"] = 0
            return df

        is_bull = (df[ema_col].notna() & (df["close"] > df[ema_col])).fillna(False)
        is_bear = (df[ema_col].notna() & (df["close"] < df[ema_col])).fillna(False)

        qfc = df["qfc_value"]

        # 简化入场：QFC 超卖/超买 + 拐头 + ADX 过滤
        # 做多：QFC < 25 且拐头向上 + ADX > 25 + 牛市（收紧条件）
        pullback_up = (qfc < 25.0) & (qfc > qfc.shift(1)) & (qfc.shift(1) > qfc.shift(2))
        # 做空：QFC > 75 且拐头向下 + ADX > 25 + 熊市
        pullback_down = (qfc > 75.0) & (qfc < qfc.shift(1)) & (qfc.shift(1) < qfc.shift(2))

        # ADX 过滤：只在趋势明确时交易（收紧到 25）
        adx_ok = df["adx_10"] > 25.0

        base = [
            df["volume"] > 0,
            qfc.notna(),
            adx_ok,
        ]

        long_conditions = [
            *base,
            is_bull,
            pullback_up.fillna(False),
        ]
        short_conditions = [
            *base,
            is_bear,
            pullback_down.fillna(False),
        ]

        df.loc[reduce(lambda x, y: x & y, long_conditions), ["enter_long", "enter_tag"]] = (1, "QFC_LONG")
        df.loc[reduce(lambda x, y: x & y, short_conditions), ["enter_short", "enter_tag"]] = (1, "QFC_SHORT")
        return df

    def populate_exit_trend(self, df: DataFrame, metadata: dict) -> DataFrame:
        """
        出场由 custom_exit / custom_stoploss 控制，这里保持最小实现即可。
        """
        return df

    def _get_last_analyzed_candle(self, pair: str) -> dict | None:
        dp = getattr(self, "dp", None)
        if dp is None:
            return None
        try:
            dataframe, _ = dp.get_analyzed_dataframe(pair, self.timeframe)
        except Exception:
            return None
        if dataframe is None or dataframe.empty:
            return None
        candle = dataframe.iloc[-1]
        try:
            return candle.to_dict()
        except Exception:
            return None

    def leverage(
        self,
        pair: str,
        current_time: datetime,
        current_rate: float,
        proposed_leverage: float,
        max_leverage: float,
        entry_tag: str | None,
        side: str,
        **kwargs,
    ) -> float:
        # 激进版：5x 杠杆
        return float(min(5.0, max_leverage))

    def custom_stoploss(
        self,
        pair: str,
        trade: Trade,
        current_time: datetime,
        current_rate: float,
        current_profit: float,
        after_fill: bool,
        **kwargs,
    ) -> float | None:
        """
        动态止损：
        - 基础：2.5 * ATR(10)
        - 追踪：盈利 5% 后收紧到 2%
        """
        # 追踪止损：盈利 5% 后收紧
        if current_profit >= 0.05:
            return 0.02  # 止损收紧到 2%

        candle = self._get_last_analyzed_candle(pair)
        if not candle:
            return None

        atr = float(candle.get("atr_10", float("nan")))
        if not np.isfinite(atr) or atr <= 0:
            return None

        open_rate = float(getattr(trade, "open_rate", float("nan")))
        if not np.isfinite(open_rate) or open_rate <= 0:
            return None

        is_short = bool(getattr(trade, "is_short", False))
        mult = float(max(0.0, self.stoploss_atr_mult))
        stop_rate = open_rate + (atr * mult) if is_short else open_rate - (atr * mult)

        leverage = float(getattr(trade, "leverage", 1.0) or 1.0)
        leverage = float(max(1.0, leverage))
        return float(stoploss_from_absolute(stop_rate, float(current_rate), is_short=is_short, leverage=leverage))

    def custom_exit(
        self,
        pair: str,
        trade: Trade,
        current_time: datetime,
        current_rate: float,
        current_profit: float,
        **kwargs,
    ) -> str | None:
        """
        出场规则：
        - 止盈：5.0 * ATR(10)
        - 亏损快速退出：30 分钟
        - 超时：90 分钟 且 profit < 0.3%
        """
        opened_at = getattr(trade, "open_date_utc", None) or getattr(trade, "open_date", None)
        if opened_at is None:
            return None

        # 亏损单快速退出：30 分钟
        if current_profit < 0 and current_time >= opened_at + self.timeout_loss:
            return "QFC_LOSS_TIMEOUT"

        candle = self._get_last_analyzed_candle(pair)
        if candle:
            atr = float(candle.get("atr_10", float("nan")))
        else:
            atr = float("nan")

        open_rate = float(getattr(trade, "open_rate", float("nan")))
        if np.isfinite(open_rate) and open_rate > 0 and np.isfinite(atr) and atr > 0:
            mult = float(max(0.0, self.takeprofit_atr_mult))
            is_short = bool(getattr(trade, "is_short", False))
            target = open_rate - (atr * mult) if is_short else open_rate + (atr * mult)

            if is_short:
                if float(current_rate) <= float(target):
                    return "QFC_TP"
            else:
                if float(current_rate) >= float(target):
                    return "QFC_TP"

        # 普通超时
        if current_time >= opened_at + self.timeout and current_profit < self.timeout_min_profit:
            return "QFC_TIMEOUT"

        return None

    def custom_exit_price(
        self,
        pair: str,
        trade: Trade,
        current_time: datetime,
        proposed_rate: float,
        current_profit: float,
        exit_tag: str | None,
        **kwargs,
    ) -> float:
        """
        出场报价：
        - QFC_TP：用 Entry ± 3*ATR 的目标价（更符合“固定 RR”）
        - QFC_TIMEOUT：用更贴近“市价”的让价限价近似（提高成交概率）
        """
        tag = (exit_tag or "").strip()
        is_short = bool(getattr(trade, "is_short", False))

        if tag == "QFC_TP":
            candle = self._get_last_analyzed_candle(pair)
            if candle:
                atr = float(candle.get("atr_10", float("nan")))
            else:
                atr = float("nan")

            open_rate = float(getattr(trade, "open_rate", float("nan")))
            if np.isfinite(open_rate) and open_rate > 0 and np.isfinite(atr) and atr > 0:
                mult = float(max(0.0, self.takeprofit_atr_mult))
                target = open_rate - (atr * mult) if is_short else open_rate + (atr * mult)
                if np.isfinite(target) and target > 0:
                    return float(target)

        if tag == "QFC_TIMEOUT":
            rate = float(proposed_rate)
            slip = 0.001  # 0.1%
            # 平空：买回 -> 稍高更易成交；平多：卖出 -> 稍低更易成交
            return float(rate * (1.0 + slip)) if is_short else float(rate * (1.0 - slip))

        return float(proposed_rate)
