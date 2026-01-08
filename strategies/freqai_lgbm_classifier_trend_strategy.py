from __future__ import annotations

import logging
from datetime import datetime
from functools import reduce

import numpy as np
import talib.abstract as ta
from pandas import DataFrame

from freqtrade.exchange.exchange_utils_timeframe import timeframe_to_minutes
from freqtrade.persistence import Trade
from freqtrade.strategy import BooleanParameter, DecimalParameter, IStrategy, IntParameter

logger = logging.getLogger(__name__)


class FreqaiLGBMClassifierTrendStrategy(IStrategy):
    """
    FreqAI + LightGBM（二分类）趋势策略示例。

    核心思路：
    - 预测目标：未来 N 根K线的“均值收益率”是否高于阈值（分类标签：up / down）
    - 入场：up 概率 > 阈值 + 趋势过滤（EMA）
    - 出场：up 概率跌破阈值 / 智能退出 + 动态止盈止损（ATR）
    """

    INTERFACE_VERSION = 3

    timeframe = "1h"
    process_only_new_candles = True

    startup_candle_count: int = 240

    can_short = False
    use_exit_signal = True

    use_custom_roi = True
    use_custom_stoploss = True

    minimal_roi = {"0": 1.0}
    stoploss = -0.10

    # --- 分类标签阈值：未来均值收益率 > 阈值 才算 “up”
    # 0.3% 是一个偏保守的起点：大致覆盖手续费 + 少量滑点（实际可结合交易所费率调整）
    label_return_threshold: float = 0.003

    # --- 入场/出场阈值（可用于 hyperopt）
    buy_prob_threshold = DecimalParameter(0.50, 0.80, default=0.60, decimals=2, space="buy", optimize=True)
    sell_prob_threshold = DecimalParameter(0.20, 0.50, default=0.40, decimals=2, space="sell", optimize=True)

    # --- 趋势过滤 ---
    buy_use_trend_filter = BooleanParameter(default=True, space="buy", optimize=False)
    buy_ema_long = IntParameter(100, 300, default=200, space="buy", optimize=False)

    # --- 风控（ATR） ---
    risk_atr_period = IntParameter(7, 28, default=14, space="sell", optimize=False)
    sell_tp_atr_mult = DecimalParameter(0.5, 8.0, default=3.0, decimals=2, space="sell", optimize=True)
    sell_tp_min = DecimalParameter(0.0, 0.10, default=0.02, decimals=3, space="sell", optimize=True)
    sell_tp_max = DecimalParameter(0.0, 0.30, default=0.0, decimals=3, space="sell", optimize=True)

    sell_sl_atr_mult = DecimalParameter(0.5, 8.0, default=2.0, decimals=2, space="sell", optimize=True)
    sell_sl_min = DecimalParameter(0.0, 0.20, default=0.02, decimals=3, space="sell", optimize=True)
    sell_sl_max = DecimalParameter(0.0, 0.30, default=0.0, decimals=3, space="sell", optimize=True)

    # --- 追踪止损 ---
    sell_use_trailing_stop = BooleanParameter(default=True, space="sell", optimize=False)
    sell_trailing_stop_positive = DecimalParameter(0.0, 0.05, default=0.01, decimals=3, space="sell", optimize=False)
    sell_trailing_stop_offset = DecimalParameter(0.0, 0.10, default=0.02, decimals=3, space="sell", optimize=False)

    # --- 智能退出：up 概率低于阈值则退出（盈利单立即退出；亏损/持平单需超过预测窗口才退出）
    sell_smart_exit_prob_threshold = DecimalParameter(0.20, 0.60, default=0.45, decimals=2, space="sell", optimize=False)

    def feature_engineering_expand_all(
        self,
        dataframe: DataFrame,
        period: int,
        metadata: dict,
        **kwargs,
    ) -> DataFrame:
        close_safe = dataframe["close"].replace(0, np.nan)

        rsi = ta.RSI(dataframe, timeperiod=period)  # type: ignore
        mfi = ta.MFI(dataframe, timeperiod=period)
        adx = ta.ADX(dataframe, timeperiod=period)
        ema = ta.EMA(dataframe, timeperiod=period)
        atr = ta.ATR(dataframe, timeperiod=period)
        natr = ta.NATR(dataframe, timeperiod=period)
        bb = ta.BBANDS(dataframe, timeperiod=period, nbdevup=2.0, nbdevdn=2.0)
        bb_mid = bb["middleband"].replace(0, np.nan)
        bb_width = (bb["upperband"] - bb["lowerband"]) / bb_mid

        dataframe["%-rsi-period"] = rsi / 100.0
        dataframe["%-mfi-period"] = mfi / 100.0
        dataframe["%-adx-period"] = adx / 100.0
        dataframe["%-dist_ema-period"] = (dataframe["close"] - ema) / ema.replace(0, np.nan)
        dataframe["%-atr_pct-period"] = atr / close_safe
        dataframe["%-natr-period"] = natr / 100.0
        dataframe["%-bb_width-period"] = bb_width
        dataframe["%-roc-period"] = ta.ROC(dataframe, timeperiod=period) / 100.0

        return dataframe.replace([np.inf, -np.inf], np.nan)

    def feature_engineering_expand_basic(self, dataframe: DataFrame, metadata: dict, **kwargs) -> DataFrame:
        dataframe["%-pct_change"] = dataframe["close"].pct_change()
        vol_mean_24 = dataframe["volume"].rolling(24).mean()
        dataframe["%-volume_ratio_24"] = dataframe["volume"] / vol_mean_24.replace(0, np.nan)
        return dataframe.replace([np.inf, -np.inf], np.nan)

    def feature_engineering_standard(self, dataframe: DataFrame, metadata: dict, **kwargs) -> DataFrame:
        close_safe = dataframe["close"].replace(0, np.nan)

        ema_period = max(1, int(self.buy_ema_long.value))
        dataframe["ema_long"] = ta.EMA(dataframe, timeperiod=ema_period)
        dataframe["%-dist_ema_long"] = (dataframe["close"] - dataframe["ema_long"]) / close_safe

        dataframe["%-day_of_week"] = dataframe["date"].dt.dayofweek
        dataframe["%-hour_of_day"] = dataframe["date"].dt.hour
        return dataframe

    def set_freqai_targets(self, dataframe: DataFrame, metadata: dict, **kwargs) -> DataFrame:
        label_period = int(self.freqai_info["feature_parameters"]["label_period_candles"])
        label_period = max(1, label_period)

        future_mean_return = (
            dataframe["close"]
            .shift(-label_period)
            .rolling(label_period)
            .mean()
            / dataframe["close"]
            - 1
        )

        # 说明：分类标签必须是离散值（字符串）
        dataframe["&s_up_or_down"] = np.where(
            future_mean_return > float(self.label_return_threshold),
            "up",
            "down",
        )

        # 为分类器显式声明类别名（便于输出概率列：up / down）
        try:
            self.freqai.class_names = ["down", "up"]
        except Exception:
            pass

        return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe = self.freqai.start(dataframe, metadata, self)

        if "ema_long" not in dataframe.columns:
            ema_period = max(1, int(self.buy_ema_long.value))
            dataframe["ema_long"] = ta.EMA(dataframe, timeperiod=ema_period)

        atr_period = max(1, int(self.risk_atr_period.value))
        dataframe["atr"] = ta.ATR(dataframe, timeperiod=atr_period)
        dataframe["atr_pct"] = dataframe["atr"] / dataframe["close"].replace(0, np.nan)

        return dataframe

    def populate_entry_trend(self, df: DataFrame, metadata: dict) -> DataFrame:
        if "up" not in df.columns:
            return df

        prob_thr = float(self.buy_prob_threshold.value)
        use_trend = bool(self.buy_use_trend_filter.value)

        conditions = [
            df["do_predict"] == 1,
            df["volume"] > 0,
            df["up"] > prob_thr,
        ]
        if use_trend:
            conditions.append(df["close"] > df["ema_long"])

        if conditions:
            df.loc[reduce(lambda x, y: x & y, conditions), ["enter_long", "enter_tag"]] = (
                1,
                "FREQAI_LGBM_CLS_LONG",
            )

        return df

    def populate_exit_trend(self, df: DataFrame, metadata: dict) -> DataFrame:
        if "up" not in df.columns:
            return df

        prob_thr = float(self.sell_prob_threshold.value)
        conditions = [
            df["do_predict"] == 1,
            df["volume"] > 0,
            df["up"] < prob_thr,
        ]

        if conditions:
            df.loc[reduce(lambda x, y: x & y, conditions), ["exit_long", "exit_tag"]] = (
                1,
                "FREQAI_LGBM_CLS_EXIT",
            )

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

    def custom_exit(
        self,
        pair: str,
        trade: Trade,
        current_time: datetime,
        current_rate: float,
        current_profit: float,
        **kwargs,
    ) -> str | None:
        if trade.is_short:
            return None

        candle = self._get_last_analyzed_candle(pair)
        if not candle:
            return None
        if int(candle.get("do_predict", 0)) != 1:
            return None

        try:
            prob_up = float(candle.get("up"))
        except Exception:
            return None

        thr = float(self.sell_smart_exit_prob_threshold.value)
        if float(current_profit) > 0:
            if np.isfinite(prob_up) and prob_up <= thr:
                return "FREQAI_SMART_EXIT"
            return None

        # 亏损/持平：超过预测窗口仍未走强，且 up 概率已显著降低，则退出
        try:
            label_period = int(self.freqai_info["feature_parameters"]["label_period_candles"])
            tf_minutes = int(timeframe_to_minutes(self.timeframe))
        except Exception:
            return None
        horizon_minutes = int(label_period * tf_minutes) if label_period > 0 and tf_minutes > 0 else 0
        if horizon_minutes <= 0:
            return None

        try:
            opened_at = getattr(trade, "open_date_utc", None) or getattr(trade, "open_date", None)
            if opened_at is None:
                return None
            trade_duration_minutes = int((current_time - opened_at).total_seconds() // 60)
            trade_duration_minutes = max(0, trade_duration_minutes)
        except Exception:
            return None

        if trade_duration_minutes >= horizon_minutes and np.isfinite(prob_up) and prob_up <= thr:
            return "FREQAI_TIME_EXIT"

        return None

    def custom_roi(
        self,
        pair: str,
        trade: Trade,
        current_time: datetime,
        trade_duration: int,
        entry_tag: str | None,
        side: str,
        **kwargs,
    ) -> float | None:
        if side != "long":
            return None

        candle = self._get_last_analyzed_candle(pair)
        if not candle:
            return None

        try:
            atr_pct = float(candle.get("atr_pct"))
        except Exception:
            atr_pct = float("nan")

        if not np.isfinite(atr_pct) or atr_pct <= 0:
            return None

        tp_mult = float(self.sell_tp_atr_mult.value)
        tp_min = float(self.sell_tp_min.value)
        tp_max = float(self.sell_tp_max.value)
        tp_mult = max(0.0, tp_mult)
        tp_min = max(0.0, tp_min)
        tp_max = max(0.0, tp_max)

        roi = max(tp_min, atr_pct * tp_mult)
        if tp_max > 0:
            roi = min(roi, tp_max)

        if not np.isfinite(roi) or roi <= 0:
            return None
        return roi

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
        candle = self._get_last_analyzed_candle(pair)
        if not candle:
            return None

        try:
            atr_pct = float(candle.get("atr_pct"))
        except Exception:
            atr_pct = float("nan")

        if not np.isfinite(atr_pct) or atr_pct <= 0:
            return None

        sl_mult = float(self.sell_sl_atr_mult.value)
        sl_min = float(self.sell_sl_min.value)
        sl_max = float(self.sell_sl_max.value)
        sl_mult = max(0.0, sl_mult)
        sl_min = max(0.0, sl_min)
        sl_max = max(0.0, sl_max)

        sl = max(sl_min, atr_pct * sl_mult)
        if sl_max > 0:
            sl = min(sl, sl_max)

        if not np.isfinite(sl) or sl <= 0:
            return None

        if bool(self.sell_use_trailing_stop.value):
            trailing_offset = float(self.sell_trailing_stop_offset.value)
            trailing_positive = float(self.sell_trailing_stop_positive.value)
            if (
                np.isfinite(trailing_offset)
                and np.isfinite(trailing_positive)
                and trailing_offset > 0
                and trailing_positive > 0
                and float(current_profit) >= trailing_offset
            ):
                sl = min(sl, trailing_positive)

        return sl

