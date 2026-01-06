# pragma pylint: disable=missing-docstring, invalid-name, pointless-string-statement
# flake8: noqa: F401
# isort: skip_file
# --- 请勿删除这些导入 ---
import numpy as np
import pandas as pd
from datetime import datetime, timedelta, timezone
from pandas import DataFrame
from typing import Dict, Optional, Union, Tuple

from freqtrade.strategy import (
    IStrategy,
    Trade,
    Order,
    PairLocks,
    informative,  # @informative 装饰器
    # 超参优化（Hyperopt）参数
    BooleanParameter,
    CategoricalParameter,
    DecimalParameter,
    IntParameter,
    RealParameter,
    # timeframe 辅助函数
    timeframe_to_minutes,
    timeframe_to_next_date,
    timeframe_to_prev_date,
    # 策略辅助函数
    merge_informative_pair,
    stoploss_from_absolute,
    stoploss_from_open,
    AnnotationType,
)

# --------------------------------
# 在这里添加你需要的库导入
import talib.abstract as ta
from technical import qtpylib


class MyOkxSpotStrategy(IStrategy):
    """
    这是一个用于快速上手的策略模板。
    更多信息：https://www.freqtrade.io/en/latest/strategy-customization/

    策略逻辑（非常简化，适合入门理解）：
    - 开多：RSI 上穿 `buy_rsi`
    - 平多：RSI 上穿 `sell_rsi`

    你可以做：
    - 修改类名（运行时的 `-s/--strategy` 或配置里的 `strategy` 也要同步修改）
    - 增删指标、改造入场/出场条件
    - 引入你需要的第三方库

    你必须保留：
    - “请勿删除这些导入”区域内的必要导入（Freqtrade 运行可能会用到）
    - 方法：`populate_indicators`、`populate_entry_trend`、`populate_exit_trend`
    """

    # 策略接口版本：用于兼容新版策略接口。
    # 需要时请参考文档或示例策略以获取最新版本。
    INTERFACE_VERSION = 3

    # 策略默认 K 线周期。
    timeframe = "5m"

    # 是否允许做空？（现货一般为 False）
    can_short: bool = False

    # 最小 ROI（止盈）设置。
    # 如果配置文件中包含 `minimal_roi`，这里会被覆盖。
    minimal_roi = {
        "60": 0.01,
        "30": 0.02,
        "0": 0.04
    }

    # 止损设置。
    # 如果配置文件中包含 `stoploss`，这里会被覆盖。
    stoploss = -0.10

    # 追踪止损（Trailing Stop）
    trailing_stop = False
    # trailing_only_offset_is_reached = False
    # trailing_stop_positive = 0.01
    # trailing_stop_positive_offset = 0.0  # Disabled / not configured

    # 仅在新 K 线出现时运行 `populate_indicators()`。
    process_only_new_candles = True

    # 这些值也可以在配置文件中覆盖。
    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False

    # 策略开始产生有效信号前所需的最小 K 线数量（预热）。
    startup_candle_count: int = 30

    # 策略参数
    buy_rsi = IntParameter(10, 40, default=30, space="buy")
    sell_rsi = IntParameter(60, 90, default=70, space="sell")

    def informative_pairs(self):
        """
        定义额外的“信息对/周期”（informative）组合，用于从交易所缓存更多数据。
        这些组合本身不会直接交易，除非它们也在 whitelist（白名单）里。

        返回：形如 `(pair, interval)` 的元组列表。
        示例：`[("ETH/USDT", "5m"), ("BTC/USDT", "15m")]`
        """
        return []

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        为传入的 DataFrame 计算技术指标（TA）。

        性能提示：指标越多越耗内存/CPU；建议只计算策略实际用到的指标。

        :param dataframe: 交易所 K 线数据
        :param metadata: 额外信息，例如当前交易对
        :return: 包含所需指标列的 DataFrame
        """
        # 动量指标
        # ------------------------------------

        # RSI 指标
        dataframe["rsi"] = ta.RSI(dataframe)

        # 从订单簿获取最优买一/卖一（示例，默认关闭）
        # ------------------------------------
        """
        # 先检查 dataprovider 是否可用
        if self.dp:
            if self.dp.runmode.value in ("live", "dry_run"):
                ob = self.dp.orderbook(metadata["pair"], 1)
                dataframe["best_bid"] = ob["bids"][0][0]
                dataframe["best_ask"] = ob["asks"][0][0]
        """

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        基于技术指标，为 DataFrame 生成入场信号（开仓信号）。

        :param dataframe: DataFrame
        :param metadata: 额外信息，例如当前交易对
        :return: 添加了入场信号列的 DataFrame
        """
        dataframe.loc[
            (
                (qtpylib.crossed_above(dataframe["rsi"], self.buy_rsi.value))  # 信号：RSI 上穿 buy_rsi
                & (dataframe["volume"] > 0)  # 过滤：成交量不为 0
            ),
            "enter_long"] = 1
        # 如需做空请取消注释（仅在合约/杠杆模式下生效，详情请查看官方文档）
        """
        dataframe.loc[
            (
                (qtpylib.crossed_above(dataframe["rsi"], self.sell_rsi.value))  # 信号：RSI 上穿 sell_rsi
                (dataframe['volume'] > 0)  # 过滤：成交量不为 0
            ),
            'enter_short'] = 1
        """

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        基于技术指标，为 DataFrame 生成出场信号（平仓/卖出信号）。

        :param dataframe: DataFrame
        :param metadata: 额外信息，例如当前交易对
        :return: 添加了出场信号列的 DataFrame
        """
        dataframe.loc[
            (
                (qtpylib.crossed_above(dataframe["rsi"], self.sell_rsi.value))  # 信号：RSI 上穿 sell_rsi
                & (dataframe["volume"] > 0)  # 过滤：成交量不为 0
            ),
            "exit_long"] = 1
        # 如需做空请取消注释（仅在合约/杠杆模式下生效，详情请查看官方文档）
        """
        dataframe.loc[
            (
                (qtpylib.crossed_above(dataframe["rsi"], self.buy_rsi.value))  # 信号：RSI 上穿 buy_rsi
                (dataframe['volume'] > 0)  # 过滤：成交量不为 0
            ),
            'exit_short'] = 1
        """
        return dataframe
