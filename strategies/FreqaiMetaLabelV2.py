"""
FreqAI Meta-Labeling Strategy V2 - 优化版

基于 2025 年加密货币市场分析报告的量化策略重构：
1. 切换为 LightGBMClassifier（二分类问题）
2. 非对称三重屏障（TP=2.5×ATR, SL=1.5×ATR）
3. 向量化标签生成
4. 放宽基础策略过滤（增加 ML 学习样本）

标签逻辑：
- 上barrier = 入场价 + profit_atr_mult * ATR → 先触发 = "win"
- 下barrier = 入场价 - loss_atr_mult * ATR → 先触发 = "lose"
- 时间barrier = prediction_period 根K线 → 超时 = "lose"
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

import numpy as np
import talib.abstract as ta
from pandas import DataFrame

from freqtrade.persistence import Order, Trade
from freqtrade.strategy import IStrategy
from freqtrade.strategy.parameters import DecimalParameter, IntParameter
from freqtrade.strategy.strategy_helper import stoploss_from_open

logger = logging.getLogger(__name__)


class FreqaiMetaLabelV2(IStrategy):
    """
    FreqAI Meta-Labeling Strategy V2

    优化点：
    1. 使用 LightGBMClassifier + is_unbalance 处理类别失衡
    2. 非对称三重屏障：TP=2.5×ATR, SL=1.5×ATR
    3. 向量化标签生成（提升训练效率）
    4. 放宽基础策略过滤（增加召回率）
    """

    INTERFACE_VERSION = 3

    # ==================== 基础配置 ====================
    timeframe = "1h"
    process_only_new_candles = True
    startup_candle_count = 240
    can_short = False
    use_exit_signal = True

    # ==================== 止损配置 ====================
    use_custom_stoploss = True
    stoploss = -0.05  # 5% 硬止损（给更多呼吸空间）
    trailing_stop = False  # 完全禁用移动止损
    # 注释掉以下参数，避免意外触发
    # trailing_stop_positive = 0.015
    # trailing_stop_positive_offset = 0.02
    # trailing_only_offset_is_reached = True

    # ROI - 让利润奔跑
    minimal_roi = {"0": 0.10, "120": 0.05, "240": 0.02}

    # ==================== Triple Barrier 参数（非对称优化）====================
    profit_atr_mult = 2.5   # 止盈 = 2.5 × ATR（更宽，让利润奔跑）
    loss_atr_mult = 1.5     # 止损 = 1.5 × ATR（更紧，快速止损）
    prediction_period = 12  # 向前看 12 根K线（12小时）
    atr_period = 14         # ATR 计算周期

    # ==================== Hyperopt 参数（放宽过滤）====================
    ml_threshold = DecimalParameter(0.4, 0.8, default=0.55, space="buy")
    buy_rsi_min = IntParameter(20, 50, default=30, space="buy")
    buy_rsi_max = IntParameter(60, 85, default=80, space="buy")
    buy_adx = IntParameter(10, 25, default=15, space="buy")

    # ==================== 杠杆配置 ====================
    leverage_value = 3.0

    # ==================== 自定义数据存储 ====================
    custom_info: dict = {}

    def leverage(self, pair: str, current_time: datetime, current_rate: float,
                 proposed_leverage: float, max_leverage: float,
                 entry_tag: str | None, side: str, **kwargs) -> float:
        return float(min(self.leverage_value, max_leverage))

    # ==================== FreqAI 特征工程 ====================
    def feature_engineering_expand_all(self, dataframe: DataFrame, period: int,
                                       metadata: dict, **kwargs) -> DataFrame:
        """多周期特征"""
        # RSI
        dataframe[f"%-rsi-period_{period}"] = ta.RSI(dataframe, timeperiod=period)

        # ROC (动量)
        dataframe[f"%-roc-period_{period}"] = ta.ROC(dataframe, timeperiod=period) / 100.0

        # 布林带位置
        bb = ta.BBANDS(dataframe, timeperiod=period)
        dataframe[f"%-bb_lower-period_{period}"] = (
            (dataframe["close"] - bb["lowerband"]) / (bb["upperband"] - bb["lowerband"])
        )

        # NATR (标准化波动率)
        dataframe[f"%-natr-period_{period}"] = ta.NATR(dataframe, timeperiod=period) / 100.0

        # ADX (趋势强度)
        dataframe[f"%-adx-period_{period}"] = ta.ADX(dataframe, timeperiod=period) / 100.0

        # MFI (资金流)
        dataframe[f"%-mfi-period_{period}"] = ta.MFI(dataframe, timeperiod=period) / 100.0

        return dataframe.replace([np.inf, -np.inf], np.nan)

    def feature_engineering_expand_basic(self, dataframe: DataFrame,
                                         metadata: dict, **kwargs) -> DataFrame:
        """基础特征"""
        # 价格变化
        dataframe["%-pct_change"] = dataframe["close"].pct_change()

        # 成交量比率
        vol_mean = dataframe["volume"].rolling(24).mean()
        dataframe["%-volume_ratio"] = dataframe["volume"] / vol_mean.replace(0, np.nan)

        # 价格位置
        high_20 = dataframe["high"].rolling(20).max()
        low_20 = dataframe["low"].rolling(20).min()
        dataframe["%-price_position"] = (
            (dataframe["close"] - low_20) / (high_20 - low_20).replace(0, np.nan)
        )

        # 波动率 regime（高/低波动环境）
        natr = ta.NATR(dataframe, timeperiod=14)
        natr_ma = natr.rolling(50).mean()
        dataframe["%-vol_regime"] = natr / natr_ma.replace(0, np.nan)

        return dataframe.replace([np.inf, -np.inf], np.nan)

    def feature_engineering_standard(self, dataframe: DataFrame,
                                     metadata: dict, **kwargs) -> DataFrame:
        """标准特征"""
        dataframe["%-day_of_week"] = dataframe["date"].dt.dayofweek
        dataframe["%-hour_of_day"] = dataframe["date"].dt.hour
        return dataframe

    def set_freqai_targets(self, dataframe: DataFrame,
                           metadata: dict, **kwargs) -> DataFrame:
        """
        向量化 Triple Barrier 标签生成（分类器版本）

        使用 ATR 构建自适应的止盈止损 barrier：
        - 上barrier = close + profit_atr_mult * ATR
        - 下barrier = close - loss_atr_mult * ATR
        - 时间barrier = label_period_candles 根K线

        标签（字符串，用于分类器）：
        - "win": 先触发上barrier
        - "lose": 先触发下barrier 或超时
        """
        label_period = int(self.freqai_info["feature_parameters"]["label_period_candles"])
        label_period = max(1, label_period)

        # 显式声明分类器类别名，确保输出概率列名为 "lose" / "win"
        try:
            self.freqai.class_names = ["lose", "win"]
        except Exception:
            pass

        atr = ta.ATR(dataframe, timeperiod=self.atr_period)

        close = dataframe["close"].values
        high = dataframe["high"].values
        low = dataframe["low"].values
        atr_values = atr.values
        n = len(dataframe)

        # 预计算所有 barrier
        upper_barrier = close + self.profit_atr_mult * atr_values
        lower_barrier = close - self.loss_atr_mult * atr_values

        # 初始化：默认 lose（超时或止损）
        labels = np.full(n, "lose", dtype=object)

        # 记录每个样本是否已确定结果（用于正确处理 barrier 触发顺序）
        determined = np.zeros(n, dtype=bool)
        idx = np.arange(n)
        valid_atr = ~np.isnan(atr_values)

        # 逐个 offset 检查 barrier 触发
        for offset in range(1, label_period + 1):
            if offset >= n:
                break

            # 未来价格
            future_high = np.empty(n)
            future_low = np.empty(n)
            future_high[:] = np.nan
            future_low[:] = np.nan
            future_high[:-offset] = high[offset:]
            future_low[:-offset] = low[offset:]

            # 有效范围（排除边界和已确定的样本）
            valid_mask = (idx < (n - offset)) & ~determined & valid_atr

            # 检查 SL 触发（优先，因为同一根K线内 SL 可能先触发）
            sl_hit = valid_mask & (future_low <= lower_barrier)
            labels[sl_hit] = "lose"
            determined[sl_hit] = True

            # 检查 TP 触发（仅对尚未确定的样本）
            valid_mask_tp = valid_mask & ~determined
            tp_hit = valid_mask_tp & (future_high >= upper_barrier)
            labels[tp_hit] = "win"
            determined[tp_hit] = True

        # 处理边界情况：最后 label_period 根K线无法计算
        labels[n - label_period:] = "lose"

        # 处理 ATR 为 NaN 的情况
        labels[np.isnan(atr_values)] = "lose"

        dataframe["&s-win"] = labels
        return dataframe

    # ==================== 指标计算 ====================
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # FreqAI 启动
        dataframe = self.freqai.start(dataframe, metadata, self)

        # ATR（用于动态止损）
        dataframe["atr"] = ta.ATR(dataframe, timeperiod=self.atr_period)

        # ========== 基础策略指标 ==========
        # RSI
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)
        dataframe["roc"] = ta.ROC(dataframe, timeperiod=14) / 100.0

        # 布林带
        bb = ta.BBANDS(dataframe, timeperiod=20)
        dataframe["bb_lower"] = bb["lowerband"]
        dataframe["bb_upper"] = bb["upperband"]
        dataframe["bb_mid"] = bb["middleband"]

        # ADX (趋势强度过滤)
        dataframe["adx"] = ta.ADX(dataframe, timeperiod=14)

        # EMA 200 (趋势方向过滤 - Regime Filter)
        dataframe["ema_200"] = ta.EMA(dataframe, timeperiod=200)

        return dataframe

    # ==================== 入场信号 (Meta-Labeling) ====================
    def populate_entry_trend(self, df: DataFrame, metadata: dict) -> DataFrame:
        df["enter_long"] = 0
        df["enter_short"] = 0
        df["exit_long"] = 0
        df["exit_short"] = 0

        if "win" not in df.columns:
            return df

        # ========== 基础策略：放宽过滤（增加召回率）==========
        rsi_neutral = (df["rsi"] > self.buy_rsi_min.value) & (df["rsi"] < self.buy_rsi_max.value)
        above_bb_mid = df["close"] > df["bb_mid"]
        adx_trending = df["adx"] > self.buy_adx.value
        positive_momentum = df["roc"] > 0

        # ========== Regime Filter: 只在牛市做多 ==========
        is_bull_market = df["close"] > df["ema_200"]

        base_signal = rsi_neutral & above_bb_mid & adx_trending & positive_momentum & is_bull_market

        # ========== ML 过滤 (Classifier Probability) ==========
        # 分类器输出概率列，列名为类别名称 "win"
        do_predict = df.get("do_predict", 1)
        ml_prob = df.get("win", 0.0)  # 分类器输出的 "win" 类概率
        ml_filter = (do_predict == 1) & (ml_prob > self.ml_threshold.value)

        # ========== Meta-Labeling: 基础信号 + ML 过滤 ==========
        entry_condition = base_signal & ml_filter

        df.loc[entry_condition, "enter_long"] = 1
        df.loc[entry_condition, "enter_tag"] = "META_V2_LONG"

        return df

    # ==================== 出场信号 ====================
    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["exit_long"] = 0
        dataframe["exit_short"] = 0
        return dataframe

    # ==================== 关键：将 ATR 写入 Trade 数据 ====================
    def confirm_trade_entry(self, pair: str, order_type: str, amount: float, rate: float,
                            time_in_force: str, current_time: datetime, entry_tag: str | None,
                            side: str, **kwargs) -> bool:
        """在开仓前确认：确保当前 ATR 可用（用于后续动态止损）。"""
        df, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if df.empty:
            return False

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
                return False
            df = df_cut

        last_candle = df.iloc[-1]
        current_atr = last_candle.get("atr")

        if current_atr is None or not np.isfinite(current_atr) or current_atr <= 0:
            return False

        return True

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
        - `confirm_trade_entry` 不包含 trade 实例，无法持久化到 Trade 自定义数据表。
        - 必须在 `order_filled` 里使用 `trade.set_custom_data()` 落盘，保证回测/实盘一致。
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

        last_candle = df.iloc[-1]
        current_atr = last_candle.get("atr")

        if current_atr is None or not np.isfinite(current_atr) or current_atr <= 0:
            return

        trade.set_custom_data("entry_atr", float(current_atr))

    def custom_stoploss(self, pair: str, trade: Trade, current_time: datetime,
                        current_rate: float, current_profit: float, after_fill: bool,
                        **kwargs) -> float | None:
        """
        动态止损：以入场 ATR 固定距离（相对开仓价），并换算为相对当前价的返回值。

        关键点：
        - 入场 ATR 从 `trade` 自定义数据读取（由 `order_filled` 写入）。
        - 返回值需要是“相对当前价”的距离（使用 `stoploss_from_open` 换算）。
        """
        entry_atr = trade.get_custom_data("entry_atr")
        if entry_atr is None:
            return None

        try:
            entry_atr = float(entry_atr)
        except Exception:
            return None

        if not np.isfinite(entry_atr) or entry_atr <= 0 or trade.open_rate <= 0:
            return None

        # 使用非对称的 loss_atr_mult
        initial_stop_distance = entry_atr * float(self.loss_atr_mult)
        leverage = float(trade.leverage or 1.0)
        if not np.isfinite(leverage) or leverage <= 0:
            leverage = 1.0

        # Freqtrade 期货止损口径：custom_stoploss 返回的是“本次交易风险”（已考虑杠杆），而非纯价格波动比例。
        # ATR 计算得到的是价格距离，因此需要乘以杠杆换算为风险比例。
        open_relative_stop_atr = -(initial_stop_distance / float(trade.open_rate)) * leverage
        # 开仓价口径的“最大亏损”约束：ATR 止损不允许比硬止损更宽
        open_relative_stop = max(open_relative_stop_atr, float(self.stoploss))
        dynamic_sl = stoploss_from_open(
            open_relative_stop=open_relative_stop,
            current_profit=float(current_profit),
            is_short=bool(trade.is_short),
            leverage=leverage,
        )

        return float(dynamic_sl)
