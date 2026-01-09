from __future__ import annotations

from datetime import datetime, timedelta
from functools import reduce

import numpy as np
import talib.abstract as ta
from pandas import DataFrame

from freqtrade.persistence import Trade
from freqtrade.strategy import IStrategy
from freqtrade.strategy.strategy_helper import stoploss_from_absolute


class TheBearRider(IStrategy):
    """
    The Bear Rider（熊市骑手）——顺势回调做空（期货）策略。

    核心思想：
    - 放弃“均值回归接飞刀”，只在宏观下跌趋势中做空
    - 以 EMA200 作为趋势门控：只在 close < EMA200 时允许开空
    - 以 EMA20 作为“回调阻力位”：当价格上影线触碰 EMA20 后，挂 EMA20 限价单等待回测做空

    目标：
    - 在熊市/崩盘阶段减少逆势交易，提高胜率与可控性
    - 入场做 Maker（限价挂阻力位），避免追涨杀跌的反向选择
    """

    INTERFACE_VERSION = 3

    timeframe = "5m"
    can_short = True
    process_only_new_candles = True

    # 指标所需：EMA200 + EMA20 + ATR(14) + 少量缓冲
    startup_candle_count: int = 250

    use_exit_signal = True
    use_custom_stoploss = True

    # 用 custom_exit 控制出场（固定 TP + 强制时间退出），避免 ROI 干扰
    minimal_roi = {"0": 1.0}
    stoploss = -0.25

    # --- 策略参数（固定结构，避免“手调过拟合”）---
    ema_trend_period = 200
    ema_resistance_period = 20
    atr_period = 14

    take_profit_pct = 0.015  # 1.5% 固定止盈
    stop_atr_mult = 2.0  # 止损：Entry + 2*ATR（空单）

    entry_retest_timeout = timedelta(minutes=25)  # 5 根 5m 未成交则撤单（由 config 的 unfilledtimeout 控制）
    max_trade_duration = timedelta(minutes=60)  # 持仓超过 60 分钟强制退出

    order_types = {
        "entry": "limit",
        "exit": "limit",
        "stoploss": "market",
        "stoploss_on_exchange": False,
    }
    order_time_in_force = {"entry": "GTC", "exit": "GTC"}

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["ema_200"] = ta.EMA(dataframe, timeperiod=int(self.ema_trend_period))
        dataframe["ema_20"] = ta.EMA(dataframe, timeperiod=int(self.ema_resistance_period))
        dataframe["atr_14"] = ta.ATR(dataframe, timeperiod=int(self.atr_period))

        return dataframe.replace([np.inf, -np.inf], np.nan)

    def populate_entry_trend(self, df: DataFrame, metadata: dict) -> DataFrame:
        """
        只做熊市空单：
        - 趋势门控：close < EMA200
        - 回调触碰：high > EMA20（上影触碰短期均线）
        """
        base = [
            df["volume"] > 0,
            df["ema_200"].notna(),
            df["ema_20"].notna(),
            df["atr_14"].notna(),
        ]

        bear = (df["close"] < df["ema_200"]).fillna(False)
        touched = (df["high"] > df["ema_20"]).fillna(False)

        short_conditions = [
            *base,
            bear,
            touched,
        ]

        df.loc[reduce(lambda x, y: x & y, short_conditions), ["enter_short", "enter_tag"]] = (
            1,
            "BR_PULLBACK_SHORT",
        )
        return df

    def populate_exit_trend(self, df: DataFrame, metadata: dict) -> DataFrame:
        """
        出场信号由 `custom_exit` 决定（固定止盈 + 时间止损），这里保持最小实现即可。

        说明：
        - Freqtrade 要求策略必须实现 `populate_exit_trend`
        - 本策略不使用基于指标的静态出场信号，避免与 custom_exit 逻辑冲突
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

    def custom_entry_price(
        self,
        pair: str,
        trade: Trade | None,
        current_time: datetime,
        proposed_rate: float,
        entry_tag: str | None,
        side: str,
        **kwargs,
    ) -> float:
        """
        入场限价：
        - 空单：挂 EMA20（阻力位）等待回测成交
        """
        if side != "short":
            return float(proposed_rate)

        candle = self._get_last_analyzed_candle(pair)
        if not candle:
            return float(proposed_rate)

        ema_20 = float(candle.get("ema_20", float("nan")))
        if np.isfinite(ema_20) and ema_20 > 0:
            return float(ema_20)
        return float(proposed_rate)

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
        - 固定止盈：>= 1.5% 触发（回测中会以可成交的限价出场，避免挂单拖延）
        - 时间止损：持仓超过 60 分钟强制退出
        """
        opened_at = getattr(trade, "open_date_utc", None) or getattr(trade, "open_date", None)
        if opened_at is None:
            return None

        if current_time >= opened_at + self.max_trade_duration:
            return "BR_TIME_EXIT"

        if float(current_profit) >= float(self.take_profit_pct):
            return "BR_TP_1P5"

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
        出场限价：
        - BR_TP_1P5：按入场价计算 1.5% 固定止盈目标
        - BR_TIME_EXIT：用“可立即成交”的让价限价近似市价退出
        """
        tag = (exit_tag or "").strip()

        open_rate = float(getattr(trade, "open_rate", float("nan")))
        if tag == "BR_TP_1P5" and np.isfinite(open_rate) and open_rate > 0:
            tp = float(self.take_profit_pct)
            tp = float(max(0.0, tp))
            if bool(getattr(trade, "is_short", False)):
                return float(open_rate * (1.0 - tp))
            return float(open_rate * (1.0 + tp))

        if tag == "BR_TIME_EXIT":
            rate = float(proposed_rate)
            slip = 0.001  # 0.1%
            if bool(getattr(trade, "is_short", False)):
                # 平空：买回 -> 稍微高一点更容易成交
                return float(rate * (1.0 + slip))
            # 平多：卖出 -> 稍微低一点更容易成交
            return float(rate * (1.0 - slip))

        return float(proposed_rate)

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
        动态止损：Entry ± 2*ATR
        - 空单：entry + 2*ATR
        - 多单：entry - 2*ATR（目前策略不做多，但保留健壮性）
        """
        candle = self._get_last_analyzed_candle(pair)
        if not candle:
            return None

        atr = float(candle.get("atr_14", float("nan")))
        if not np.isfinite(atr) or atr <= 0:
            return None

        open_rate = float(getattr(trade, "open_rate", float("nan")))
        if not np.isfinite(open_rate) or open_rate <= 0:
            return None

        is_short = bool(getattr(trade, "is_short", False))
        mult = float(max(0.0, self.stop_atr_mult))
        stop_rate = open_rate + (atr * mult) if is_short else open_rate - (atr * mult)

        leverage = float(getattr(trade, "leverage", 1.0) or 1.0)
        leverage = float(max(1.0, leverage))
        return float(stoploss_from_absolute(stop_rate, float(current_rate), is_short=is_short, leverage=leverage))
