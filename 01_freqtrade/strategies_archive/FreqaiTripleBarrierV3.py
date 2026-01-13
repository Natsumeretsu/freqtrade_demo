"""
FreqAI Triple Barrier 策略 V3（分类器 + 纯 ML 入场）

目标：
- 让“训练目标”与“实盘执行逻辑”完全一致：训练阶段直接生成 ATR 动态三重障碍标签（win/lose）。
- 入场由 FreqAI 分类器输出的 win 概率驱动，辅以趋势/体制过滤，避免在噪声段过度交易。
- 出场严格使用 Triple Barrier（止盈/止损/时间退出），并在期货杠杆口径下返回正确的止损语义。

说明：
- 本策略与 `FreqaiMetaLabelV2` 的差异：不依赖基础策略生成候选信号（召回），而是更“纯”的 ML 驱动版本。
  这有助于验证：在当前数据/特征下，单靠 ML 能否稳定筛选出具备正期望的交易。
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


class FreqaiTripleBarrierV3(IStrategy):
    """
    FreqAI Triple Barrier（V3）

    Public API（可调核心参数）：
    - `profit_mult`：止盈障碍倍数（ATR）
    - `stop_mult`：止损障碍倍数（ATR）
    - `min_profit_at_timeout`：时间障碍触发时的最小盈利阈值
    - `enter_win_prob`：入场需要的 win 概率阈值
    """

    INTERFACE_VERSION = 3

    # ==================== 基础配置 ====================
    timeframe = "1h"
    process_only_new_candles = True
    startup_candle_count = 240
    can_short = False
    use_exit_signal = True

    # ==================== Triple Barrier 参数 ====================
    atr_period = 14
    profit_mult = 2.5
    stop_mult = 1.5
    min_profit_at_timeout = 0.003

    # 波动率过滤（避免极端噪声段）
    min_atr_pct = 0.005
    max_atr_pct = 0.04

    # ==================== ML 阈值 ====================
    enter_win_prob = 0.60
    exit_win_prob = 0.45

    # ==================== ROI/止损 ====================
    # ROI 仅做兜底（主要由 TB 离场）
    minimal_roi = {"0": 100}

    use_custom_stoploss = True
    stoploss = -0.08
    trailing_stop = False

    # ==================== 保护配置 ====================
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

    # ==================== 杠杆配置 ====================
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

    # ==================== Informative Pairs（4h 体制） ====================
    def informative_pairs(self):
        pairs = self.dp.current_whitelist()
        return [(pair, "4h") for pair in pairs]

    # ==================== FreqAI 特征工程 ====================
    def feature_engineering_expand_all(self, dataframe: DataFrame, period: int, metadata: dict, **kwargs) -> DataFrame:
        dataframe[f"%-rsi-period_{period}"] = ta.RSI(dataframe, timeperiod=period) / 100.0
        dataframe[f"%-roc-period_{period}"] = ta.ROC(dataframe, timeperiod=period) / 100.0

        bb = ta.BBANDS(dataframe, timeperiod=period)
        bb_mid = bb["middleband"].replace(0, np.nan)
        dataframe[f"%-bb_width-period_{period}"] = (bb["upperband"] - bb["lowerband"]) / bb_mid

        dataframe[f"%-adx-period_{period}"] = ta.ADX(dataframe, timeperiod=period) / 100.0
        dataframe[f"%-natr-period_{period}"] = ta.NATR(dataframe, timeperiod=period) / 100.0
        dataframe[f"%-mfi-period_{period}"] = ta.MFI(dataframe, timeperiod=period) / 100.0

        return dataframe.replace([np.inf, -np.inf], np.nan)

    def feature_engineering_expand_basic(self, dataframe: DataFrame, metadata: dict, **kwargs) -> DataFrame:
        dataframe["%-pct_change_1"] = dataframe["close"].pct_change(1)
        dataframe["%-pct_change_3"] = dataframe["close"].pct_change(3)
        dataframe["%-pct_change_6"] = dataframe["close"].pct_change(6)

        vol_mean_24 = dataframe["volume"].rolling(24).mean()
        dataframe["%-volume_ratio_24"] = dataframe["volume"] / vol_mean_24.replace(0, np.nan)

        high_24 = dataframe["high"].rolling(24).max()
        low_24 = dataframe["low"].rolling(24).min()
        denom = (high_24 - low_24).replace(0, np.nan)
        dataframe["%-price_position_24"] = (dataframe["close"] - low_24) / denom

        return dataframe.replace([np.inf, -np.inf], np.nan)

    def feature_engineering_standard(self, dataframe: DataFrame, metadata: dict, **kwargs) -> DataFrame:
        dataframe["%-hour_of_day"] = dataframe["date"].dt.hour / 24.0
        dataframe["%-day_of_week"] = dataframe["date"].dt.dayofweek / 7.0
        return dataframe

    # ==================== Target：TB 分类标签 ====================
    def set_freqai_targets(self, dataframe: DataFrame, metadata: dict, **kwargs) -> DataFrame:
        """
        Triple Barrier 标签（分类）：
        - win：未来 N 根内先触达 TP
        - lose：先触达 SL 或超时

        同一根 K 线同时触达上下障碍时，默认判定为 lose（更保守，避免标签偏乐观）。
        """
        label_period = int(self.freqai_info["feature_parameters"]["label_period_candles"])
        label_period = max(1, label_period)

        # 显式声明类别名，确保推理阶段输出概率列名为 "lose" / "win"
        try:
            self.freqai.class_names = ["lose", "win"]
        except Exception:
            pass

        atr = ta.ATR(dataframe, timeperiod=int(self.atr_period))
        close = dataframe["close"].values
        high = dataframe["high"].values
        low = dataframe["low"].values
        atr_values = atr.values
        count = len(dataframe)

        upper_barrier = close + float(self.profit_mult) * atr_values
        lower_barrier = close - float(self.stop_mult) * atr_values

        labels = np.full(count, "lose", dtype=object)
        determined = np.zeros(count, dtype=bool)
        index = np.arange(count)
        valid_atr = ~np.isnan(atr_values)

        for offset in range(1, label_period + 1):
            if offset >= count:
                break

            future_high = np.full(count, np.nan)
            future_low = np.full(count, np.nan)
            future_high[:-offset] = high[offset:]
            future_low[:-offset] = low[offset:]

            valid_mask = (index < (count - offset)) & ~determined & valid_atr

            # SL 优先（同 K 线内上下触达，保守判定为 lose）
            sl_hit = valid_mask & (future_low <= lower_barrier)
            determined[sl_hit] = True

            valid_mask_tp = valid_mask & ~determined
            tp_hit = valid_mask_tp & (future_high >= upper_barrier)
            labels[tp_hit] = "win"
            determined[tp_hit] = True

        labels[count - label_period :] = "lose"
        labels[np.isnan(atr_values)] = "lose"

        dataframe["&s-win"] = labels
        return dataframe

    # ==================== 指标计算 ====================
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe = self.freqai.start(dataframe, metadata, self)

        dataframe["atr"] = ta.ATR(dataframe, timeperiod=int(self.atr_period))
        dataframe["atr_pct"] = dataframe["atr"] / dataframe["close"].replace(0, np.nan)

        dataframe["ema_200"] = ta.EMA(dataframe, timeperiod=200)
        dataframe["uptrend"] = dataframe["close"] > dataframe["ema_200"]

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

    # ==================== 入场（纯 ML） ====================
    def populate_entry_trend(self, df: DataFrame, metadata: dict) -> DataFrame:
        df["enter_long"] = 0
        df["enter_short"] = 0

        if "win" not in df.columns:
            return df

        win_prob = df["win"]
        do_predict = df.get("do_predict", 0)
        atr_pct = df.get("atr_pct", 0)
        regime_4h = df.get("regime_4h_4h", 0)

        base_cond = (
            (do_predict == 1)
            & (df["volume"] > 0)
            & (atr_pct >= float(self.min_atr_pct))
            & (atr_pct <= float(self.max_atr_pct))
            & df.get("uptrend", False)
            & (regime_4h >= 0)
        )

        entry_cond = base_cond & (win_prob > float(self.enter_win_prob))
        df.loc[entry_cond, ["enter_long", "enter_tag"]] = (1, "TB_V3_LONG")
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

    # ==================== 止损（Lower Barrier，期货风险口径） ====================
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

        min_risk = 0.03
        max_risk = abs(float(self.stoploss)) if np.isfinite(float(self.stoploss)) else 0.08
        if max_risk <= 0:
            max_risk = 0.08
        if max_risk < min_risk:
            min_risk = max_risk

        return float(max(min(desired_sl, max_risk), min_risk))

    # ==================== 出场（Upper + Vertical + 信号衰减） ====================
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
        if trade.is_short:
            return None

        entry_atr = trade.get_custom_data("entry_atr")
        if entry_atr is None:
            return None
        try:
            entry_atr = float(entry_atr)
        except Exception:
            return None
        if not np.isfinite(entry_atr) or entry_atr <= 0 or float(trade.open_rate) <= 0:
            return None

        tp_rate = float(trade.open_rate) + entry_atr * float(self.profit_mult)
        if float(current_rate) >= tp_rate:
            return "TB_TAKE_PROFIT"

        candle = self._get_last_candle(pair)
        if candle and int(candle.get("do_predict", 0)) == 1:
            try:
                win_prob = float(candle.get("win"))
            except Exception:
                win_prob = float("nan")
            if np.isfinite(win_prob) and win_prob < float(self.exit_win_prob) and float(current_profit) > 0.01:
                return "TB_SIGNAL_FADE"

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
                return "TB_TIME_EXIT"
            if float(current_profit) > 0:
                return "TB_TIME_PROFIT"

        return None

