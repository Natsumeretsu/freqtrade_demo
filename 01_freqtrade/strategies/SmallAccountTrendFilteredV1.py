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

from trading_system.infrastructure.container import get_container
from trading_system.application.factor_sets import get_factor_templates, render_factor_names
from trading_system.application.risk_scaling import linear_scale_down, linear_scale_up, macro_sma_soft_scale
from trading_system.application.entry_gates import (
    atr_pct_range_ok,
    ema_trend_ok,
    macro_sma_regime_ok,
    momentum_ok,
    price_not_too_far_from_ema,
    volume_ratio_min_ok,
)
from trading_system.application.gate_pipeline import combine_gates, gate_funnel, render_gate_funnel_summary
from trading_system.application.signal_ops import bull_mode, crossed_above, crossed_below, reentry_event
from trading_system.infrastructure.freqtrade_data import build_macro_sma_informative_dataframe, get_analyzed_dataframe_upto_time

logger = logging.getLogger(__name__)


class SmallAccountTrendFilteredV1(IStrategy):
    """
    小资金（10USDT 起）现货趋势策略 v1（波动率/趋势过滤版）

    设计目标：
    - 只做多（小资金优先降低复杂度与爆仓风险）
    - 用“趋势 + 波动率”双过滤，减少震荡期的频繁止损/手续费磨损
    - 用更积极的退出（ROI + 更早触发的追踪止损）把利润落袋，提升稳定性

    核心思路（4h）：
    - 入场：趋势状态（EMA 短期 > EMA 长期）+ 动量确认（MACD 柱体为正）+ ADX 过滤 + ATR% 过滤 + EMA 长期上行
    - 出场：EMA 死叉（保底）+ ROI（落袋）+ 追踪止损（让利润奔跑但不回吐太多）
    - 仓位：动态风险预算（趋势越强，投入资金越多；长期趋势走弱时自动降风险）

    交易分型（enter_tag，用于归因与调参）：
    - bull：顺势主入场（趋势过滤最严格，目标是稳健）
    - cross：趋势启动/均线交叉类机会（更偏“抓启动”，但会更噪声）
    - reentry：趋势中回撤再入（已加更强趋势闸门，避免净拖累）
    - event：事件/异常波动类（若启用，必须更保守的风险预算）

    关键风控（已落地）：
    - reentry 闸门：价格需处于长期 EMA 之上，且短长 EMA 乖离达到阈值，避免弱势反弹里反复试错
    - bull 尾部收敛：仅当浮亏超过最小亏损阈值时，才允许启用 ATR 动态止损（避免牛市正常回踩被洗出）
    - 弱势 bull 降仓：更长 lookback 的弱势体制下，bull 档位自动降风险，降低结构性下行的回撤与亏损

    已验证回测与复现入口（跨设备可用，避免每次都重跑）：
    - 基准口径（smallaccount 默认）：
      - OKX spot，BTC/USDT，4h
      - dry_run_wallet=10，max_open_trades=1，fee=0.0006
      - 稳定性门槛：每窗口 trades≥5、profit>0、maxDD≤20%
    - 关键结果摘要（年度窗口 2020-2025，riskB 口径，2026-01-12；具体以报告为准）：
      - 最大回撤：≤ 19.04%（最差窗口 2021）
      - 唯一亏损年份：2022 -0.97%（已压到接近打平）
      - 牛市捕获示例（策略收益 vs 大盘涨幅）：2020 98.57% vs 187.69%，2023 52.91% vs 155.01%，2024 46.20% vs 118.52%
    - 核心痛点（跨年稳定性）：
      - 2021/2022：bull 类交易在急跌/弱势阶段更易吃到固定 -10% stoploss（尾部风险主要来源）
      - reentry：在弱趋势/反弹阶段容易净拖累（已通过更强趋势闸门抑制）
      - 单币种 long-only：想更“不跑输牛市”通常意味着更高 time-in-market，但会抬高回撤（天然权衡）
    - 综合结论与复现实验口径（已提交到 git，跨设备可直接打开）：
      - docs/reports/small_account_benchmark_SmallAccountTrendFilteredV1_4h_2026-01-12.md
      - docs/reports/risk_pain_points_SmallAccountTrendFilteredV1_4h_2026-01-12.md
      - docs/reports/change_summary_2026-01-12.md
    - 复现命令（会生成本地产物到 artifacts/benchmarks/，默认不随 git 同步）：
      - ./scripts/analysis/small_account_benchmark.ps1 -Strategy "SmallAccountTrendFilteredV1" -Pairs @("BTC/USDT") -Timeframe "4h"
      - ./scripts/analysis/small_account_benchmark.ps1 -Strategy "SmallAccountTrendFilteredV1" -Pairs @("BTC/USDT") -Timeframe "4h" -Timeranges @("20200101-20201231","20210101-20211231","20220101-20221231","20230101-20231231","20240101-20241231","20250101-20251231")

    重要说明：
    - 不承诺任何实盘收益；这是一个“可验证、可迭代”的基线策略。
    - 若数据从 2023 开始，任何超长周期指标都会存在“前置历史不足”的冷启动期，请用多窗口回测评估稳定性。
    - 为了避免牛市“掉队”，会用更宽松的追踪止损来减少过早离场（并通过回测基准验证回撤上限）。
    """

    INTERFACE_VERSION = 3

    timeframe = "4h"
    startup_candle_count = 240

    # 趋势策略：尽量不靠 ROI “到点就走”，主要依赖追踪止损让利润奔跑
    minimal_roi = {"0": 100}

    # 黑天鹅兜底
    stoploss = -0.10

    # 追踪止损：趋势段给利润更大呼吸空间，降低“提前下车”导致的牛市跑输
    trailing_stop = True
    trailing_stop_positive_offset = 0.08
    trailing_stop_positive = 0.06
    trailing_only_offset_is_reached = True

    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False

    # 保护：避免刚出场就立刻“打回去”（尤其是追踪止损触发后）
    protections = [
        {"method": "CooldownPeriod", "stop_duration_candles": 1},
        {
            "method": "StoplossGuard",
            "lookback_period_candles": 48,
            "trade_limit": 1,
            "stop_duration_candles": 12,
            "only_per_pair": True,
        },
    ]

    use_custom_stoploss = True

    # --- 参数（保守范围，避免过拟合）---
    buy_ema_short_len = IntParameter(10, 30, default=20, space="buy", optimize=True)
    buy_ema_long_len = IntParameter(50, 180, default=120, space="buy", optimize=True)
    buy_adx = IntParameter(12, 35, default=20, space="buy", optimize=True)

    # EMA 长期上行过滤：对比 N 根 K 线前的值
    buy_ema_slope_lookback = IntParameter(2, 12, default=6, space="buy", optimize=True)

    # EMA 长期“有效上行”阈值（百分比口径）：避免弱趋势/震荡里反复进出
    buy_ema_long_min_slope = DecimalParameter(
        0.0, 0.02, default=0.0, decimals=3, space="buy", optimize=True
    )

    # 追高抑制：价格偏离短 EMA 过远时不追（默认 6%）
    buy_max_ema_short_offset = DecimalParameter(
        0.01, 0.12, default=0.06, decimals=3, space="buy", optimize=True
    )

    # 牛市模式（不掉队）：当价格显著高于长期 EMA 时，允许在“趋势过滤仍成立”的前提下更积极再入
    buy_bull_ema_long_offset = DecimalParameter(
        0.02, 0.20, default=0.08, decimals=3, space="buy", optimize=True
    )

    # 趋势强度补充：EMA 乖离最小值（百分比口径），避免“刚上穿一点点”就进
    buy_min_ema_spread = DecimalParameter(
        0.0, 0.05, default=0.005, decimals=3, space="buy", optimize=True
    )

    # 回踩再入（reentry）专用：更强趋势闸门，避免弱趋势里的“反抽再上穿”净拖累
    buy_reentry_min_ema_long_offset = DecimalParameter(
        0.0, 0.10, default=0.02, decimals=3, space="buy", optimize=False
    )
    buy_reentry_min_ema_spread = DecimalParameter(
        0.0, 0.05, default=0.01, decimals=3, space="buy", optimize=False
    )

    # --- 风险开关因子（可回测，默认关闭）---
    # 高阶趋势（宏观体制）过滤：用日线均线做 risk-on / risk-off 门控
    macro_pair = "BTC/USDT"
    macro_timeframe = "1d"

    buy_use_macro_trend_filter = BooleanParameter(default=False, space="buy", optimize=False)
    buy_macro_sma_period = IntParameter(100, 300, default=200, space="buy", optimize=False)
    buy_macro_sma_slope_lookback = IntParameter(5, 60, default=20, space="buy", optimize=False)
    buy_macro_sma_min_slope = DecimalParameter(0.0, 0.05, default=0.0, decimals=3, space="buy", optimize=False)

    # 波动率上限过滤：避免极端波动时“追涨/抄底”导致止损链条
    buy_use_atr_pct_max_filter = BooleanParameter(default=False, space="buy", optimize=False)
    buy_atr_pct_max = DecimalParameter(0.01, 0.20, default=0.10, decimals=3, space="buy", optimize=False)

    # 流动性代理：用成交量相对均值过滤“低流动性/低活跃”时段（对 BTC 通常影响很小）
    buy_use_volume_ratio_filter = BooleanParameter(default=False, space="buy", optimize=False)
    buy_volume_ratio_lookback = IntParameter(12, 240, default=72, space="buy", optimize=False)
    buy_volume_ratio_min = DecimalParameter(0.5, 1.5, default=0.8, decimals=3, space="buy", optimize=False)

    # 门控可观测性：输出 gate funnel（通过率/边际卡口贡献）到策略实例缓存（默认关闭）
    buy_debug_gate_stats = BooleanParameter(default=False, space="buy", optimize=False)

    # --- 风险预算折扣（软风险开关，默认关闭）---
    # 说明：不改变“信号逻辑”，只在仓位层面做 0~1 的折扣，
    # 用于降低熊段/高波动/低流动性时的尾部风险，避免出现长期“0 trades”的回测假象。
    buy_use_macro_trend_stake_scale = BooleanParameter(default=False, space="buy", optimize=False)
    buy_macro_stake_scale_floor = DecimalParameter(
        0.05, 1.00, default=0.25, decimals=3, space="buy", optimize=False
    )

    buy_use_atr_pct_stake_scale = BooleanParameter(default=False, space="buy", optimize=False)
    buy_atr_pct_soft_start = DecimalParameter(
        0.01, 0.20, default=0.06, decimals=3, space="buy", optimize=False
    )
    buy_atr_pct_soft_end = DecimalParameter(
        0.01, 0.20, default=0.12, decimals=3, space="buy", optimize=False
    )
    buy_atr_pct_soft_floor = DecimalParameter(
        0.05, 1.00, default=0.25, decimals=3, space="buy", optimize=False
    )

    buy_use_volume_ratio_stake_scale = BooleanParameter(default=False, space="buy", optimize=False)
    buy_volume_ratio_soft_min = DecimalParameter(
        0.20, 1.50, default=0.70, decimals=3, space="buy", optimize=False
    )
    buy_volume_ratio_soft_target = DecimalParameter(
        0.20, 1.50, default=1.00, decimals=3, space="buy", optimize=False
    )
    buy_volume_ratio_soft_floor = DecimalParameter(
        0.05, 1.00, default=0.25, decimals=3, space="buy", optimize=False
    )

    # ATR 自适应止损：把“最坏单笔亏损”从固定 -10% 收敛到“随波动率变化”的区间
    # 说明：止损触发的“趋势走弱判断”使用 sell_ema_slope_lookback（更长窗口），
    # 避免牛市回撤中的短暂 EMA 回落就过早触发止损。
    sell_ema_slope_lookback = IntParameter(6, 60, default=24, space="sell", optimize=True)

    sell_stop_atr_mult = DecimalParameter(
        2.0, 8.0, default=5.0, decimals=2, space="sell", optimize=True
    )
    sell_stop_min_loss = DecimalParameter(
        0.01, 0.06, default=0.03, decimals=3, space="sell", optimize=True
    )
    sell_bear_max_loss = DecimalParameter(
        0.03, 0.12, default=0.06, decimals=3, space="sell", optimize=True
    )

    # 动态风险预算（仓位管理）
    # 目标：在不改变“信号逻辑”的前提下，通过仓位分档更贴合 smallaccount 的“稳健/控回撤”目标，
    # 同时在强趋势（尤其牛市）里尽量不掉队。
    buy_stake_frac_bull = DecimalParameter(
        0.10, 1.00, default=1.00, decimals=3, space="buy", optimize=False
    )
    buy_stake_frac_strong = DecimalParameter(
        0.10, 1.00, default=0.90, decimals=3, space="buy", optimize=False
    )
    buy_stake_frac_normal = DecimalParameter(
        0.10, 1.00, default=0.75, decimals=3, space="buy", optimize=False
    )
    buy_stake_frac_weak = DecimalParameter(
        0.05, 1.00, default=0.50, decimals=3, space="buy", optimize=False
    )
    buy_stake_frac_bull_weak = DecimalParameter(
        0.05, 1.00, default=0.25, decimals=3, space="buy", optimize=False
    )

    # 用更长窗口判定“宏观弱势”（避免熊市反弹把 4 天斜率拉成正就误判为强势）
    buy_stake_weak_regime_lookback = IntParameter(12, 240, default=72, space="buy", optimize=False)
    buy_stake_strong_adx_delta = IntParameter(0, 20, default=5, space="buy", optimize=False)
    buy_stake_strong_spread_delta = DecimalParameter(
        0.0, 0.05, default=0.01, decimals=3, space="buy", optimize=False
    )
    buy_stake_strong_slope_delta = DecimalParameter(
        0.0, 0.02, default=0.005, decimals=3, space="buy", optimize=False
    )

    def informative_pairs(self):
        """
        宏观过滤需要额外 timeframe 数据（默认：BTC/USDT 1d）。
        """
        return [(str(self.macro_pair), str(self.macro_timeframe))]

    def _get_macro_informative_dataframe(self) -> DataFrame | None:
        dp = getattr(self, "dp", None)
        if dp is None:
            return None

        cached = getattr(self, "_macro_inf_df", None)
        if isinstance(cached, DataFrame) and not cached.empty:
            return cached

        pair = str(getattr(self, "macro_pair", "BTC/USDT"))
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
        动态风险预算（仓位管理）：
        - 牛市/强趋势：尽量用满可用资金（不掉队）
        - 趋势一般：用中等仓位，降低噪声期回撤
        - 长期趋势走弱：主动降风险，减少熊段尾部单笔亏损对账户的伤害

        说明：
        - 返回值为“本次下单 stake_amount”。
        - 返回 0 / None 会阻止开仓，但本策略默认不使用“仓位层面的强制禁入”，而是只做降风险。
        """
        if str(side).lower() != "long":
            return float(proposed_stake)

        # dp 在回测/实盘可用；若不可用则回退到默认 stake
        dp = getattr(self, "dp", None)
        if dp is None:
            return float(proposed_stake)

        df = get_analyzed_dataframe_upto_time(dp, pair=pair, timeframe=self.timeframe, current_time=current_time)
        if df is None or df.empty:
            return float(proposed_stake)

        stake_frac = self._pick_stake_fraction(
            df=df,
            entry_tag=(str(entry_tag).strip().lower() if entry_tag else ""),
        )
        if not np.isfinite(stake_frac) or stake_frac <= 0:
            return float(proposed_stake)

        stake_frac = float(max(0.0, min(1.0, stake_frac)))
        risk_mult = self._risk_stake_multiplier(df=df)
        if np.isfinite(risk_mult) and risk_mult > 0:
            stake_frac = float(max(0.0, min(1.0, stake_frac * float(min(1.0, risk_mult)))))

        # unlimited 模式下用 max_stake 作为基准；固定 stake 下只做“缩小”，不做放大
        cfg_stake_amount = str(getattr(self, "config", {}).get("stake_amount", "")).strip().lower()
        base_stake = float(max_stake) if cfg_stake_amount == "unlimited" else float(proposed_stake)
        stake = float(base_stake * stake_frac)

        # 保底约束：尊重 max/min stake
        stake = float(min(stake, float(max_stake)))
        if min_stake is not None and np.isfinite(float(min_stake)):
            stake = float(max(stake, float(min_stake)))

        return stake

    def _pick_stake_fraction(self, *, df: DataFrame, entry_tag: str) -> float:
        """
        根据趋势强度选择仓位档位（返回 0~1 的比例）。

        注意：本函数不应抛异常，避免影响回测/实盘稳定性。
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

            # 长期趋势走弱（与 custom_stoploss 同口径）：优先降风险
            weak_regime = False
            weak_n = int(self.buy_stake_weak_regime_lookback.value)
            if weak_n > 0 and len(df) > weak_n:
                ema_then = float(df[ema_l_col].iloc[-1 - weak_n])
                if np.isfinite(ema_then) and ema_then > 0 and ema_l < ema_then:
                    weak_regime = True

            # 牛市模式（优先不掉队）
            bull_offset = float(self.buy_bull_ema_long_offset.value)
            bull_mode = close > (ema_l * (1.0 + bull_offset))

            if weak_regime:
                # 长期趋势走弱时，优先控回撤：
                # - 趋势启动（cross）是“反转/起涨”的关键开端：仍保留中等仓位，避免错过主升段
                # - bull 模式（高于长期 EMA 较多）在弱势反弹中更容易被打回去：不再满仓
                if entry_tag == "cross":
                    return float(self.buy_stake_frac_normal.value)
                if entry_tag == "bull" or bull_mode:
                    return float(self.buy_stake_frac_bull_weak.value)
                return float(self.buy_stake_frac_weak.value)

            if entry_tag == "bull" or bull_mode:
                return float(self.buy_stake_frac_bull.value)

            # 强趋势判定：比入场阈值更“苛刻”一点，用于加大仓位
            spread = (ema_s / ema_l) - 1.0
            strong_adx = adx >= (int(self.buy_adx.value) + int(self.buy_stake_strong_adx_delta.value))

            min_spread = float(self.buy_min_ema_spread.value)
            strong_spread = spread >= (min_spread + float(self.buy_stake_strong_spread_delta.value))

            strong_slope = False
            slope_n = int(self.buy_ema_slope_lookback.value)
            min_slope = float(self.buy_ema_long_min_slope.value)
            if slope_n > 0 and len(df) > slope_n:
                ema_then = float(df[ema_l_col].iloc[-1 - slope_n])
                if np.isfinite(ema_then) and ema_then > 0:
                    slope_pct = (ema_l / ema_then) - 1.0
                    strong_slope = slope_pct >= (min_slope + float(self.buy_stake_strong_slope_delta.value))

            if strong_adx and strong_spread and strong_slope:
                return float(self.buy_stake_frac_strong.value)

            return float(self.buy_stake_frac_normal.value)
        except Exception:
            return 1.0

    def _risk_stake_multiplier(self, *, df: DataFrame) -> float:
        """
        软风险开关：把宏观/波动率/流动性映射为 0~1 的仓位折扣（仅在仓位层面生效）。
        """
        try:
            if df is None or df.empty:
                return 1.0

            last = df.iloc[-1]
            mult = 1.0

            # 宏观体制：日线收盘在 SMA 下方时，仓位打折；SMA 斜率越弱，折扣越大
            if bool(self.buy_use_macro_trend_stake_scale.value):
                inf_tf = str(getattr(self, "macro_timeframe", "1d"))
                macro_close_col = f"macro_close_{inf_tf}"
                macro_sma_col = f"macro_sma_{inf_tf}"
                mult *= float(
                    macro_sma_soft_scale(
                        df,
                        macro_close_col=macro_close_col,
                        macro_sma_col=macro_sma_col,
                        is_long=True,
                        floor=float(self.buy_macro_stake_scale_floor.value),
                        slope_lookback=int(self.buy_macro_sma_slope_lookback.value),
                        min_slope=float(self.buy_macro_sma_min_slope.value),
                    )
                )

            # 波动率上限：atr_pct 越高，仓位越小（线性折扣）
            if bool(self.buy_use_atr_pct_stake_scale.value):
                atr_pct = float(last.get("atr_pct", np.nan))
                if np.isfinite(atr_pct) and atr_pct > 0:
                    mult *= float(
                        linear_scale_down(
                            value=atr_pct,
                            start_value=float(self.buy_atr_pct_soft_start.value),
                            end_value=float(self.buy_atr_pct_soft_end.value),
                            floor=float(self.buy_atr_pct_soft_floor.value),
                        )
                    )

            # 流动性代理：volume_ratio 越低，仓位越小（从 min -> target 线性恢复）
            if bool(self.buy_use_volume_ratio_stake_scale.value):
                vr = float(last.get("volume_ratio", np.nan))
                if np.isfinite(vr) and vr > 0:
                    mult *= float(
                        linear_scale_up(
                            value=vr,
                            min_value=float(self.buy_volume_ratio_soft_min.value),
                            target_value=float(self.buy_volume_ratio_soft_target.value),
                            floor=float(self.buy_volume_ratio_soft_floor.value),
                        )
                    )

            return float(max(0.0, min(1.0, mult)))
        except Exception:
            return 1.0

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        short_len = int(self.buy_ema_short_len.value)
        long_len = int(self.buy_ema_long_len.value)

        df = dataframe.copy()
        templates = get_factor_templates("SmallAccountTrendFilteredV1")
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
            vol_lb = int(self.buy_volume_ratio_lookback.value)
            if vol_lb > 0:
                factor_names.append(f"volume_ratio_{vol_lb}")

        df = get_container().factor_usecase().execute(df, factor_names)
        df = self._merge_macro_indicators(df)
        return df.replace([np.inf, -np.inf], np.nan)

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

    def custom_stoploss(
        self,
        pair: str,
        trade: Trade,
        current_time: datetime,
        current_rate: float,
        current_profit: float,
        after_fill: bool,
        **kwargs,
    ) -> float | None:
        """
        ATR 动态止损（仅做多，spot 风险口径）：
        - 默认仅在“长期趋势走弱”时启用：把尾部风险收敛到更合理区间
        - 但对 `enter_tag=bull` 的交易更敏感：即使长期 EMA 仍上行，也允许启用 ATR 动态止损，
          避免 bull 模式在急跌/回撤中频繁吃满固定 -10% 止损
        - 基于入场时 ATR 计算“绝对止损价”
        - 用最小亏损阈值避免止损过紧（减少噪声止损）
        - 不允许超过策略兜底 stoploss（避免单笔尾部风险过大）
        """
        entry_atr = trade.get_custom_data("entry_atr")
        if entry_atr is None:
            return None

        try:
            entry_atr = float(entry_atr)
        except Exception:
            return None

        open_rate = float(trade.open_rate)
        current_rate = float(current_rate)
        if (
            not np.isfinite(entry_atr)
            or entry_atr <= 0
            or not np.isfinite(open_rate)
            or open_rate <= 0
            or not np.isfinite(current_rate)
            or current_rate <= 0
        ):
            return None

        # 趋势强势（EMA 长期上行）时不收紧止损，避免被“噪声止损”反复洗出
        dp = getattr(self, "dp", None)
        if dp is None:
            return None
        df = get_analyzed_dataframe_upto_time(dp, pair=pair, timeframe=self.timeframe, current_time=current_time)
        if df is None or df.empty:
            return None

        long_len = int(self.buy_ema_long_len.value)
        ema_col = f"ema_long_{long_len}"
        slope_n = int(self.sell_ema_slope_lookback.value)
        if ema_col not in df.columns or len(df) <= slope_n:
            return None

        try:
            ema_now = float(df[ema_col].iloc[-1])
            ema_then = float(df[ema_col].iloc[-1 - slope_n])
        except Exception:
            return None
        # 是否需要启用 ATR 动态止损：
        # - 长期 EMA 走弱：回看窗口内出现下行（原逻辑）
        # - 或者 bull 交易：对急跌更敏感，避免频繁吃满固定 -10% 止损
        long_ema_weak = bool(np.isfinite(ema_now) and np.isfinite(ema_then) and ema_now < ema_then)

        # bull 交易的“尾部风险”更敏感，但不能太早收紧（避免牛市正常回踩就被洗出）。
        # 因此仅当浮亏超过最小亏损阈值（sell_stop_min_loss）时，才允许启用 ATR 动态止损。
        min_loss_gate = float(self.sell_stop_min_loss.value)
        if not np.isfinite(min_loss_gate) or min_loss_gate <= 0:
            min_loss_gate = 0.03

        enter_tag = str(getattr(trade, "enter_tag", "") or "").strip().lower()
        bull_sensitive = bool(
            enter_tag == "bull"
            and np.isfinite(float(current_profit))
            and float(current_profit) <= -float(min_loss_gate)
        )

        if not long_ema_weak and not bull_sensitive:
            return None

        # 目标止损价：open - ATR*mult
        atr_mult = float(self.sell_stop_atr_mult.value)
        stop_rate = open_rate - (entry_atr * atr_mult)
        if not np.isfinite(stop_rate) or stop_rate <= 0:
            return None

        # 把止损宽度约束在 [min_loss, max_loss]（按“入场价”口径）
        max_loss = abs(float(self.stoploss)) if np.isfinite(float(self.stoploss)) else 0.10
        if not np.isfinite(max_loss) or max_loss <= 0:
            max_loss = 0.10

        bear_max = float(self.sell_bear_max_loss.value)
        if np.isfinite(bear_max) and bear_max > 0:
            max_loss = min(max_loss, bear_max)

        min_loss = float(self.sell_stop_min_loss.value)
        if not np.isfinite(min_loss) or min_loss <= 0:
            min_loss = 0.03
        if max_loss < min_loss:
            min_loss = max_loss

        stop_rate_min = open_rate * (1.0 - max_loss)
        stop_rate_max = open_rate * (1.0 - min_loss)
        if stop_rate_max < stop_rate_min:
            stop_rate_max = stop_rate_min

        stop_rate = max(stop_rate, stop_rate_min)
        stop_rate = min(stop_rate, stop_rate_max)

        desired_sl = float(
            stoploss_from_absolute(
                stop_rate=stop_rate,
                current_rate=current_rate,
                is_short=False,
                leverage=1.0,
            )
        )
        if not np.isfinite(desired_sl) or desired_sl <= 0:
            return None

        return desired_sl

    def populate_entry_trend(self, df: DataFrame, metadata: dict) -> DataFrame:
        df["enter_long"] = 0
        df["enter_tag"] = ""

        short_len = int(self.buy_ema_short_len.value)
        long_len = int(self.buy_ema_long_len.value)
        adx_val = int(self.buy_adx.value)
        slope_n = int(self.buy_ema_slope_lookback.value)
        min_slope = float(self.buy_ema_long_min_slope.value)

        if short_len >= long_len:
            return df

        ema_s = df[f"ema_short_{short_len}"]
        ema_l = df[f"ema_long_{long_len}"]

        # 宏观体制过滤（默认关闭）：日线 close 必须高于 SMA，且 SMA 在窗口内“有效上行”
        inf_tf = str(getattr(self, "macro_timeframe", "1d"))
        macro_close_col = f"macro_close_{inf_tf}"
        macro_sma_col = f"macro_sma_{inf_tf}"
        macro_ok = macro_sma_regime_ok(
            df,
            enabled=bool(self.buy_use_macro_trend_filter.value),
            macro_close_col=macro_close_col,
            macro_sma_col=macro_sma_col,
            is_long=True,
            require_columns=True,
            slope_lookback=int(self.buy_macro_sma_slope_lookback.value),
            min_slope=float(self.buy_macro_sma_min_slope.value),
            fail_open=False,
        )

        # 趋势过滤：EMA 长期必须“有效上行”（避免震荡市频繁“假突破”）
        ema_l_up = ema_trend_ok(ema_l, lookback=slope_n, min_slope=min_slope, direction="up")

        # 趋势强度补充：短长 EMA 乖离必须达到阈值（避免弱趋势反复上穿）
        min_spread = float(self.buy_min_ema_spread.value)
        ema_spread = (ema_s / ema_l) - 1.0
        ema_spread_ok = ema_spread > min_spread

        # 动量确认：MACD 柱体为正（更偏“牛市不掉队”的趋势跟随）
        macd_ok = df["macdhist"] > 0

        # 波动率过滤：必须有足够波动覆盖手续费与噪声（经验阈值：0.4%）
        vol_ok = atr_pct_range_ok(
            df,
            min_pct=0.004,
            use_max_filter=bool(self.buy_use_atr_pct_max_filter.value),
            max_pct=float(self.buy_atr_pct_max.value),
        )

        trend_up = ema_s > ema_l

        # 入场事件（趋势启动 / 回踩再上穿）：减少震荡期持续“贴着条件就进”
        reentry_min_offset = float(self.buy_reentry_min_ema_long_offset.value)
        reentry_min_spread = float(self.buy_reentry_min_ema_spread.value)
        cross_up = crossed_above(ema_s, ema_l)
        reentry = reentry_event(
            df["close"],
            ema_s,
            ema_l,
            side="long",
            min_long_offset=reentry_min_offset,
            spread_metric=ema_spread,
            min_spread=reentry_min_spread,
        )
        entry_event = cross_up | reentry

        # 牛市模式：显著高于长期 EMA 时，允许“趋势内再入”，提升 time-in-market
        bull_offset = float(self.buy_bull_ema_long_offset.value)
        bull_mode_mask = bull_mode(df["close"], ema_l, offset=bull_offset)

        entry_signal = entry_event | bull_mode_mask

        # 抑制追高：价格距离短 EMA 过远时不追，尽量等回踩/回补后再进
        max_offset = float(self.buy_max_ema_short_offset.value)
        not_too_far = price_not_too_far_from_ema(df["close"], ema_s, max_offset=max_offset, side="long")

        # 动量二次确认：优先在“向上推进”的 K 线上入场，避免下跌过程里反复抄底
        momentum_up = momentum_ok(df["close"], side="long")

        # 流动性代理：低活跃时段降低入场（对 BTC 通常影响很小，但对多币种更关键）
        liq_ok = volume_ratio_min_ok(
            df,
            enabled=bool(self.buy_use_volume_ratio_filter.value),
            min_ratio=float(self.buy_volume_ratio_min.value),
            require_column=True,
            fail_open=False,
        )

        gates = [
            ("volume", df["volume"] > 0),
            ("macro", macro_ok),
            ("entry_signal", entry_signal),
            ("trend_state", trend_up),
            ("close_above_ema_s", (df["close"] > ema_s)),
            ("not_too_far", not_too_far),
            ("momentum", momentum_up),
            ("adx", (df["adx"] > adx_val)),
            ("ema_long_trend", ema_l_up),
            ("ema_spread", ema_spread_ok),
            ("atr_pct", vol_ok),
            ("macdhist", macd_ok),
            ("liquidity", liq_ok),
        ]
        if bool(self.buy_debug_gate_stats.value):
            enter, funnel = gate_funnel(gates, index=df.index, fillna=True)
            pair = str(metadata.get("pair", "")).strip()
            cache = getattr(self, "_gate_funnel_cache", None)
            if not isinstance(cache, dict):
                cache = {}
                setattr(self, "_gate_funnel_cache", cache)
            cache[(pair, "long")] = [r.to_dict() for r in funnel]

            logged = getattr(self, "_gate_funnel_logged", None)
            if not isinstance(logged, set):
                logged = set()
                setattr(self, "_gate_funnel_logged", logged)
            log_key = (pair, "long")
            if pair and log_key not in logged:
                logged.add(log_key)
                logger.info("门控漏斗 %s %s: %s", pair, "long", render_gate_funnel_summary(funnel, top_k=3))
        else:
            enter = combine_gates(gates, index=df.index, fillna=True)

        df.loc[enter, "enter_long"] = 1

        # 记录 enter_tag：便于在回测结果里拆分分析（results_per_enter_tag）
        # 优先级：bull > cross > reentry > event
        df.loc[enter & bull_mode_mask.fillna(False), "enter_tag"] = "bull"
        df.loc[enter & ~bull_mode_mask.fillna(False) & cross_up.fillna(False), "enter_tag"] = "cross"
        df.loc[
            enter & ~bull_mode_mask.fillna(False) & ~cross_up.fillna(False) & reentry.fillna(False),
            "enter_tag",
        ] = "reentry"
        df.loc[
            enter
            & (df["enter_tag"] == ""),
            "enter_tag",
        ] = "event"
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
        cross_down = crossed_below(ema_s, ema_l)

        df.loc[((df["volume"] > 0) & cross_down), "exit_long"] = 1
        return df
