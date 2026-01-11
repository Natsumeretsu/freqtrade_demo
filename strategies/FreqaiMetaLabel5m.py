"""
FreqAI 5-Minute Scalping Strategy

Core Logic:
1. Model predicts direction (long/short/neutral) based on future price movement
2. Entry: Model prediction + trend alignment + RSI filter
3. Exit: Time-based or signal reversal

Optimized for high-frequency 5m trading.
"""
from __future__ import annotations

import logging
from datetime import datetime

import numpy as np
import talib.abstract as ta
from pandas import DataFrame

from freqtrade.persistence import Trade
from freqtrade.strategy import IStrategy

logger = logging.getLogger(__name__)


class FreqaiMetaLabel5m(IStrategy):

    INTERFACE_VERSION = 3

    # ==================== Core Config ====================
    timeframe = "5m"
    process_only_new_candles = True
    startup_candle_count = 500
    can_short = True
    use_exit_signal = True

    # ==================== Risk Management ====================
    stoploss = -0.015  # 1.5% tight stop for 5m scalping
    trailing_stop = True
    trailing_stop_positive = 0.005  # Start trailing at 0.5%
    trailing_stop_positive_offset = 0.01  # Trail 0.5% behind
    trailing_only_offset_is_reached = True

    minimal_roi = {"0": 0.015, "30": 0.008, "60": 0.004}  # 1.5% -> 0.8% -> 0.4%

    # ==================== Protection ====================
    protections = [
        {"method": "CooldownPeriod", "stop_duration_candles": 3},
        {
            "method": "StoplossGuard",
            "lookback_period_candles": 288,
            "trade_limit": 3,
            "stop_duration_candles": 36,
            "only_per_pair": True,
        },
    ]

    # ==================== Leverage ====================
    leverage_value = 5.0  # Higher leverage for scalping

    def leverage(self, pair: str, current_time: datetime, current_rate: float,
                 proposed_leverage: float, max_leverage: float,
                 entry_tag: str | None, side: str, **kwargs) -> float:
        return float(min(self.leverage_value, max_leverage))

    def informative_pairs(self):
        return []

    # ==================== FreqAI Feature Engineering ====================
    def feature_engineering_expand_all(self, dataframe: DataFrame, period: int,
                                       metadata: dict, **kwargs) -> DataFrame:
        dataframe[f"%-rsi-period_{period}"] = ta.RSI(dataframe, timeperiod=period)
        dataframe[f"%-roc-period_{period}"] = ta.ROC(dataframe, timeperiod=period) / 100.0

        bb = ta.BBANDS(dataframe, timeperiod=period)
        dataframe[f"%-bb_width-period_{period}"] = (
            (bb["upperband"] - bb["lowerband"]) / bb["middleband"]
        )
        dataframe[f"%-bb_pos-period_{period}"] = (
            (dataframe["close"] - bb["lowerband"]) / (bb["upperband"] - bb["lowerband"])
        )

        dataframe[f"%-natr-period_{period}"] = ta.NATR(dataframe, timeperiod=period) / 100.0
        dataframe[f"%-adx-period_{period}"] = ta.ADX(dataframe, timeperiod=period) / 100.0

        return dataframe.replace([np.inf, -np.inf], np.nan)

    def feature_engineering_expand_basic(self, dataframe: DataFrame,
                                         metadata: dict, **kwargs) -> DataFrame:
        dataframe["%-pct_change"] = dataframe["close"].pct_change()
        dataframe["%-pct_change_3"] = dataframe["close"].pct_change(3)
        dataframe["%-pct_change_6"] = dataframe["close"].pct_change(6)

        vol_mean = dataframe["volume"].rolling(48).mean()
        dataframe["%-volume_ratio"] = dataframe["volume"] / vol_mean.replace(0, np.nan)

        # Trend strength
        dataframe["%-ema_diff"] = (
            ta.EMA(dataframe, timeperiod=12) - ta.EMA(dataframe, timeperiod=26)
        ) / dataframe["close"]

        return dataframe.replace([np.inf, -np.inf], np.nan)

    def feature_engineering_standard(self, dataframe: DataFrame,
                                     metadata: dict, **kwargs) -> DataFrame:
        dataframe["%-hour_of_day"] = dataframe["date"].dt.hour
        dataframe["%-minute_of_hour"] = dataframe["date"].dt.minute // 15
        dataframe["%-day_of_week"] = dataframe["date"].dt.dayofweek
        return dataframe

    def set_freqai_targets(self, dataframe: DataFrame,
                           metadata: dict, **kwargs) -> DataFrame:
        """
        Direction classification for 5m scalping:
        - "long" if price rises by threshold within window
        - "short" if price falls by threshold within window
        - "neutral" otherwise
        """
        label_period = int(self.freqai_info["feature_parameters"]["label_period_candles"])
        profit_threshold = 0.006  # 0.6% for 5m scalping

        # Calculate max upside/downside in next N candles
        future_max = dataframe["high"].rolling(label_period).max().shift(-label_period)
        future_min = dataframe["low"].rolling(label_period).min().shift(-label_period)
        current_close = dataframe["close"]

        long_ok = (future_max / current_close - 1) >= profit_threshold
        short_ok = (1 - future_min / current_close) >= profit_threshold

        dataframe["&s_direction"] = np.where(
            long_ok & ~short_ok, "long",
            np.where(short_ok & ~long_ok, "short", "neutral")
        )
        return dataframe

    # ==================== Indicators ====================
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe = self.freqai.start(dataframe, metadata, self)

        # Generate signals for entry logic
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)
        dataframe["ema_fast"] = ta.EMA(dataframe, timeperiod=12)
        dataframe["ema_slow"] = ta.EMA(dataframe, timeperiod=26)
        dataframe["uptrend"] = dataframe["ema_fast"] > dataframe["ema_slow"]

        dataframe["atr"] = ta.ATR(dataframe, timeperiod=14)
        dataframe["atr_pct"] = dataframe["atr"] / dataframe["close"]

        return dataframe

    # ==================== Entry Signals ====================
    def populate_entry_trend(self, df: DataFrame, metadata: dict) -> DataFrame:
        df["enter_long"] = 0
        df["enter_short"] = 0

        pred = df.get("&s_direction", "neutral")
        do_predict = df.get("do_predict", 1)
        rsi = df.get("rsi", 50)
        uptrend = df.get("uptrend", False)
        atr_pct = df.get("atr_pct", 0)

        # Base condition: model is confident and volatility is reasonable
        base_cond = (do_predict == 1) & (atr_pct < 0.03) & (atr_pct > 0.003)

        # Long: model predicts long + RSI not overbought + uptrend
        long_cond = base_cond & (pred == "long") & (rsi < 65) & uptrend
        df.loc[long_cond, "enter_long"] = 1
        df.loc[long_cond, "enter_tag"] = "SCALP_LONG"

        # Short: model predicts short + RSI not oversold + downtrend
        short_cond = base_cond & (pred == "short") & (rsi > 35) & ~uptrend
        df.loc[short_cond, "enter_short"] = 1
        df.loc[short_cond, "enter_tag"] = "SCALP_SHORT"

        return df

    # ==================== Exit Signals ====================
    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["exit_long"] = 0
        dataframe["exit_short"] = 0
        return dataframe

    def custom_exit(self, pair: str, trade: Trade, current_time: datetime,
                    current_rate: float, current_profit: float, **kwargs) -> str | None:
        df, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if df.empty:
            return None

        # Time-based exit for scalping
        trade_duration = (current_time - trade.open_date_utc).total_seconds() / 60
        if trade_duration > 30 and current_profit < 0.002:
            return "TIME_EXIT"

        last = df.iloc[-1]
        pred = last.get("&s_direction", "neutral")

        # Exit long if prediction turns bearish and we have profit
        if not trade.is_short and current_profit > 0.003 and pred in ["short", "neutral"]:
            return "SIGNAL_EXIT"

        # Exit short if prediction turns bullish and we have profit
        if trade.is_short and current_profit > 0.003 and pred in ["long", "neutral"]:
            return "SIGNAL_EXIT_SHORT"

        return None
