"""
FreqAI Meta-Labeling Strategy with Dynamic Triple Barriers

核心思想：
1. 动态标签：使用 ATR 构建自适应的 Triple Barrier
2. Meta-Labeling：基础策略生成候选信号，ML 过滤

标签逻辑：
- 上barrier = 入场价 + profit_atr_mult * ATR → 先触发 = 1 (win)
- 下barrier = 入场价 - loss_atr_mult * ATR → 先触发 = 0 (lose)
- 时间barrier = prediction_period 根K线 → 超时 = 0 (no opportunity)
"""
from __future__ import annotations

import logging
from datetime import datetime

import numpy as np
import talib.abstract as ta
from pandas import DataFrame

from freqtrade.persistence import Trade
from freqtrade.strategy import IStrategy
from freqtrade.strategy.parameters import DecimalParameter, IntParameter

logger = logging.getLogger(__name__)


class FreqaiMetaLabel(IStrategy):
    """
    FreqAI Meta-Labeling Strategy

    使用动态 ATR Triple Barrier 生成标签
    基础策略 + ML 过滤的 Meta-Labeling 入场
    """

    INTERFACE_VERSION = 3

    # ==================== 基础配置 ====================
    timeframe = "1h"
    process_only_new_candles = True
    startup_candle_count = 240
    can_short = False
    use_exit_signal = True

    # ==================== 止损配置 (不对称防御) ====================
    use_custom_stoploss = True
    stoploss = -0.03  # 3% 硬止损（从 5% 收紧，强行矫正盈亏比）
    trailing_stop = False  # 继续保持关闭
    trailing_stop_positive = 0.015
    trailing_stop_positive_offset = 0.02
    trailing_only_offset_is_reached = True

    # ROI - 让利润奔跑
    minimal_roi = {"0": 0.10, "120": 0.05, "240": 0.02}

    # ==================== Triple Barrier 参数 ====================
    # ATR 乘数 - 更宽的止盈目标
    profit_atr_mult = 2.0   # 止盈 = 2.0 * ATR (更宽)
    loss_atr_mult = 2.0     # 止损 = 2.0 * ATR (与止盈对称)
    prediction_period = 8   # 向前看 8 根K线（8小时，给更多时间达到目标）
    atr_period = 14         # ATR 计算周期

    # ==================== Hyperopt 参数 (Optimized 2024-01-06) ====================
    ml_threshold = DecimalParameter(0.4, 0.8, default=0.60, space="buy")
    buy_rsi_min = IntParameter(30, 55, default=41, space="buy")
    buy_rsi_max = IntParameter(60, 80, default=73, space="buy")
    buy_adx = IntParameter(15, 30, default=21, space="buy")

    # ==================== 杠杆配置 ====================
    leverage_value = 3.0

    # ==================== 自定义数据存储 ====================
    custom_info: dict = {}  # 存储每个 pair 的入场 ATR

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
        动态 Triple Barrier 标签生成

        使用 ATR 构建自适应的止盈止损barrier：
        - 上barrier = close + profit_atr_mult * ATR
        - 下barrier = close - loss_atr_mult * ATR
        - 时间barrier = prediction_period 根K线

        标签：
        - 1: 先触发上barrier (win)
        - 0: 先触发下barrier 或超时 (lose/no opportunity)
        """
        # 计算 ATR
        atr = ta.ATR(dataframe, timeperiod=self.atr_period)

        close = dataframe["close"].values
        high = dataframe["high"].values
        low = dataframe["low"].values
        atr_values = atr.values

        labels = []
        n = len(dataframe)

        for i in range(n):
            # 处理 ATR 为 NaN 的情况
            if np.isnan(atr_values[i]) or i + self.prediction_period >= n:
                labels.append(0.0)
                continue

            entry_price = close[i]
            current_atr = atr_values[i]

            # 动态 barrier
            upper_barrier = entry_price + self.profit_atr_mult * current_atr
            lower_barrier = entry_price - self.loss_atr_mult * current_atr

            label = 0.0  # 默认：超时或触发下barrier

            # 遍历未来 K 线，检查哪个 barrier 先被触发
            for j in range(i + 1, min(i + 1 + self.prediction_period, n)):
                # 检查是否触发上barrier（止盈）
                if high[j] >= upper_barrier:
                    label = 1.0
                    break
                # 检查是否触发下barrier（止损）
                if low[j] <= lower_barrier:
                    label = 0.0
                    break
            # 如果循环结束没有 break，说明超时，label 保持 0.0

            labels.append(label)

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

        # ========== 基础策略：动量突破 ==========
        rsi_neutral_strong = (df["rsi"] > self.buy_rsi_min.value) & (df["rsi"] < self.buy_rsi_max.value)
        above_bb_mid = df["close"] > df["bb_mid"]
        adx_trending = df["adx"] > self.buy_adx.value
        positive_momentum = df["roc"] > 0

        # ========== Regime Filter: 只在牛市做多 ==========
        is_bull_market = df["close"] > df["ema_200"]

        base_signal = rsi_neutral_strong & above_bb_mid & adx_trending & positive_momentum & is_bull_market

        # ========== ML 过滤 (Regressor Score) ==========
        do_predict = df.get("do_predict", 1)
        ml_score = df.get("&s-win", 0.0)
        ml_filter = (do_predict == 1) & (ml_score > self.ml_threshold.value)

        # ========== Meta-Labeling: 基础信号 + ML 过滤 ==========
        entry_condition = base_signal & ml_filter

        df.loc[entry_condition, "enter_long"] = 1
        df.loc[entry_condition, "enter_tag"] = "META_ATR_LONG"

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
        """
        在开仓确认时，将当前的 ATR 值保存到 trade 的 custom_data 中。
        """
        df, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if df.empty:
            return False

        last_candle = df.iloc[-1]
        current_atr = last_candle.get("atr")

        if current_atr is None or np.isnan(current_atr) or current_atr == 0:
            return False

        # 使用 custom_trade_data 持久化存储（Freqtrade 会自动传递给 trade）
        self.custom_trade_data = {"entry_atr": float(current_atr)}

        return True

    def custom_stoploss(self, pair: str, trade: Trade, current_time: datetime,
                        current_rate: float, current_profit: float, after_fill: bool,
                        **kwargs) -> float | None:
        """
        简化版动态止损：仅基于 ATR 的固定止损，无移动止损
        """
        # 获取开仓 ATR
        entry_atr = None
        tr_data = getattr(trade, 'custom_data', None)
        if isinstance(tr_data, dict):
            entry_atr = tr_data.get("entry_atr")

        # 如果没有 ATR，直接返回硬止损
        if entry_atr is None:
            return self.stoploss

        # 计算动态止损距离 (固定止损，不移动)
        initial_stop_distance = entry_atr * self.loss_atr_mult
        initial_stop_ratio = -(initial_stop_distance / trade.open_rate)

        # 返回 ATR 止损，但不能宽于硬止损
        return max(initial_stop_ratio, self.stoploss)
