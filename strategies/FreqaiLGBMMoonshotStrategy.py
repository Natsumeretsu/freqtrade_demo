from __future__ import annotations

from functools import reduce

import numpy as np
import talib.abstract as ta
from pandas import DataFrame

from datetime import datetime

from freqtrade.strategy import BooleanParameter, DecimalParameter
from freqtrade.persistence import Trade
from freqtrade.exchange import timeframe_to_minutes

from freqai_lgbm_trend_strategy import FreqaiLGBMTrendStrategy


class FreqaiLGBMMoonshotStrategy(FreqaiLGBMTrendStrategy):
    """
    Profile B: The Moonshot（小资金、追求高频与高收益、可承受更高回撤）。

    目标：
    - 明显提高进场频率（期望 3-5 trades/day 量级）
    - 放宽追踪止损触发（更晚触发 + 更宽回撤），减少“被震荡洗出”
    """

    # 期货模式：使用期货交易对进行宏观过滤
    btc_regime_pair = "BTC/USDT:USDT"

    # Moonshot: 禁用 custom_stoploss，使用固定止损
    use_custom_stoploss = False
    stoploss = -0.15  # 固定 15% 止损（放宽以减少被震出）

    # BTC 4h EMA200 Regime Gate：
    # - 牛市（BTC_close_4h > BTC_ema200_4h）：使用优化后的 buy_pred_threshold
    # - 熊市（BTC_close_4h < BTC_ema200_4h）：Nuclear Winter（预测阈值>=0.01 + 价格站上自身 EMA50）
    btc_regime_bear_pred_threshold_min = 0.01  # 降低熊市阈值
    btc_regime_bear_rel_strength_ema_period = 50

    # Moonshot 允许更高波动与回撤，因此对 protections 做“更温和”的配置，避免频次被 StoplossGuard 过度压制。
    protections = [
        {"method": "CooldownPeriod", "stop_duration_candles": 1},
        {
            "method": "StoplossGuard",
            "lookback_period_candles": 72,
            "trade_limit": 4,
            "stop_duration_candles": 6,
            "only_per_pair": True,
        },
    ]

    buy_pred_threshold = DecimalParameter(0.001, 0.03, default=0.006, decimals=3, space="buy", optimize=True)

    buy_use_trend_filter = BooleanParameter(default=False, space="buy", optimize=False)
    buy_use_fast_trend_filter = BooleanParameter(default=False, space="buy", optimize=False)
    buy_use_ema_short_slope_filter = BooleanParameter(default=False, space="buy", optimize=False)
    buy_use_ema_long_slope_filter = BooleanParameter(default=False, space="buy", optimize=False)

    buy_use_max_atr_pct_filter = BooleanParameter(default=True, space="buy", optimize=False)
    buy_max_atr_pct = DecimalParameter(0.010, 0.25, default=0.120, decimals=3, space="buy", optimize=True)

    # Moonshot: 放宽止损和追踪止损，避免被震出
    sell_sl_max = DecimalParameter(0.05, 0.15, default=0.12, decimals=3, space="sell", optimize=True)

    # Moonshot: 禁用追踪止损（主要亏损来源）
    sell_use_trailing_stop = BooleanParameter(default=False, space="sell", optimize=False)
    sell_trailing_stop_positive = DecimalParameter(0.01, 0.10, default=0.05, decimals=3, space="sell", optimize=True)
    sell_trailing_stop_offset = DecimalParameter(0.01, 0.15, default=0.06, decimals=3, space="sell", optimize=True)

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
        """Moonshot: 使用 5x 杠杆追求高收益"""
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
        Moonshot 版本：简化止损逻辑，禁用时间衰减
        只使用基于 ATR 的固定止损，不收紧
        """
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

        base_sl = max(sl_min, atr_pct * sl_mult)
        if sl_max > 0:
            base_sl = min(base_sl, sl_max)

        if not np.isfinite(base_sl) or base_sl <= 0:
            return None

        # Moonshot: 不使用时间衰减，保持固定止损
        return base_sl

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe = super().populate_indicators(dataframe, metadata)

        # 相对强度过滤：交易对自身 EMA50（基础 timeframe=1h）
        ema_period = int(getattr(self, "btc_regime_bear_rel_strength_ema_period", 50))
        ema_period = max(1, ema_period)
        dataframe["ema_50"] = ta.EMA(dataframe, timeperiod=ema_period)

        return dataframe

    def populate_entry_trend(self, df: DataFrame, metadata: dict) -> DataFrame:
        pred_col = "&s_close_mean"
        bull_thr = float(self.buy_pred_threshold.value)

        bear_thr = float(getattr(self, "btc_regime_bear_pred_threshold_min", 0.03))
        bear_thr = float(max(0.0, bear_thr))

        inf_tf = str(getattr(self, "btc_regime_timeframe", "4h"))
        btc_close_col = f"btc_close_{inf_tf}"
        btc_ema200_col = f"btc_ema200_{inf_tf}"

        if btc_close_col in df.columns and btc_ema200_col in df.columns:
            is_bull = (df[btc_close_col] > df[btc_ema200_col]).fillna(False)
        else:
            # 无法判断宏观状态时按熊市处理（更符合风控目标）
            is_bull = (df["close"] < 0).fillna(False)

        base_conditions = [
            df["do_predict"] == 1,
            df["volume"] > 0,
        ]

        if bool(self.buy_use_max_atr_pct_filter.value):
            max_atr_pct = float(self.buy_max_atr_pct.value)
            if np.isfinite(max_atr_pct) and max_atr_pct > 0:
                base_conditions.append(df["atr_pct"] > 0)
                base_conditions.append(df["atr_pct"] < max_atr_pct)

        bull_conditions = [
            *base_conditions,
            is_bull,
            df[pred_col] > bull_thr,
        ]
        bear_conditions = [
            *base_conditions,
            ~is_bull,
            df[pred_col] > bear_thr,
            df["close"] > df["ema_50"],
        ]

        df.loc[
            reduce(lambda x, y: x & y, bull_conditions),
            ["enter_long", "enter_tag"],
        ] = (1, "FREQAI_LGBM_LONG")

        df.loc[
            reduce(lambda x, y: x & y, bear_conditions),
            ["enter_long", "enter_tag"],
        ] = (1, "FREQAI_LGBM_LONG_SNIPER")

        return df

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
        Moonshot 版本的智能退出：对亏损单更宽容
        - 盈利单：模型转弱立刻退出（继承父类逻辑）
        - 亏损单：延长超时到 2 倍预测窗口，且只有预测明显转负才退出
        """
        if trade.is_short:
            return None

        candle = self._get_last_analyzed_candle(pair)
        if not candle:
            return None

        if int(candle.get("do_predict", 0)) != 1:
            return None

        try:
            pred = float(candle.get("&s_close_mean"))
        except Exception:
            return None

        try:
            atr_pct = float(candle.get("atr_pct"))
        except Exception:
            atr_pct = float("nan")

        # Loss Cut：预测跌幅超过 2*ATR 立即退出
        if np.isfinite(pred) and np.isfinite(atr_pct) and atr_pct > 0 and pred <= (-2.0 * atr_pct):
            return "FREQAI_LOSS_CUT"

        thr = float(self.sell_smart_exit_pred_threshold.value)

        # 盈利单：模型转弱立刻退出
        if float(current_profit) > 0:
            if np.isfinite(pred) and pred <= thr:
                return "FREQAI_SMART_EXIT"
            return None

        # 亏损单：更宽容的超时逻辑
        try:
            label_period = int(self.freqai_info["feature_parameters"]["label_period_candles"])
            tf_minutes = int(timeframe_to_minutes(self.timeframe))
        except Exception:
            return None

        # Moonshot: 延长到 2 倍预测窗口（12 小时而非 6 小时）
        horizon_minutes = int(label_period * tf_minutes * 2) if label_period > 0 and tf_minutes > 0 else 0
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

        # Moonshot: 只有预测明显转负（< -0.005）才退出，而非 <= 0
        moonshot_exit_thr = -0.005
        if trade_duration_minutes >= horizon_minutes and np.isfinite(pred) and pred <= moonshot_exit_thr:
            return "FREQAI_TIME_EXIT"

        return None
