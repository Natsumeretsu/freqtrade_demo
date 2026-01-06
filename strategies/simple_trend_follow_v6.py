import pandas as pd
import talib.abstract as ta
from pandas import DataFrame
from technical import qtpylib

from freqtrade.enums import RunMode
from freqtrade.strategy import IStrategy, IntParameter


class SimpleTrendFollowV6(IStrategy):
    """
    简易趋势跟踪策略（工程化版本）

    核心思路：
    - 只做多：短期 EMA 上穿长期 EMA 作为入场信号
    - 大趋势过滤：收盘价必须在 EMA200 之上
    - 趋势强度过滤：ADX 必须超过阈值
    - 出场：均线死叉作为保底退出信号；主要依赖追踪止损让利润奔跑

    性能策略：
    - Hyperopt（且 analyze_per_epoch=False）时：在 populate_indicators 里预计算全部候选 EMA 列，提升超参速度
    - 其他模式（含 Hyperopt+analyze_per_epoch=True）时：仅计算当前参数对应的 EMA 列，节省内存/延迟
    """

    INTERFACE_VERSION = 3

    # --- 策略基础配置 ---
    timeframe = "4h"
    startup_candle_count = 240

    # 纯趋势：几乎不靠 ROI 出场
    minimal_roi = {"0": 100}

    # 硬止损（黑天鹅兜底）
    stoploss = -0.10

    # 追踪止损：利润>6% 才开始追，追踪距离 5%
    trailing_stop = True
    trailing_stop_positive_offset = 0.06
    trailing_stop_positive = 0.05
    trailing_only_offset_is_reached = True

    use_exit_signal = True

    # --- Hyperopt 参数（仅 buy 空间）---
    buy_ema_short_len = IntParameter(10, 45, default=20, space="buy", optimize=True)
    buy_ema_long_len = IntParameter(50, 200, default=200, space="buy", optimize=True)
    buy_adx = IntParameter(15, 50, default=25, space="buy", optimize=True)

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        runmode = self.dp.runmode if self.dp else RunMode.OTHER
        analyze_per_epoch = bool(self.config.get("analyze_per_epoch", False)) if self.config else False

        new_cols = {}
        if runmode == RunMode.HYPEROPT and not analyze_per_epoch:
            # Hyperopt 单次计算指标：预生成所有候选 EMA 列（空间换时间）
            for val in self.buy_ema_short_len.range:
                new_cols[f"ema_short_{val}"] = ta.EMA(dataframe, timeperiod=val)
            for val in self.buy_ema_long_len.range:
                new_cols[f"ema_long_{val}"] = ta.EMA(dataframe, timeperiod=val)
        else:
            # 非 Hyperopt/按 epoch 重新分析：仅计算当前参数对应的 EMA 列（时间换空间）
            short_val = self.buy_ema_short_len.value
            long_val = self.buy_ema_long_len.value
            new_cols[f"ema_short_{short_val}"] = ta.EMA(dataframe, timeperiod=short_val)
            new_cols[f"ema_long_{long_val}"] = ta.EMA(dataframe, timeperiod=long_val)

        # 固定指标（不参与优化）
        new_cols["adx"] = ta.ADX(dataframe)
        new_cols["ema200_fixed"] = ta.EMA(dataframe, timeperiod=200)

        # 一次性合并指标列，避免逐列插入导致 DataFrame 高度碎片化（PerformanceWarning）。
        # 说明：为避免同名重复列，若上游已存在同名列，这里先 drop 再合并以覆盖旧值。
        new_df = pd.DataFrame(new_cols, index=dataframe.index)
        existing_cols = [c for c in new_df.columns if c in dataframe.columns]
        if existing_cols:
            dataframe = dataframe.drop(columns=existing_cols)
        dataframe = pd.concat([dataframe, new_df], axis=1)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        short_val = self.buy_ema_short_len.value
        long_val = self.buy_ema_long_len.value
        adx_val = self.buy_adx.value

        # 保险：避免短周期 >= 长周期导致信号失真
        if short_val >= long_val:
            return dataframe

        ema_short = dataframe[f"ema_short_{short_val}"]
        ema_long = dataframe[f"ema_long_{long_val}"]

        dataframe.loc[
            (
                qtpylib.crossed_above(ema_short, ema_long)
                & (dataframe["close"] > dataframe["ema200_fixed"])
                & (dataframe["adx"] > adx_val)
                & (dataframe["volume"] > 0)
            ),
            "enter_long",
        ] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        short_val = self.buy_ema_short_len.value
        long_val = self.buy_ema_long_len.value

        ema_short = dataframe[f"ema_short_{short_val}"]
        ema_long = dataframe[f"ema_long_{long_val}"]

        dataframe.loc[
            (qtpylib.crossed_below(ema_short, ema_long) & (dataframe["volume"] > 0)),
            "exit_long",
        ] = 1

        return dataframe
