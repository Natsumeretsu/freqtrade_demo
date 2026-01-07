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


class FreqaiLGBMTrendStrategy(IStrategy):
    """
    FreqAI + LightGBM（回归）趋势策略示例。

    核心思路：
    - 特征工程交给 FreqAI：使用 `%` 前缀定义特征列，支持滚动训练与自动缩放。
    - 预测目标为未来 N 根 K 线的“均值收益率”（回归目标，列名前缀必须为 `&`）。
    - 交易逻辑：趋势过滤（EMA）+ 预测阈值（只做预测涨幅足够大的机会）。
    """

    INTERFACE_VERSION = 3

    timeframe = "1h"
    process_only_new_candles = True

    # 需要覆盖 EMA200 + 一些滚动特征
    startup_candle_count: int = 240

    can_short = False
    use_exit_signal = True

    # 使用 Freqtrade 内置回调（不要手写“自定义退出引擎”）
    use_custom_roi = True
    use_custom_stoploss = True

    # ROI 只做兜底：主要靠预测信号出场
    minimal_roi = {"0": 1.0}
    stoploss = -0.10

    # --- 入场/出场阈值（可用于 hyperopt）---
    # 默认 1.5%：给手续费/滑点留缓冲，避免“胜率假象”下的费率磨损
    buy_pred_threshold = DecimalParameter(0.01, 0.06, default=0.015, decimals=3, space="buy", optimize=True)
    sell_pred_threshold = DecimalParameter(-0.06, 0.0, default=-0.005, decimals=3, space="sell", optimize=True)

    # --- 趋势过滤 ---
    buy_use_trend_filter = BooleanParameter(default=True, space="buy", optimize=False)
    buy_ema_long = IntParameter(100, 300, default=200, space="buy", optimize=False)

    # --- 风控：基于 ATR 的动态止盈/动态止损（通过 custom_roi / custom_stoploss 实现）---
    risk_atr_period = IntParameter(7, 28, default=14, space="sell", optimize=False)
    sell_tp_atr_mult = DecimalParameter(0.5, 8.0, default=3.0, decimals=2, space="sell", optimize=True)
    sell_tp_min = DecimalParameter(0.0, 0.10, default=0.02, decimals=3, space="sell", optimize=True)
    sell_tp_max = DecimalParameter(0.0, 0.30, default=0.0, decimals=3, space="sell", optimize=True)

    sell_sl_atr_mult = DecimalParameter(0.5, 8.0, default=2.0, decimals=2, space="sell", optimize=True)
    sell_sl_min = DecimalParameter(0.0, 0.20, default=0.02, decimals=3, space="sell", optimize=True)
    sell_sl_max = DecimalParameter(0.0, 0.30, default=0.0, decimals=3, space="sell", optimize=True)

    # --- 风控：追踪止损（盈利达到阈值后，将止损收紧到“离现价固定距离”）---
    sell_use_trailing_stop = BooleanParameter(default=True, space="sell", optimize=False)
    sell_trailing_stop_positive = DecimalParameter(0.0, 0.05, default=0.01, decimals=3, space="sell", optimize=False)
    sell_trailing_stop_offset = DecimalParameter(0.0, 0.10, default=0.02, decimals=3, space="sell", optimize=False)

    # --- 风控：预测转弱时的“智能退出”（仅在盈利时触发，避免被噪音反复洗出）---
    sell_smart_exit_pred_threshold = DecimalParameter(-0.05, 0.05, default=0.0, decimals=3, space="sell", optimize=False)

    def feature_engineering_expand_all(
        self,
        dataframe: DataFrame,
        period: int,
        metadata: dict,
        **kwargs,
    ) -> DataFrame:
        """
        低层特征（会按 freqai 配置自动扩展：period/timeframe/shift/corr-pairs）。

        约定：
        - 所有特征列名必须以 `%` 开头（否则不会进模型）。
        - 避免直接喂“绝对价格”，优先喂“相对值/比率”（更抗非平稳）。
        """
        close_safe = dataframe["close"].replace(0, np.nan)

        rsi = ta.RSI(dataframe, timeperiod=period) # type: ignore
        mfi = ta.MFI(dataframe, timeperiod=period)
        adx = ta.ADX(dataframe, timeperiod=period)
        ema = ta.EMA(dataframe, timeperiod=period)
        atr = ta.ATR(dataframe, timeperiod=period)
        natr = ta.NATR(dataframe, timeperiod=period)
        bb = ta.BBANDS(dataframe, timeperiod=period, nbdevup=2.0, nbdevdn=2.0)
        bb_mid = bb["middleband"].replace(0, np.nan)
        bb_width = (bb["upperband"] - bb["lowerband"]) / bb_mid

        # 标准化到相对尺度（即便 FreqAI 有 scaler，依然推荐先做“相对化”）
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
        """
        不需要 period 扩展的一些基础特征。
        """
        dataframe["%-pct_change"] = dataframe["close"].pct_change()
        vol_mean_24 = dataframe["volume"].rolling(24).mean()
        dataframe["%-volume_ratio_24"] = dataframe["volume"] / vol_mean_24.replace(0, np.nan)
        return dataframe.replace([np.inf, -np.inf], np.nan)

    def feature_engineering_standard(self, dataframe: DataFrame, metadata: dict, **kwargs) -> DataFrame:
        """
        仅在基础 timeframe 调用一次，适合放“不会自动扩展”的特征。
        """
        close_safe = dataframe["close"].replace(0, np.nan)

        # 趋势强度（相对长期均线偏离，避免直接喂“绝对价格”）
        ema_period = max(1, int(self.buy_ema_long.value))
        dataframe["ema_long"] = ta.EMA(dataframe, timeperiod=ema_period)
        dataframe["%-dist_ema_long"] = (dataframe["close"] - dataframe["ema_long"]) / close_safe

        dataframe["%-day_of_week"] = dataframe["date"].dt.dayofweek
        dataframe["%-hour_of_day"] = dataframe["date"].dt.hour
        return dataframe

    def set_freqai_targets(self, dataframe: DataFrame, metadata: dict, **kwargs) -> DataFrame:
        """
        设置回归目标：未来 label_period_candles 根K线的“均值收益率”。
        """
        label_period = int(self.freqai_info["feature_parameters"]["label_period_candles"])
        label_period = max(1, label_period)

        dataframe["&s_close_mean"] = (
            dataframe["close"]
            .shift(-label_period)
            .rolling(label_period)
            .mean()
            / dataframe["close"]
            - 1
        )
        return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # FreqAI 会自动调用 feature_engineering_* 和 set_freqai_targets，并将预测结果回填到 dataframe
        dataframe = self.freqai.start(dataframe, metadata, self)

        # 供策略过滤使用的趋势线（不加 %，避免被当作特征）
        if "ema_long" not in dataframe.columns:
            ema_period = max(1, int(self.buy_ema_long.value))
            dataframe["ema_long"] = ta.EMA(dataframe, timeperiod=ema_period)

        # 风控使用的 ATR（不加 %，避免和 FreqAI 的特征扩展混在一起）
        atr_period = max(1, int(self.risk_atr_period.value))
        dataframe["atr"] = ta.ATR(dataframe, timeperiod=atr_period)
        dataframe["atr_pct"] = dataframe["atr"] / dataframe["close"].replace(0, np.nan)

        return dataframe

    def populate_entry_trend(self, df: DataFrame, metadata: dict) -> DataFrame:
        pred_thr = float(self.buy_pred_threshold.value)
        use_trend = bool(self.buy_use_trend_filter.value)

        conditions = [
            df["do_predict"] == 1,
            df["volume"] > 0,
            df["&s_close_mean"] > pred_thr,
        ]
        if use_trend:
            conditions.append(df["close"] > df["ema_long"])

        if conditions:
            df.loc[reduce(lambda x, y: x & y, conditions), ["enter_long", "enter_tag"]] = (1, "FREQAI_LGBM_LONG")

        return df

    def populate_exit_trend(self, df: DataFrame, metadata: dict) -> DataFrame:
        pred_thr = float(self.sell_pred_threshold.value)
        conditions = [
            df["do_predict"] == 1,
            df["volume"] > 0,
            df["&s_close_mean"] < pred_thr,
        ]

        if conditions:
            df.loc[reduce(lambda x, y: x & y, conditions), ["exit_long", "exit_tag"]] = (1, "FREQAI_LGBM_EXIT")

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
        """
        智能退出（更贴近“模型转弱就走”的实盘行为）：
        - 仅在当前单已盈利时触发（避免在浮亏期被短期噪音反复洗出）
        - 当模型预测未来均值收益 <= 阈值时退出
        """
        if trade.is_short:
            return None
        if float(current_profit) <= 0:
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

        thr = float(self.sell_smart_exit_pred_threshold.value)
        if np.isfinite(pred) and pred <= thr:
            return "FREQAI_SMART_EXIT"

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
        """
        动态止盈（Freqtrade 内置 custom_roi）。
        - 返回“达到多少利润就允许止盈”的阈值（比例），例如 0.02 表示 +2%
        - 与 minimal_roi 同时存在时，取较低者触发
        """
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
        """
        动态止损/跟踪止损（Freqtrade 内置 custom_stoploss）。
        - 返回“相对 current_rate 的距离”（比例），例如 0.03 表示止损价在现价下方 3%
        - 该止损只能上移（更紧），不会下移（更松）
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
        sl_mult = max(0.0, sl_mult)
        sl_min = max(0.0, sl_min)
        sl_max = max(0.0, sl_max)

        sl = max(sl_min, atr_pct * sl_mult)
        if sl_max > 0:
            sl = min(sl, sl_max)

        if not np.isfinite(sl) or sl <= 0:
            return None

        # 追踪止损：盈利达到 offset 后，将止损收紧到离现价 trailing_positive 的距离
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

        # 可选：预测窗口结束仍未赚钱，则更积极地收紧止损（避免“拖到大回撤”）
        try:
            label_period = int(self.freqai_info["feature_parameters"]["label_period_candles"])
        except Exception:
            label_period = 0
        if label_period > 0 and float(current_profit) < 0:
            try:
                tf_minutes = int(timeframe_to_minutes(self.timeframe))
            except Exception:
                tf_minutes = 0
            horizon_minutes = int(label_period * tf_minutes) if tf_minutes > 0 else 0
            if horizon_minutes > 0 and int(trade_duration) >= horizon_minutes:
                sl = min(sl, 0.01)

        return sl
