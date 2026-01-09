from __future__ import annotations

from datetime import datetime, timedelta
from functools import reduce

import numpy as np
import talib.abstract as ta
from pandas import DataFrame

from freqtrade.persistence import Trade
from freqtrade.strategy import IStrategy
from freqtrade.strategy.strategy_helper import stoploss_from_absolute


class TheArmoredRubberBand(IStrategy):
    """
    The Armored Rubber Band（装甲橡皮筋）——期货均值回归（多/空）策略。

    趋势自适应（Trend-Adaptive Mean Reversion）版本：
    - 牛市（close > EMA200）：只做多（回踩下轨挂更深限价做多）
    - 熊市（close < EMA200）：只做空（反弹到均值上方后，等待上轨挂单做空）

    设计目标（面向实盘的“反向选择/延迟/毒性流”问题）：
    1) Smart Maker：只在极端偏离时挂“更深”的限价单，要求提供流动性得到溢价
    2) Panic Filter：遇到大幅恐慌 K 线不接刀，避免波动陷阱
    3) 动态风险：ATR 止损（入场价 ± 2*ATR），并用 Rotten Fish 规则做时间止损
    """

    INTERFACE_VERSION = 3

    timeframe = "5m"
    can_short = True
    process_only_new_candles = True

    # 指标所需：EMA200 + BB(20) + ATR(14) + 少量缓冲
    startup_candle_count: int = 250

    use_exit_signal = True
    use_custom_stoploss = True

    minimal_roi = {"0": 1.0}
    stoploss = -0.25

    # --- 参数（固定结构，避免“手调过拟合”）---
    ema_trend_period = 200

    rsi_period = 4
    rsi_long_bull = 30
    rsi_short_bear = 70

    bb_period = 20
    bb_dev = 2.0

    atr_period = 14
    panic_atr_mult = 3.0
    stop_atr_mult = 2.0

    maker_premium = 0.005  # 0.5%

    rotten_fish_max_age = timedelta(minutes=30)
    rotten_fish_min_profit = 0.005  # 0.5%
    rotten_fish_small_winner_extension = timedelta(minutes=30)  # 6 根 5m K 线
    rotten_fish_winner_extension = timedelta(hours=1)  # 12 根 5m K 线

    order_types = {
        "entry": "limit",
        "exit": "limit",
        "stoploss": "market",
        "stoploss_on_exchange": False,
    }
    order_time_in_force = {"entry": "GTC", "exit": "GTC"}

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
        # 生产默认：2x，且不超过交易所允许上限
        return float(min(2.0, max_leverage))

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["ema_200"] = ta.EMA(dataframe, timeperiod=int(self.ema_trend_period))

        rsi = ta.RSI(dataframe, timeperiod=int(self.rsi_period))
        dataframe["rsi_4"] = rsi

        bb = ta.BBANDS(
            dataframe,
            timeperiod=int(self.bb_period),
            nbdevup=float(self.bb_dev),
            nbdevdn=float(self.bb_dev),
        )
        dataframe["bb_upper"] = bb["upperband"].replace(0, np.nan)
        dataframe["bb_middle"] = bb["middleband"].replace(0, np.nan)
        dataframe["bb_lower"] = bb["lowerband"].replace(0, np.nan)

        dataframe["atr_14"] = ta.ATR(dataframe, timeperiod=int(self.atr_period))

        # 当前 K 线实体（用于 Panic Filter）
        dataframe["candle_range"] = (dataframe["high"] - dataframe["low"]).abs()

        return dataframe.replace([np.inf, -np.inf], np.nan)

    def populate_entry_trend(self, df: DataFrame, metadata: dict) -> DataFrame:
        is_bull = (df["ema_200"].notna() & (df["close"] > df["ema_200"])).fillna(False)
        is_bear = (df["ema_200"].notna() & (df["close"] < df["ema_200"])).fillna(False)

        # Panic Filter：恐慌大波动不入场（避免“接在火车头前”）
        panic_ok = (
            (df["atr_14"] > 0)
            & np.isfinite(df["atr_14"])
            & (df["candle_range"] < (df["atr_14"] * float(self.panic_atr_mult)))
        )

        base = [
            df["volume"] > 0,
            panic_ok,
            df["ema_200"].notna(),
            df["bb_lower"].notna(),
            df["bb_upper"].notna(),
            df["bb_middle"].notna(),
            df["rsi_4"].notna(),
        ]

        long_conditions = [
            *base,
            is_bull,
            df["rsi_4"] < float(self.rsi_long_bull),
            df["close"] < df["bb_lower"],
        ]

        short_conditions = [
            *base,
            is_bear,
            df["rsi_4"] > float(self.rsi_short_bear),
            df["close"] > df["bb_middle"],
        ]

        df.loc[reduce(lambda x, y: x & y, long_conditions), ["enter_long", "enter_tag"]] = (
            1,
            "ARB_TREND_LONG",
        )
        df.loc[reduce(lambda x, y: x & y, short_conditions), ["enter_short", "enter_tag"]] = (
            1,
            "ARB_TREND_SHORT",
        )
        return df

    def populate_exit_trend(self, df: DataFrame, metadata: dict) -> DataFrame:
        # 触及目标价位即认为“回归完成”，触发出场（价格由 custom_exit_price 决定）
        base = [
            df["volume"] > 0,
            df["bb_middle"].notna(),
        ]

        exit_long = [
            *base,
            df["close"] >= df["bb_middle"],
        ]
        exit_short = [
            *base,
            df["close"] <= df["bb_middle"],
        ]

        df.loc[reduce(lambda x, y: x & y, exit_long), ["exit_long", "exit_tag"]] = (1, "ARB_TP_MID")
        df.loc[reduce(lambda x, y: x & y, exit_short), ["exit_short", "exit_tag"]] = (1, "ARB_TP_MID")
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
        Smart Maker（顺势版本）：
        - 多单：挂在下轨更下方 0.5%（要求“恐慌溢价”）
        - 空单：挂在上轨（等待反弹到上轨再做空）
        """
        candle = self._get_last_analyzed_candle(pair)
        if not candle:
            return float(proposed_rate)

        premium = float(max(0.0, self.maker_premium))
        if side == "long":
            bb_lower = float(candle.get("bb_lower", float("nan")))
            if np.isfinite(bb_lower) and bb_lower > 0:
                return float(bb_lower * (1.0 - premium))
        elif side == "short":
            bb_upper = float(candle.get("bb_upper", float("nan")))
            if np.isfinite(bb_upper) and bb_upper > 0:
                return float(bb_upper)

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
        Rotten Fish（腐烂的鱼，改进版）：
        - 亏损单：持仓超过 30 分钟仍未转正，立刻砍掉
        - 盈利单：允许更长时间触发 TP（避免把“慢赢单”砍成 Rotten Fish）
          - profit > 0.5%：额外给 12 根 5m（1 小时）
          - 0 < profit <= 0.5%：额外给 6 根 5m（30 分钟）
        """
        opened_at = getattr(trade, "open_date_utc", None) or getattr(trade, "open_date", None)
        if opened_at is None:
            return None

        if current_time < opened_at + self.rotten_fish_max_age:
            return None

        profit = float(current_profit)

        # 只快速砍亏：30 分钟仍未盈利，直接出局
        if profit <= 0.0:
            return "ARB_ROTTEN_FISH"

        min_profit = float(self.rotten_fish_min_profit)
        extra = (
            self.rotten_fish_winner_extension
            if profit > min_profit
            else self.rotten_fish_small_winner_extension
        )

        if current_time < opened_at + self.rotten_fish_max_age + extra:
            return None

        return "ARB_ROTTEN_FISH"

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
        - 多单 TP：布林中轨（到达后多为空间通常会“可成交”）
        - 空单 TP：布林中轨（均值回归完成即落袋，不贪下轨）
        - Rotten Fish：用更贴近“市价”的可成交限价（尽量立刻成交）
        """
        tag = (exit_tag or "").strip()

        # 近似“市价”出场：用轻微让价提高成交概率（避免挂单卡住）
        if tag == "ARB_ROTTEN_FISH":
            rate = float(proposed_rate)
            slip = 0.001  # 0.1%
            if bool(getattr(trade, "is_short", False)):
                # 平空：买回 -> 稍微高一点更容易成交
                return float(rate * (1.0 + slip))
            # 平多：卖出 -> 稍微低一点更容易成交
            return float(rate * (1.0 - slip))

        candle = self._get_last_analyzed_candle(pair)
        if not candle:
            return float(proposed_rate)

        bb_middle = float(candle.get("bb_middle", float("nan")))
        if np.isfinite(bb_middle) and bb_middle > 0:
            return float(bb_middle)
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
        - 多单：entry - 2*ATR
        - 空单：entry + 2*ATR
        返回值为“相对 current_rate 的距离”（正数），由 stoploss_from_absolute 计算。
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
