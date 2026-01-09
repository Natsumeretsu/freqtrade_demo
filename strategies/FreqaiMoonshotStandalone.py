"""
FreqAI Moonshot 独立策略（组合模式）

所有参数集中在此文件管理，避免被其他文件覆盖。
"""
from __future__ import annotations

import logging
from datetime import datetime
from functools import reduce

import numpy as np
import talib.abstract as ta
from pandas import DataFrame

from freqtrade.persistence import Trade
from freqtrade.strategy import IStrategy, merge_informative_pair

logger = logging.getLogger(__name__)


class FreqaiMoonshotStandalone(IStrategy):
    """
    FreqAI + LightGBM 期货策略（独立版本）

    所有参数直接定义在此类中，不依赖 JSON 配置文件覆盖。
    """

    INTERFACE_VERSION = 3

    # ==================== 基础配置 ====================
    timeframe = "1h"
    process_only_new_candles = True
    startup_candle_count = 240
    can_short = False
    use_exit_signal = True

    # ==================== 止损配置 ====================
    # 稳定版：固定止损 + 固定止盈
    use_custom_stoploss = False
    stoploss = -0.15  # 固定 15% 止损
    trailing_stop = False

    # ROI 兜底
    minimal_roi = {"0": 0.10}

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

    # ==================== 入场参数 ====================
    buy_pred_threshold = 0.008  # 0.8% 阈值
    buy_max_atr_pct = 0.10      # 收紧波动率

    # ==================== 出场参数 ====================
    sell_smart_exit_threshold = 0.0

    # ==================== 宏观过滤 ====================
    btc_regime_pair = "BTC/USDT:USDT"
    btc_regime_timeframe = "4h"
    btc_regime_ema_period = 200
    btc_regime_bear_threshold_min = 0.01

    # ==================== 杠杆配置 ====================
    leverage_value = 3.0  # 3倍杠杆（最优配置）

    def leverage(self, pair: str, current_time: datetime, current_rate: float,
                 proposed_leverage: float, max_leverage: float,
                 entry_tag: str | None, side: str, **kwargs) -> float:
        return float(min(self.leverage_value, max_leverage))

    def informative_pairs(self):
        return [(self.btc_regime_pair, self.btc_regime_timeframe)]

    # ==================== FreqAI 特征工程 ====================
    def feature_engineering_expand_all(self, dataframe: DataFrame, period: int,
                                       metadata: dict, **kwargs) -> DataFrame:
        dataframe[f"%-rsi-period_{period}"] = ta.RSI(dataframe, timeperiod=period)
        dataframe[f"%-roc-period_{period}"] = ta.ROC(dataframe, timeperiod=period) / 100.0

        bb = ta.BBANDS(dataframe, timeperiod=period)
        dataframe[f"%-bb_width-period_{period}"] = (
            (bb["upperband"] - bb["lowerband"]) / bb["middleband"]
        )

        natr = ta.NATR(dataframe, timeperiod=period)
        dataframe[f"%-natr-period_{period}"] = natr / 100.0

        return dataframe.replace([np.inf, -np.inf], np.nan)

    def feature_engineering_expand_basic(self, dataframe: DataFrame,
                                         metadata: dict, **kwargs) -> DataFrame:
        dataframe["%-pct_change"] = dataframe["close"].pct_change()
        vol_mean = dataframe["volume"].rolling(24).mean()
        dataframe["%-volume_ratio"] = dataframe["volume"] / vol_mean.replace(0, np.nan)
        return dataframe.replace([np.inf, -np.inf], np.nan)

    def feature_engineering_standard(self, dataframe: DataFrame,
                                     metadata: dict, **kwargs) -> DataFrame:
        dataframe["%-day_of_week"] = dataframe["date"].dt.dayofweek
        dataframe["%-hour_of_day"] = dataframe["date"].dt.hour
        return dataframe

    def set_freqai_targets(self, dataframe: DataFrame,
                           metadata: dict, **kwargs) -> DataFrame:
        label_period = int(self.freqai_info["feature_parameters"]["label_period_candles"])
        label_period = max(1, label_period)

        dataframe["&s_close_mean"] = (
            dataframe["close"].shift(-label_period).rolling(label_period).mean()
            / dataframe["close"] - 1
        )
        return dataframe

    # ==================== 指标计算 ====================
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # FreqAI 启动
        dataframe = self.freqai.start(dataframe, metadata, self)

        # BTC 宏观过滤
        dataframe = self._merge_btc_regime(dataframe)

        # ATR
        dataframe["atr"] = ta.ATR(dataframe, timeperiod=14)
        dataframe["atr_pct"] = dataframe["atr"] / dataframe["close"].replace(0, np.nan)

        return dataframe

    def _merge_btc_regime(self, dataframe: DataFrame) -> DataFrame:
        try:
            inf = self.dp.get_pair_dataframe(self.btc_regime_pair, self.btc_regime_timeframe)
            if inf.empty:
                dataframe["btc_bull"] = True
                return dataframe

            inf["btc_ema200"] = ta.EMA(inf, timeperiod=self.btc_regime_ema_period)
            inf["btc_bull"] = inf["close"] > inf["btc_ema200"]
            inf = inf[["date", "btc_bull"]].copy()

            dataframe = merge_informative_pair(
                dataframe, inf, self.timeframe, self.btc_regime_timeframe, ffill=True
            )
            col = f"btc_bull_{self.btc_regime_timeframe}"
            dataframe["btc_bull"] = dataframe.get(col, True)

        except Exception as e:
            logger.warning(f"BTC regime error: {e}")
            dataframe["btc_bull"] = True

        return dataframe

    # ==================== 入场信号 ====================
    def populate_entry_trend(self, df: DataFrame, metadata: dict) -> DataFrame:
        df["enter_long"] = 0

        pred = df.get("&s_close_mean", 0)
        do_predict = df.get("do_predict", 1)
        atr_pct = df.get("atr_pct", 0)
        btc_bull = df.get("btc_bull", True).astype(bool)

        base_thr = self.buy_pred_threshold
        bear_thr = max(base_thr * 2.5, self.btc_regime_bear_threshold_min)

        bull_cond = btc_bull & (pred > base_thr)
        bear_cond = (~btc_bull) & (pred > bear_thr)

        entry_cond = (do_predict == 1) & (atr_pct < self.buy_max_atr_pct) & (bull_cond | bear_cond)

        df.loc[entry_cond, "enter_long"] = 1
        df.loc[entry_cond & btc_bull, "enter_tag"] = "FREQAI_LONG"
        df.loc[entry_cond & (~btc_bull), "enter_tag"] = "FREQAI_LONG_SNIPER"

        return df

    # ==================== 出场信号 ====================
    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["exit_long"] = 0
        return dataframe

    def custom_exit(self, pair: str, trade: Trade, current_time: datetime,
                    current_rate: float, current_profit: float, **kwargs) -> str | None:
        if trade.is_short:
            return None

        df, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if df.empty:
            return None

        last = df.iloc[-1]
        if int(last.get("do_predict", 0)) != 1:
            return None

        try:
            pred = float(last.get("&s_close_mean", 0))
        except Exception:
            return None

        if current_profit > 0 and pred <= self.sell_smart_exit_threshold:
            return "FREQAI_SMART_EXIT"

        return None
