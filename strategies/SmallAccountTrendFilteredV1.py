from __future__ import annotations

from functools import reduce

import numpy as np
import talib.abstract as ta
from pandas import DataFrame
from technical import qtpylib

from freqtrade.strategy import IStrategy, IntParameter


class SmallAccountTrendFilteredV1(IStrategy):
    """
    小资金（10USDT 起）现货趋势策略 v1（波动率/趋势过滤版）

    设计目标：
    - 只做多（小资金优先降低复杂度与爆仓风险）
    - 用“趋势 + 波动率”双过滤，减少震荡期的频繁止损/手续费磨损
    - 用更积极的退出（ROI + 更早触发的追踪止损）把利润落袋，提升稳定性

    核心思路（4h）：
    - 入场：EMA 短期上穿 EMA 长期 + ADX 过滤 + ATR% 过滤 + EMA 长期上行
    - 出场：EMA 死叉（保底）+ ROI（落袋）+ 追踪止损（让利润奔跑但不回吐太多）

    重要说明：
    - 不承诺任何实盘收益；这是一个“可验证、可迭代”的基线策略。
    - 若数据从 2023 开始，任何超长周期指标都会存在“前置历史不足”的冷启动期，请用多窗口回测评估稳定性。
    """

    INTERFACE_VERSION = 3

    timeframe = "4h"
    startup_candle_count = 240

    # 趋势策略：尽量不靠 ROI “到点就走”，主要依赖追踪止损让利润奔跑
    minimal_roi = {"0": 100}

    # 黑天鹅兜底
    stoploss = -0.10

    # 追踪止损：利润 6% 开始追踪，回撤 5% 出场（更贴近“趋势跟随”的持有方式）
    trailing_stop = True
    trailing_stop_positive_offset = 0.06
    trailing_stop_positive = 0.05
    trailing_only_offset_is_reached = True

    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False

    # --- 参数（保守范围，避免过拟合）---
    buy_ema_short_len = IntParameter(10, 30, default=20, space="buy", optimize=True)
    buy_ema_long_len = IntParameter(50, 180, default=120, space="buy", optimize=True)
    buy_adx = IntParameter(12, 35, default=20, space="buy", optimize=True)

    # EMA 长期上行过滤：对比 N 根 K 线前的值
    buy_ema_slope_lookback = IntParameter(2, 12, default=6, space="buy", optimize=True)

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        short_len = int(self.buy_ema_short_len.value)
        long_len = int(self.buy_ema_long_len.value)

        df = dataframe.copy()
        df[f"ema_short_{short_len}"] = ta.EMA(df, timeperiod=short_len)
        df[f"ema_long_{long_len}"] = ta.EMA(df, timeperiod=long_len)
        df["adx"] = ta.ADX(df, timeperiod=14)
        df["atr"] = ta.ATR(df, timeperiod=14)
        df["atr_pct"] = df["atr"] / df["close"]

        return df.replace([np.inf, -np.inf], np.nan)

    def populate_entry_trend(self, df: DataFrame, metadata: dict) -> DataFrame:
        df["enter_long"] = 0

        short_len = int(self.buy_ema_short_len.value)
        long_len = int(self.buy_ema_long_len.value)
        adx_val = int(self.buy_adx.value)
        slope_n = int(self.buy_ema_slope_lookback.value)

        if short_len >= long_len:
            return df

        ema_s = df[f"ema_short_{short_len}"]
        ema_l = df[f"ema_long_{long_len}"]

        # 趋势过滤：EMA 长期必须上行（避免震荡市频繁“假突破”）
        ema_l_up = ema_l > ema_l.shift(slope_n)

        # 波动率过滤：必须有足够波动覆盖手续费与噪声（经验阈值：0.4%）
        vol_ok = df["atr_pct"] > 0.004

        conds = [
            df["volume"] > 0,
            qtpylib.crossed_above(ema_s, ema_l),
            (df["adx"] > adx_val),
            ema_l_up.fillna(False),
            vol_ok.fillna(False),
        ]

        df.loc[reduce(lambda x, y: x & y, conds), "enter_long"] = 1
        return df

    def populate_exit_trend(self, df: DataFrame, metadata: dict) -> DataFrame:
        df["exit_long"] = 0

        short_len = int(self.buy_ema_short_len.value)
        long_len = int(self.buy_ema_long_len.value)
        if short_len >= long_len:
            return df

        ema_s = df.get(f"ema_short_{short_len}")
        ema_l = df.get(f"ema_long_{long_len}")
        if ema_s is None or ema_l is None:
            return df

        # 保底退出：趋势破坏（死叉）
        cross_down = qtpylib.crossed_below(ema_s, ema_l)

        df.loc[((df["volume"] > 0) & cross_down), "exit_long"] = 1
        return df
