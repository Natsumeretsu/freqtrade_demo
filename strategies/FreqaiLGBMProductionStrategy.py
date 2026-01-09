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


# -----------------------------------------------------------------------------
# ✅ 生产参数建议（写在配置 configs/freqai/*.json 的 freqai.model_training_parameters 中）
#
# 基于 LightGBM 官方调参建议（Context7）：
# - 建议显式设置 max_depth，并保证 num_leaves <= 2^max_depth；同时用 min_data_in_leaf 抑制过拟合。
# - 对 ~10,000 行（1h）数据：learning_rate 建议 0.03~0.06；
#   - 若 learning_rate≈0.05：n_estimators 通常 400~800 足够（配合特征子采样/袋装更稳）
#   - 若 learning_rate≈0.03：n_estimators 可提高到 800~1200（建议结合回测/Walk-forward）
# - returns 这种重尾分布可考虑更稳健的目标函数：objective="huber" 或 "regression_l1"（需实测对收益的影响）
#
# 示例（仅供参考，需结合你的交易对与回测期调整）：
# {
#   "n_estimators": 700,
#   "learning_rate": 0.05,
#   "max_depth": 6,
#   "num_leaves": 48,
#   "min_data_in_leaf": 200,
#   "feature_fraction": 0.8,
#   "bagging_fraction": 0.7,
#   "bagging_freq": 5,
#   "lambda_l2": 1.0,
#   "n_jobs": -1
# }
# -----------------------------------------------------------------------------


