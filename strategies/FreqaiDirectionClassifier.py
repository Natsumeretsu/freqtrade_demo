"""
FreqAI 方向分类策略 V2

核心改进：
1. 使用分类标签（long/short/neutral）而非回归
2. 基于实际可交易的价格变化阈值定义标签
3. 对称学习：模型同时学习上涨和下跌模式
4. 更合理的标签定义：考虑交易成本和滑点

标签定义逻辑：
- 如果未来 N 根K线的最大涨幅 > threshold 且 > 最大跌幅：标签 = "long"
- 如果未来 N 根K线的最大跌幅 > threshold 且 > 最大涨幅：标签 = "short"
- 否则：标签 = "neutral"
"""
from __future__ import annotations

import logging
from datetime import datetime

import numpy as np
import talib.abstract as ta
from pandas import DataFrame

from freqtrade.persistence import Trade
from freqtrade.strategy import IStrategy

logger = logging.getLogger(__name__)


class FreqaiDirectionClassifier(IStrategy):
    """
    FreqAI 方向分类策略

    使用 LightGBMClassifier 预测方向（long/short/neutral）
    """

    INTERFACE_VERSION = 3

    # ==================== 基础配置 ====================
    timeframe = "1h"  # 1小时周期
    process_only_new_candles = True
    startup_candle_count = 240  # 10 days of 1h candles
    can_short = False  # LONG ONLY - based on Moonshot optimization
    use_exit_signal = True

    # ==================== 止损配置 ====================
    use_custom_stoploss = False
    stoploss = -0.025  # 2.5% 止损 (更紧)
    trailing_stop = True
    trailing_stop_positive = 0.01  # 盈利 1% 后启动移动止损
    trailing_stop_positive_offset = 0.015  # 盈利 1.5% 后才开始移动
    trailing_only_offset_is_reached = True

    # ROI 兜底 - 让盈利跑得更远
    minimal_roi = {"0": 0.05, "120": 0.03, "240": 0.02}  # 更宽松的止盈

    # ==================== 保护配置 ====================
    protections = [
        {"method": "CooldownPeriod", "stop_duration_candles": 1},
        {
            "method": "StoplossGuard",
            "lookback_period_candles": 72,
            "trade_limit": 4,
            "stop_duration_candles": 6,
            "only_per_pair": True,
        },
    ]

    # ==================== 标签参数 ====================
    # 1h周期：向前看6根K线 = 6小时
    label_lookahead = 6         # 向前看 6 根K线（6小时）
    label_threshold = 0.025     # 2.5% 的价格变化（增加交易机会）

    # ==================== 入场参数 ====================
    buy_max_atr_pct = 0.035     # 最大波动率 3.5%

    # ==================== 杠杆配置 ====================
    leverage_value = 3.0

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

        # 布林带宽度
        bb = ta.BBANDS(dataframe, timeperiod=period)
        dataframe[f"%-bb_width-period_{period}"] = (
            (bb["upperband"] - bb["lowerband"]) / bb["middleband"]
        )

        # NATR (标准化波动率)
        natr = ta.NATR(dataframe, timeperiod=period)
        dataframe[f"%-natr-period_{period}"] = natr / 100.0

        # MACD
        macd = ta.MACD(dataframe, fastperiod=period, slowperiod=period*2, signalperiod=int(period*0.7))
        dataframe[f"%-macd-period_{period}"] = macd["macd"] / dataframe["close"]
        dataframe[f"%-macdsignal-period_{period}"] = macd["macdsignal"] / dataframe["close"]

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

        # 价格位置（相对于高低点）
        high_20 = dataframe["high"].rolling(20).max()
        low_20 = dataframe["low"].rolling(20).min()
        dataframe["%-price_position"] = (dataframe["close"] - low_20) / (high_20 - low_20).replace(0, np.nan)

        # K线形态
        dataframe["%-candle_body"] = (dataframe["close"] - dataframe["open"]) / dataframe["open"]
        dataframe["%-upper_shadow"] = (dataframe["high"] - dataframe[["close", "open"]].max(axis=1)) / dataframe["open"]
        dataframe["%-lower_shadow"] = (dataframe[["close", "open"]].min(axis=1) - dataframe["low"]) / dataframe["open"]

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
        方向分类标签生成

        对于每个时间点，向前看 label_lookahead 根K线：
        - 计算最大涨幅 = (future_high_max - current_close) / current_close
        - 计算最大跌幅 = (current_close - future_low_min) / current_close
        - 如果最大涨幅 > threshold 且 > 最大跌幅：标签 = "long"
        - 如果最大跌幅 > threshold 且 > 最大涨幅：标签 = "short"
        - 否则：标签 = "neutral"
        """
        lookahead = self.label_lookahead
        threshold = self.label_threshold

        close_prices = dataframe["close"].values
        high_prices = dataframe["high"].values
        low_prices = dataframe["low"].values

        labels = []

        for i in range(len(dataframe)):
            if i + lookahead >= len(dataframe):
                labels.append("neutral")
                continue

            current_close = close_prices[i]

            # 计算未来 lookahead 根K线的最高价和最低价
            future_high_max = np.max(high_prices[i+1:i+1+lookahead])
            future_low_min = np.min(low_prices[i+1:i+1+lookahead])

            # 计算最大涨幅和最大跌幅
            max_up = (future_high_max - current_close) / current_close
            max_down = (current_close - future_low_min) / current_close

            # 判断标签
            if max_up > threshold and max_up > max_down:
                labels.append("long")
            elif max_down > threshold and max_down > max_up:
                labels.append("short")
            else:
                labels.append("neutral")

        dataframe["&s_direction"] = labels
        return dataframe

    # ==================== 指标计算 ====================
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # FreqAI 启动
        dataframe = self.freqai.start(dataframe, metadata, self)

        # ATR
        dataframe["atr"] = ta.ATR(dataframe, timeperiod=14)
        dataframe["atr_pct"] = dataframe["atr"] / dataframe["close"].replace(0, np.nan)

        return dataframe

    # ==================== 入场信号 ====================
    def populate_entry_trend(self, df: DataFrame, metadata: dict) -> DataFrame:
        df["enter_long"] = 0
        df["enter_short"] = 0

        # 获取分类器预测结果
        pred = df.get("&s_direction", "neutral")
        do_predict = df.get("do_predict", 1)
        atr_pct = df.get("atr_pct", 0)

        base_cond = (do_predict == 1) & (atr_pct < self.buy_max_atr_pct)

        # 做多：预测为 long
        long_cond = base_cond & (pred == "long")
        df.loc[long_cond, "enter_long"] = 1
        df.loc[long_cond, "enter_tag"] = "DIR_LONG"

        # 做空：预测为 short + 价格在 4h EMA_200 下方 (disabled since can_short=False)
        # short_cond = base_cond & (pred == "short") & (above_ema == False)
        # df.loc[short_cond, "enter_short"] = 1
        # df.loc[short_cond, "enter_tag"] = "DIR_SHORT"

        return df

    # ==================== 出场信号 ====================
    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["exit_long"] = 0
        dataframe["exit_short"] = 0
        return dataframe

    def custom_exit(self, pair: str, trade: Trade, current_time: datetime,
                    current_rate: float, current_profit: float, **kwargs) -> str | None:
        """基于预测方向变化的智能出场"""
        df, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if df.empty:
            return None

        last = df.iloc[-1]
        if int(last.get("do_predict", 0)) != 1:
            return None

        pred = last.get("&s_direction", "neutral")

        # 做多持仓，预测转为 short 且有盈利
        if not trade.is_short and current_profit > 0.02:
            if pred == "short":
                return "DIR_SMART_EXIT"

        # 做空持仓，预测转为 long 且有盈利
        if trade.is_short and current_profit > 0.02:
            if pred == "long":
                return "DIR_SMART_EXIT_SHORT"

        return None
