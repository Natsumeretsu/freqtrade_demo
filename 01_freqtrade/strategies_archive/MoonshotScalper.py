from __future__ import annotations

from datetime import datetime

import pandas as pd
import talib.abstract as ta
from pandas import DataFrame
from technical import qtpylib

from freqtrade.enums import RunMode
from freqtrade.exchange.exchange_utils_timeframe import timeframe_to_minutes
from freqtrade.persistence import Trade
from freqtrade.strategy import DecimalParameter, IStrategy, IntParameter


class MoonshotScalper(IStrategy):
    """
    MoonshotScalper：极高风险 1m 合约剥头皮策略（教学/研究用途）。

    ⚠️ 关键约束与风险提示（请务必读完）：
    - 尘埃限额（Dust Limit）：起始资金仅 10 USDT，若权益跌破约 5~6 USDT，
      交易所可能拒单/无法开仓（最小下单额、保证金不足等）。
    - 强平风险（Liquidation Risk）：20x 杠杆下，约 -5% 价格波动即可逼近强平。
      本策略在 futures 模式下将止损按“含杠杆后的 ROE”口径设置为 -0.40（名义约等价 -2% 价格波动），
      以尽量在强平前止损，但滑点/撮合延迟仍可能导致强平。
    - 滑点（Slippage）：1m + 市价单会带来显著滑点与手续费影响，回测通常高估实盘表现。

    说明：
    - 本策略仅做多（Long Only）。
    - 杠杆通过 leverage 回调固定为 20x（自动受交易所/交易对最大杠杆限制）。
    """

    INTERFACE_VERSION = 3

    timeframe = "1m"
    can_short = False
    process_only_new_candles = True

    # 需覆盖 max(bb_window=40) / volume_ma(20) / RSI(14) / EMA(20)
    startup_candle_count = 50

    # --- 风控/止盈止损（生存修正版） ---
    # 原 -0.40 太激进（2次即死）。
    # 修正为 -0.15（约等价 20x 下 -0.75% 价格波动）。
    # 这提供了约 4-5 次连败的生存缓冲，防止因 Dust Limit (5U) 导致策略停摆。
    stoploss = -0.15

    minimal_roi = {"0": 0.05, "2": 0.03, "5": 0.01}

    trailing_stop = True
    trailing_stop_positive = 0.01
    trailing_stop_positive_offset = 0.02
    trailing_only_offset_is_reached = True

    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False

    # --- Hyperopt 参数（买入/卖出空间） ---
    buy_volume_mult = DecimalParameter(
        1.5, 5.0, default=2.0, decimals=2, space="buy", optimize=True, load=True
    )
    buy_rsi = IntParameter(50, 75, default=60, space="buy", optimize=True, load=True)

    bb_window = IntParameter(10, 40, default=20, space="buy", optimize=True, load=True)
    bb_std = DecimalParameter(1.5, 3.0, default=2.0, decimals=2, space="buy", optimize=True, load=True)
    ema_trend_period = IntParameter(5, 20, default=9, space="buy", optimize=True, load=True)

    sell_rsi = IntParameter(50, 80, default=70, space="sell", optimize=True, load=True)
    stagnation_candles = IntParameter(5, 20, default=10, space="sell", optimize=True, load=True)
    stagnation_profit = DecimalParameter(
        0.001, 0.02, default=0.005, decimals=3, space="sell", optimize=True, load=True
    )

    @staticmethod
    def _bb_mid_col(window: int) -> str:
        return f"bb_mid_{window}"

    @staticmethod
    def _bb_std_col(window: int) -> str:
        return f"bb_std_{window}"

    @staticmethod
    def _ema_trend_col(period: int) -> str:
        return f"ema_trend_{period}"

    def _should_precompute_for_hyperopt(self) -> bool:
        runmode = self.dp.runmode if self.dp else RunMode.OTHER
        analyze_per_epoch = bool(self.config.get("analyze_per_epoch", False)) if self.config else False
        return runmode == RunMode.HYPEROPT and not analyze_per_epoch

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        precompute = self._should_precompute_for_hyperopt()

        new_cols: dict[str, object] = {}

        # 固定指标
        new_cols["rsi"] = ta.RSI(dataframe, timeperiod=14)
        new_cols["volume_ma"] = dataframe["volume"].rolling(window=20).mean()

        # 动态 EMA：为 hyperopt 预生成所有候选列（默认 analyze_per_epoch=False）
        ema_periods = (
            [int(v) for v in self.ema_trend_period.range] if precompute else [int(self.ema_trend_period.value)]
        )
        for period in ema_periods:
            new_cols[self._ema_trend_col(period)] = ta.EMA(dataframe, timeperiod=period)

        # 动态布林：只预生成“中轨 + 1σ标准差”两列，std 倍数在入场时再乘，避免组合爆炸
        bb_windows = [int(v) for v in self.bb_window.range] if precompute else [int(self.bb_window.value)]
        for window in bb_windows:
            base = qtpylib.bollinger_bands(dataframe["close"], window=window, stds=1.0)
            new_cols[self._bb_mid_col(window)] = base["mid"]
            new_cols[self._bb_std_col(window)] = base["upper"] - base["mid"]

        # 一次性合并，避免逐列插入导致 DataFrame 高度碎片化
        new_df = pd.DataFrame(new_cols, index=dataframe.index)
        existing_cols = [c for c in new_df.columns if c in dataframe.columns]
        if existing_cols:
            dataframe = dataframe.drop(columns=existing_cols)
        dataframe = pd.concat([dataframe, new_df], axis=1)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        volume_mult = float(self.buy_volume_mult.value)
        rsi_threshold = int(self.buy_rsi.value)

        bb_window = int(self.bb_window.value)
        bb_std_mult = float(self.bb_std.value)
        ema_period = int(self.ema_trend_period.value)

        bb_mid = dataframe[self._bb_mid_col(bb_window)]
        bb_upper = bb_mid + (dataframe[self._bb_std_col(bb_window)] * bb_std_mult)
        ema_trend = dataframe[self._ema_trend_col(ema_period)]

        dataframe.loc[
            (
                (dataframe["close"] > bb_upper)
                & (dataframe["volume"] > (dataframe["volume_ma"] * volume_mult))
                & (dataframe["rsi"] > rsi_threshold)
                & (dataframe["close"] > ema_trend)
                & (dataframe["volume"] > 0)
            ),
            ["enter_long", "enter_tag"],
        ] = (1, "BB_BREAKOUT_VOL_RSI_EMA")

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # 智能 RSI 离场：阈值由 sell_rsi 决定（从强势区回落即离场）
        thr = int(self.sell_rsi.value)
        rsi_drop = (dataframe["rsi"] < thr) & (dataframe["rsi"].shift(1) >= thr)

        dataframe.loc[
            (rsi_drop & (dataframe["volume"] > 0)),
            ["exit_long", "exit_tag"],
        ] = (1, f"RSI_DROP_BELOW_{thr}")

        return dataframe

    def leverage(
        self,
        pair: str,
        current_time: datetime,
        current_rate: float,
        proposed_leverage: float,
        max_leverage: float,
        entry_tag: str | None,
        side: str,
        **kwargs,
    ) -> float:
        # 合约模式下被调用：固定 20x，但不超过该交易对允许的最大杠杆
        if side != "long":
            return 1.0
        return float(min(20.0, max_leverage))

    def custom_exit(
        self,
        pair: str,
        trade: Trade,
        current_time: datetime,
        current_rate: float,
        current_profit: float,
        **kwargs,
    ) -> str | None:
        # 动态僵局退出：等待 N 根K线仍未达到最低利润，则主动退出（避免 1m 剥头皮“拖成慢性亏损”）
        if trade.is_short:
            return None

        stagnation_candles = int(self.stagnation_candles.value)
        stagnation_profit = float(self.stagnation_profit.value)

        tf_minutes = int(timeframe_to_minutes(self.timeframe))
        if tf_minutes <= 0:
            return None

        opened_at = getattr(trade, "open_date_utc", None) or getattr(trade, "open_date", None)
        if opened_at is None:
            return None

        trade_duration_minutes = int((current_time - opened_at).total_seconds() // 60)
        trade_duration_candles = trade_duration_minutes // tf_minutes

        if trade_duration_candles >= stagnation_candles and float(current_profit) < stagnation_profit:
            return f"STAGNATION_EXIT_{stagnation_candles}C_{int(stagnation_profit * 10000)}BP"

        return None
