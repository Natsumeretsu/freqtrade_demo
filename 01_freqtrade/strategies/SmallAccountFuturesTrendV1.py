from __future__ import annotations

from datetime import datetime
import logging

import numpy as np
from pandas import DataFrame

from freqtrade.persistence import Order, Trade
from freqtrade.strategy import (
    BooleanParameter,
    DecimalParameter,
    IStrategy,
    IntParameter,
    merge_informative_pair,
)
from freqtrade.strategy.strategy_helper import stoploss_from_absolute

from trading_system.application.factor_sets import get_factor_templates, render_factor_names
from trading_system.application.entry_gates import (
    atr_pct_range_ok,
    ema_trend_ok,
    macro_sma_regime_ok,
    momentum_ok,
    price_not_too_far_from_ema,
    volume_ratio_min_ok,
)
from trading_system.application.gate_pipeline import combine_gates, gate_funnel
from trading_system.application.gate_pipeline import render_gate_funnel_summary
from trading_system.application.risk_scaling import macro_sma_soft_scale, step_max, step_min
from trading_system.application.signal_ops import bear_mode, bull_mode, crossed_above, crossed_below, reentry_event
from trading_system.infrastructure.container import get_container
from trading_system.infrastructure.freqtrade_data import (
    build_macro_sma_informative_dataframe,
    get_analyzed_dataframe_upto_time,
    get_latest_funding_rate,
)

