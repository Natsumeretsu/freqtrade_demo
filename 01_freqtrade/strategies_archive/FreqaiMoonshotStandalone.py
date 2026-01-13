"""
FreqAI Moonshot Standalone Strategy (5-minute scalping)

First Principles Design:
- Model predicts price change over next 6 candles (30 minutes)
- Use fixed stoploss, exit via custom_exit when time exceeds prediction window
- Higher entry threshold = fewer but higher quality trades
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


class FreqaiMoonshotStandalone(IStrategy):

    INTERFACE_VERSION = 3

    # ==================== Core Config ====================
    timeframe = "5m"  # 5-minute for more trading opportunities
    process_only_new_candles = True
    startup_candle_count = 500
    can_short = True
    use_exit_signal = True

    # ==================== Risk Management ====================
    use_custom_stoploss = False
    stoploss = -0.02  # 2% stoploss (tighter to cut losses faster)
    trailing_stop = True
    trailing_stop_positive = 0.008
    trailing_stop_positive_offset = 0.012
    trailing_only_offset_is_reached = True

    # ROI targets
    minimal_roi = {"0": 0.015, "20": 0.008}  # 1.5% -> 0.8%

    # ==================== Protection ====================
    protections = [
        {"method": "CooldownPeriod", "stop_duration_candles": 2},
        {
            "method": "StoplossGuard",
            "lookback_period_candles": 288,  # 24 hours for 5m
            "trade_limit": 4,
            "stop_duration_candles": 24,
            "only_per_pair": True,
        },
    ]

    # ==================== Entry Parameters ====================
    buy_pred_threshold = 0.015   # +1.5% for long
    sell_pred_threshold = -0.015  # -1.5% for short (disabled)
    buy_max_atr_pct = 0.03  # ATR filter

    # ==================== Exit Parameters ====================
    max_trade_duration_min = 60  # 1 hour for 5m timeframe

    # ==================== Leverage ====================
    leverage_value = 3.0

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

        natr = ta.NATR(dataframe, timeperiod=period)
        dataframe[f"%-natr-period_{period}"] = natr / 100.0

        return dataframe.replace([np.inf, -np.inf], np.nan)

    def feature_engineering_expand_basic(self, dataframe: DataFrame,
                                         metadata: dict, **kwargs) -> DataFrame:
        dataframe["%-pct_change"] = dataframe["close"].pct_change()
        vol_mean = dataframe["volume"].rolling(48).mean()
        dataframe["%-volume_ratio"] = dataframe["volume"] / vol_mean.replace(0, np.nan)
        return dataframe.replace([np.inf, -np.inf], np.nan)

    def feature_engineering_standard(self, dataframe: DataFrame,
                                     metadata: dict, **kwargs) -> DataFrame:
        dataframe["%-day_of_week"] = dataframe["date"].dt.dayofweek
        dataframe["%-hour_of_day"] = dataframe["date"].dt.hour
        dataframe["%-minute_of_hour"] = dataframe["date"].dt.minute // 15
        return dataframe

    def set_freqai_targets(self, dataframe: DataFrame,
                           metadata: dict, **kwargs) -> DataFrame:
        label_period = int(self.freqai_info["feature_parameters"]["label_period_candles"])
        label_period = max(1, label_period)

        dataframe["&s_close_pct"] = (
            dataframe["close"].shift(-label_period) / dataframe["close"] - 1
        )
        return dataframe

    # ==================== Indicators ====================
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe = self.freqai.start(dataframe, metadata, self)

        dataframe["atr"] = ta.ATR(dataframe, timeperiod=14)
        dataframe["atr_pct"] = dataframe["atr"] / dataframe["close"].replace(0, np.nan)

        return dataframe

    # ==================== Entry Signals ====================
    def populate_entry_trend(self, df: DataFrame, metadata: dict) -> DataFrame:
        df["enter_long"] = 0
        df["enter_short"] = 0

        pred = df.get("&s_close_pct", 0)
        do_predict = df.get("do_predict", 1)
        atr_pct = df.get("atr_pct", 0)

        base_cond = (do_predict == 1) & (atr_pct < self.buy_max_atr_pct)

        # Long only - shorts are losing money
        long_cond = base_cond & (pred > self.buy_pred_threshold)
        df.loc[long_cond, "enter_long"] = 1
        df.loc[long_cond, "enter_tag"] = "FREQAI_LONG"

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

        # Time-based exit: cut losses after max duration
        trade_duration = (current_time - trade.open_date_utc).total_seconds() / 60
        if trade_duration > self.max_trade_duration_min and current_profit < 0.003:
            return "TIME_EXIT"

        last = df.iloc[-1]
        if int(last.get("do_predict", 0)) != 1:
            return None

        try:
            pred = float(last.get("&s_close_pct", 0))
        except Exception:
            return None

        # Exit long: profitable and prediction turns negative
        if not trade.is_short and current_profit > 0.002 and pred <= 0:
            return "FREQAI_SMART_EXIT"

        # Exit short: profitable and prediction turns positive
        if trade.is_short and current_profit > 0.002 and pred >= 0:
            return "FREQAI_SMART_EXIT_SHORT"

        return None
