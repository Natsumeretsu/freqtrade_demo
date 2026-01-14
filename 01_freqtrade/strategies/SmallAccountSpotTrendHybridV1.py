from __future__ import annotations

from functools import reduce

import numpy as np
import talib.abstract as ta
from pandas import DataFrame
from technical import qtpylib

from freqtrade.strategy import IStrategy, IntParameter, merge_informative_pair


class SmallAccountSpotTrendHybridV1(IStrategy):
    """
    小资金现货趋势策略 v1（4h 入场 + 1d 宏观过滤）

    关键改进点（相对“纯 4h EMA 交叉”）：
    - 用 1d SMA200 做宏观过滤：只在大趋势向上时开仓，减少震荡/熊市的频繁亏损
    - 4h 仍用于捕捉更快的入场点（比纯日线更灵敏）

    这类策略的核心目标不是“每天都有交易”，而是：
    - 在小资金阶段优先保证可复现的正期望
    - 把手续费/噪声交易降到最低
    """

    INTERFACE_VERSION = 3

    timeframe = "4h"
    informative_timeframe = "1d"

    startup_candle_count = 240

    minimal_roi = {"0": 100}
    stoploss = -0.12

    trailing_stop = True
    trailing_stop_positive_offset = 0.06
    trailing_stop_positive = 0.05
    trailing_only_offset_is_reached = True

    use_exit_signal = True

    # --- 可调参数（保守范围，避免过拟合）---
    buy_ema_short_len = IntParameter(10, 45, default=20, space="buy", optimize=True)
    buy_ema_long_len = IntParameter(50, 250, default=200, space="buy", optimize=True)
    buy_adx = IntParameter(15, 50, default=25, space="buy", optimize=True)

    @property
    def _macro_col(self) -> str:
        return f"macro_bull_{self.informative_timeframe}"

    def informative_pairs(self):
        dp = getattr(self, "dp", None)
        if dp is None:
            return []
        return [(pair, self.informative_timeframe) for pair in dp.current_whitelist()]

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        df = dataframe.copy()

        short_val = int(self.buy_ema_short_len.value)
        long_val = int(self.buy_ema_long_len.value)

        df[f"ema_short_{short_val}"] = ta.EMA(df, timeperiod=short_val)
        df[f"ema_long_{long_val}"] = ta.EMA(df, timeperiod=long_val)

        df["adx"] = ta.ADX(df, timeperiod=14)
        df["ema200_4h"] = ta.EMA(df, timeperiod=200)

        # --- 1d 宏观过滤（SMA200）---
        dp = getattr(self, "dp", None)
        if dp is not None:
            try:
                inf = dp.get_pair_dataframe(pair=metadata["pair"], timeframe=self.informative_timeframe)
                if inf is not None and not inf.empty:
                    inf = inf.copy()
                    inf["sma200"] = ta.SMA(inf, timeperiod=200)
                    inf["macro_bull"] = (inf["close"] > inf["sma200"]).astype(int)
                    inf_small = inf[["date", "macro_bull"]].copy()
                    df = merge_informative_pair(df, inf_small, self.timeframe, self.informative_timeframe, ffill=True)
            except Exception:
                pass

        return df.replace([np.inf, -np.inf], np.nan)

    def populate_entry_trend(self, df: DataFrame, metadata: dict) -> DataFrame:
        df["enter_long"] = 0

        short_val = int(self.buy_ema_short_len.value)
        long_val = int(self.buy_ema_long_len.value)
        adx_val = int(self.buy_adx.value)

        if short_val >= long_val:
            return df

        ema_short = df[f"ema_short_{short_val}"]
        ema_long = df[f"ema_long_{long_val}"]

        macro_col = self._macro_col
        if macro_col not in df.columns:
            return df

        conds = [
            df["volume"] > 0,
            (df[macro_col] == 1).fillna(False),
            df["close"] > df["ema200_4h"],
            df["adx"] > adx_val,
            qtpylib.crossed_above(ema_short, ema_long),
        ]

        df.loc[reduce(lambda x, y: x & y, conds), "enter_long"] = 1
        return df

    def populate_exit_trend(self, df: DataFrame, metadata: dict) -> DataFrame:
        df["exit_long"] = 0

        short_val = int(self.buy_ema_short_len.value)
        long_val = int(self.buy_ema_long_len.value)

        ema_short = df.get(f"ema_short_{short_val}")
        ema_long = df.get(f"ema_long_{long_val}")

        macro_col = self._macro_col
        macro_turns_bear = (df[macro_col] == 0).fillna(False) if macro_col in df.columns else False

        # 出场：均线死叉 或 宏观转熊
        if ema_short is not None and ema_long is not None:
            cross_down = qtpylib.crossed_below(ema_short, ema_long)
        else:
            cross_down = False

        df.loc[((cross_down | macro_turns_bear) & (df["volume"] > 0)), "exit_long"] = 1
        return df
