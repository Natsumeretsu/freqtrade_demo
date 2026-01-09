from __future__ import annotations

import logging
from datetime import datetime
from functools import reduce

import numpy as np
import talib.abstract as ta
from pandas import DataFrame

from freqtrade.exchange.exchange_utils_timeframe import timeframe_to_minutes
from freqtrade.persistence import Trade
from freqtrade.strategy import BooleanParameter, DecimalParameter, IStrategy, IntParameter, merge_informative_pair

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

    # --- 保护：减少暴跌/极端震荡时的“连环亏损” ---
    protections = [
        {"method": "CooldownPeriod", "stop_duration_candles": 2},
        {
            "method": "StoplossGuard",
            "lookback_period_candles": 48,
            "trade_limit": 2,
            "stop_duration_candles": 24,
            "only_per_pair": True,
        },
    ]

    # --- 入场/出场阈值（可用于 hyperopt）---
    # 默认 1.2%：多窗口扫参后更稳健，且仍给手续费/滑点留出缓冲空间
    buy_pred_threshold = DecimalParameter(0.002, 0.06, default=0.012, decimals=3, space="buy", optimize=True)
    sell_pred_threshold = DecimalParameter(-0.06, 0.0, default=-0.005, decimals=3, space="sell", optimize=True)

    # --- 宏观过滤：BTC/USDT 4h EMA200（更贴近加密市场节奏，解决熊市 Beta 拖累） ---
    # 规则：
    # - 牛市：BTC 收盘价 > EMA200 -> 使用常规 buy_pred_threshold
    # - 熊市：BTC 收盘价 < EMA200 -> 触发 “Sniper Penalty”，提高入场阈值，仅在模型高置信时出手
    #
    # 注：这不是“完全停止交易”，而是降低熊市的无效高频进场，避免被 Beta 拖累。
    btc_regime_pair = "BTC/USDT"
    btc_regime_timeframe = "4h"
    btc_regime_ema_period = 200
    btc_regime_bear_pred_threshold_multiplier = 2.5
    btc_regime_bear_pred_threshold_min = 0.02

    # --- 趋势过滤 ---
    buy_use_trend_filter = BooleanParameter(default=True, space="buy", optimize=False)
    buy_ema_long = IntParameter(100, 300, default=200, space="buy", optimize=False)
    buy_ema_short = IntParameter(20, 120, default=50, space="buy", optimize=False)
    buy_use_fast_trend_filter = BooleanParameter(default=True, space="buy", optimize=False)
    buy_use_ema_short_slope_filter = BooleanParameter(default=True, space="buy", optimize=False)
    buy_ema_short_slope_lookback = IntParameter(6, 72, default=24, space="buy", optimize=False)

    # --- 熊市/暴跌免疫：入场状态过滤（优先避免“下跌趋势中的反弹诱多”）---
    buy_use_ema_long_slope_filter = BooleanParameter(default=True, space="buy", optimize=False)
    buy_ema_long_slope_lookback = IntParameter(12, 240, default=48, space="buy", optimize=False)

    buy_use_max_atr_pct_filter = BooleanParameter(default=True, space="buy", optimize=False)
    buy_max_atr_pct = DecimalParameter(0.005, 0.10, default=0.040, decimals=3, space="buy", optimize=True)

    buy_use_adx_filter = BooleanParameter(default=False, space="buy", optimize=False)
    buy_adx_period = IntParameter(7, 28, default=14, space="buy", optimize=False)
    buy_adx_min = IntParameter(10, 50, default=15, space="buy", optimize=True)

    # --- 风控：基于 ATR 的动态止盈/动态止损（通过 custom_roi / custom_stoploss 实现）---
    risk_atr_period = IntParameter(7, 28, default=14, space="sell", optimize=False)
    sell_tp_atr_mult = DecimalParameter(0.5, 8.0, default=3.0, decimals=2, space="sell", optimize=True)
    sell_tp_min = DecimalParameter(0.0, 0.10, default=0.02, decimals=3, space="sell", optimize=True)
    sell_tp_max = DecimalParameter(0.0, 0.30, default=0.0, decimals=3, space="sell", optimize=True)

    sell_sl_atr_mult = DecimalParameter(0.5, 8.0, default=2.0, decimals=2, space="sell", optimize=True)
    sell_sl_min = DecimalParameter(0.0, 0.20, default=0.02, decimals=3, space="sell", optimize=True)
    sell_sl_max = DecimalParameter(0.03, 0.20, default=0.08, decimals=3, space="sell", optimize=True)

    # --- 风控：追踪止损（盈利达到阈值后，将止损收紧到“离现价固定距离”）---
    sell_use_trailing_stop = BooleanParameter(default=True, space="sell", optimize=False)
    sell_trailing_stop_positive = DecimalParameter(0.005, 0.10, default=0.03, decimals=3, space="sell", optimize=True)
    sell_trailing_stop_offset = DecimalParameter(0.005, 0.15, default=0.04, decimals=3, space="sell", optimize=True)

    # --- 风控：预测转弱时的“智能退出”（仅在盈利时触发，避免被噪音反复洗出）---
    # smart-exit 阈值建议从 0.0 起步：更贴近“预测转负才走”，减少在趋势/震荡中的过早止盈
    sell_smart_exit_pred_threshold = DecimalParameter(-0.05, 0.05, default=0.0, decimals=3, space="sell", optimize=False)

    def informative_pairs(self):
        return [(self.btc_regime_pair, self.btc_regime_timeframe)]

    def _log_btc_regime_warning(self, message: str) -> None:
        if bool(getattr(self, "_btc_regime_warned", False)):
            return
        setattr(self, "_btc_regime_warned", True)
        logger.warning(message)

    def _get_btc_regime_informative_dataframe(self) -> DataFrame | None:
        dp = getattr(self, "dp", None)
        if dp is None:
            return None

        cached = getattr(self, "_btc_regime_inf_df", None)
        if isinstance(cached, DataFrame) and not cached.empty:
            return cached

        pair = str(getattr(self, "btc_regime_pair", "BTC/USDT"))
        inf_tf = str(getattr(self, "btc_regime_timeframe", "4h"))

        try:
            informative = dp.get_pair_dataframe(pair=pair, timeframe=inf_tf)
        except Exception as e:
            self._log_btc_regime_warning(f"无法加载宏观过滤数据：{pair} {inf_tf}，原因：{e}")
            return None

        if informative is None or informative.empty:
            self._log_btc_regime_warning(
                f"宏观过滤数据为空：{pair} {inf_tf}。请先下载对应 timeframe 的历史数据（例如：download-data --pairs \"BTC/USDT\" --timeframes \"{inf_tf}\"）。"
            )
            return None

        informative = informative.copy()
        informative["btc_close"] = informative["close"]

        ema_period = int(getattr(self, "btc_regime_ema_period", 200))
        ema_period = max(1, ema_period)
        informative["btc_ema200"] = ta.EMA(informative, timeperiod=ema_period)

        informative_small = informative[["date", "btc_close", "btc_ema200"]].copy()
        informative_small = informative_small.replace([np.inf, -np.inf], np.nan)

        setattr(self, "_btc_regime_inf_df", informative_small)
        return informative_small

    def _merge_btc_regime_indicators(self, dataframe: DataFrame) -> DataFrame:
        informative = self._get_btc_regime_informative_dataframe()
        if informative is None:
            return dataframe

        inf_tf = str(getattr(self, "btc_regime_timeframe", "4h"))
        return merge_informative_pair(dataframe, informative, self.timeframe, inf_tf, ffill=True)

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

        # 合并宏观过滤指标（BTC/USDT 1d SMA200）到基础 timeframe
        dataframe = self._merge_btc_regime_indicators(dataframe)

        # 供策略过滤使用的趋势线（不加 %，避免被当作特征）
        if "ema_long" not in dataframe.columns:
            ema_period = max(1, int(self.buy_ema_long.value))
            dataframe["ema_long"] = ta.EMA(dataframe, timeperiod=ema_period)
        if "ema_short" not in dataframe.columns:
            ema_period = max(1, int(self.buy_ema_short.value))
            dataframe["ema_short"] = ta.EMA(dataframe, timeperiod=ema_period)

        # 风控使用的 ATR（不加 %，避免和 FreqAI 的特征扩展混在一起）
        atr_period = max(1, int(self.risk_atr_period.value))
        dataframe["atr"] = ta.ATR(dataframe, timeperiod=atr_period)
        dataframe["atr_pct"] = dataframe["atr"] / dataframe["close"].replace(0, np.nan)

        # 入场过滤使用的 ADX（不加 %，避免被当作特征）
        if bool(self.buy_use_adx_filter.value) and "adx" not in dataframe.columns:
            adx_period = max(1, int(self.buy_adx_period.value))
            dataframe["adx"] = ta.ADX(dataframe, timeperiod=adx_period)

        return dataframe

    def populate_entry_trend(self, df: DataFrame, metadata: dict) -> DataFrame:
        base_pred_thr = float(self.buy_pred_threshold.value)
        bear_mult = float(getattr(self, "btc_regime_bear_pred_threshold_multiplier", 2.5))
        bear_min = float(getattr(self, "btc_regime_bear_pred_threshold_min", 0.02))

        bear_mult = max(1.0, bear_mult)
        bear_thr = base_pred_thr * bear_mult
        if np.isfinite(bear_min) and bear_min > 0:
            bear_thr = max(bear_thr, bear_min)

        inf_tf = str(getattr(self, "btc_regime_timeframe", "4h"))
        btc_close_col = f"btc_close_{inf_tf}"
        btc_ema200_col = f"btc_ema200_{inf_tf}"

        # 默认“保守失败”（无法判断宏观状态时按熊市处理）：更符合风控目标
        pred_thr: float | np.ndarray
        if btc_close_col in df.columns and btc_ema200_col in df.columns:
            is_bull = df[btc_close_col] > df[btc_ema200_col]
            pred_thr = np.where(is_bull, base_pred_thr, bear_thr)
        else:
            pred_thr = bear_thr

        use_trend = bool(self.buy_use_trend_filter.value)
        use_fast_trend = bool(self.buy_use_fast_trend_filter.value)
        use_ema_short_slope = bool(self.buy_use_ema_short_slope_filter.value)
        ema_short_slope_lookback = max(1, int(self.buy_ema_short_slope_lookback.value))
        use_ema_long_slope = bool(self.buy_use_ema_long_slope_filter.value)
        ema_long_slope_lookback = max(1, int(self.buy_ema_long_slope_lookback.value))
        use_max_atr_pct = bool(self.buy_use_max_atr_pct_filter.value)
        max_atr_pct = float(self.buy_max_atr_pct.value)
        use_adx = bool(self.buy_use_adx_filter.value)
        adx_min = float(self.buy_adx_min.value)

        conditions = [
            df["do_predict"] == 1,
            df["volume"] > 0,
            df["&s_close_mean"] > pred_thr,
        ]
        if use_trend:
            conditions.append(df["close"] > df["ema_long"])
            if use_ema_long_slope and "ema_long" in df.columns:
                conditions.append(df["ema_long"] > df["ema_long"].shift(ema_long_slope_lookback))
            if use_fast_trend and "ema_short" in df.columns:
                conditions.append(df["ema_short"] > df["ema_long"])
                conditions.append(df["close"] > df["ema_short"])
                if use_ema_short_slope:
                    conditions.append(df["ema_short"] > df["ema_short"].shift(ema_short_slope_lookback))
        if use_max_atr_pct and np.isfinite(max_atr_pct) and max_atr_pct > 0:
            conditions.append(df["atr_pct"] > 0)
            conditions.append(df["atr_pct"] < max_atr_pct)
        if use_adx and np.isfinite(adx_min) and adx_min > 0 and "adx" in df.columns:
            conditions.append(df["adx"] > adx_min)

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
        - Loss Cut：若模型预测跌幅超过 2*ATR（折算到 atr_pct），立即退出（无视盈亏）
        - 盈利单：模型转弱（预测 <= 阈值）立刻退出，保护利润
        - 亏损/持平单：仅当持仓时间 >= 预测窗口后，模型仍转弱（预测 <= 阈值）才退出，避免被短期噪音反复洗出
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

        # Loss Cut：pred 是“收益率预测”，与 atr_pct 同量纲；阈值为 -2*ATR
        if np.isfinite(pred) and np.isfinite(atr_pct) and atr_pct > 0 and pred <= (-2.0 * atr_pct):
            return "FREQAI_LOSS_CUT"

        thr = float(self.sell_smart_exit_pred_threshold.value)
        if float(current_profit) > 0:
            if np.isfinite(pred) and pred <= thr:
                return "FREQAI_SMART_EXIT"
            return None

        # 亏损/持平：超过预测窗口仍未走强，且预测已转弱，则退出止损（避免“拖到大回撤”）
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

        if trade_duration_minutes >= horizon_minutes and np.isfinite(pred) and pred <= thr:
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
        动态止损/跟踪止损 + 时间衰减（增强版）。
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

        base_sl = max(sl_min, atr_pct * sl_mult)
        if sl_max > 0:
            base_sl = min(base_sl, sl_max)

        if not np.isfinite(base_sl) or base_sl <= 0:
            return None

        sl = base_sl

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
                return sl

        # 时间衰减：亏损/持平单随时间收紧止损（避免“耗完预测信息后继续死扛”）
        if float(current_profit) <= 0 and base_sl > sl_min:
            try:
                label_period = int(self.freqai_info["feature_parameters"]["label_period_candles"])
                tf_minutes = int(timeframe_to_minutes(self.timeframe))
            except Exception:
                return sl

            horizon_minutes = int(label_period * tf_minutes) if label_period > 0 and tf_minutes > 0 else 0
            if horizon_minutes <= 0:
                return sl

            try:
                opened_at = getattr(trade, "open_date_utc", None) or getattr(trade, "open_date", None)
                if opened_at is None:
                    return sl
                trade_duration_minutes = int((current_time - opened_at).total_seconds() // 60)
                trade_duration_minutes = max(0, trade_duration_minutes)
            except Exception:
                return sl

            age_ratio = float(trade_duration_minutes) / float(horizon_minutes)
            age_ratio = float(np.clip(age_ratio, 0.0, 1.0))
            sl = base_sl - (base_sl - sl_min) * age_ratio
            sl = float(max(sl_min, sl))

        return sl
