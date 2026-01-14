from __future__ import annotations

from datetime import datetime
import logging
from pathlib import Path
from typing import Any

import numpy as np
from pandas import DataFrame
import yaml

from freqtrade.persistence import Trade
from freqtrade.strategy import BooleanParameter, DecimalParameter, IStrategy, IntParameter, merge_informative_pair

from trading_system.application.timing_audit import TimingAuditParams, position_from_thresholds, precompute_quantile_thresholds
from trading_system.infrastructure.container import get_container
from trading_system.infrastructure.freqtrade_data import get_analyzed_dataframe_upto_time

logger = logging.getLogger(__name__)

class _FactorSpec:
    """
    轻量因子描述结构（避免 dataclass：Freqtrade 的策略加载器在某些路径下会触发 dataclasses 的模块解析问题）。
    """

    __slots__ = ("name", "direction", "side", "weight")

    def __init__(self, *, name: str, direction: str, side: str, weight: float) -> None:
        self.name = str(name)
        self.direction = str(direction)
        self.side = str(side)
        self.weight = float(weight)


class SmallAccountFuturesTimingExecV1(IStrategy):
    """
    小资金合约择时执行器 v1（OKX USDT 本位永续）

    你要解决的核心问题是：
    - “对每个币，用什么因子做择时，短期（30/60天）能不能赚到超额？”

    这类需求不适合在策略里手写一堆 if/else 指标规则：
    - 你真正想要的是：批量造因子 -> 批量体检 -> 只把“过关”的因子塞进一个通用执行器

    本策略就是这个“通用执行器”：
    - 主信号：15m（默认）
    - 复核信号：1h（默认）
    - 每个 timeframe 支持多因子加权投票（默认取 TopK=3 的同权）
    - 信号生成方式与 scripts/qlib/timing_audit.py 一致：滚动分位阈值 -> 多/空/空仓

    配置入口：
    - 在 Freqtrade config 中新增字段：timing_policy_path
      例如：04_shared/config/timing_policy_okx_futures_15m_1h.yaml
    """

    INTERFACE_VERSION = 3
    can_short = True

    timeframe = "15m"
    confirm_timeframe = "1h"

    # 重要：OKX 15m 单次可拉取的 K 线数量有限（约 300/次，Freqtrade 默认最多拼 5 次≈1500）。
    # 因此主周期（15m）的 lookback_days 默认取 14 天（<= 1500/96≈15.6 天）。
    startup_candle_count = 1400

    minimal_roi = {"0": 100}
    stoploss = -0.06

    # 轻量追踪止损：让盈利在短周期里尽量不回吐太多
    trailing_stop = True
    trailing_stop_positive_offset = 0.02
    trailing_stop_positive = 0.01
    trailing_only_offset_is_reached = True

    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False

    # --- 可调参数（默认不参与优化） ---
    buy_main_quantiles = IntParameter(3, 10, default=5, space="buy", optimize=False)
    buy_main_lookback_days = IntParameter(3, 15, default=14, space="buy", optimize=False)
    buy_main_entry_threshold = DecimalParameter(0.10, 1.00, default=0.67, decimals=2, space="buy", optimize=False)

    buy_confirm_quantiles = IntParameter(3, 10, default=5, space="buy", optimize=False)
    buy_confirm_lookback_days = IntParameter(5, 60, default=30, space="buy", optimize=False)
    buy_confirm_entry_threshold = DecimalParameter(0.10, 1.00, default=0.67, decimals=2, space="buy", optimize=False)

    buy_require_confirm = BooleanParameter(default=True, space="buy", optimize=False)
    buy_enable_short = BooleanParameter(default=True, space="buy", optimize=False)

    # futures 杠杆：先给一个保守默认值（收益想更激进可以调高，但回撤与爆仓风险会同步上升）
    buy_leverage_base = DecimalParameter(1.0, 10.0, default=2.0, decimals=2, space="buy", optimize=False)

    def informative_pairs(self):
        """
        为每个交易对拉取 confirm_timeframe（默认 1h）数据，用于复核信号。
        """
        dp = getattr(self, "dp", None)
        if dp is not None:
            try:
                pairs = list(dp.current_whitelist())
            except Exception:
                pairs = []
        else:
            pairs = []

        if not pairs:
            try:
                pairs = list((getattr(self, "config", {}) or {}).get("exchange", {}).get("pair_whitelist", []) or [])
            except Exception:
                pairs = []

        tf = str(getattr(self, "confirm_timeframe", "1h")).strip() or "1h"
        return [(str(p), tf) for p in pairs]

    # -------------------------
    # policy 加载与解析
    # -------------------------
    @staticmethod
    def _repo_root() -> Path:
        return Path(__file__).resolve().parents[2]

    def _policy_path(self) -> Path:
        cfg = getattr(self, "config", {}) or {}
        raw = str(cfg.get("timing_policy_path", "")).strip()
        if raw:
            return (self._repo_root() / Path(raw)).resolve()
        return (self._repo_root() / "04_shared/config/timing_policy_okx_futures_15m_1h.yaml").resolve()

    def _load_policy(self) -> dict[str, Any]:
        cached = getattr(self, "_timing_policy_cache", None)
        if isinstance(cached, dict) and "policy" in cached and "path" in cached:
            if Path(str(cached["path"])).resolve() == self._policy_path():
                pol = cached.get("policy")
                if isinstance(pol, dict):
                    return pol

        path = self._policy_path()
        if not path.is_file():
            logger.warning("timing_policy 不存在，使用默认兜底：%s", path.as_posix())
            pol = {"pairs": {}, "defaults": {}}
            setattr(self, "_timing_policy_cache", {"path": path.as_posix(), "policy": pol})
            return pol

        try:
            raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except Exception as e:
            logger.warning("timing_policy 解析失败，使用默认兜底：%s (%s)", path.as_posix(), e)
            raw = {}

        pol = raw if isinstance(raw, dict) else {}
        setattr(self, "_timing_policy_cache", {"path": path.as_posix(), "policy": pol})
        return pol

    def _policy_setting(self, *, scope: str, key: str, default: Any) -> Any:
        pol = self._load_policy()
        block = pol.get(scope, {}) if isinstance(pol.get(scope, {}), dict) else {}
        v = block.get(key)
        return default if v is None else v

    @staticmethod
    def _parse_factor_specs(block: Any) -> list[_FactorSpec]:
        """
        解析 factors 列表：
        - name: 因子名
        - direction: pos/neg
        - side: both/long/short（多空都做/只做多/只做空）
        - weight: 权重（>0）
        """
        if not isinstance(block, list):
            return []

        out: list[_FactorSpec] = []
        for it in block:
            if not isinstance(it, dict):
                continue
            name = str(it.get("name", "")).strip()
            if not name:
                continue
            direction = str(it.get("direction", "pos")).strip().lower()
            if direction not in {"pos", "neg"}:
                direction = "pos"
            side = str(it.get("side", "both")).strip().lower()
            if side not in {"both", "long", "short"}:
                side = "both"
            try:
                w = float(it.get("weight", 1.0))
            except Exception:
                w = 1.0
            if not np.isfinite(w) or w <= 0:
                w = 1.0
            out.append(_FactorSpec(name=name, direction=direction, side=side, weight=float(w)))
        return out

    def _policy_factors_for_pair(self, *, pair: str) -> tuple[list[_FactorSpec], list[_FactorSpec]]:
        """
        返回：main_factors, confirm_factors
        """
        pol = self._load_policy()
        pairs = pol.get("pairs", {}) if isinstance(pol.get("pairs", {}), dict) else {}
        defaults = pol.get("defaults", {}) if isinstance(pol.get("defaults", {}), dict) else {}

        pair_cfg = pairs.get(str(pair), {}) if isinstance(pairs.get(str(pair), {}), dict) else {}

        def _pick(scope: str) -> list[_FactorSpec]:
            # pair 优先，其次 defaults，最后兜底 ema_20/neg
            block = None
            if isinstance(pair_cfg.get(scope, {}), dict):
                block = pair_cfg.get(scope, {}).get("factors")
            if block is None and isinstance(defaults.get(scope, {}), dict):
                block = defaults.get(scope, {}).get("factors")
            specs = self._parse_factor_specs(block)
            if specs:
                return specs
            return [_FactorSpec(name="ema_20", direction="neg", side="both", weight=1.0)]

        return _pick("main"), _pick("confirm")

    # -------------------------
    # 信号计算（与 timing_audit 对齐）
    # -------------------------
    @staticmethod
    def _long_short_scores_from_factors(
        *,
        df: DataFrame,
        factor_specs: list[_FactorSpec],
        timeframe: str,
        quantiles: int,
        lookback_days: int,
    ) -> tuple[np.ndarray, np.ndarray]:
        if df is None or df.empty or not factor_specs:
            z = np.zeros(len(df), dtype="float64")
            return z, z

        names = [s.name for s in factor_specs if str(s.name).strip()]
        names = list(dict.fromkeys(names))  # 去重保序
        if not names:
            z = np.zeros(len(df), dtype="float64")
            return z, z

        missing = [n for n in names if n not in df.columns]
        if missing:
            # 缺列属于“配置/计算不一致”，直接当作无信号（避免误用）
            z = np.zeros(len(df), dtype="float64")
            return z, z

        X = df[names].astype("float64")
        p = TimingAuditParams(
            timeframe=str(timeframe),
            horizon=1,
            quantiles=int(quantiles),
            lookback_days=int(lookback_days),
            fee_rate=0.0,
            slippage_rate=0.0,
            rolling_days=[30],
        )
        q_high, q_low = precompute_quantile_thresholds(X=X, params=p)
        if q_high is None or q_low is None or q_high.empty or q_low.empty:
            z = np.zeros(len(df), dtype="float64")
            return z, z

        long_votes = np.zeros(len(df), dtype="float64")
        short_votes = np.zeros(len(df), dtype="float64")
        denom_long = 0.0
        denom_short = 0.0
        for spec in factor_specs:
            if spec.name not in X.columns:
                continue
            pos = position_from_thresholds(
                x=X[spec.name],
                q_high=q_high[spec.name],
                q_low=q_low[spec.name],
                direction=str(spec.direction),
            ).fillna(0.0)
            w = float(spec.weight)
            if not np.isfinite(w) or w <= 0:
                continue

            side = str(spec.side).strip().lower()
            arr = pos.to_numpy(dtype="float64")
            if side in {"both", "long"}:
                denom_long += float(w)
                long_votes += float(w) * (arr > 0.0).astype("float64")
            if side in {"both", "short"}:
                denom_short += float(w)
                short_votes += float(w) * (arr < 0.0).astype("float64")

        if not np.isfinite(denom_long) or denom_long <= 0:
            long_score = np.zeros(len(df), dtype="float64")
        else:
            long_score = (long_votes / float(denom_long)).astype("float64")

        if not np.isfinite(denom_short) or denom_short <= 0:
            short_score = np.zeros(len(df), dtype="float64")
        else:
            short_score = (short_votes / float(denom_short)).astype("float64")

        return long_score, short_score

    @staticmethod
    def _signal_from_long_short_scores(long_score: np.ndarray, short_score: np.ndarray, *, threshold: float) -> np.ndarray:
        thr = float(threshold)
        if not np.isfinite(thr) or thr <= 0:
            thr = 0.67

        sig = np.zeros(len(long_score), dtype="float64")
        long_ok = long_score >= thr
        short_ok = short_score >= thr

        sig[long_ok & (~short_ok)] = 1.0
        sig[short_ok & (~long_ok)] = -1.0

        # 发生“多空同时满足阈值”的情况时，选更强的一侧；打平则空仓
        both = long_ok & short_ok
        sig[both & (long_score > short_score)] = 1.0
        sig[both & (short_score > long_score)] = -1.0
        return sig

    # -------------------------
    # Freqtrade hooks
    # -------------------------
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        if dataframe is None or dataframe.empty:
            return dataframe

        pair = str((metadata or {}).get("pair", "")).strip()
        main_specs, confirm_specs = self._policy_factors_for_pair(pair=pair)

        main_quantiles = int(self._policy_setting(scope="main", key="quantiles", default=int(self.buy_main_quantiles.value)))
        main_lookback = int(
            self._policy_setting(scope="main", key="lookback_days", default=int(self.buy_main_lookback_days.value))
        )
        main_thr = float(
            self._policy_setting(scope="main", key="entry_threshold", default=float(self.buy_main_entry_threshold.value))
        )

        confirm_quantiles = int(
            self._policy_setting(scope="confirm", key="quantiles", default=int(self.buy_confirm_quantiles.value))
        )
        confirm_lookback = int(
            self._policy_setting(scope="confirm", key="lookback_days", default=int(self.buy_confirm_lookback_days.value))
        )
        confirm_thr = float(
            self._policy_setting(
                scope="confirm", key="entry_threshold", default=float(self.buy_confirm_entry_threshold.value)
            )
        )

        # 1) 计算主周期因子
        main_factor_names = [s.name for s in main_specs]
        dataframe = get_container().factor_usecase().execute(dataframe, main_factor_names)

        main_long, main_short = self._long_short_scores_from_factors(
            df=dataframe,
            factor_specs=main_specs,
            timeframe=str(self.timeframe),
            quantiles=int(main_quantiles),
            lookback_days=int(main_lookback),
        )
        dataframe["timing_main_long_score"] = main_long
        dataframe["timing_main_short_score"] = main_short
        dataframe["timing_main_score"] = (main_long - main_short).astype("float64")
        dataframe["timing_main_sig"] = self._signal_from_long_short_scores(main_long, main_short, threshold=float(main_thr))

        # 2) 计算复核周期因子，并 merge 到主 dataframe
        dp = getattr(self, "dp", None)
        inf_tf = str(getattr(self, "confirm_timeframe", "1h")).strip() or "1h"
        if dp is not None and pair:
            try:
                inf = dp.get_pair_dataframe(pair=pair, timeframe=inf_tf)
            except Exception:
                inf = None
            if inf is not None and not inf.empty and "date" in inf.columns:
                confirm_factor_names = [s.name for s in confirm_specs]
                inf2 = get_container().factor_usecase().execute(inf, confirm_factor_names)

                confirm_long, confirm_short = self._long_short_scores_from_factors(
                    df=inf2,
                    factor_specs=confirm_specs,
                    timeframe=inf_tf,
                    quantiles=int(confirm_quantiles),
                    lookback_days=int(confirm_lookback),
                )
                inf2["timing_confirm_long_score"] = confirm_long
                inf2["timing_confirm_short_score"] = confirm_short
                inf2["timing_confirm_score"] = (confirm_long - confirm_short).astype("float64")
                inf2["timing_confirm_sig"] = self._signal_from_long_short_scores(
                    confirm_long, confirm_short, threshold=float(confirm_thr)
                )

                informative_small = inf2[
                    ["date", "timing_confirm_long_score", "timing_confirm_short_score", "timing_confirm_score", "timing_confirm_sig"]
                ].copy()
                dataframe = merge_informative_pair(dataframe, informative_small, self.timeframe, inf_tf, ffill=True)

        return dataframe.replace([np.inf, -np.inf], np.nan)

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["enter_long"] = 0
        dataframe["enter_short"] = 0

        if dataframe is None or dataframe.empty:
            return dataframe

        inf_tf = str(getattr(self, "confirm_timeframe", "1h")).strip() or "1h"
        confirm_col = f"timing_confirm_sig_{inf_tf}"

        main_sig = dataframe.get("timing_main_sig")
        confirm_sig = dataframe.get(confirm_col)

        if main_sig is None:
            return dataframe

        # confirm 不可用时：可选择 fail-open（不要求 confirm）
        require_confirm = bool(self.buy_require_confirm.value)
        if require_confirm and confirm_sig is None:
            return dataframe

        long_ok = main_sig.astype("float64") == 1.0
        short_ok = main_sig.astype("float64") == -1.0
        if confirm_sig is not None:
            long_ok = long_ok & (confirm_sig.astype("float64") == 1.0)
            short_ok = short_ok & (confirm_sig.astype("float64") == -1.0)

        dataframe.loc[long_ok & (dataframe["volume"] > 0), "enter_long"] = 1
        if bool(self.buy_enable_short.value):
            dataframe.loc[short_ok & (dataframe["volume"] > 0), "enter_short"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["exit_long"] = 0
        dataframe["exit_short"] = 0

        if dataframe is None or dataframe.empty:
            return dataframe

        inf_tf = str(getattr(self, "confirm_timeframe", "1h")).strip() or "1h"
        confirm_col = f"timing_confirm_sig_{inf_tf}"

        main_sig = dataframe.get("timing_main_sig")
        confirm_sig = dataframe.get(confirm_col)
        if main_sig is None:
            return dataframe

        require_confirm = bool(self.buy_require_confirm.value)

        # 退出规则：任一信号不再同向则退出（更偏“快进快出”）
        exit_long = main_sig.astype("float64") != 1.0
        exit_short = main_sig.astype("float64") != -1.0
        if require_confirm and confirm_sig is not None:
            exit_long = exit_long | (confirm_sig.astype("float64") != 1.0)
            exit_short = exit_short | (confirm_sig.astype("float64") != -1.0)

        dataframe.loc[exit_long & (dataframe["volume"] > 0), "exit_long"] = 1
        dataframe.loc[exit_short & (dataframe["volume"] > 0), "exit_short"] = 1
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
        """
        合约杠杆：给一个可控的默认值，并允许自动风控层做缩放。
        """
        side_l = str(side).strip().lower()
        if side_l not in {"long", "short"}:
            return 1.0

        base = float(self.buy_leverage_base.value)
        lev = base if np.isfinite(base) and base > 0 else 1.0

        dp = getattr(self, "dp", None)
        if dp is not None:
            try:
                df = get_analyzed_dataframe_upto_time(dp, pair=pair, timeframe=str(self.timeframe), current_time=current_time)
                if df is not None and not df.empty:
                    decision = get_container().auto_risk_service().decision_with_df(
                        df=df,
                        dp=dp,
                        pair=pair,
                        timeframe=str(self.timeframe),
                        current_time=current_time,
                        side=side_l,
                    )
                    s = float(getattr(decision, "leverage_scale", 1.0))
                    if np.isfinite(s) and s > 0:
                        lev *= float(s)
            except Exception:
                pass

        lev = float(max(1.0, lev))
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
        最后一层准入：自动降风险闭环（crit / 恢复期）可直接禁止新开仓。
        """
        side_l = str(side).strip().lower()
        if side_l not in {"long", "short"}:
            return True

        dp = getattr(self, "dp", None)
        if dp is None:
            return True

        try:
            decision = get_container().auto_risk_service().decision(
                dp=dp,
                pair=pair,
                timeframe=str(self.timeframe),
                current_time=current_time,
                side=side_l,
            )
            if decision is not None and not bool(getattr(decision, "allow_entry", True)):
                return False
        except Exception:
            pass

        return True

    def confirm_trade_exit(
        self,
        pair: str,
        trade: Trade,
        order_type: str,
        amount: float,
        rate: float,
        time_in_force: str,
        exit_reason: str,
        current_time: datetime,
        **kwargs,
    ) -> bool:
        # 退出默认放行（让策略自身 exit 信号与止损/追踪止损生效）
        return True