logger = logging.getLogger(__name__)


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

    # cross 准入 Gate：只对 cross_* 增加更强确认（reentry_* 保持为主要频率来源）
    buy_use_cross_gate = BooleanParameter(default=True, space="buy", optimize=False)
    buy_gate_cross_min_spread = DecimalParameter(0.0, 0.05, default=0.01, decimals=4, space="buy", optimize=True)
    buy_gate_cross_adx_delta = IntParameter(0, 20, default=5, space="buy", optimize=True)
    buy_gate_cross_slope_lookback = IntParameter(2, 48, default=12, space="buy", optimize=True)
    buy_gate_cross_min_slope_pct = DecimalParameter(0.0, 0.02, default=0.003, decimals=4, space="buy", optimize=True)
    buy_gate_cross_min_macdhist_pct = DecimalParameter(
        0.0, 0.01, default=0.0005, decimals=5, space="buy", optimize=True
    )

    # 资金费率过滤（可选）：仅在 DataProvider 提供 funding_rate 数据时生效；缺数据则放行（不影响回测）
    buy_use_funding_rate_filter = BooleanParameter(default=False, space="buy", optimize=False)
    buy_funding_rate_max = DecimalParameter(0.0, 0.005, default=0.0003, decimals=5, space="buy", optimize=False)

    # Qlib/研究层模型（可选）：默认作为“软风险折扣 + 极端反向硬保险丝”（更贴近业界做法）
    buy_use_qlib_model_filter = BooleanParameter(default=False, space="buy", optimize=False)
    buy_qlib_fail_open = BooleanParameter(default=True, space="buy", optimize=False)
    buy_qlib_soft_scale_enabled = BooleanParameter(default=True, space="buy", optimize=False)
    buy_qlib_soft_scale_floor = DecimalParameter(0.0, 1.0, default=0.30, decimals=3, space="buy", optimize=False)
    buy_qlib_proba_threshold = DecimalParameter(
        0.50, 0.80, default=0.55, decimals=3, space="buy", optimize=False
    )  # 该概率以上视为“满仓/满风险”，中间线性插值
    buy_qlib_apply_to_stake = BooleanParameter(default=True, space="buy", optimize=False)
    buy_qlib_apply_to_leverage = BooleanParameter(default=False, space="buy", optimize=False)
    buy_qlib_hard_fuse_enabled = BooleanParameter(default=True, space="buy", optimize=False)
    buy_qlib_hard_fuse_min_proba = DecimalParameter(0.35, 0.49, default=0.45, decimals=3, space="buy", optimize=False)

    # 门控可观测性：输出 gate funnel（通过率/边际卡口贡献）到策略实例缓存（默认关闭）
    buy_debug_gate_stats = BooleanParameter(default=False, space="buy", optimize=False)

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

    # --- 小账户护栏：按账户规模封顶杠杆（优先级高于趋势加成，低于交易所 max_leverage）---
    buy_use_account_leverage_cap = BooleanParameter(default=True, space="buy", optimize=False)
    buy_account_tier1_usdt = IntParameter(10, 500, default=100, space="buy", optimize=False)
    buy_account_tier2_usdt = IntParameter(100, 10000, default=1000, space="buy", optimize=False)
    buy_account_leverage_cap_tier1 = DecimalParameter(1.0, 5.0, default=2.0, decimals=2, space="buy", optimize=False)
    buy_account_leverage_cap_tier2 = DecimalParameter(1.0, 10.0, default=3.0, decimals=2, space="buy", optimize=False)
    buy_account_leverage_cap_tier3 = DecimalParameter(1.0, 20.0, default=5.0, decimals=2, space="buy", optimize=False)

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
        informative_small = build_macro_sma_informative_dataframe(
            dp,
            pair=pair,
            timeframe=inf_tf,
            sma_period=int(self.buy_macro_sma_period.value),
        )
        if informative_small is None or informative_small.empty:
            return None

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
        templates = get_factor_templates("SmallAccountFuturesTrendV1")
        factor_names = render_factor_names(
            templates,
            {
                "ema_short_len": short_len,
                "ema_long_len": long_len,
                "volume_ratio_lookback": int(self.buy_volume_ratio_lookback.value),
            },
        )
        if not factor_names:
            factor_names = [
                f"ema_short_{short_len}",
                f"ema_long_{long_len}",
                "adx",
                "atr",
                "atr_pct",
                "macd",
                "macdsignal",
                "macdhist",
            ]

        # volume_ratio：仅当过滤开关启用时才计算，避免无谓开销
        if not bool(self.buy_use_volume_ratio_filter.value):
            factor_names = [n for n in factor_names if not str(n).startswith("volume_ratio")]

        dataframe = get_container().factor_usecase().execute(dataframe, factor_names)

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

        df = get_analyzed_dataframe_upto_time(dp, pair=pair, timeframe=self.timeframe, current_time=current_time)
        if df is None or df.empty:
            return

        last = df.iloc[-1]
        entry_atr = last.get("atr")
        if entry_atr is None or not np.isfinite(entry_atr) or float(entry_atr) <= 0:
            return

        trade.set_custom_data("entry_atr", float(entry_atr))

        # 记录入场时的模型概率（便于回测/复盘做归因分析；不影响信号本身）
        if bool(self.buy_use_qlib_model_filter.value):
            if trade.get_custom_data("entry_ml_proba_up") is not None:
                return

            svc = get_container().qlib_signal_service()
            proba_up = svc.entry_proba_up(
                dp=dp,
                pair=pair,
                timeframe=str(self.timeframe),
                current_time=current_time,
            )
            if proba_up is None or not np.isfinite(float(proba_up)):
                return

            side = "short" if bool(getattr(trade, "is_short", False)) else "long"
            side_proba = svc.side_proba(proba_up=float(proba_up), side=side)
            scale = (
                svc.soft_scale(
                    side_proba=float(side_proba),
                    floor=float(self.buy_qlib_soft_scale_floor.value),
                    threshold=float(self.buy_qlib_proba_threshold.value),
                )
                if side_proba is not None
                else None
            )

            trade.set_custom_data("entry_ml_proba_up", float(proba_up))
            if side_proba is not None and np.isfinite(float(side_proba)):
                trade.set_custom_data("entry_ml_side_proba", float(side_proba))
            if scale is not None and np.isfinite(float(scale)):
                trade.set_custom_data("entry_ml_scale", float(scale))

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
                inf_tf = str(getattr(self, "macro_timeframe", "1d"))
                macro_close_col = f"macro_close_{inf_tf}"
                macro_sma_col = f"macro_sma_{inf_tf}"
                mult *= float(
                    macro_sma_soft_scale(
                        df,
                        macro_close_col=macro_close_col,
                        macro_sma_col=macro_sma_col,
                        is_long=str(side).lower() == "long",
                        floor=float(self.buy_macro_stake_scale_floor.value),
                        slope_lookback=int(self.buy_macro_sma_slope_lookback.value),
                        min_slope=float(self.buy_macro_sma_min_slope.value),
                    )
                )

            # 波动率过滤：atr_pct 过低则不交易（由入场条件处理），过高则风险折扣
            if bool(self.buy_use_atr_pct_max_filter.value):
                mult *= float(
                    step_max(
                        value=float(last.get("atr_pct", np.nan)),
                        max_value=float(self.buy_atr_pct_max.value),
                        floor=0.5,
                    )
                )

            # 流动性代理：volume_ratio 低于阈值时折扣
            if bool(self.buy_use_volume_ratio_filter.value):
                mult *= float(
                    step_min(
                        value=float(last.get("volume_ratio", np.nan)),
                        min_value=float(self.buy_volume_ratio_min.value),
                        floor=0.5,
                    )
                )

            return float(max(0.0, min(1.0, mult)))
        except Exception:
            return 1.0

    def _get_account_equity_usdt(self) -> float | None:
        """
        获取“账户规模（USDT）”的粗粒度估计：
        - 实盘/模拟盘：优先读取 self.wallets（实时余额）
        - 回测：回退到 config.dry_run_wallet
        """
        cfg = getattr(self, "config", {}) or {}
        stake_currency = str(cfg.get("stake_currency") or "USDT").strip() or "USDT"

        wallets = getattr(self, "wallets", None)
        if wallets is not None:
            try:
                total = float(wallets.get_total(stake_currency))
                if np.isfinite(total) and total > 0:
                    return total
            except Exception:
                pass
            try:
                total = float(wallets.get_total_stake_amount())
                if np.isfinite(total) and total > 0:
                    return total
            except Exception:
                pass

        try:
            dry = float(cfg.get("dry_run_wallet", np.nan))
            if np.isfinite(dry) and dry > 0:
                return dry
        except Exception:
            return None

        return None

    def _account_leverage_cap(self) -> float | None:
        """
        根据账户规模分档封顶杠杆（返回 1~N；返回 None 表示不启用/不可用）。
        """
        try:
            if not bool(self.buy_use_account_leverage_cap.value):
                return None

            equity = self._get_account_equity_usdt()
            if equity is None or not np.isfinite(equity) or float(equity) <= 0:
                return None

            tier1 = int(self.buy_account_tier1_usdt.value)
            tier2 = int(self.buy_account_tier2_usdt.value)
            if tier1 <= 0 or tier2 <= 0 or tier1 >= tier2:
                return None

            if float(equity) < float(tier1):
                cap = float(self.buy_account_leverage_cap_tier1.value)
            elif float(equity) < float(tier2):
                cap = float(self.buy_account_leverage_cap_tier2.value)
            else:
                cap = float(self.buy_account_leverage_cap_tier3.value)

            if not np.isfinite(cap) or cap <= 0:
                return None
            return float(max(1.0, cap))
        except Exception:
            return None

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

        df = get_analyzed_dataframe_upto_time(dp, pair=pair, timeframe=self.timeframe, current_time=current_time)
        if df is None or df.empty:
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

        # 研究层模型：软过滤（默认只作用于仓位，避免与动态杠杆叠加过强）
        if bool(self.buy_use_qlib_model_filter.value) and bool(self.buy_qlib_soft_scale_enabled.value):
            if bool(self.buy_qlib_apply_to_stake.value):
                svc = get_container().qlib_signal_service()
                proba_up = svc.entry_proba_up(
                    dp=dp,
                    pair=pair,
                    timeframe=str(self.timeframe),
                    current_time=current_time,
                )
                if proba_up is not None:
                    side_proba = svc.side_proba(proba_up=float(proba_up), side=side_l)
                    if side_proba is not None:
                        stake_frac *= float(
                            svc.soft_scale(
                                side_proba=float(side_proba),
                                floor=float(self.buy_qlib_soft_scale_floor.value),
                                threshold=float(self.buy_qlib_proba_threshold.value),
                            )
                        )
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

        df = get_analyzed_dataframe_upto_time(dp, pair=pair, timeframe=self.timeframe, current_time=current_time)
        if df is None or df.empty:
            return 1.0

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

        # 研究层模型：可选作用于杠杆（默认关闭，避免与仓位折扣叠加过强）
        if bool(self.buy_use_qlib_model_filter.value) and bool(self.buy_qlib_soft_scale_enabled.value):
            if bool(self.buy_qlib_apply_to_leverage.value):
                svc = get_container().qlib_signal_service()
                proba_up = svc.entry_proba_up(
                    dp=dp,
                    pair=pair,
                    timeframe=str(self.timeframe),
                    current_time=current_time,
                )
                if proba_up is not None:
                    side_proba = svc.side_proba(proba_up=float(proba_up), side=side_l)
                    if side_proba is not None:
                        lev *= float(
                            svc.soft_scale(
                                side_proba=float(side_proba),
                                floor=float(self.buy_qlib_soft_scale_floor.value),
                                threshold=float(self.buy_qlib_proba_threshold.value),
                            )
                        )

        lev = float(max(1.0, lev))
        acc_cap = self._account_leverage_cap()
        if acc_cap is not None and np.isfinite(acc_cap) and acc_cap > 0:
            lev = float(min(lev, float(max(1.0, acc_cap))))
        if np.isfinite(max_leverage) and max_leverage > 0:
            lev = float(min(lev, float(max_leverage)))

        return lev

    def confirm_trade_entry(
        self,
        pair: str,
        order_type: str,
        amount: float,
        rate: float,
        time_in_force: str,
        current_time: datetime,
        entry_tag: str | None,
        side: str,
        **kwargs,
    ) -> bool:
        """
        最后一层准入：资金费率过滤（可选）。

        说明：
        - 资金费率属于“交易所状态”，回测通常没有对应历史序列；
          因此这里仅在 DataProvider 能提供 funding_rate 数据时才会真正拦截。
        - 可选叠加研究层模型保险丝：当模型概率“强烈反向”时拒绝入场（其余场景用软折扣去降风险）。
        """
        side_l = str(side).lower()
        if side_l not in {"long", "short"}:
            return True

        dp = getattr(self, "dp", None)

        if bool(self.buy_use_funding_rate_filter.value) and dp is not None:
            funding_rate = get_latest_funding_rate(dp, pair=pair, current_time=current_time)
            if funding_rate is not None and np.isfinite(float(funding_rate)):
                max_fr = float(self.buy_funding_rate_max.value)
                if np.isfinite(max_fr) and max_fr > 0:
                    # funding_rate > 0：long 付费；funding_rate < 0：short 付费
                    if side_l == "long" and float(funding_rate) > max_fr:
                        return False
                    if side_l == "short" and float(funding_rate) < -max_fr:
                        return False

        if bool(self.buy_use_qlib_model_filter.value):
            if dp is None:
                return bool(self.buy_qlib_fail_open.value)

            svc = get_container().qlib_signal_service()
            proba_up = svc.entry_proba_up(
                dp=dp,
                pair=pair,
                timeframe=str(self.timeframe),
                current_time=current_time,
            )
            if proba_up is None:
                return bool(self.buy_qlib_fail_open.value)

            side_proba = svc.side_proba(proba_up=float(proba_up), side=side_l)
            if side_proba is None:
                return True

            # 硬保险丝：模型强烈反向时拒绝入场（避免在明显逆风方向硬扛）
            if svc.hard_fuse_block(
                side_proba=float(side_proba),
                enabled=bool(self.buy_qlib_hard_fuse_enabled.value),
                min_proba=float(self.buy_qlib_hard_fuse_min_proba.value),
            ):
                return False

        return True

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

        df = get_analyzed_dataframe_upto_time(dp, pair=pair, timeframe=self.timeframe, current_time=current_time)
        if df is None or df.empty:
            return None

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

        # long：EMA 上行；short：EMA 下行
        ema_l_trend_ok_long = ema_trend_ok(ema_l, lookback=slope_n, min_slope=min_slope, direction="up")
        ema_l_trend_ok_short = ema_trend_ok(ema_l, lookback=slope_n, min_slope=min_slope, direction="down")

        atr_min = float(self.buy_atr_pct_min.value)
        vol_ok = atr_pct_range_ok(
            df,
            min_pct=atr_min,
            use_max_filter=bool(self.buy_use_atr_pct_max_filter.value),
            max_pct=float(self.buy_atr_pct_max.value),
        )

        liq_ok = volume_ratio_min_ok(
            df,
            enabled=bool(self.buy_use_volume_ratio_filter.value),
            min_ratio=float(self.buy_volume_ratio_min.value),
            require_column=True,
            fail_open=False,
        )

        inf_tf = str(getattr(self, "macro_timeframe", "1d"))
        macro_close_col = f"macro_close_{inf_tf}"
        macro_sma_col = f"macro_sma_{inf_tf}"
        macro_ok_long = macro_sma_regime_ok(
            df,
            enabled=bool(self.buy_use_macro_trend_filter.value),
            macro_close_col=macro_close_col,
            macro_sma_col=macro_sma_col,
            is_long=True,
            require_columns=False,
            slope_lookback=0,
            min_slope=0.0,
            fail_open=True,
        )
        macro_ok_short = macro_sma_regime_ok(
            df,
            enabled=bool(self.buy_use_macro_trend_filter.value),
            macro_close_col=macro_close_col,
            macro_sma_col=macro_sma_col,
            is_long=False,
            require_columns=False,
            slope_lookback=0,
            min_slope=0.0,
            fail_open=True,
        )

        max_offset = float(self.buy_max_ema_short_offset.value)
        not_too_far_long = price_not_too_far_from_ema(df["close"], ema_s, max_offset=max_offset, side="long")
        not_too_far_short = price_not_too_far_from_ema(df["close"], ema_s, max_offset=max_offset, side="short")

        momentum_up = momentum_ok(df["close"], side="long")
        momentum_down = momentum_ok(df["close"], side="short")

        cross_gate_on = bool(self.buy_use_cross_gate.value)
        cross_min_spread = float(self.buy_gate_cross_min_spread.value)
        cross_adx_delta = int(self.buy_gate_cross_adx_delta.value)
        cross_lb = int(self.buy_gate_cross_slope_lookback.value)
        cross_min_slope = float(self.buy_gate_cross_min_slope_pct.value)
        cross_min_macd = float(self.buy_gate_cross_min_macdhist_pct.value)

        # 归一化动量强度（避免只看正负号）
        close = df["close"].replace(0, np.nan)
        macdhist_pct = df["macdhist"] / close

        cross_min_spread_eff = float(max(min_spread, cross_min_spread))
        cross_adx_min = float(adx_val + cross_adx_delta)

        ema_l_slope_pct_cross = (ema_l / ema_l.shift(cross_lb)) - 1.0 if cross_lb > 0 else 0.0

        # --- long ---
        reentry_min_offset = float(self.buy_reentry_min_ema_long_offset.value)
        reentry_min_spread = float(self.buy_reentry_min_ema_spread.value)
        cross_up = crossed_above(ema_s, ema_l)
        reentry_long = reentry_event(
            df["close"],
            ema_s,
            ema_l,
            side="long",
            min_long_offset=reentry_min_offset,
            spread_metric=spread_abs,
            min_spread=reentry_min_spread,
        )

        bull_offset = float(self.buy_bull_ema_long_offset.value)
        bull_mode_mask = bull_mode(df["close"], ema_l, offset=bull_offset)

        cross_gate_long = df["volume"] > 0
        if cross_gate_on:
            cross_gate_long = (
                (spread_abs >= cross_min_spread_eff)
                & (df["adx"] >= cross_adx_min)
                & (macdhist_pct >= cross_min_macd)
                & (ema_l_slope_pct_cross >= cross_min_slope)
            )

        trigger_cross_long = cross_up & cross_gate_long
        trigger_reentry_long = reentry_long

        gates_long = [
            ("volume", df["volume"] > 0),
            ("macro", macro_ok_long),
            ("trend_state", (ema_s > ema_l)),
            ("ema_long_trend", ema_l_trend_ok_long),
            ("adx", (df["adx"] > adx_val)),
            ("ema_spread", ema_spread_ok),
            ("atr_pct", vol_ok),
            ("macdhist", (df["macdhist"] > 0)),
            ("not_too_far", not_too_far_long),
            ("momentum", momentum_up),
            ("liquidity", liq_ok),
            ("trigger", (trigger_cross_long | trigger_reentry_long)),
        ]
        if bool(self.buy_debug_gate_stats.value):
            enter_long, funnel_long = gate_funnel(gates_long, index=df.index, fillna=True)
            pair = str(metadata.get("pair", "")).strip()
            cache = getattr(self, "_gate_funnel_cache", None)
            if not isinstance(cache, dict):
                cache = {}
                setattr(self, "_gate_funnel_cache", cache)
            cache[(pair, "long")] = [r.to_dict() for r in funnel_long]

            logged = getattr(self, "_gate_funnel_logged", None)
            if not isinstance(logged, set):
                logged = set()
                setattr(self, "_gate_funnel_logged", logged)
            log_key = (pair, "long")
            if pair and log_key not in logged:
                logged.add(log_key)
                logger.info("门控漏斗 %s %s: %s", pair, "long", render_gate_funnel_summary(funnel_long, top_k=3))
        else:
            enter_long = combine_gates(gates_long, index=df.index, fillna=True)

        df.loc[enter_long, "enter_long"] = 1

        df.loc[enter_long & bull_mode_mask.fillna(False), "enter_tag"] = "bull"
        df.loc[
            enter_long & ~bull_mode_mask.fillna(False) & trigger_cross_long.fillna(False),
            "enter_tag",
        ] = "cross_long"
        df.loc[
            enter_long
            & ~bull_mode_mask.fillna(False)
            & ~trigger_cross_long.fillna(False)
            & trigger_reentry_long.fillna(False),
            "enter_tag",
        ] = "reentry_long"
        df.loc[enter_long & (df["enter_tag"] == ""), "enter_tag"] = "event_long"

        # --- short ---
        cross_down = crossed_below(ema_s, ema_l)
        reentry_short = reentry_event(
            df["close"],
            ema_s,
            ema_l,
            side="short",
            min_long_offset=reentry_min_offset,
            spread_metric=spread_abs,
            min_spread=reentry_min_spread,
        )

        bear_offset = float(self.buy_bear_ema_long_offset.value)
        bear_mode_mask = bear_mode(df["close"], ema_l, offset=bear_offset)

        cross_gate_short = df["volume"] > 0
        if cross_gate_on:
            cross_gate_short = (
                (spread_abs >= cross_min_spread_eff)
                & (df["adx"] >= cross_adx_min)
                & (macdhist_pct <= -cross_min_macd)
                & (ema_l_slope_pct_cross <= -cross_min_slope)
            )

        trigger_cross_short = cross_down & cross_gate_short
        trigger_reentry_short = reentry_short

        gates_short = [
            ("volume", df["volume"] > 0),
            ("macro", macro_ok_short),
            ("trend_state", (ema_s < ema_l)),
            ("ema_long_trend", ema_l_trend_ok_short),
            ("adx", (df["adx"] > adx_val)),
            ("ema_spread", ema_spread_ok),
            ("atr_pct", vol_ok),
            ("macdhist", (df["macdhist"] < 0)),
            ("not_too_far", not_too_far_short),
            ("momentum", momentum_down),
            ("liquidity", liq_ok),
            ("trigger", (trigger_cross_short | trigger_reentry_short)),
        ]
        if bool(self.buy_debug_gate_stats.value):
            enter_short, funnel_short = gate_funnel(gates_short, index=df.index, fillna=True)
            pair = str(metadata.get("pair", "")).strip()
            cache = getattr(self, "_gate_funnel_cache", None)
            if not isinstance(cache, dict):
                cache = {}
                setattr(self, "_gate_funnel_cache", cache)
            cache[(pair, "short")] = [r.to_dict() for r in funnel_short]

            logged = getattr(self, "_gate_funnel_logged", None)
            if not isinstance(logged, set):
                logged = set()
                setattr(self, "_gate_funnel_logged", logged)
            log_key = (pair, "short")
            if pair and log_key not in logged:
                logged.add(log_key)
                logger.info("门控漏斗 %s %s: %s", pair, "short", render_gate_funnel_summary(funnel_short, top_k=3))
        else:
            enter_short = combine_gates(gates_short, index=df.index, fillna=True)

        df.loc[enter_short, "enter_short"] = 1

        df.loc[enter_short & bear_mode_mask.fillna(False), "enter_tag"] = "bear"
        df.loc[
            enter_short & ~bear_mode_mask.fillna(False) & trigger_cross_short.fillna(False),
            "enter_tag",
        ] = "cross_short"
        df.loc[
            enter_short
            & ~bear_mode_mask.fillna(False)
            & ~trigger_cross_short.fillna(False)
            & trigger_reentry_short.fillna(False),
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

        cross_down = crossed_below(ema_s, ema_l)
        cross_up = crossed_above(ema_s, ema_l)

        df.loc[((df["volume"] > 0) & cross_down), "exit_long"] = 1
        df.loc[((df["volume"] > 0) & cross_up), "exit_short"] = 1

        return df
