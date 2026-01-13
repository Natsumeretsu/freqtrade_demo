"""
FreqAI CTA 趋势策略 V3（单币对 + 期货 + 多/空）

设计目标：
1) 单币对聚焦：默认仅用于 BTC/USDT:USDT（主流币对流动性更好、噪声相对更可控）。
2) CTA 双向：同时支持做多/做空（can_short=True），以获得“相对市场”的 alpha 潜力。
3) 目标对齐：训练阶段用 ATR 动态三重障碍生成多分类标签（long/short/neutral），执行阶段使用相同的
   Triple Barrier（止盈/止损/时间）管理持仓，避免“训练学的东西”和“交易做的事情”不一致。

注意：
- futures 下 custom_stoploss 的返回值是“本次交易风险%（已考虑杠杆）”，不能直接返回价格波动比例。
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import numpy as np
import talib.abstract as ta
from pandas import DataFrame

from freqtrade.exchange.exchange_utils_timeframe import timeframe_to_minutes
from freqtrade.persistence import Order, Trade
from freqtrade.strategy import IStrategy, merge_informative_pair
from freqtrade.strategy.strategy_helper import stoploss_from_absolute

logger = logging.getLogger(__name__)


class FreqaiCTATrendV3(IStrategy):
    """
    FreqAI CTA 趋势（V3）

