from __future__ import annotations

from datetime import datetime, timezone
from functools import reduce

import numpy as np
import pandas as pd
import talib.abstract as ta
from pandas import DataFrame
from technical import qtpylib

from freqtrade.persistence import Order, Trade
from freqtrade.strategy import (
    BooleanParameter,
    DecimalParameter,
    IStrategy,
    IntParameter,
    merge_informative_pair,
)
from freqtrade.strategy.strategy_helper import stoploss_from_absolute


class SmallAccountFuturesTrendV1(IStrategy):
    """
    小资金合约趋势策略 v1（OKX USDT 本位永续，适合 10~10,000 USDT 的“生存优先”路线）

    设计目标：
    - 允许做空（熊市不必“只能躺平”）
    - 用中频趋势信号 + 体制/波动率/流动性门控，避免高频费用吞噬
    - 杠杆上限使用交易所返回的 max_leverage（策略内部只做“动态降杠杆/降仓”）

    重要说明：
    - 回测对资金费率/滑点/断线/风控限额等建模有限，实盘必须更保守。
    - 小账户最常见死因是“仓位单位错误 + 杠杆尾部风险”，务必把风险预算当作第一优先级。
    """

    INTERFACE_VERSION = 3
    can_short = True

    timeframe = "4h"
    startup_candle_count = 240

    # 趋势策略：尽量不依赖 ROI “到点就走”，主要依赖追踪止损与趋势破坏退出
    minimal_roi = {"0": 100}

    # 黑天鹅兜底（合约会叠加杠杆风险，因此必须配合动态杠杆/仓位）
    stoploss = -0.05

    trailing_stop = True
    trailing_stop_positive_offset = 0.06
    trailing_stop_positive = 0.04
    trailing_only_offset_is_reached = True

    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False

    protections = [
        {"method": "CooldownPeriod", "stop_duration_candles": 1},
        {
            "method": "StoplossGuard",
            "lookback_period_candles": 48,
            "trade_limit": 1,
            "stop_duration_candles": 12,
            "required_profit": 0.0,
            "only_per_pair": True,
            "only_per_side": False,
        },
        {
            "method": "MaxDrawdown",
            "lookback_period_candles": 96,
            "trade_limit": 2,
            "stop_duration_candles": 24,
            "max_allowed_drawdown": 0.25,
        },
    ]

    # --- 入场参数（长短共用）---
    buy_ema_short_len = IntParameter(10, 45, default=20, space="buy", optimize=True)
    buy_ema_long_len = IntParameter(80, 240, default=160, space="buy", optimize=True)
    buy_adx = IntParameter(12, 40, default=20, space="buy", optimize=True)

    buy_ema_slope_lookback = IntParameter(2, 24, default=6, space="buy", optimize=True)
    buy_ema_long_min_slope = DecimalParameter(0.0, 0.02, default=0.0, decimals=3, space="buy", optimize=True)

    buy_max_ema_short_offset = DecimalParameter(
        0.01, 0.12, default=0.06, decimals=3, space="buy", optimize=True
    )
    buy_bull_ema_long_offset = DecimalParameter(
        0.02, 0.20, default=0.08, decimals=3, space="buy", optimize=True
    )
    buy_bear_ema_long_offset = DecimalParameter(
        0.02, 0.20, default=0.08, decimals=3, space="buy", optimize=True
    )

    buy_min_ema_spread = DecimalParameter(
        0.0, 0.05, default=0.005, decimals=3, space="buy", optimize=True
    )

    buy_reentry_min_ema_long_offset = DecimalParameter(
        0.0, 0.10, default=0.02, decimals=3, space="buy", optimize=False
    )
    buy_reentry_min_ema_spread = DecimalParameter(
        0.0, 0.05, default=0.01, decimals=3, space="buy", optimize=False
    )

    # 波动率过滤：至少要有足够波动覆盖手续费与噪声
    buy_atr_pct_min = DecimalParameter(0.001, 0.02, default=0.004, decimals=4, space="buy", optimize=False)
    buy_use_atr_pct_max_filter = BooleanParameter(default=False, space="buy", optimize=False)
    buy_atr_pct_max = DecimalParameter(0.01, 0.20, default=0.10, decimals=3, space="buy", optimize=False)

    # 流动性代理：成交量相对均值
    buy_use_volume_ratio_filter = BooleanParameter(default=False, space="buy", optimize=False)
    buy_volume_ratio_lookback = IntParameter(12, 240, default=72, space="buy", optimize=False)
    buy_volume_ratio_min = DecimalParameter(0.5, 1.5, default=0.8, decimals=3, space="buy", optimize=False)

    # --- 宏观体制（1d）---
    macro_pair = "BTC/USDT:USDT"
    macro_timeframe = "1d"

    # 硬门控（容易导致 0 trades，默认关闭）
    buy_use_macro_trend_filter = BooleanParameter(default=False, space="buy", optimize=False)
    buy_macro_sma_period = IntParameter(100, 300, default=200, space="buy", optimize=False)
    buy_macro_sma_slope_lookback = IntParameter(5, 60, default=20, space="buy", optimize=False)
    buy_macro_sma_min_slope = DecimalParameter(0.0, 0.05, default=0.0, decimals=3, space="buy", optimize=False)

    # 软门控：不改信号，只做仓位/杠杆折扣（默认开启更贴合“生存优先”）
    buy_use_macro_trend_stake_scale = BooleanParameter(default=True, space="buy", optimize=False)
    buy_macro_stake_scale_floor = DecimalParameter(
        0.05, 1.00, default=0.25, decimals=3, space="buy", optimize=False
    )

    # --- 动态风险预算（仓位）---
    buy_stake_frac_bull = DecimalParameter(0.10, 1.00, default=1.00, decimals=3, space="buy", optimize=False)
    buy_stake_frac_bear = DecimalParameter(0.10, 1.00, default=1.00, decimals=3, space="buy", optimize=False)
    buy_stake_frac_strong = DecimalParameter(0.10, 1.00, default=1.00, decimals=3, space="buy", optimize=False)
    buy_stake_frac_normal = DecimalParameter(0.05, 1.00, default=0.80, decimals=3, space="buy", optimize=False)
    buy_stake_frac_weak = DecimalParameter(0.05, 1.00, default=0.40, decimals=3, space="buy", optimize=False)
    buy_stake_frac_bull_weak = DecimalParameter(0.05, 1.00, default=0.25, decimals=3, space="buy", optimize=False)
    buy_stake_frac_bear_weak = DecimalParameter(0.05, 1.00, default=0.25, decimals=3, space="buy", optimize=False)

    buy_stake_weak_regime_lookback = IntParameter(12, 240, default=72, space="buy", optimize=False)
    buy_stake_strong_adx_delta = IntParameter(0, 20, default=5, space="buy", optimize=False)
    buy_stake_strong_spread_delta = DecimalParameter(
        0.0, 0.05, default=0.01, decimals=3, space="buy", optimize=False
    )
    buy_stake_strong_slope_delta = DecimalParameter(
        0.0, 0.02, default=0.005, decimals=3, space="buy", optimize=False
    )

    # --- 动态杠杆（上限由交易所 max_leverage 决定）---
    buy_leverage_base = DecimalParameter(1.0, 10.0, default=2.0, decimals=2, space="buy", optimize=False)
    buy_leverage_trend_mult = DecimalParameter(1.0, 3.0, default=1.5, decimals=2, space="buy", optimize=False)
    buy_leverage_weak_mult = DecimalParameter(0.3, 1.0, default=0.7, decimals=2, space="buy", optimize=False)

    # --- 退出/止损参数 ---
    sell_ema_slope_lookback = IntParameter(6, 60, default=24, space="sell", optimize=False)
    sell_stop_atr_mult = DecimalParameter(2.0, 8.0, default=4.0, decimals=2, space="sell", optimize=False)
    sell_stop_min_loss = DecimalParameter(0.005, 0.05, default=0.02, decimals=3, space="sell", optimize=False)
    sell_bear_max_loss = DecimalParameter(0.01, 0.10, default=0.03, decimals=3, space="sell", optimize=False)

    def informative_pairs(self):
        # 只有在宏观相关开关启用时才拉取 1d 数据，避免“没下 1d 数据就回测报错”
        if bool(self.buy_use_macro_trend_filter.value) or bool(self.buy_use_macro_trend_stake_scale.value):
            return [(str(self.macro_pair), str(self.macro_timeframe))]
        return []

    def _get_macro_informative_dataframe(self) -> DataFrame | None:
        dp = getattr(self, "dp", None)
        if dp is None:
            return None

        cached = getattr(self, "_macro_inf_df", None)
        if isinstance(cached, DataFrame) and not cached.empty:
            return cached

        pair = str(getattr(self, "macro_pair", "BTC/USDT:USDT"))
        inf_tf = str(getattr(self, "macro_timeframe", "1d"))

        try:
            informative = dp.get_pair_dataframe(pair=pair, timeframe=inf_tf)
        except Exception:
            return None
        if informative is None or informative.empty:
            return None

        informative = informative.copy()
        informative["macro_close"] = informative["close"]

        sma_period = max(1, int(self.buy_macro_sma_period.value))
        informative["macro_sma"] = ta.SMA(informative, timeperiod=sma_period)

        informative_small = informative[["date", "macro_close", "macro_sma"]].copy()
        informative_small = informative_small.replace([np.inf, -np.inf], np.nan)

        setattr(self, "_macro_inf_df", informative_small)
        return informative_small

    def _merge_macro_indicators(self, dataframe: DataFrame) -> DataFrame:
        informative = self._get_macro_informative_dataframe()
        if informative is None:
            return dataframe

        inf_tf = str(getattr(self, "macro_timeframe", "1d"))
        return merge_informative_pair(dataframe, informative, self.timeframe, inf_tf, ffill=True)

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        short_len = int(self.buy_ema_short_len.value)
        long_len = int(self.buy_ema_long_len.value)

        new_cols: dict[str, pd.Series] = {}
        new_cols[f"ema_short_{short_len}"] = ta.EMA(dataframe, timeperiod=short_len)
        new_cols[f"ema_long_{long_len}"] = ta.EMA(dataframe, timeperiod=long_len)
        new_cols["adx"] = ta.ADX(dataframe, timeperiod=14)
        new_cols["atr"] = ta.ATR(dataframe, timeperiod=14)
        new_cols["atr_pct"] = new_cols["atr"] / dataframe["close"]

        vol_lb = int(self.buy_volume_ratio_lookback.value)
        if vol_lb > 0:
            vol_mean = dataframe["volume"].rolling(vol_lb).mean()
            new_cols["volume_ratio"] = dataframe["volume"] / vol_mean.replace(0, np.nan)

        macd = ta.MACD(dataframe, fastperiod=12, slowperiod=26, signalperiod=9)
        new_cols["macd"] = macd["macd"]
        new_cols["macdsignal"] = macd["macdsignal"]
        new_cols["macdhist"] = macd["macdhist"]

        new_df = pd.DataFrame(new_cols, index=dataframe.index)
        existing_cols = [c for c in new_df.columns if c in dataframe.columns]
        if existing_cols:
            dataframe = dataframe.drop(columns=existing_cols)
        dataframe = pd.concat([dataframe, new_df], axis=1)

        dataframe = self._merge_macro_indicators(dataframe)

        return dataframe.replace([np.inf, -np.inf], np.nan)

    def order_filled(
        self,
        pair: str,
        trade: Trade,
        order: Order,
        current_time: datetime,
        **kwargs,
    ) -> None:
        """
        在入场成交后，把“入场时 ATR”落盘到 trade.custom_data，保证回测/实盘一致。
        """
        if order.ft_order_side != trade.entry_side:
            return

        if trade.get_custom_data("entry_atr") is not None:
            return

        dp = getattr(self, "dp", None)
        if dp is None:
            return

        try:
            df, _ = dp.get_analyzed_dataframe(pair, self.timeframe)
        except Exception:
            return
        if df is None or df.empty:
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
            if df_cut is not None:
                df = df_cut

        last = df.iloc[-1]
        entry_atr = last.get("atr")
        if entry_atr is None or not np.isfinite(entry_atr) or float(entry_atr) <= 0:
            return

        trade.set_custom_data("entry_atr", float(entry_atr))

    def _risk_multiplier(self, *, df: DataFrame, side: str) -> float:
        """
        把体制/波动率/流动性映射为 0~1 的风险折扣（用于 stake 与 leverage）。

        - 宏观体制：对 long/short 使用“方向相反”的判定（long 偏好上行体制，short 偏好下行体制）。
        - 波动率与流动性：双向同口径（越高波动/越差流动性越保守）。
        """
        try:
            if df is None or df.empty:
                return 1.0

            last = df.iloc[-1]
            mult = 1.0

            # 宏观体制（软门控）
            if bool(self.buy_use_macro_trend_stake_scale.value):
                floor = float(self.buy_macro_stake_scale_floor.value)
                if np.isfinite(floor):
                    floor = float(max(0.0, min(1.0, floor)))
                    inf_tf = str(getattr(self, "macro_timeframe", "1d"))
                    macro_close_col = f"macro_close_{inf_tf}"
                    macro_sma_col = f"macro_sma_{inf_tf}"
                    macro_close = float(last.get(macro_close_col, np.nan))
                    macro_sma = float(last.get(macro_sma_col, np.nan))
                    if np.isfinite(macro_close) and np.isfinite(macro_sma) and macro_sma > 0:
                        is_long = str(side).lower() == "long"
                        regime_ok = (macro_close > macro_sma) if is_long else (macro_close < macro_sma)

                        if not regime_ok:
                            mult *= floor
                        else:
                            lb = int(self.buy_macro_sma_slope_lookback.value)
                            min_slope = float(self.buy_macro_sma_min_slope.value)
                            if (
                                lb > 0
                                and np.isfinite(min_slope)
                                and min_slope > 0
                                and len(df) > lb
                                and macro_sma_col in df.columns
                            ):
                                sma_then = float(df[macro_sma_col].iloc[-1 - lb])
                                if np.isfinite(sma_then) and sma_then > 0:
                                    slope = (macro_sma / sma_then) - 1.0
                                    strength = float(max(0.0, slope)) if is_long else float(max(0.0, -slope))

                                    if strength <= 0:
                                        mult *= floor
                                    elif strength >= min_slope:
                                        mult *= 1.0
                                    else:
                                        mult *= float(floor + (1.0 - floor) * (strength / min_slope))

            # 波动率过滤：atr_pct 过低则不交易（由入场条件处理），过高则风险折扣
            atr_pct = float(last.get("atr_pct", np.nan))
            if np.isfinite(atr_pct) and atr_pct > 0 and bool(self.buy_use_atr_pct_max_filter.value):
                atr_max = float(self.buy_atr_pct_max.value)
                if np.isfinite(atr_max) and atr_max > 0 and atr_pct > atr_max:
                    # 极端高波动：直接做保守折扣（不强行禁止，避免 0 trades）
                    mult *= 0.5

            # 流动性代理：volume_ratio 低于阈值时折扣
            if bool(self.buy_use_volume_ratio_filter.value):
                vr = float(last.get("volume_ratio", np.nan))
                liq_min = float(self.buy_volume_ratio_min.value)
                if np.isfinite(vr) and np.isfinite(liq_min) and liq_min > 0 and vr < liq_min:
                    mult *= 0.5

            return float(max(0.0, min(1.0, mult)))
        except Exception:
            return 1.0

    def custom_stake_amount(
        self,
        pair: str,
        current_time: datetime,
        current_rate: float,
        proposed_stake: float,
        min_stake: float | None,
        max_stake: float,
        leverage: float,
        entry_tag: str | None,
        side: str,
        **kwargs,
    ) -> float:
        """
        动态风险预算（仓位，返回 stake_amount = 保证金金额）：
        - 强趋势更积极，弱体制更保守
        - 不用 “return 0 禁止开仓”，而是优先“降仓/降杠杆”，避免 0 trades 造成的回测幻觉
        """
        side_l = str(side).lower()
        if side_l not in {"long", "short"}:
            return float(proposed_stake)

        dp = getattr(self, "dp", None)
        if dp is None:
            return float(proposed_stake)

        try:
            df, _ = dp.get_analyzed_dataframe(pair, self.timeframe)
        except Exception:
            return float(proposed_stake)
        if df is None or df.empty:
            return float(proposed_stake)

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
            if df_cut is not None:
                df = df_cut

        if df.empty:
            return float(proposed_stake)

        stake_frac = self._pick_stake_fraction(
            df=df,
            entry_tag=(str(entry_tag).strip().lower() if entry_tag else ""),
            side=side_l,
        )
        if not np.isfinite(stake_frac) or stake_frac <= 0:
            return float(proposed_stake)

        stake_frac = float(max(0.0, min(1.0, stake_frac)))
        stake_frac *= float(self._risk_multiplier(df=df, side=side_l))
        stake_frac = float(max(0.0, min(1.0, stake_frac)))

        cfg_stake_amount = str(getattr(self, "config", {}).get("stake_amount", "")).strip().lower()
        base_stake = float(max_stake) if cfg_stake_amount == "unlimited" else float(proposed_stake)
        stake = float(base_stake * stake_frac)

        stake = float(min(stake, float(max_stake)))
        if min_stake is not None and np.isfinite(float(min_stake)):
            stake = float(max(stake, float(min_stake)))

        return stake

    def _pick_stake_fraction(self, *, df: DataFrame, entry_tag: str, side: str) -> float:
        """
        根据趋势强度选择仓位档位（返回 0~1 的比例）。
        """
        try:
            short_len = int(self.buy_ema_short_len.value)
            long_len = int(self.buy_ema_long_len.value)
            if short_len <= 0 or long_len <= 0 or short_len >= long_len:
                return 1.0

            ema_s_col = f"ema_short_{short_len}"
            ema_l_col = f"ema_long_{long_len}"
            if ema_s_col not in df.columns or ema_l_col not in df.columns:
                return 1.0

            last = df.iloc[-1]
            close = float(last.get("close", np.nan))
            ema_s = float(last.get(ema_s_col, np.nan))
            ema_l = float(last.get(ema_l_col, np.nan))
            adx = float(last.get("adx", np.nan))
            if (
                not np.isfinite(close)
                or not np.isfinite(ema_s)
                or not np.isfinite(ema_l)
                or ema_l <= 0
                or not np.isfinite(adx)
            ):
                return 1.0

            weak_n = int(self.buy_stake_weak_regime_lookback.value)
            weak_regime = False
            if weak_n > 0 and len(df) > weak_n:
                ema_then = float(df[ema_l_col].iloc[-1 - weak_n])
                if np.isfinite(ema_then) and ema_then > 0:
                    # long：长期 EMA 走弱；short：长期 EMA 走强（短线做空更危险）
                    weak_regime = (ema_l < ema_then) if side == "long" else (ema_l > ema_then)

            bull_offset = float(self.buy_bull_ema_long_offset.value)
            bear_offset = float(self.buy_bear_ema_long_offset.value)
            bull_mode = close > (ema_l * (1.0 + bull_offset))
            bear_mode = close < (ema_l * (1.0 - bear_offset))

            if weak_regime:
                # 弱体制优先降风险：保留“cross”作为可能的反转启动点，避免完全错过趋势切换
                if entry_tag.startswith("cross"):
                    return float(self.buy_stake_frac_normal.value)
                if side == "long":
                    if entry_tag == "bull" or bull_mode:
                        return float(self.buy_stake_frac_bull_weak.value)
                    return float(self.buy_stake_frac_weak.value)
                if entry_tag == "bear" or bear_mode:
                    return float(self.buy_stake_frac_bear_weak.value)
                return float(self.buy_stake_frac_weak.value)

            if side == "long" and (entry_tag == "bull" or bull_mode):
                return float(self.buy_stake_frac_bull.value)
            if side == "short" and (entry_tag == "bear" or bear_mode):
                return float(self.buy_stake_frac_bear.value)

            spread = abs((ema_s / ema_l) - 1.0)
            min_spread = float(self.buy_min_ema_spread.value)
            strong_spread = spread >= (min_spread + float(self.buy_stake_strong_spread_delta.value))
            strong_adx = adx >= (int(self.buy_adx.value) + int(self.buy_stake_strong_adx_delta.value))

            strong_slope = False
            slope_n = int(self.buy_ema_slope_lookback.value)
            min_slope = float(self.buy_ema_long_min_slope.value)
            if slope_n > 0 and len(df) > slope_n:
                ema_then = float(df[ema_l_col].iloc[-1 - slope_n])
                if np.isfinite(ema_then) and ema_then > 0:
                    slope_pct = abs((ema_l / ema_then) - 1.0)
                    strong_slope = slope_pct >= (min_slope + float(self.buy_stake_strong_slope_delta.value))

            if strong_adx and strong_spread and strong_slope:
                return float(self.buy_stake_frac_strong.value)

            return float(self.buy_stake_frac_normal.value)
        except Exception:
            return 1.0

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
        """
        动态杠杆：
        - 上限使用交易所返回的 max_leverage
        - 弱体制/高波动/低流动性 → 降杠杆
        - 趋势强（bull/bear/cross）→ 适度上调，但仍受 max_leverage 限制
        """
        side_l = str(side).lower()
        if side_l not in {"long", "short"}:
            return 1.0

        dp = getattr(self, "dp", None)
        if dp is None:
            return 1.0

        try:
            df, _ = dp.get_analyzed_dataframe(pair, self.timeframe)
        except Exception:
            return 1.0
        if df is None or df.empty:
            return 1.0

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
            if df_cut is not None:
                df = df_cut

        base = float(self.buy_leverage_base.value)
        lev = base if np.isfinite(base) and base > 0 else 1.0

        tag = (str(entry_tag).strip().lower() if entry_tag else "")
        if tag in {"bull", "bear"} or tag.startswith("cross"):
            lev *= float(self.buy_leverage_trend_mult.value)

        # 弱体制优先降低杠杆（比仓位更优先）
        weak_n = int(self.buy_stake_weak_regime_lookback.value)
        if weak_n > 0:
            long_len = int(self.buy_ema_long_len.value)
            ema_l_col = f"ema_long_{long_len}"
            if ema_l_col in df.columns and len(df) > weak_n:
                ema_l = float(df[ema_l_col].iloc[-1])
                ema_then = float(df[ema_l_col].iloc[-1 - weak_n])
                if np.isfinite(ema_l) and np.isfinite(ema_then) and ema_then > 0:
                    weak_regime = (ema_l < ema_then) if side_l == "long" else (ema_l > ema_then)
                    if weak_regime:
                        lev *= float(self.buy_leverage_weak_mult.value)

        lev *= float(self._risk_multiplier(df=df, side=side_l))

        lev = float(max(1.0, lev))
        if np.isfinite(max_leverage) and max_leverage > 0:
            lev = float(min(lev, float(max_leverage)))

        return lev

    def custom_stoploss(
        self,
        pair: str,
        trade: Trade,
        current_time: datetime,
        current_rate: float,
        current_profit: float,
        **kwargs,
    ) -> float | None:
        """
        ATR 动态止损：
        - 仅当已出现一定浮亏（sell_stop_min_loss）且“长期趋势对该方向不友好”时启用
        - 目标：在尾部行情里限制单笔最大亏损（sell_bear_max_loss）
        """
        entry_atr = trade.get_custom_data("entry_atr")
        if entry_atr is None or not np.isfinite(entry_atr) or float(entry_atr) <= 0:
            return None

        if float(current_profit) > -float(self.sell_stop_min_loss.value):
            return None

        dp = getattr(self, "dp", None)
        if dp is None:
            return None

        try:
            df, _ = dp.get_analyzed_dataframe(pair, self.timeframe)
        except Exception:
            return None
        if df is None or df.empty:
            return None

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
            if df_cut is not None:
                df = df_cut

        if df.empty:
            return None

        long_len = int(self.buy_ema_long_len.value)
        ema_l_col = f"ema_long_{long_len}"
        if ema_l_col not in df.columns:
            return None

        slope_n = int(self.sell_ema_slope_lookback.value)
        if slope_n <= 0 or len(df) <= slope_n:
            return None

        ema_l_now = float(df[ema_l_col].iloc[-1])
        ema_l_then = float(df[ema_l_col].iloc[-1 - slope_n])
        if not np.isfinite(ema_l_now) or not np.isfinite(ema_l_then) or ema_l_then <= 0:
            return None

        # 对 long：EMA 走弱；对 short：EMA 走强（短线做空更危险）
        trend_unfriendly = (ema_l_now < ema_l_then) if not trade.is_short else (ema_l_now > ema_l_then)
        if not trend_unfriendly:
            return None

        atr_mult = float(self.sell_stop_atr_mult.value)
        if not np.isfinite(atr_mult) or atr_mult <= 0:
            return None

        open_rate = float(trade.open_rate)
        stop_rate = (
            open_rate - (float(entry_atr) * atr_mult)
            if not trade.is_short
            else open_rate + (float(entry_atr) * atr_mult)
        )

        max_loss = float(self.sell_bear_max_loss.value)
        if np.isfinite(max_loss) and max_loss > 0:
            if trade.is_short:
                stop_rate = float(min(stop_rate, open_rate * (1.0 + max_loss)))
            else:
                stop_rate = float(max(stop_rate, open_rate * (1.0 - max_loss)))

        return float(
            stoploss_from_absolute(
                current_rate=current_rate,
                stop_rate=stop_rate,
                current_profit=current_profit,
                is_short=trade.is_short,
                leverage=getattr(trade, "leverage", 1.0),
            )
        )

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        df = dataframe.copy()
        df["enter_long"] = 0
        df["enter_short"] = 0
        df["enter_tag"] = ""

        short_len = int(self.buy_ema_short_len.value)
        long_len = int(self.buy_ema_long_len.value)
        if short_len >= long_len:
            return df

        ema_s = df.get(f"ema_short_{short_len}")
        ema_l = df.get(f"ema_long_{long_len}")
        if ema_s is None or ema_l is None:
            return df

        adx_val = float(self.buy_adx.value)
        min_spread = float(self.buy_min_ema_spread.value)
        slope_n = int(self.buy_ema_slope_lookback.value)
        min_slope = float(self.buy_ema_long_min_slope.value)

        spread = (ema_s / ema_l) - 1.0
        spread_abs = spread.abs()
        ema_spread_ok = spread_abs > min_spread

        ema_l_trend_ok_long = True
        ema_l_trend_ok_short = True
        if slope_n > 0:
            # long：EMA 上行；short：EMA 下行
            ema_l_trend_ok_long = ema_l > (ema_l.shift(slope_n) * (1.0 + min_slope))
            ema_l_trend_ok_short = ema_l < (ema_l.shift(slope_n) * (1.0 - min_slope))

        atr_min = float(self.buy_atr_pct_min.value)
        vol_ok = df["atr_pct"] > atr_min
        if bool(self.buy_use_atr_pct_max_filter.value):
            atr_max = float(self.buy_atr_pct_max.value)
            if np.isfinite(atr_max) and atr_max > 0:
                vol_ok = vol_ok & (df["atr_pct"] < atr_max)

        liq_ok = df["volume"] > 0
        if bool(self.buy_use_volume_ratio_filter.value):
            if "volume_ratio" not in df.columns:
                return df
            liq_min = float(self.buy_volume_ratio_min.value)
            if np.isfinite(liq_min) and liq_min > 0:
                liq_ok = df["volume_ratio"] >= liq_min

        macro_ok_long = df["volume"] > 0
        macro_ok_short = df["volume"] > 0
        if bool(self.buy_use_macro_trend_filter.value):
            inf_tf = str(getattr(self, "macro_timeframe", "1d"))
            macro_close_col = f"macro_close_{inf_tf}"
            macro_sma_col = f"macro_sma_{inf_tf}"
            if macro_close_col in df.columns and macro_sma_col in df.columns:
                macro_ok_long = df[macro_close_col] > df[macro_sma_col]
                macro_ok_short = df[macro_close_col] < df[macro_sma_col]

        max_offset = float(self.buy_max_ema_short_offset.value)
        not_too_far_long = df["close"] <= (ema_s * (1.0 + max_offset))
        not_too_far_short = df["close"] >= (ema_s * (1.0 - max_offset))

        momentum_up = df["close"] > df["close"].shift(1)
        momentum_down = df["close"] < df["close"].shift(1)

        # --- long ---
        cross_up = qtpylib.crossed_above(ema_s, ema_l)
        reentry_long_raw = qtpylib.crossed_above(df["close"], ema_s)
        reentry_min_offset = float(self.buy_reentry_min_ema_long_offset.value)
        reentry_min_spread = float(self.buy_reentry_min_ema_spread.value)
        reentry_long = reentry_long_raw & (df["close"] > (ema_l * (1.0 + reentry_min_offset))) & (
            spread_abs > reentry_min_spread
        )

        bull_offset = float(self.buy_bull_ema_long_offset.value)
        bull_mode = df["close"] > (ema_l * (1.0 + bull_offset))

        enter_long = reduce(
            lambda x, y: x & y,
            [
                df["volume"] > 0,
                macro_ok_long.fillna(False),
                (ema_s > ema_l).fillna(False),
                ema_l_trend_ok_long.fillna(False),
                (df["adx"] > adx_val).fillna(False),
                ema_spread_ok.fillna(False),
                vol_ok.fillna(False),
                (df["macdhist"] > 0).fillna(False),
                not_too_far_long.fillna(False),
                momentum_up.fillna(False),
                liq_ok.fillna(False),
                (cross_up | reentry_long).fillna(False),
            ],
        )
        df.loc[enter_long, "enter_long"] = 1

        df.loc[enter_long & bull_mode.fillna(False), "enter_tag"] = "bull"
        df.loc[enter_long & ~bull_mode.fillna(False) & cross_up.fillna(False), "enter_tag"] = "cross_long"
        df.loc[
            enter_long
            & ~bull_mode.fillna(False)
            & ~cross_up.fillna(False)
            & reentry_long.fillna(False),
            "enter_tag",
        ] = "reentry_long"
        df.loc[enter_long & (df["enter_tag"] == ""), "enter_tag"] = "event_long"

        # --- short ---
        cross_down = qtpylib.crossed_below(ema_s, ema_l)
        reentry_short_raw = qtpylib.crossed_below(df["close"], ema_s)
        reentry_short = reentry_short_raw & (df["close"] < (ema_l * (1.0 - reentry_min_offset))) & (
            spread_abs > reentry_min_spread
        )

        bear_offset = float(self.buy_bear_ema_long_offset.value)
        bear_mode = df["close"] < (ema_l * (1.0 - bear_offset))

        enter_short = reduce(
            lambda x, y: x & y,
            [
                df["volume"] > 0,
                macro_ok_short.fillna(False),
                (ema_s < ema_l).fillna(False),
                ema_l_trend_ok_short.fillna(False),
                (df["adx"] > adx_val).fillna(False),
                ema_spread_ok.fillna(False),
                vol_ok.fillna(False),
                (df["macdhist"] < 0).fillna(False),
                not_too_far_short.fillna(False),
                momentum_down.fillna(False),
                liq_ok.fillna(False),
                (cross_down | reentry_short).fillna(False),
            ],
        )
        df.loc[enter_short, "enter_short"] = 1

        df.loc[enter_short & bear_mode.fillna(False), "enter_tag"] = "bear"
        df.loc[enter_short & ~bear_mode.fillna(False) & cross_down.fillna(False), "enter_tag"] = "cross_short"
        df.loc[
            enter_short
            & ~bear_mode.fillna(False)
            & ~cross_down.fillna(False)
            & reentry_short.fillna(False),
            "enter_tag",
        ] = "reentry_short"
        df.loc[enter_short & (df["enter_tag"] == ""), "enter_tag"] = "event_short"

        return df

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        df = dataframe.copy()
        df["exit_long"] = 0
        df["exit_short"] = 0

        short_len = int(self.buy_ema_short_len.value)
        long_len = int(self.buy_ema_long_len.value)
        if short_len >= long_len:
            return df

        ema_s = df.get(f"ema_short_{short_len}")
        ema_l = df.get(f"ema_long_{long_len}")
        if ema_s is None or ema_l is None:
            return df

        cross_down = qtpylib.crossed_below(ema_s, ema_l)
        cross_up = qtpylib.crossed_above(ema_s, ema_l)

        df.loc[((df["volume"] > 0) & cross_down), "exit_long"] = 1
        df.loc[((df["volume"] > 0) & cross_up), "exit_short"] = 1

        return df
