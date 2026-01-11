"""
FreqAI Triple Barrier Strategy (1h Trend/Swing)

Core Logic - Triple Barrier Method:
1. Upper Barrier (TP): Entry + ATR * profit_mult → Dynamic take profit
2. Lower Barrier (SL): Entry - ATR * stop_mult → Dynamic stop loss
3. Vertical Barrier (Time): Force exit after X candles → Kill zombie trades

Why Triple Barrier?
- Adapts to volatility: High ATR = wider barriers, Low ATR = tighter barriers
- Time barrier prevents capital lock-up in sideways markets
- Regime filter ensures we trade WITH the trend, not against it
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import numpy as np
import talib.abstract as ta
from pandas import DataFrame

from freqtrade.persistence import Order, Trade
from freqtrade.strategy import IStrategy, merge_informative_pair
from freqtrade.strategy.strategy_helper import stoploss_from_absolute

logger = logging.getLogger(__name__)


class FreqaiTripleBarrierV2(IStrategy):

    INTERFACE_VERSION = 3

    # ==================== Core Config ====================
    timeframe = "1h"
    process_only_new_candles = True
    startup_candle_count = 240  # 10 days of 1h candles
    can_short = False  # LONG ONLY - shorts were losing money
    use_exit_signal = True

    # ==================== Triple Barrier Parameters ====================
    # ATR multipliers for dynamic barriers
    profit_mult = 2.5      # TP = ATR * 2.5 (~2.5% in normal volatility)
    stop_mult = 1.5        # SL = ATR * 1.5 (~1.5% in normal volatility)
    vertical_barrier_hours = 12  # Force exit after 12 hours (stale prediction)
    min_profit_at_timeout = 0.003  # 0.3% minimum profit to hold at timeout

    # Entry thresholds - HIGHER = fewer but better trades
    pred_threshold_long = 0.02   # Model predicts +2% for long (was 1.5%)
    pred_threshold_short = -0.02  # Not used (long only)
    max_atr_pct = 0.04  # Skip if ATR > 4% (tighter filter)

    # ==================== Disable ROI - Use Triple Barrier Only ====================
    minimal_roi = {"0": 100}  # Effectively disabled (100 = 10000%)

    # ==================== Stoploss ====================
    # IMPORTANT: Disable trailing_stop to avoid conflict with custom_stoploss
    use_custom_stoploss = True
    stoploss = -0.08  # 8% fallback (custom_stoploss handles dynamic SL)
    trailing_stop = False  # DISABLED - we use custom_stoploss for dynamic SL

    # ==================== Protection ====================
    protections = [
        {"method": "CooldownPeriod", "stop_duration_candles": 2},
        {
            "method": "StoplossGuard",
            "lookback_period_candles": 48,
            "trade_limit": 3,
            "stop_duration_candles": 12,
            "only_per_pair": True,
        },
    ]

    # ==================== Leverage ====================
    leverage_value = 3.0

    def leverage(self, pair: str, current_time: datetime, current_rate: float,
                 proposed_leverage: float, max_leverage: float,
                 entry_tag: str | None, side: str, **kwargs) -> float:
        return float(min(self.leverage_value, max_leverage))

    # ==================== Informative Pairs (4h for regime) ====================
    def informative_pairs(self):
        pairs = self.dp.current_whitelist()
        return [(pair, "4h") for pair in pairs]

    # ==================== FreqAI Feature Engineering ====================
    def feature_engineering_expand_all(self, dataframe: DataFrame, period: int,
                                       metadata: dict, **kwargs) -> DataFrame:
        """
        Features that get expanded across multiple periods.
        These are the core technical indicators normalized for ML.
        """
        # RSI - Already 0-100, normalize to 0-1
        dataframe[f"%-rsi-period_{period}"] = ta.RSI(dataframe, timeperiod=period) / 100.0

        # ROC (Rate of Change) - Already percentage, scale down
        dataframe[f"%-roc-period_{period}"] = ta.ROC(dataframe, timeperiod=period) / 100.0

        # Bollinger Band Width - Volatility measure
        bb = ta.BBANDS(dataframe, timeperiod=period)
        dataframe[f"%-bb_width-period_{period}"] = (
            (bb["upperband"] - bb["lowerband"]) / bb["middleband"]
        )

        # ADX - Trend strength (0-100, normalize)
        dataframe[f"%-adx-period_{period}"] = ta.ADX(dataframe, timeperiod=period) / 100.0

        # NATR - Normalized ATR (already percentage)
        dataframe[f"%-natr-period_{period}"] = ta.NATR(dataframe, timeperiod=period) / 100.0

        # MFI - Money Flow Index (0-100, normalize)
        dataframe[f"%-mfi-period_{period}"] = ta.MFI(dataframe, timeperiod=period) / 100.0

        return dataframe.replace([np.inf, -np.inf], np.nan)

    def feature_engineering_expand_basic(self, dataframe: DataFrame,
                                         metadata: dict, **kwargs) -> DataFrame:
        """
        Basic features without period expansion.
        """
        # Price momentum features
        dataframe["%-pct_change_1"] = dataframe["close"].pct_change(1)
        dataframe["%-pct_change_3"] = dataframe["close"].pct_change(3)
        dataframe["%-pct_change_6"] = dataframe["close"].pct_change(6)
        dataframe["%-pct_change_12"] = dataframe["close"].pct_change(12)

        # Volume ratio (current vs rolling mean)
        vol_mean = dataframe["volume"].rolling(24).mean()
        dataframe["%-volume_ratio"] = dataframe["volume"] / vol_mean.replace(0, np.nan)

        # High-Low range as volatility proxy
        dataframe["%-hl_range"] = (dataframe["high"] - dataframe["low"]) / dataframe["close"]

        # Distance from recent high/low (mean reversion signal)
        dataframe["%-dist_from_high_24"] = (
            dataframe["close"] / dataframe["high"].rolling(24).max() - 1
        )
        dataframe["%-dist_from_low_24"] = (
            dataframe["close"] / dataframe["low"].rolling(24).min() - 1
        )

        return dataframe.replace([np.inf, -np.inf], np.nan)

    def feature_engineering_standard(self, dataframe: DataFrame,
                                     metadata: dict, **kwargs) -> DataFrame:
        """
        Time-based features for capturing market cycles.
        """
        dataframe["%-hour_of_day"] = dataframe["date"].dt.hour / 24.0
        dataframe["%-day_of_week"] = dataframe["date"].dt.dayofweek / 7.0
        return dataframe

    def set_freqai_targets(self, dataframe: DataFrame,
                           metadata: dict, **kwargs) -> DataFrame:
        """
        Target: Future return over prediction_length candles.
        This is what the model learns to predict.
        """
        label_period = int(self.freqai_info["feature_parameters"]["label_period_candles"])
        label_period = max(1, label_period)

        # Predict percentage change over next N candles
        dataframe["&s_close_pct"] = (
            dataframe["close"].shift(-label_period) / dataframe["close"] - 1
        )
        return dataframe

    # ==================== Indicators ====================
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Start FreqAI
        dataframe = self.freqai.start(dataframe, metadata, self)

        # ATR for Triple Barrier calculations
        dataframe["atr"] = ta.ATR(dataframe, timeperiod=14)
        dataframe["atr_pct"] = dataframe["atr"] / dataframe["close"].replace(0, np.nan)

        # Trend indicators for regime filter
        dataframe["ema_50"] = ta.EMA(dataframe, timeperiod=50)
        dataframe["ema_200"] = ta.EMA(dataframe, timeperiod=200)

        # Regime: Price above/below EMA200
        dataframe["uptrend"] = dataframe["close"] > dataframe["ema_200"]
        dataframe["downtrend"] = dataframe["close"] < dataframe["ema_200"]

        # Get 4h informative for higher timeframe regime
        informative_4h = self.dp.get_pair_dataframe(pair=metadata["pair"], timeframe="4h")
        if not informative_4h.empty:
            informative_4h["ema_50_4h"] = ta.EMA(informative_4h, timeperiod=50)
            informative_4h["ema_200_4h"] = ta.EMA(informative_4h, timeperiod=200)
            informative_4h["regime_4h"] = np.where(
                informative_4h["close"] > informative_4h["ema_200_4h"], 1,
                np.where(informative_4h["close"] < informative_4h["ema_200_4h"], -1, 0)
            )
            informative_4h = informative_4h[["date", "regime_4h"]].copy()
            dataframe = merge_informative_pair(dataframe, informative_4h,
                                               self.timeframe, "4h", ffill=True)

        return dataframe

    # ==================== Entry Signals ====================
    def populate_entry_trend(self, df: DataFrame, metadata: dict) -> DataFrame:
        df["enter_long"] = 0
        df["enter_short"] = 0

        pred = df.get("&s_close_pct", 0)
        do_predict = df.get("do_predict", 1)
        atr_pct = df.get("atr_pct", 0)
        uptrend = df.get("uptrend", False)
        downtrend = df.get("downtrend", False)
        regime_4h = df.get("regime_4h_4h", 0)

        # Base condition: model confident + volatility reasonable
        base_cond = (do_predict == 1) & (atr_pct < self.max_atr_pct) & (atr_pct > 0.005)

        # LONG: Strong bullish prediction + 1h uptrend + 4h bullish regime
        long_cond = (
            base_cond &
            (pred > self.pred_threshold_long) &
            uptrend &
            (regime_4h >= 0)  # 4h not bearish
        )
        df.loc[long_cond, "enter_long"] = 1
        df.loc[long_cond, "enter_tag"] = "TB_LONG"

        # SHORT: Strong bearish prediction + 1h downtrend + 4h bearish regime
        short_cond = (
            base_cond &
            (pred < self.pred_threshold_short) &
            downtrend &
            (regime_4h <= 0)  # 4h not bullish
        )
        df.loc[short_cond, "enter_short"] = 1
        df.loc[short_cond, "enter_tag"] = "TB_SHORT"

        return df

    # ==================== Exit Signals ====================
    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["exit_long"] = 0
        dataframe["exit_short"] = 0
        return dataframe

    def order_filled(
        self,
        pair: str,
        trade: Trade,
        order: Order,
        current_time: datetime,
        **kwargs,
    ) -> None:
        """
        订单成交回调：在入场单成交后，把入场 ATR 写入 trade 自定义数据。

        说明：
        - Triple Barrier 的上下障碍应该基于“入场时刻的波动率尺度”，否则会被止损“越收越紧”卡死。
        - 使用 `trade.set_custom_data()` 落盘，保证回测/实盘一致。
        """
        if order.ft_order_side != trade.entry_side:
            return

        if trade.get_custom_data("entry_atr") is not None:
            return

        df, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if df.empty:
            return

        if "date" in df.columns:
            df_cut = None
            for t in (
                current_time,
                current_time.replace(tzinfo=None),
                current_time.replace(tzinfo=timezone.utc),
            ):
                try:
                    tmp = df[df["date"] <= t]
                except Exception:
                    continue
                if not tmp.empty:
                    df_cut = tmp
                    break
            if df_cut is None:
                return
            df = df_cut

        last = df.iloc[-1]
        entry_atr = last.get("atr")
        if entry_atr is None or not np.isfinite(entry_atr) or float(entry_atr) <= 0:
            return

        trade.set_custom_data("entry_atr", float(entry_atr))

    # ==================== Custom Stoploss (Lower Barrier) ====================
    def custom_stoploss(self, pair: str, trade: Trade, current_time: datetime,
                        current_rate: float, current_profit: float,
                        after_fill: bool, **kwargs) -> float | None:
        """
        固定下障碍止损（Lower Barrier）：基于入场 ATR 的固定价格止损，并换算为 Freqtrade 需要的“相对当前价风险”。

        注意：
        - 期货下 custom_stoploss 返回的是“本次交易风险”（已考虑杠杆），不能直接用价格比例替代。
        - 这里使用固定入场 ATR 生成 stop_rate，避免 ATR 变化导致止损被动收紧（回测中会表现为大量 trailing_stop_loss）。
        """
        entry_atr = trade.get_custom_data("entry_atr")
        if entry_atr is None:
            return None

        try:
            entry_atr = float(entry_atr)
        except Exception:
            return None

        if (
            not np.isfinite(entry_atr)
            or entry_atr <= 0
            or float(trade.open_rate) <= 0
            or float(current_rate) <= 0
        ):
            return None

        stop_rate = float(trade.open_rate) - entry_atr * float(self.stop_mult)
        if stop_rate <= 0:
            return None

        leverage = float(trade.leverage or 1.0)
        if not np.isfinite(leverage) or leverage <= 0:
            leverage = 1.0

        desired_sl = float(
            stoploss_from_absolute(
                stop_rate=stop_rate,
                current_rate=float(current_rate),
                is_short=bool(trade.is_short),
                leverage=leverage,
            )
        )
        if not np.isfinite(desired_sl) or desired_sl <= 0:
            return None

        # 风险裁剪（以“账户风险%”口径）：最紧不低于 3%，最宽不超过策略硬止损。
        min_risk = 0.03
        max_risk = abs(float(self.stoploss)) if np.isfinite(float(self.stoploss)) else 0.08
        if max_risk <= 0:
            max_risk = 0.08
        if max_risk < min_risk:
            min_risk = max_risk

        return float(max(min(desired_sl, max_risk), min_risk))

    # ==================== Custom Exit (Upper + Vertical Barrier) ====================
    def custom_exit(self, pair: str, trade: Trade, current_time: datetime,
                    current_rate: float, current_profit: float, **kwargs) -> str | None:
        """
        Triple Barrier Exit Logic:
        1. Upper Barrier: Take profit at ATR * profit_mult
        2. Vertical Barrier: Force exit after X hours if profit is weak
        3. Signal Reversal: Exit if model prediction flips
        """
        df, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if df.empty:
            return None

        last = df.iloc[-1]
        entry_atr = trade.get_custom_data("entry_atr")
        if entry_atr is None:
            return None
        try:
            entry_atr = float(entry_atr)
        except Exception:
            return None
        if not np.isfinite(entry_atr) or entry_atr <= 0 or float(trade.open_rate) <= 0:
            return None

        # === UPPER BARRIER (Dynamic Take Profit) ===
        tp_rate = float(trade.open_rate) + entry_atr * float(self.profit_mult)
        if float(current_rate) >= tp_rate:
            return "TB_TAKE_PROFIT"

        # === VERTICAL BARRIER (Time-based Exit) ===
        # This is crucial: kills "zombie trades" that go nowhere
        trade_duration_hours = (current_time - trade.open_date_utc).total_seconds() / 3600

        if trade_duration_hours >= self.vertical_barrier_hours:
            # If we've been in trade too long with weak profit, exit
            if current_profit < self.min_profit_at_timeout:
                return "TB_TIME_EXIT"
            # If profitable but not hitting TP, take what we have
            elif current_profit > 0:
                return "TB_TIME_PROFIT"

        # === SIGNAL REVERSAL EXIT ===
        # Exit if model prediction strongly reverses
        if int(last.get("do_predict", 0)) == 1:
            pred = float(last.get("&s_close_pct", 0))

            # Long position: exit if prediction turns bearish
            if not trade.is_short and current_profit > 0.01:
                if pred < -0.005:  # Model now predicts down
                    return "TB_SIGNAL_REVERSAL"

            # Short position: exit if prediction turns bullish
            if trade.is_short and current_profit > 0.01:
                if pred > 0.005:  # Model now predicts up
                    return "TB_SIGNAL_REVERSAL"

        return None