标签（多分类）：
- long：未来窗口内，做多先触达 TP（且未先触达 SL）
- short：未来窗口内，做空先触达 TP（且未先触达 SL）
- neutral：其余情况（超时/震荡/双向噪声）
"""

    INTERFACE_VERSION = 3

    # ==================== 基础配置 ====================
    timeframe = "1h"
    process_only_new_candles = True
    startup_candle_count = 240

    can_short = True
    use_exit_signal = True

    # ==================== Triple Barrier 参数 ====================
    atr_period = 14
    profit_mult = 2.5
    stop_mult = 1.5
    min_profit_at_timeout = 0.003

    min_atr_pct = 0.005
    max_atr_pct = 0.05

    # ==================== ML 阈值（可按回测再调） ====================
    enter_prob = 0.55
    exit_prob = 0.45
    prob_margin = 0.05

    # ==================== ROI/止损 ====================
    minimal_roi = {"0": 100}

    use_custom_stoploss = True
    stoploss = -0.12
    trailing_stop = False

    # ==================== 保护 ====================
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

    # ==================== 杠杆 ====================
    leverage_value = 3.0

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
        return float(min(self.leverage_value, max_leverage))

    # ==================== Informative（4h 体制过滤） ====================
    def informative_pairs(self):
        pairs = self.dp.current_whitelist()
        return [(pair, "4h") for pair in pairs]

    # ==================== FreqAI 特征工程 ====================
    def feature_engineering_expand_all(self, dataframe: DataFrame, period: int, metadata: dict, **kwargs) -> DataFrame:
        close_safe = dataframe["close"].replace(0, np.nan)

        dataframe[f"%-rsi-period_{period}"] = ta.RSI(dataframe, timeperiod=period) / 100.0
        dataframe[f"%-roc-period_{period}"] = ta.ROC(dataframe, timeperiod=period) / 100.0
        dataframe[f"%-adx-period_{period}"] = ta.ADX(dataframe, timeperiod=period) / 100.0

        ema = ta.EMA(dataframe, timeperiod=period)
        dataframe[f"%-dist_ema-period_{period}"] = (dataframe["close"] - ema) / ema.replace(0, np.nan)

        atr = ta.ATR(dataframe, timeperiod=period)
        dataframe[f"%-atr_pct-period_{period}"] = atr / close_safe

        bb = ta.BBANDS(dataframe, timeperiod=period)
        bb_mid = bb["middleband"].replace(0, np.nan)
        dataframe[f"%-bb_width-period_{period}"] = (bb["upperband"] - bb["lowerband"]) / bb_mid

        dataframe[f"%-mfi-period_{period}"] = ta.MFI(dataframe, timeperiod=period) / 100.0
        dataframe[f"%-natr-period_{period}"] = ta.NATR(dataframe, timeperiod=period) / 100.0

        return dataframe.replace([np.inf, -np.inf], np.nan)

    def feature_engineering_expand_basic(self, dataframe: DataFrame, metadata: dict, **kwargs) -> DataFrame:
        dataframe["%-pct_change_1"] = dataframe["close"].pct_change(1)
        dataframe["%-pct_change_3"] = dataframe["close"].pct_change(3)
        dataframe["%-pct_change_6"] = dataframe["close"].pct_change(6)

        # 波动率结构：短/长 ATR 比值（趋势通常伴随结构性变化）
        atr_6 = ta.ATR(dataframe, timeperiod=6)
        atr_24 = ta.ATR(dataframe, timeperiod=24)
        dataframe["%-atr_ratio_6_24"] = (atr_6 / atr_24.replace(0, np.nan)).replace([np.inf, -np.inf], np.nan)

        vol_mean_24 = dataframe["volume"].rolling(24).mean()
        dataframe["%-volume_ratio_24"] = dataframe["volume"] / vol_mean_24.replace(0, np.nan)

        return dataframe.replace([np.inf, -np.inf], np.nan)

    def feature_engineering_standard(self, dataframe: DataFrame, metadata: dict, **kwargs) -> DataFrame:
        dataframe["%-hour_of_day"] = dataframe["date"].dt.hour / 24.0
        dataframe["%-day_of_week"] = dataframe["date"].dt.dayofweek / 7.0
        return dataframe

    # ==================== Target：三分类方向（TB 对齐） ====================
    def set_freqai_targets(self, dataframe: DataFrame, metadata: dict, **kwargs) -> DataFrame:
        label_period = int(self.freqai_info["feature_parameters"]["label_period_candles"])
        label_period = max(1, label_period)

        # 显式声明类别名，确保推理阶段输出概率列：neutral / short / long
        try:
            self.freqai.class_names = ["neutral", "short", "long"]
        except Exception:
            pass

        atr = ta.ATR(dataframe, timeperiod=int(self.atr_period))
        close = dataframe["close"].values
        high = dataframe["high"].values
        low = dataframe["low"].values
        atr_values = atr.values
        count = len(dataframe)

        valid_atr = ~np.isnan(atr_values)
        index = np.arange(count)

        # 多单障碍（以 close 为入场）
        long_tp = close + float(self.profit_mult) * atr_values
        long_sl = close - float(self.stop_mult) * atr_values

        # 空单障碍（以 close 为入场）
        short_tp = close - float(self.profit_mult) * atr_values
        short_sl = close + float(self.stop_mult) * atr_values

        long_win = np.zeros(count, dtype=bool)
        long_done = np.zeros(count, dtype=bool)
        short_win = np.zeros(count, dtype=bool)
        short_done = np.zeros(count, dtype=bool)

        for offset in range(1, label_period + 1):
            if offset >= count:
                break

            future_high = np.full(count, np.nan)
            future_low = np.full(count, np.nan)
            future_high[:-offset] = high[offset:]
            future_low[:-offset] = low[offset:]

            valid_mask = (index < (count - offset)) & valid_atr

            # --- long：SL 优先，其次 TP（同 K 线双触达 -> lose）
            long_mask = valid_mask & ~long_done
            long_sl_hit = long_mask & (future_low <= long_sl)
            long_done[long_sl_hit] = True

            long_tp_hit = (long_mask & ~long_done) & (future_high >= long_tp)
            long_win[long_tp_hit] = True
            long_done[long_tp_hit] = True

            # --- short：SL 优先，其次 TP（同 K 线双触达 -> lose）
            short_mask = valid_mask & ~short_done
            short_sl_hit = short_mask & (future_high >= short_sl)
            short_done[short_sl_hit] = True

            short_tp_hit = (short_mask & ~short_done) & (future_low <= short_tp)
            short_win[short_tp_hit] = True
            short_done[short_tp_hit] = True

        labels = np.full(count, "neutral", dtype=object)
        labels[long_win & ~short_win] = "long"
        labels[short_win & ~long_win] = "short"

        labels[count - label_period :] = "neutral"
        labels[~valid_atr] = "neutral"

        dataframe["&s-direction"] = labels
        return dataframe

    # ==================== 指标计算 ====================
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe = self.freqai.start(dataframe, metadata, self)

        dataframe["atr"] = ta.ATR(dataframe, timeperiod=int(self.atr_period))
        dataframe["atr_pct"] = dataframe["atr"] / dataframe["close"].replace(0, np.nan)

        dataframe["ema_200"] = ta.EMA(dataframe, timeperiod=200)
        dataframe["uptrend"] = dataframe["close"] > dataframe["ema_200"]
        dataframe["downtrend"] = dataframe["close"] < dataframe["ema_200"]

        informative_4h = self.dp.get_pair_dataframe(pair=metadata["pair"], timeframe="4h")
        if not informative_4h.empty:
            informative_4h["ema_200_4h"] = ta.EMA(informative_4h, timeperiod=200)
            informative_4h["regime_4h"] = np.where(
                informative_4h["close"] > informative_4h["ema_200_4h"],
                1,
                np.where(informative_4h["close"] < informative_4h["ema_200_4h"], -1, 0),
            )
            informative_4h = informative_4h[["date", "regime_4h"]].copy()
            dataframe = merge_informative_pair(dataframe, informative_4h, self.timeframe, "4h", ffill=True)

        return dataframe

    # ==================== 入场（CTA 双向） ====================
    def populate_entry_trend(self, df: DataFrame, metadata: dict) -> DataFrame:
        df["enter_long"] = 0
        df["enter_short"] = 0

        # multi-class：概率列名就是 class_names
        if not {"long", "short", "neutral"}.issubset(set(df.columns)):
            return df

        prob_long = df["long"]
        prob_short = df["short"]
        do_predict = df.get("do_predict", 0)
        atr_pct = df.get("atr_pct", 0)
        regime_4h = df.get("regime_4h_4h", 0)

        base = (
            (do_predict == 1)
            & (df["volume"] > 0)
            & (atr_pct >= float(self.min_atr_pct))
            & (atr_pct <= float(self.max_atr_pct))
        )

        long_cond = (
            base
            & df.get("uptrend", False)
            & (regime_4h >= 0)
            & (prob_long > float(self.enter_prob))
            & (prob_long > (prob_short + float(self.prob_margin)))
        )
        df.loc[long_cond, ["enter_long", "enter_tag"]] = (1, "CTA_V3_LONG")

        short_cond = (
            base
            & df.get("downtrend", False)
            & (regime_4h <= 0)
            & (prob_short > float(self.enter_prob))
            & (prob_short > (prob_long + float(self.prob_margin)))
        )
        df.loc[short_cond, ["enter_short", "enter_tag"]] = (1, "CTA_V3_SHORT")

        return df

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["exit_long"] = 0
        dataframe["exit_short"] = 0
        return dataframe

    # ==================== 关键：入场 ATR 落盘 ====================
    def order_filled(
        self,
        pair: str,
        trade: Trade,
        order: Order,
        current_time: datetime,
        **kwargs,
    ) -> None:
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

    # ==================== 止损（Lower Barrier，futures 风险口径） ====================
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

        is_short = bool(trade.is_short)
        stop_rate = (
            float(trade.open_rate) + entry_atr * float(self.stop_mult)
            if is_short
            else float(trade.open_rate) - entry_atr * float(self.stop_mult)
        )
        if stop_rate <= 0:
            return None

        leverage = float(trade.leverage or 1.0)
        if not np.isfinite(leverage) or leverage <= 0:
            leverage = 1.0

        desired_sl = float(
            stoploss_from_absolute(
                stop_rate=stop_rate,
                current_rate=float(current_rate),
                is_short=is_short,
                leverage=leverage,
            )
        )
        if not np.isfinite(desired_sl) or desired_sl <= 0:
            return None

        min_risk = 0.03
        max_risk = abs(float(self.stoploss)) if np.isfinite(float(self.stoploss)) else 0.12
        if max_risk <= 0:
            max_risk = 0.12
        if max_risk < min_risk:
            min_risk = max_risk

        return float(max(min(desired_sl, max_risk), min_risk))

    # ==================== 出场（TP + 时间 + 信号反转/衰减） ====================
    def _get_last_candle(self, pair: str) -> dict | None:
        dp = getattr(self, "dp", None)
        if dp is None:
            return None
        try:
            df, _ = dp.get_analyzed_dataframe(pair, self.timeframe)
        except Exception:
            return None
        if df is None or df.empty:
            return None
        candle = df.iloc[-1]
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
        entry_atr = trade.get_custom_data("entry_atr")
        if entry_atr is None:
            return None
        try:
            entry_atr = float(entry_atr)
        except Exception:
            return None
        if not np.isfinite(entry_atr) or entry_atr <= 0 or float(trade.open_rate) <= 0:
            return None

        is_short = bool(trade.is_short)
        open_rate = float(trade.open_rate)

        tp_rate = open_rate - entry_atr * float(self.profit_mult) if is_short else open_rate + entry_atr * float(self.profit_mult)
        if (is_short and float(current_rate) <= tp_rate) or ((not is_short) and float(current_rate) >= tp_rate):
            return "CTA_TAKE_PROFIT"

        candle = self._get_last_candle(pair)
        if candle and int(candle.get("do_predict", 0)) == 1:
            try:
                prob_long = float(candle.get("long"))
                prob_short = float(candle.get("short"))
            except Exception:
                prob_long = float("nan")
                prob_short = float("nan")

            # 信号反转：在有一定盈利时，若优势方向明显反转则落袋
            if float(current_profit) > 0.01 and np.isfinite(prob_long) and np.isfinite(prob_short):
                if not is_short and prob_short > (prob_long + float(self.prob_margin)):
                    return "CTA_SIGNAL_REVERSAL"
                if is_short and prob_long > (prob_short + float(self.prob_margin)):
                    return "CTA_SIGNAL_REVERSAL"

            # 信号衰减：概率跌破阈值则提前退出（只对盈利单执行，避免过早止损化）
            if float(current_profit) > 0.01:
                side_prob = prob_short if is_short else prob_long
                if np.isfinite(side_prob) and side_prob < float(self.exit_prob):
                    return "CTA_SIGNAL_FADE"

        # 时间障碍（对齐 label_period_candles）
        try:
            label_period = int(self.freqai_info["feature_parameters"]["label_period_candles"])
            tf_minutes = int(timeframe_to_minutes(self.timeframe))
        except Exception:
            return None
        horizon_minutes = int(max(1, label_period) * tf_minutes)

        opened_at = getattr(trade, "open_date_utc", None) or getattr(trade, "open_date", None)
        if opened_at is None:
            return None
        trade_duration_minutes = int((current_time - opened_at).total_seconds() // 60)
        trade_duration_minutes = max(0, trade_duration_minutes)

        if trade_duration_minutes >= horizon_minutes:
            if float(current_profit) < float(self.min_profit_at_timeout):
                return "CTA_TIME_EXIT"
            if float(current_profit) > 0:
                return "CTA_TIME_PROFIT"

        return None

