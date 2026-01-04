# pragma pylint: disable=missing-docstring, invalid-name, pointless-string-statement
# flake8: noqa: F401
# isort: skip_file
# --- 请勿删除这些导入 ---
import numpy as np
import pandas as pd
from datetime import datetime, timedelta, timezone
from pandas import DataFrame
from typing import Optional, Union

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
)

# --------------------------------
# 在这里添加你需要的库导入
import talib.abstract as ta
from technical import qtpylib


# 这是一个示例策略，你可以自由修改。
class SampleStrategy(IStrategy):
    """
    这是一个用于参考与学习的示例策略。
    更多信息：https://www.freqtrade.io/en/latest/strategy-customization/

    你可以做：
    - 修改类名（运行时的 `-s/--strategy` 或配置里的 `strategy` 也要同步修改）
    - 增删指标、改造入场/出场条件
    - 引入你需要的第三方库

    你必须保留：
    - “请勿删除这些导入”区域内的必要导入（Freqtrade 运行可能会用到）
    - 方法：`populate_indicators`、`populate_entry_trend`、`populate_exit_trend`

    建议保留（便于快速跑通与对照学习）：
    - `timeframe`、`minimal_roi`、`stoploss`、`trailing_*`
    """

    # 策略接口版本：用于兼容新版策略接口。
    # 需要时请参考文档或示例策略以获取最新版本。
    INTERFACE_VERSION = 3

    # 是否允许做空？（现货一般为 False）
    can_short: bool = False

    # 最小 ROI（止盈）设置。
    # 如果配置文件中包含 `minimal_roi`，这里会被覆盖。
    minimal_roi = {
        # "120": 0.0,  # 持仓 120 分钟后以保本退出
        "60": 0.01,
        "30": 0.02,
        "0": 0.04,
    }

    # 止损设置。
    # 如果配置文件中包含 `stoploss`，这里会被覆盖。
    stoploss = -0.10

    # 追踪止损（Trailing Stop）
    trailing_stop = False
    # trailing_only_offset_is_reached = False
    # trailing_stop_positive = 0.01
    # trailing_stop_positive_offset = 0.0  # Disabled / not configured

    # 策略默认 K 线周期。
    timeframe = "5m"

    # 仅在新 K 线出现时运行 `populate_indicators()`。
    process_only_new_candles = True

    # 这些值也可以在配置文件中覆盖。
    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False

    # 可用于超参优化（hyperopt）的参数
    buy_rsi = IntParameter(low=1, high=50, default=30, space="buy", optimize=True, load=True)
    sell_rsi = IntParameter(low=50, high=100, default=70, space="sell", optimize=True, load=True)
    short_rsi = IntParameter(low=51, high=100, default=70, space="sell", optimize=True, load=True)
    exit_short_rsi = IntParameter(
        low=1, high=50, default=30, space="exit", optimize=True, load=True
    )

    # 策略开始产生有效信号前所需的最小 K 线数量（预热）。
    startup_candle_count: int = 200

    # 可选：订单类型映射
    order_types = {
        "entry": "limit",
        "exit": "limit",
        "stoploss": "market",
        "stoploss_on_exchange": False,
    }

    # 可选：订单有效期（Time in Force）
    order_time_in_force = {"entry": "GTC", "exit": "GTC"}

    plot_config = {
        "main_plot": {
            "tema": {},
            "sar": {"color": "white"},
        },
        "subplots": {
            "MACD": {
                "macd": {"color": "blue"},
                "macdsignal": {"color": "orange"},
            },
            "RSI": {
                "rsi": {"color": "red"},
            },
        },
    }

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

        # 动量指标（Momentum Indicators）
        # ------------------------------------

        # ADX（平均趋向指数）
        dataframe["adx"] = ta.ADX(dataframe)

        # # 正向方向指标 / 方向运动（Plus Directional Movement）
        # dataframe['plus_dm'] = ta.PLUS_DM(dataframe)
        # dataframe['plus_di'] = ta.PLUS_DI(dataframe)

        # # 负向方向指标 / 方向运动（Minus Directional Movement）
        # dataframe['minus_dm'] = ta.MINUS_DM(dataframe)
        # dataframe['minus_di'] = ta.MINUS_DI(dataframe)

        # # Aroon / Aroon 振荡器
        # aroon = ta.AROON(dataframe)
        # dataframe['aroonup'] = aroon['aroonup']
        # dataframe['aroondown'] = aroon['aroondown']
        # dataframe['aroonosc'] = ta.AROONOSC(dataframe)

        # # AO（Awesome Oscillator，动量振荡器）
        # dataframe['ao'] = qtpylib.awesome_oscillator(dataframe)

        # # KC（Keltner Channel，肯特纳通道）
        # keltner = qtpylib.keltner_channel(dataframe)
        # dataframe["kc_upperband"] = keltner["upper"]
        # dataframe["kc_lowerband"] = keltner["lower"]
        # dataframe["kc_middleband"] = keltner["mid"]
        # dataframe["kc_percent"] = (
        #     (dataframe["close"] - dataframe["kc_lowerband"]) /
        #     (dataframe["kc_upperband"] - dataframe["kc_lowerband"])
        # )
        # dataframe["kc_width"] = (
        #     (dataframe["kc_upperband"] - dataframe["kc_lowerband"]) / dataframe["kc_middleband"]
        # )

        # # UO（Ultimate Oscillator，终极振荡器）
        # dataframe['uo'] = ta.ULTOSC(dataframe)

        # # CCI（商品通道指数）：常见阈值 [超卖:-100, 超买:100]
        # dataframe['cci'] = ta.CCI(dataframe)

        # RSI 指标
        dataframe["rsi"] = ta.RSI(dataframe)

        # # RSI 的逆费舍尔变换：取值 [-1.0, 1.0]（https://goo.gl/2JGGoy）
        # rsi = 0.1 * (dataframe['rsi'] - 50)
        # dataframe['fisher_rsi'] = (np.exp(2 * rsi) - 1) / (np.exp(2 * rsi) + 1)

        # # 归一化后的 RSI 逆费舍尔变换：取值 [0.0, 100.0]（https://goo.gl/2JGGoy）
        # dataframe['fisher_rsi_norma'] = 50 * (dataframe['fisher_rsi'] + 1)

        # # 随机指标（Stochastic）慢速版本
        # stoch = ta.STOCH(dataframe)
        # dataframe['slowd'] = stoch['slowd']
        # dataframe['slowk'] = stoch['slowk']

        # 随机指标（Stochastic）快速版本
        stoch_fast = ta.STOCHF(dataframe)
        dataframe["fastd"] = stoch_fast["fastd"]
        dataframe["fastk"] = stoch_fast["fastk"]

        # # 随机 RSI（Stochastic RSI）
        # 使用前请先阅读：https://github.com/freqtrade/freqtrade/issues/2961
        # STOCHRSI 与 TradingView 的实现不完全一致，可能导致结果与你预期不一致。
        # stoch_rsi = ta.STOCHRSI(dataframe)
        # dataframe['fastd_rsi'] = stoch_rsi['fastd']
        # dataframe['fastk_rsi'] = stoch_rsi['fastk']

        # MACD（指数平滑异同移动平均线）
        macd = ta.MACD(dataframe)
        dataframe["macd"] = macd["macd"]
        dataframe["macdsignal"] = macd["macdsignal"]
        dataframe["macdhist"] = macd["macdhist"]

        # MFI（资金流量指标）
        dataframe["mfi"] = ta.MFI(dataframe)

        # # ROC
        # dataframe['roc'] = ta.ROC(dataframe)

        # 叠加指标（Overlap Studies）
        # ------------------------------------

        # 布林带（Bollinger Bands）
        bollinger = qtpylib.bollinger_bands(qtpylib.typical_price(dataframe), window=20, stds=2)
        dataframe["bb_lowerband"] = bollinger["lower"]
        dataframe["bb_middleband"] = bollinger["mid"]
        dataframe["bb_upperband"] = bollinger["upper"]
        dataframe["bb_percent"] = (dataframe["close"] - dataframe["bb_lowerband"]) / (
            dataframe["bb_upperband"] - dataframe["bb_lowerband"]
        )
        dataframe["bb_width"] = (dataframe["bb_upperband"] - dataframe["bb_lowerband"]) / dataframe[
            "bb_middleband"
        ]

        # 加权布林带（使用 EMA 而非 SMA）
        # weighted_bollinger = qtpylib.weighted_bollinger_bands(
        #     qtpylib.typical_price(dataframe), window=20, stds=2
        # )
        # dataframe["wbb_upperband"] = weighted_bollinger["upper"]
        # dataframe["wbb_lowerband"] = weighted_bollinger["lower"]
        # dataframe["wbb_middleband"] = weighted_bollinger["mid"]
        # dataframe["wbb_percent"] = (
        #     (dataframe["close"] - dataframe["wbb_lowerband"]) /
        #     (dataframe["wbb_upperband"] - dataframe["wbb_lowerband"])
        # )
        # dataframe["wbb_width"] = (
        #     (dataframe["wbb_upperband"] - dataframe["wbb_lowerband"]) /
        #     dataframe["wbb_middleband"]
        # )

        # # EMA（指数移动平均）
        # dataframe['ema3'] = ta.EMA(dataframe, timeperiod=3)
        # dataframe['ema5'] = ta.EMA(dataframe, timeperiod=5)
        # dataframe['ema10'] = ta.EMA(dataframe, timeperiod=10)
        # dataframe['ema21'] = ta.EMA(dataframe, timeperiod=21)
        # dataframe['ema50'] = ta.EMA(dataframe, timeperiod=50)
        # dataframe['ema100'] = ta.EMA(dataframe, timeperiod=100)

        # # SMA（简单移动平均）
        # dataframe['sma3'] = ta.SMA(dataframe, timeperiod=3)
        # dataframe['sma5'] = ta.SMA(dataframe, timeperiod=5)
        # dataframe['sma10'] = ta.SMA(dataframe, timeperiod=10)
        # dataframe['sma21'] = ta.SMA(dataframe, timeperiod=21)
        # dataframe['sma50'] = ta.SMA(dataframe, timeperiod=50)
        # dataframe['sma100'] = ta.SMA(dataframe, timeperiod=100)

        # 抛物线 SAR（Parabolic SAR）
        dataframe["sar"] = ta.SAR(dataframe)

        # TEMA（三重指数移动平均）
        dataframe["tema"] = ta.TEMA(dataframe, timeperiod=9)

        # 周期指标（Cycle Indicator）
        # ------------------------------------
        # 希尔伯特变换指标：SineWave
        hilbert = ta.HT_SINE(dataframe)
        dataframe["htsine"] = hilbert["sine"]
        dataframe["htleadsine"] = hilbert["leadsine"]

        # K 线形态识别：看涨形态（Bullish patterns）
        # ------------------------------------
        # # 锤子线（Hammer）：取值 [0, 100]
        # dataframe['CDLHAMMER'] = ta.CDLHAMMER(dataframe)
        # # 倒锤子线（Inverted Hammer）：取值 [0, 100]
        # dataframe['CDLINVERTEDHAMMER'] = ta.CDLINVERTEDHAMMER(dataframe)
        # # 蜻蜓十字（Dragonfly Doji）：取值 [0, 100]
        # dataframe['CDLDRAGONFLYDOJI'] = ta.CDLDRAGONFLYDOJI(dataframe)
        # # 刺透形态（Piercing Line）：取值 [0, 100]
        # dataframe['CDLPIERCING'] = ta.CDLPIERCING(dataframe) # 取值 [0, 100]
        # # 启明星（Morning Star）：取值 [0, 100]
        # dataframe['CDLMORNINGSTAR'] = ta.CDLMORNINGSTAR(dataframe) # 取值 [0, 100]
        # # 三白兵（Three White Soldiers）：取值 [0, 100]
        # dataframe['CDL3WHITESOLDIERS'] = ta.CDL3WHITESOLDIERS(dataframe) # 取值 [0, 100]

        # K 线形态识别：看跌形态（Bearish patterns）
        # ------------------------------------
        # # 上吊线（Hanging Man）：取值 [0, 100]
        # dataframe['CDLHANGINGMAN'] = ta.CDLHANGINGMAN(dataframe)
        # # 流星线（Shooting Star）：取值 [0, 100]
        # dataframe['CDLSHOOTINGSTAR'] = ta.CDLSHOOTINGSTAR(dataframe)
        # # 墓碑十字（Gravestone Doji）：取值 [0, 100]
        # dataframe['CDLGRAVESTONEDOJI'] = ta.CDLGRAVESTONEDOJI(dataframe)
        # # 乌云盖顶（Dark Cloud Cover）：取值 [0, 100]
        # dataframe['CDLDARKCLOUDCOVER'] = ta.CDLDARKCLOUDCOVER(dataframe)
        # # 黄昏十字星（Evening Doji Star）：取值 [0, 100]
        # dataframe['CDLEVENINGDOJISTAR'] = ta.CDLEVENINGDOJISTAR(dataframe)
        # # 黄昏星（Evening Star）：取值 [0, 100]
        # dataframe['CDLEVENINGSTAR'] = ta.CDLEVENINGSTAR(dataframe)

        # K 线形态识别：多空通用形态（Bullish/Bearish patterns）
        # ------------------------------------
        # # 三线打击（Three Line Strike）：取值 [0, -100, 100]
        # dataframe['CDL3LINESTRIKE'] = ta.CDL3LINESTRIKE(dataframe)
        # # 纺锤线（Spinning Top）：取值 [0, -100, 100]
        # dataframe['CDLSPINNINGTOP'] = ta.CDLSPINNINGTOP(dataframe) # 取值 [0, -100, 100]
        # # 吞没形态（Engulfing）：取值 [0, -100, 100]
        # dataframe['CDLENGULFING'] = ta.CDLENGULFING(dataframe) # 取值 [0, -100, 100]
        # # 孕线形态（Harami）：取值 [0, -100, 100]
        # dataframe['CDLHARAMI'] = ta.CDLHARAMI(dataframe) # 取值 [0, -100, 100]
        # # 三外升/三外降（Three Outside Up/Down）：取值 [0, -100, 100]
        # dataframe['CDL3OUTSIDE'] = ta.CDL3OUTSIDE(dataframe) # 取值 [0, -100, 100]
        # # 三内升/三内降（Three Inside Up/Down）：取值 [0, -100, 100]
        # dataframe['CDL3INSIDE'] = ta.CDL3INSIDE(dataframe) # 取值 [0, -100, 100]

        # # K 线类型（Chart type）
        # # ------------------------------------
        # # 平均 K 线（Heikin Ashi）
        # heikinashi = qtpylib.heikinashi(dataframe)
        # dataframe['ha_open'] = heikinashi['open']
        # dataframe['ha_close'] = heikinashi['close']
        # dataframe['ha_high'] = heikinashi['high']
        # dataframe['ha_low'] = heikinashi['low']

        # 从订单簿获取最优买一/卖一（示例，默认关闭）
        # ------------------------------------
        """
        # 先检查 dataprovider 是否可用
        if self.dp:
            if self.dp.runmode.value in ('live', 'dry_run'):
                ob = self.dp.orderbook(metadata['pair'], 1)
                dataframe['best_bid'] = ob['bids'][0][0]
                dataframe['best_ask'] = ob['asks'][0][0]
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
                # 信号：RSI 上穿 buy_rsi
                (qtpylib.crossed_above(dataframe["rsi"], self.buy_rsi.value))
                & (dataframe["tema"] <= dataframe["bb_middleband"])  # 过滤：TEMA 在布林带中轨下方
                & (dataframe["tema"] > dataframe["tema"].shift(1))  # 过滤：TEMA 处于上升趋势
                & (dataframe["volume"] > 0)  # 过滤：成交量不为 0
            ),
            "enter_long",
        ] = 1

        dataframe.loc[
            (
                # 信号：RSI 上穿 short_rsi
                (qtpylib.crossed_above(dataframe["rsi"], self.short_rsi.value))
                & (dataframe["tema"] > dataframe["bb_middleband"])  # 过滤：TEMA 在布林带中轨上方
                & (dataframe["tema"] < dataframe["tema"].shift(1))  # 过滤：TEMA 处于下降趋势
                & (dataframe["volume"] > 0)  # 过滤：成交量不为 0
            ),
            "enter_short",
        ] = 1

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
                # 信号：RSI 上穿 sell_rsi
                (qtpylib.crossed_above(dataframe["rsi"], self.sell_rsi.value))
                & (dataframe["tema"] > dataframe["bb_middleband"])  # 过滤：TEMA 在布林带中轨上方
                & (dataframe["tema"] < dataframe["tema"].shift(1))  # 过滤：TEMA 处于下降趋势
                & (dataframe["volume"] > 0)  # 过滤：成交量不为 0
            ),
            "exit_long",
        ] = 1

        dataframe.loc[
            (
                # 信号：RSI 上穿 exit_short_rsi
                (qtpylib.crossed_above(dataframe["rsi"], self.exit_short_rsi.value))
                &
                # 过滤：TEMA 在布林带中轨下方
                (dataframe["tema"] <= dataframe["bb_middleband"])
                & (dataframe["tema"] > dataframe["tema"].shift(1))  # 过滤：TEMA 处于上升趋势
                & (dataframe["volume"] > 0)  # 过滤：成交量不为 0
            ),
            "exit_short",
        ] = 1

        return dataframe
