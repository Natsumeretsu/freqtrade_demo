"""
TheMomentumBreaker - 动量突破策略

设计理念：
- 只在强趋势中交易（ADX > 30）
- Donchian Channel 突破入场（经典有效）
- BTC 宏观过滤（牛市做多，熊市做空）
- 严格 ATR 动态止损 + 追踪止损

目标：简单、稳健、可盈利
"""
from __future__ import annotations

from datetime import datetime, timedelta
from functools import reduce

import numpy as np
import talib.abstract as ta
from pandas import DataFrame

from freqtrade.persistence import Trade
from freqtrade.strategy import IStrategy, merge_informative_pair
from freqtrade.strategy.strategy_helper import stoploss_from_absolute


class TheMomentumBreaker(IStrategy):
    """
    动量突破策略 - 只在强趋势中顺势交易
    """

    INTERFACE_VERSION = 3

    timeframe = "5m"  # 使用已有的 5m 数据
    can_short = False  # 只做多，不做空
    process_only_new_candles = True

    startup_candle_count: int = 100

    use_exit_signal = True
    use_custom_stoploss = True

    # 禁用 ROI，由 custom_exit 控制
    minimal_roi = {"0": 1.0}
    stoploss = -0.15  # 兜底止损 15%

    # --- 指标参数 ---
    donchian_period = 20  # Donchian Channel 周期
    adx_period = 14
    atr_period = 14
    adx_threshold = 30.0  # 只在强趋势中交易

    # --- 宏观过滤 ---
    btc_pair = "BTC/USDT:USDT"
    btc_timeframe = "4h"  # 使用 4h 数据
    btc_ema_period = 200

    # --- 风控 ---
    stoploss_atr_mult = 2.0
    takeprofit_atr_mult = 3.0  # 1:1.5 风险收益
    trailing_profit_trigger = 0.03  # 盈利 3% 后启动追踪
    trailing_stop_distance = 0.015  # 追踪止损距离 1.5%
    max_hold_time = timedelta(hours=8)  # 最大持仓 8 小时

    # --- 保护机制 ---
    protections = [
        {"method": "CooldownPeriod", "stop_duration_candles": 2},
        {
            "method": "StoplossGuard",
            "lookback_period_candles": 24,
            "trade_limit": 3,
            "stop_duration_candles": 8,
            "only_per_pair": True,
        },
    ]

    order_types = {
        "entry": "market",
        "exit": "market",
        "stoploss": "market",
        "stoploss_on_exchange": False,
    }
    order_time_in_force = {"entry": "GTC", "exit": "GTC"}

    def informative_pairs(self):
        """获取 BTC 4h 数据用于宏观过滤"""
        pairs = [(self.btc_pair, self.btc_timeframe)]
        return pairs

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        df = dataframe.copy()

        # --- Donchian Channel ---
        df["dc_upper"] = df["high"].rolling(window=self.donchian_period).max()
        df["dc_lower"] = df["low"].rolling(window=self.donchian_period).min()
        df["dc_mid"] = (df["dc_upper"] + df["dc_lower"]) / 2

        # --- ADX (趋势强度) ---
        df["adx"] = ta.ADX(df, timeperiod=self.adx_period)

        # --- ATR (波动率) ---
        df["atr"] = ta.ATR(df, timeperiod=self.atr_period)

        # --- BTC 宏观过滤 ---
        dp = getattr(self, "dp", None)
        if dp is not None:
            try:
                btc_df = dp.get_pair_dataframe(pair=self.btc_pair, timeframe=self.btc_timeframe)
                if btc_df is not None and not btc_df.empty:
                    btc = btc_df.copy()
                    btc["btc_ema200"] = ta.EMA(btc, timeperiod=self.btc_ema_period)
                    btc["btc_bull"] = (btc["close"] > btc["btc_ema200"]).astype(int)
                    btc_small = btc[["date", "btc_bull"]].copy()
                    df = merge_informative_pair(df, btc_small, self.timeframe, self.btc_timeframe, ffill=True)
            except Exception:
                pass

        return df.replace([np.inf, -np.inf], np.nan)

    def populate_entry_trend(self, df: DataFrame, metadata: dict) -> DataFrame:
        btc_bull_col = f"btc_bull_{self.btc_timeframe}"

        # 默认无 BTC 数据时不交易
        if btc_bull_col not in df.columns:
            df["enter_long"] = 0
            df["enter_short"] = 0
            return df

        # BTC 宏观状态
        is_btc_bull = (df[btc_bull_col] == 1).fillna(False)
        is_btc_bear = (df[btc_bull_col] == 0).fillna(True)

        # Donchian 突破信号
        breakout_up = (df["close"] > df["dc_upper"].shift(1))
        breakout_down = (df["close"] < df["dc_lower"].shift(1))

        # 强趋势过滤
        strong_trend = df["adx"] > self.adx_threshold

        # 基础条件
        base = [
            df["volume"] > 0,
            df["atr"] > 0,
            strong_trend,
        ]

        # 做多：BTC 牛市 + 向上突破
        long_cond = [*base, is_btc_bull, breakout_up]
        # 做空：BTC 熊市 + 向下突破
        short_cond = [*base, is_btc_bear, breakout_down]

        df.loc[reduce(lambda x, y: x & y, long_cond), ["enter_long", "enter_tag"]] = (1, "DC_LONG")
        df.loc[reduce(lambda x, y: x & y, short_cond), ["enter_short", "enter_tag"]] = (1, "DC_SHORT")

        return df

    def populate_exit_trend(self, df: DataFrame, metadata: dict) -> DataFrame:
        return df

    def _get_last_candle(self, pair: str) -> dict | None:
        dp = getattr(self, "dp", None)
        if dp is None:
            return None
        try:
            dataframe, _ = dp.get_analyzed_dataframe(pair, self.timeframe)
        except Exception:
            return None
        if dataframe is None or dataframe.empty:
            return None
        return dataframe.iloc[-1].to_dict()

    def leverage(self, pair: str, current_time: datetime, current_rate: float,
                 proposed_leverage: float, max_leverage: float, entry_tag: str | None,
                 side: str, **kwargs) -> float:
        return float(min(3.0, max_leverage))

    def custom_stoploss(self, pair: str, trade: Trade, current_time: datetime,
                        current_rate: float, current_profit: float,
                        after_fill: bool, **kwargs) -> float | None:
        """
        动态止损：
        - 基础：2.0 * ATR
        - 追踪：盈利 3% 后收紧到 1.5%
        """
        # 追踪止损
        if current_profit >= self.trailing_profit_trigger:
            return self.trailing_stop_distance

        candle = self._get_last_candle(pair)
        if not candle:
            return None

        atr = float(candle.get("atr", float("nan")))
        if not np.isfinite(atr) or atr <= 0:
            return None

        open_rate = float(trade.open_rate)
        if open_rate <= 0:
            return None

        is_short = trade.is_short
        mult = self.stoploss_atr_mult
        stop_rate = open_rate + (atr * mult) if is_short else open_rate - (atr * mult)

        leverage = float(trade.leverage or 1.0)
        return stoploss_from_absolute(stop_rate, current_rate, is_short=is_short, leverage=leverage)

    def custom_exit(self, pair: str, trade: Trade, current_time: datetime,
                    current_rate: float, current_profit: float, **kwargs) -> str | None:
        """
        出场规则：
        - 止盈：3.0 * ATR
        - 超时：8 小时强制退出
        """
        opened_at = trade.open_date_utc or trade.open_date
        if opened_at is None:
            return None

        # 超时退出
        if current_time >= opened_at + self.max_hold_time:
            return "TIMEOUT"

        # ATR 止盈
        candle = self._get_last_candle(pair)
        if not candle:
            return None

        atr = float(candle.get("atr", float("nan")))
        open_rate = float(trade.open_rate)

        if np.isfinite(atr) and atr > 0 and open_rate > 0:
            mult = self.takeprofit_atr_mult
            is_short = trade.is_short
            target = open_rate - (atr * mult) if is_short else open_rate + (atr * mult)

            if is_short and current_rate <= target:
                return "TP"
            if not is_short and current_rate >= target:
                return "TP"

        return None
