"""
FreqAI 波动率门控网格风格策略 V1（原型）

目标：
- 不去预测方向，而是预测“未来一段时间的波动率水平”。
- 当模型预测波动率较低时，启动“均值回归/网格风格”的挂单交易；
  当模型预测波动率走高（潜在突破/趋势段）时，停止开仓，并对持仓执行更保守的退出。

说明：
- Freqtrade 并非专用网格机器人，本策略实现的是“网格风格”的单仓位均值回归（maker 入场 + 均值退出）。
- 为控制回测耗时，本原型采用 `1h`，不做 5m 全周期网格（后续可按需要再细化到 5m）。
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import numpy as np
import talib.abstract as ta
from pandas import DataFrame

from freqtrade.exchange.exchange_utils_timeframe import timeframe_to_minutes
from freqtrade.persistence import Order, Trade
from freqtrade.strategy import IStrategy
from freqtrade.strategy.strategy_helper import stoploss_from_absolute

logger = logging.getLogger(__name__)


class FreqaiVolatilityGridV1(IStrategy):
    """
    波动率预测 + 均值回归（网格风格）原型。

    - Target：`&s-volatility`（未来 N 根的实现波动率，回归）
    - 入场：预测波动率低 + 价格跌破下轨（提供流动性挂单）
    - 出场：回归到中轨 / 波动率走高风险退出 / 时间止损
    """

    INTERFACE_VERSION = 3

    timeframe = "1h"
    process_only_new_candles = True
    startup_candle_count = 240

    can_short = False
    use_exit_signal = True

    # ==================== 波动率目标参数 ====================
    vol_target_lookahead_fallback = 12

    # ==================== 均值回归参数 ====================
    bb_period = 20
    bb_dev = 2.0
    rsi_period = 14

    # 低波动率门控阈值（回归预测值的经验起点，后续应通过扫参校准）
    vol_enter_max = 0.008
    vol_exit_min = 0.015

    # maker 让价：挂在下轨更深的位置
    maker_premium = 0.002

    # ==================== 风控 ====================
    atr_period = 14
    stop_atr_mult = 2.0
    minimal_roi = {"0": 100}

    use_custom_stoploss = True
    stoploss = -0.15
    trailing_stop = False

    # 时间止损：持仓过久仍不回归则退出
    max_trade_age = timedelta(hours=24)
    min_profit_to_extend = 0.003

    order_types = {
        "entry": "limit",
        "exit": "limit",
        "stoploss": "market",
        "stoploss_on_exchange": False,
    }
    order_time_in_force = {"entry": "GTC", "exit": "GTC"}

    leverage_value = 2.0

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

    # ==================== 特征工程（轻量） ====================
    def feature_engineering_expand_all(self, dataframe: DataFrame, period: int, metadata: dict, **kwargs) -> DataFrame:
        close_safe = dataframe["close"].replace(0, np.nan)

        atr = ta.ATR(dataframe, timeperiod=period)
        dataframe[f"%-atr_pct-period_{period}"] = atr / close_safe
        dataframe[f"%-rsi-period_{period}"] = ta.RSI(dataframe, timeperiod=period) / 100.0
        dataframe[f"%-roc-period_{period}"] = ta.ROC(dataframe, timeperiod=period) / 100.0
        dataframe[f"%-natr-period_{period}"] = ta.NATR(dataframe, timeperiod=period) / 100.0

        bb = ta.BBANDS(dataframe, timeperiod=period, nbdevup=2.0, nbdevdn=2.0)
        bb_mid = bb["middleband"].replace(0, np.nan)
        dataframe[f"%-bb_width-period_{period}"] = (bb["upperband"] - bb["lowerband"]) / bb_mid

        return dataframe.replace([np.inf, -np.inf], np.nan)

    def feature_engineering_expand_basic(self, dataframe: DataFrame, metadata: dict, **kwargs) -> DataFrame:
        dataframe["%-pct_change"] = dataframe["close"].pct_change()
        vol_mean_24 = dataframe["volume"].rolling(24).mean()
        dataframe["%-volume_ratio_24"] = dataframe["volume"] / vol_mean_24.replace(0, np.nan)
        return dataframe.replace([np.inf, -np.inf], np.nan)

    def feature_engineering_standard(self, dataframe: DataFrame, metadata: dict, **kwargs) -> DataFrame:
        dataframe["%-hour_of_day"] = dataframe["date"].dt.hour / 24.0
        dataframe["%-day_of_week"] = dataframe["date"].dt.dayofweek / 7.0
        return dataframe

    # ==================== Target：未来实现波动率（回归） ====================
    def set_freqai_targets(self, dataframe: DataFrame, metadata: dict, **kwargs) -> DataFrame:
        label_period = int(self.freqai_info["feature_parameters"]["label_period_candles"])
        label_period = max(1, label_period) if label_period else int(self.vol_target_lookahead_fallback)

        close = dataframe["close"].replace(0, np.nan)
        log_ret = np.log(close / close.shift(1))

        # 未来 N 根的实现波动率（标准差）
        future_vol = log_ret.shift(-1).rolling(label_period).std().shift(-(label_period - 1))
        dataframe["&s-volatility"] = future_vol
        return dataframe

    # ==================== 指标计算 ====================
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe = self.freqai.start(dataframe, metadata, self)

        dataframe["atr"] = ta.ATR(dataframe, timeperiod=int(self.atr_period))
        dataframe["atr_pct"] = dataframe["atr"] / dataframe["close"].replace(0, np.nan)

        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=int(self.rsi_period))

        bb = ta.BBANDS(
            dataframe,
            timeperiod=int(self.bb_period),
            nbdevup=float(self.bb_dev),
            nbdevdn=float(self.bb_dev),
        )
        dataframe["bb_upper"] = bb["upperband"].replace(0, np.nan)
        dataframe["bb_middle"] = bb["middleband"].replace(0, np.nan)
        dataframe["bb_lower"] = bb["lowerband"].replace(0, np.nan)

        dataframe["ema_200"] = ta.EMA(dataframe, timeperiod=200)
        return dataframe

    # ==================== 入场：低波动率门控 + 下轨回归 ====================
    def populate_entry_trend(self, df: DataFrame, metadata: dict) -> DataFrame:
        df["enter_long"] = 0
        df["enter_short"] = 0

        pred_vol = df.get("&s-volatility", float("nan"))
        do_predict = df.get("do_predict", 0)
        atr_pct = df.get("atr_pct", 0)

        # 趋势过滤：只在大趋势为多头时做均值回归（避免熊市“接飞刀”）
        bull_regime = df["ema_200"].notna() & (df["close"] > df["ema_200"])

        cond = (
            (do_predict == 1)
            & (df["volume"] > 0)
            & bull_regime
            & (df["bb_lower"].notna() & df["bb_middle"].notna())
            & (df["rsi"].notna())
            & (atr_pct > 0)
            & np.isfinite(atr_pct)
            & (atr_pct < 0.05)
            & np.isfinite(pred_vol)
            & (pred_vol <= float(self.vol_enter_max))
            & (df["close"] < df["bb_lower"])
            & (df["rsi"] < 35)
        )

        df.loc[cond, ["enter_long", "enter_tag"]] = (1, "VOL_GRID_LONG")
        return df

    def populate_exit_trend(self, df: DataFrame, metadata: dict) -> DataFrame:
        df["exit_long"] = 0
        df["exit_short"] = 0
        return df

    # ==================== 入场 ATR 落盘（用于止损） ====================
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

    # ==================== 止损（futures 风险口径） ====================
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

        if not np.isfinite(entry_atr) or entry_atr <= 0 or float(trade.open_rate) <= 0 or float(current_rate) <= 0:
            return None

        stop_rate = float(trade.open_rate) - entry_atr * float(self.stop_atr_mult)
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
        max_risk = abs(float(self.stoploss)) if np.isfinite(float(self.stoploss)) else 0.15
        if max_risk <= 0:
            max_risk = 0.15
        if max_risk < min_risk:
            min_risk = max_risk

        return float(max(min(desired_sl, max_risk), min_risk))

    # ==================== 网格风格挂单（入场/出场价） ====================
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

    def custom_entry_price(
        self,
        pair: str,
        current_time: datetime,
        proposed_rate: float,
        entry_tag: str | None,
        side: str,
        **kwargs,
    ) -> float:
        if side != "long":
            return float(proposed_rate)

        tag = (entry_tag or "").strip()
        if tag != "VOL_GRID_LONG":
            return float(proposed_rate)

        candle = self._get_last_candle(pair)
        if not candle:
            return float(proposed_rate)

        bb_lower = float(candle.get("bb_lower", float("nan")))
        premium = float(max(0.0, self.maker_premium))
        if np.isfinite(bb_lower) and bb_lower > 0:
            return float(bb_lower * (1.0 - premium))
        return float(proposed_rate)

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
        tag = (exit_tag or "").strip()
        rate = float(proposed_rate)

        # 尝试用中轨“挂单回归”出场
        if tag in {"VG_MEAN_EXIT"}:
            candle = self._get_last_candle(pair)
            if candle:
                bb_middle = float(candle.get("bb_middle", float("nan")))
                if np.isfinite(bb_middle) and bb_middle > 0:
                    return float(bb_middle)
            return rate

        # 风险退出：轻微让价提高成交概率
        if tag in {"VG_VOL_SPIKE", "VG_TIME_EXIT"}:
            return float(rate * 0.999)

        return rate

    # ==================== 出场：均值回归 / 波动率走高 / 时间止损 ====================
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

        candle = self._get_last_candle(pair)
        if candle and int(candle.get("do_predict", 0)) == 1:
            try:
                pred_vol = float(candle.get("&s-volatility"))
            except Exception:
                pred_vol = float("nan")
            # 波动率走高：若处于亏损/微利，尽快退出
            if np.isfinite(pred_vol) and pred_vol >= float(self.vol_exit_min) and float(current_profit) < 0.01:
                return "VG_VOL_SPIKE"

        # 均值回归：触达中轨即退出
        if candle:
            bb_middle = float(candle.get("bb_middle", float("nan")))
            if np.isfinite(bb_middle) and bb_middle > 0 and float(current_rate) >= bb_middle:
                return "VG_MEAN_EXIT"

        opened_at = getattr(trade, "open_date_utc", None) or getattr(trade, "open_date", None)
        if opened_at is None:
            return None

        if current_time >= opened_at + self.max_trade_age and float(current_profit) < float(self.min_profit_to_extend):
            return "VG_TIME_EXIT"

        # 对齐预测窗口的时间退出（兜底）
        try:
            label_period = int(self.freqai_info["feature_parameters"]["label_period_candles"])
            tf_minutes = int(timeframe_to_minutes(self.timeframe))
        except Exception:
            return None
        horizon_minutes = int(max(1, label_period) * tf_minutes)
        trade_duration_minutes = int((current_time - opened_at).total_seconds() // 60)
        if trade_duration_minutes >= horizon_minutes * 2 and float(current_profit) <= 0:
            return "VG_HORIZON_EXIT"

        return None