class FreqaiLGBMProductionStrategy(IStrategy):
    """
    FreqAI + LightGBM（回归）趋势策略（生产版）。

    设计目标：
    - 坚持“回归预测未来均值收益率”的主线（比分类更细粒度，可用于风控与动态退出）
    - 特征工程严格放在 feature_engineering_* 中（FreqAI 要求），并补充机构/微观结构特征
    - 出场逻辑：智能退出 + 亏损强制止损（Loss Cut）+ 动态止盈止损（ATR）+ 止损时间衰减
    """

    INTERFACE_VERSION = 3

    timeframe = "1h"
    process_only_new_candles = True

    # 覆盖 EMA200 + rolling 特征（skew/kurt/ER）所需历史
    startup_candle_count: int = 240

    can_short = False
    use_exit_signal = True

    use_custom_roi = True
    use_custom_stoploss = True

    # ROI 仅兜底：主要由 custom_roi / custom_exit 管理
    minimal_roi = {"0": 1.0}
    stoploss = -0.10

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

    # --- 入场/出场阈值 ---
    # Wolfram：标准正态下超过 1.5σ 的单侧概率约 6.68%（用于校准“足够显著”的入场阈值量级）
    buy_pred_threshold = DecimalParameter(0.008, 0.06, default=0.012, decimals=3, space="buy", optimize=True)
    sell_pred_threshold = DecimalParameter(-0.06, 0.0, default=-0.005, decimals=3, space="sell", optimize=True)

    # --- 趋势过滤 ---
    buy_use_trend_filter = BooleanParameter(default=True, space="buy", optimize=False)
    buy_ema_long = IntParameter(100, 300, default=200, space="buy", optimize=False)
    buy_ema_short = IntParameter(20, 120, default=50, space="buy", optimize=False)
    buy_use_fast_trend_filter = BooleanParameter(default=True, space="buy", optimize=False)
    buy_use_ema_short_slope_filter = BooleanParameter(default=True, space="buy", optimize=False)
    buy_ema_short_slope_lookback = IntParameter(6, 72, default=24, space="buy", optimize=False)

    buy_use_ema_long_slope_filter = BooleanParameter(default=True, space="buy", optimize=False)
    buy_ema_long_slope_lookback = IntParameter(12, 240, default=48, space="buy", optimize=False)

    buy_use_max_atr_pct_filter = BooleanParameter(default=True, space="buy", optimize=False)
    buy_max_atr_pct = DecimalParameter(0.005, 0.10, default=0.040, decimals=3, space="buy", optimize=True)

    buy_use_adx_filter = BooleanParameter(default=False, space="buy", optimize=False)
    buy_adx_period = IntParameter(7, 28, default=14, space="buy", optimize=False)
    buy_adx_min = IntParameter(10, 50, default=15, space="buy", optimize=True)

    # --- 风控（ATR） ---
    risk_atr_period = IntParameter(7, 28, default=14, space="sell", optimize=False)
    sell_tp_atr_mult = DecimalParameter(0.5, 8.0, default=3.0, decimals=2, space="sell", optimize=True)
    sell_tp_min = DecimalParameter(0.0, 0.10, default=0.02, decimals=3, space="sell", optimize=True)
    sell_tp_max = DecimalParameter(0.0, 0.30, default=0.0, decimals=3, space="sell", optimize=True)

    sell_sl_atr_mult = DecimalParameter(0.5, 8.0, default=2.0, decimals=2, space="sell", optimize=True)
    sell_sl_min = DecimalParameter(0.0, 0.20, default=0.02, decimals=3, space="sell", optimize=True)
    sell_sl_max = DecimalParameter(0.0, 0.30, default=0.0, decimals=3, space="sell", optimize=True)

    # --- 追踪止损 ---
    sell_use_trailing_stop = BooleanParameter(default=True, space="sell", optimize=False)
    sell_trailing_stop_positive = DecimalParameter(0.0, 0.05, default=0.01, decimals=3, space="sell", optimize=False)
    sell_trailing_stop_offset = DecimalParameter(0.0, 0.10, default=0.02, decimals=3, space="sell", optimize=False)

    # --- 智能退出阈值 ---
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

        rsi = ta.RSI(dataframe, timeperiod=period)  # type: ignore
        mfi = ta.MFI(dataframe, timeperiod=period)
        adx = ta.ADX(dataframe, timeperiod=period)
        ema = ta.EMA(dataframe, timeperiod=period)
        atr = ta.ATR(dataframe, timeperiod=period)
        natr = ta.NATR(dataframe, timeperiod=period)
        bb = ta.BBANDS(dataframe, timeperiod=period, nbdevup=2.0, nbdevdn=2.0)
        bb_mid = bb["middleband"].replace(0, np.nan)
        bb_width = (bb["upperband"] - bb["lowerband"]) / bb_mid

        dataframe["%-rsi-period"] = rsi / 100.0
        dataframe["%-mfi-period"] = mfi / 100.0
        dataframe["%-adx-period"] = adx / 100.0
        dataframe["%-dist_ema-period"] = (dataframe["close"] - ema) / ema.replace(0, np.nan)
        dataframe["%-atr_pct-period"] = atr / close_safe
        dataframe["%-natr-period"] = natr / 100.0
        dataframe["%-bb_width-period"] = bb_width
        dataframe["%-roc-period"] = ta.ROC(dataframe, timeperiod=period) / 100.0

        # --- Institutional Features ---
        # 使用对数收益率（log return）进行分布统计：更贴近“机构风控”习惯的度量
        log_return = np.log(close_safe).diff()
        dataframe["%-logret_skew-period"] = log_return.rolling(period).skew()
        dataframe["%-logret_kurt-period"] = log_return.rolling(period).kurt()

        # --- Microstructure ---
        # Efficiency Ratio（Kaufman）：|ΔP(n)| / Σ|ΔP(1)|，取值 0~1，可视作趋势效率/分形维度的代理量
        change = (dataframe["close"] - dataframe["close"].shift(period)).abs()
        volatility = dataframe["close"].diff().abs().rolling(period).sum()
        dataframe["%-eff_ratio-period"] = change / volatility.replace(0, np.nan)

        return dataframe.replace([np.inf, -np.inf], np.nan)

    def feature_engineering_expand_basic(self, dataframe: DataFrame, metadata: dict, **kwargs) -> DataFrame:
        """
        不需要 period 扩展的一些基础特征。
        """
        close_safe = dataframe["close"].replace(0, np.nan)

        dataframe["%-pct_change"] = dataframe["close"].pct_change()
        dataframe["%-log_return"] = np.log(close_safe).diff()

        vol_mean_24 = dataframe["volume"].rolling(24).mean()
        dataframe["%-volume_ratio_24"] = dataframe["volume"] / vol_mean_24.replace(0, np.nan)

        return dataframe.replace([np.inf, -np.inf], np.nan)

    def feature_engineering_standard(self, dataframe: DataFrame, metadata: dict, **kwargs) -> DataFrame:
        """
        仅在基础 timeframe 调用一次，适合放“不会自动扩展”的特征。
        """
        close_safe = dataframe["close"].replace(0, np.nan)

        ema_period = max(1, int(self.buy_ema_long.value))
        dataframe["ema_long"] = ta.EMA(dataframe, timeperiod=ema_period)
        dataframe["%-dist_ema_long"] = (dataframe["close"] - dataframe["ema_long"]) / close_safe

        dataframe["%-day_of_week"] = dataframe["date"].dt.dayofweek
        dataframe["%-hour_of_day"] = dataframe["date"].dt.hour

        return dataframe.replace([np.inf, -np.inf], np.nan)

    def set_freqai_targets(self, dataframe: DataFrame, metadata: dict, **kwargs) -> DataFrame:
        """
        设置回归目标：未来 label_period_candles 根K线的“均值收益率”。
        """
        label_period = int(self.freqai_info["feature_parameters"]["label_period_candles"])
        label_period = max(1, label_period)

        dataframe["&s_close_mean"] = (
            dataframe["close"].shift(-label_period).rolling(label_period).mean() / dataframe["close"] - 1
        )
        return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # FreqAI 会自动调用 feature_engineering_* 和 set_freqai_targets，并将预测结果回填到 dataframe
        dataframe = self.freqai.start(dataframe, metadata, self)

        # 策略过滤用的趋势线（不加 %，避免被当作特征）
        if "ema_long" not in dataframe.columns:
            ema_period = max(1, int(self.buy_ema_long.value))
            dataframe["ema_long"] = ta.EMA(dataframe, timeperiod=ema_period)
        if "ema_short" not in dataframe.columns:
            ema_period = max(1, int(self.buy_ema_short.value))
            dataframe["ema_short"] = ta.EMA(dataframe, timeperiod=ema_period)

        # 风控使用的 ATR（不加 %，避免和 FreqAI 特征扩展混在一起）
        atr_period = max(1, int(self.risk_atr_period.value))
        dataframe["atr"] = ta.ATR(dataframe, timeperiod=atr_period)
        dataframe["atr_pct"] = dataframe["atr"] / dataframe["close"].replace(0, np.nan)

        # 入场过滤使用的 ADX（不加 %，避免被当作特征）
        if bool(self.buy_use_adx_filter.value) and "adx" not in dataframe.columns:
            adx_period = max(1, int(self.buy_adx_period.value))
            dataframe["adx"] = ta.ADX(dataframe, timeperiod=adx_period)

        return dataframe

    def populate_entry_trend(self, df: DataFrame, metadata: dict) -> DataFrame:
        if "do_predict" not in df.columns or "&s_close_mean" not in df.columns:
            return df

        pred_thr = float(self.buy_pred_threshold.value)
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
        if use_max_atr_pct and np.isfinite(max_atr_pct) and max_atr_pct > 0 and "atr_pct" in df.columns:
            conditions.append(df["atr_pct"] > 0)
            conditions.append(df["atr_pct"] < max_atr_pct)
        if use_adx and np.isfinite(adx_min) and adx_min > 0 and "adx" in df.columns:
            conditions.append(df["adx"] > adx_min)

        if conditions:
            df.loc[reduce(lambda x, y: x & y, conditions), ["enter_long", "enter_tag"]] = (1, "FREQAI_LGBM_PROD_LONG")

        return df

    def populate_exit_trend(self, df: DataFrame, metadata: dict) -> DataFrame:
        if "do_predict" not in df.columns or "&s_close_mean" not in df.columns:
            return df

        pred_thr = float(self.sell_pred_threshold.value)
        conditions = [
            df["do_predict"] == 1,
            df["volume"] > 0,
            df["&s_close_mean"] < pred_thr,
        ]

        if conditions:
            df.loc[reduce(lambda x, y: x & y, conditions), ["exit_long", "exit_tag"]] = (1, "FREQAI_LGBM_PROD_EXIT")

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
        智能退出（更贴近实盘行为）：
        - Loss Cut：若模型预测跌幅超过 2*ATR（折算到 atr_pct），立即退出（无视盈亏）
        - 盈利单：预测转弱（<= 阈值）立即退出，保护利润
        - 亏损/持平单：持仓时间 >= 预测窗口后仍转弱，退出止损（避免“拖到大回撤”）
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
        - Wolfram：y=max(0.02, 3x) 在 x≈0.00667 处由“固定止盈”切换到“随波动线性增长”
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
        动态止损/跟踪止损 + 时间衰减（生产增强版）。

        时间衰减逻辑（仅对亏损/持平单生效）：
        - 以预测窗口（label_period_candles）作为“信息有效期”
        - 随持仓时间线性收紧 stop 距离：从 base_sl 逐步收紧到 sl_min
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

