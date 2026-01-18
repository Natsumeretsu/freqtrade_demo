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

from trading_system.application.timing_audit import TimingAuditParams, continuous_score_from_thresholds, precompute_quantile_thresholds
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
    - 每个 timeframe 支持多因子加权连续评分（更像“投影/加权和”，默认取 TopK=3）
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

    # 方案 A（保守）：收紧止损止盈，提升盈亏比至 1.5
    minimal_roi = {
        "0": 0.12,    # 12% 立即止盈
        "30": 0.10,   # 30 分钟后 10%
        "60": 0.08,   # 1 小时后 8%
        "120": 0.06,  # 2 小时后 6%
        "240": 0.04   # 4 小时后 4%
    }
    stoploss = -0.08  # 从 -20% 收紧至 -8%

    # 调整追踪止损：提高激活点和追踪距离
    trailing_stop = True
    trailing_stop_positive_offset = 0.05  # 从 2% 提高至 5%
    trailing_stop_positive = 0.02         # 从 1% 提高至 2%
    trailing_only_offset_is_reached = True

    use_exit_signal = False
    exit_profit_only = False
    ignore_roi_if_entry_signal = False

    # --- 可调参数（默认不参与优化） ---
    buy_main_quantiles = IntParameter(3, 10, default=5, space="buy", optimize=False)
    buy_main_lookback_days = IntParameter(3, 15, default=14, space="buy", optimize=False)
    buy_main_entry_threshold = DecimalParameter(0.10, 1.00, default=0.67, decimals=2, space="buy", optimize=False)
    buy_main_exit_threshold = DecimalParameter(0.10, 1.00, default=0.67, decimals=2, space="buy", optimize=False)

    buy_confirm_quantiles = IntParameter(3, 10, default=5, space="buy", optimize=False)
    buy_confirm_lookback_days = IntParameter(5, 60, default=30, space="buy", optimize=False)
    buy_confirm_entry_threshold = DecimalParameter(0.10, 1.00, default=0.67, decimals=2, space="buy", optimize=False)
    buy_confirm_exit_threshold = DecimalParameter(0.10, 1.00, default=0.67, decimals=2, space="buy", optimize=False)

    buy_fusion_main_weight = DecimalParameter(0.0, 1.0, default=0.70, decimals=2, space="buy", optimize=False)
    buy_fusion_confirm_weight = DecimalParameter(0.0, 1.0, default=0.30, decimals=2, space="buy", optimize=False)
    buy_fusion_entry_threshold = DecimalParameter(0.10, 1.00, default=0.90, decimals=2, space="buy", optimize=False)
    buy_fusion_exit_threshold = DecimalParameter(0.10, 1.00, default=0.80, decimals=2, space="buy", optimize=False)

    buy_require_confirm = BooleanParameter(default=True, space="buy", optimize=False)
    buy_enable_short = BooleanParameter(default=True, space="buy", optimize=False)

    # futures 杠杆：先给一个保守默认值（收益想更激进可以调高，但回撤与爆仓风险会同步上升）
    buy_leverage_base = DecimalParameter(1.0, 10.0, default=2.0, decimals=2, space="buy", optimize=False)

    # 做空信号强度过滤：只有当 short_score >= 此阈值时才允许做空（0.0 = 不过滤）
    buy_short_score_min = DecimalParameter(0.0, 1.0, default=0.0, decimals=2, space="buy", optimize=False)

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
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        if df is None or df.empty or not factor_specs:
            z = np.zeros(len(df), dtype="float64")
            return z, z, z

        names = [s.name for s in factor_specs if str(s.name).strip()]
        names = list(dict.fromkeys(names))  # 去重保序
        if not names:
            z = np.zeros(len(df), dtype="float64")
            return z, z, z

        missing = [n for n in names if n not in df.columns]
        if missing:
            # 缺列属于“配置/计算不一致”，直接当作无信号（避免误用）
            z = np.zeros(len(df), dtype="float64")
            return z, z, z

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
            return z, z, z

        # 连续强度：每个因子先用 (q_low, q_high) 做鲁棒缩放映射到 [-1, 1]，再进行加权“投影/求和”。
        long_strength = np.zeros(len(df), dtype="float64")
        short_strength = np.zeros(len(df), dtype="float64")
        net_num = np.zeros(len(df), dtype="float64")
        denom_long = 0.0
        denom_short = 0.0
        denom_net = 0.0
        for spec in factor_specs:
            if spec.name not in X.columns:
                continue

            score = continuous_score_from_thresholds(
                x=X[spec.name],
                q_high=q_high[spec.name],
                q_low=q_low[spec.name],
                direction=str(spec.direction),
            )
            w = float(spec.weight)
            if not np.isfinite(w) or w <= 0:
                continue

            denom_net += float(w)
            side = str(spec.side).strip().lower()
            arr = score.to_numpy(dtype="float64")
            if side == "long":
                net_part = np.clip(arr, a_min=0.0, a_max=None)
            elif side == "short":
                net_part = np.clip(arr, a_min=None, a_max=0.0)
            else:
                net_part = arr
            net_num += float(w) * net_part

            if side in {"both", "long"}:
                denom_long += float(w)
                long_strength += float(w) * np.clip(arr, a_min=0.0, a_max=None)
            if side in {"both", "short"}:
                denom_short += float(w)
                short_strength += float(w) * np.clip(-arr, a_min=0.0, a_max=None)

        if not np.isfinite(denom_long) or denom_long <= 0:
            long_score = np.zeros(len(df), dtype="float64")
        else:
            long_score = (long_strength / float(denom_long)).astype("float64")

        if not np.isfinite(denom_short) or denom_short <= 0:
            short_score = np.zeros(len(df), dtype="float64")
        else:
            short_score = (short_strength / float(denom_short)).astype("float64")

        if not np.isfinite(denom_net) or denom_net <= 0:
            net_score = np.zeros(len(df), dtype="float64")
        else:
            net_score = (net_num / float(denom_net)).astype("float64")

        return long_score, short_score, net_score

    @staticmethod
    def _signal_from_net_score(net_score: np.ndarray, *, threshold: float) -> np.ndarray:
        """
        用净投影分数生成多/空/空仓信号：
        - net_score >= +threshold -> 1
        - net_score <= -threshold -> -1
        - 其余 -> 0
        """
        thr = float(threshold)
        if not np.isfinite(thr) or thr <= 0:
            thr = 0.67

        sig = np.zeros(len(net_score), dtype="float64")
        sig[net_score >= thr] = 1.0
        sig[net_score <= -thr] = -1.0
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
        main_exit_thr = float(
            self._policy_setting(scope="main", key="exit_threshold", default=float(self.buy_main_exit_threshold.value))
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
        confirm_exit_thr = float(
            self._policy_setting(scope="confirm", key="exit_threshold", default=float(self.buy_confirm_exit_threshold.value))
        )

        fusion_main_w = float(
            self._policy_setting(scope="fusion", key="main_weight", default=float(self.buy_fusion_main_weight.value))
        )
        fusion_confirm_w = float(
            self._policy_setting(scope="fusion", key="confirm_weight", default=float(self.buy_fusion_confirm_weight.value))
        )
        fusion_thr = float(
            self._policy_setting(scope="fusion", key="entry_threshold", default=float(self.buy_fusion_entry_threshold.value))
        )
        fusion_exit_thr = float(
            self._policy_setting(scope="fusion", key="exit_threshold", default=float(self.buy_fusion_exit_threshold.value))
        )

        # 1) 计算主周期因子
        main_factor_names = [s.name for s in main_specs]
        dataframe = get_container().factor_usecase().execute(dataframe, main_factor_names)

        main_long, main_short, main_net = self._long_short_scores_from_factors(
            df=dataframe,
            factor_specs=main_specs,
            timeframe=str(self.timeframe),
            quantiles=int(main_quantiles),
            lookback_days=int(main_lookback),
        )
        dataframe["timing_main_long_score"] = main_long
        dataframe["timing_main_short_score"] = main_short
        dataframe["timing_main_score"] = main_net.astype("float64")
        dataframe["timing_main_sig"] = self._signal_from_net_score(main_net, threshold=float(main_thr))
        dataframe["timing_main_exit_sig"] = self._signal_from_net_score(main_net, threshold=float(main_exit_thr))

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

                confirm_long, confirm_short, confirm_net = self._long_short_scores_from_factors(
                    df=inf2,
                    factor_specs=confirm_specs,
                    timeframe=inf_tf,
                    quantiles=int(confirm_quantiles),
                    lookback_days=int(confirm_lookback),
                )
                inf2["timing_confirm_long_score"] = confirm_long
                inf2["timing_confirm_short_score"] = confirm_short
                inf2["timing_confirm_score"] = confirm_net.astype("float64")
                inf2["timing_confirm_sig"] = self._signal_from_net_score(confirm_net, threshold=float(confirm_thr))
                inf2["timing_confirm_exit_sig"] = self._signal_from_net_score(
                    confirm_net, threshold=float(confirm_exit_thr)
                )

                informative_small = inf2[
                    [
                        "date",
                        "timing_confirm_long_score",
                        "timing_confirm_short_score",
                        "timing_confirm_score",
                        "timing_confirm_sig",
                        "timing_confirm_exit_sig",
                    ]
                ].copy()
                dataframe = merge_informative_pair(dataframe, informative_small, self.timeframe, inf_tf, ffill=True)

        # 3) 融合（二维投影）：final_score = w_main * main_net + w_confirm * confirm_net
        # 说明：w_* 会先裁剪为非负，再做归一化（防止阈值含义随权重尺度飘移）。
        w_main = float(fusion_main_w) if np.isfinite(fusion_main_w) else 0.0
        w_confirm = float(fusion_confirm_w) if np.isfinite(fusion_confirm_w) else 0.0
        w_main = float(max(0.0, w_main))
        w_confirm = float(max(0.0, w_confirm))

        confirm_score_col = f"timing_confirm_score_{inf_tf}"
        confirm_net_s = dataframe.get(confirm_score_col)
        if confirm_net_s is None:
            w_confirm = 0.0
            confirm_net = np.zeros(len(dataframe), dtype="float64")
        else:
            confirm_net = confirm_net_s.astype("float64").replace([np.inf, -np.inf], np.nan).fillna(0.0).to_numpy(dtype="float64")

        s = float(w_main + w_confirm)
        if not np.isfinite(s) or s <= 0:
            w_main_n = 1.0
            w_confirm_n = 0.0
        else:
            w_main_n = float(w_main / s)
            w_confirm_n = float(w_confirm / s)

        final_score = (w_main_n * main_net + w_confirm_n * confirm_net).astype("float64")
        dataframe["timing_final_score"] = final_score
        dataframe["timing_final_sig"] = self._signal_from_net_score(final_score, threshold=float(fusion_thr))
        dataframe["timing_final_exit_sig"] = self._signal_from_net_score(final_score, threshold=float(fusion_exit_thr))

        return dataframe.replace([np.inf, -np.inf], np.nan)

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["enter_long"] = 0
        dataframe["enter_short"] = 0

        if dataframe is None or dataframe.empty:
            return dataframe

        inf_tf = str(getattr(self, "confirm_timeframe", "1h")).strip() or "1h"
        confirm_score_col = f"timing_confirm_score_{inf_tf}"

        final_sig = dataframe.get("timing_final_sig")
        if final_sig is None:
            return dataframe

        require_confirm = bool(self.buy_require_confirm.value)
        if require_confirm and confirm_score_col not in dataframe.columns:
            return dataframe

        long_ok = final_sig.astype("float64") == 1.0
        short_ok = final_sig.astype("float64") == -1.0
        if require_confirm:
            confirm_net = dataframe[confirm_score_col].astype("float64")
            ok_confirm = confirm_net.notna()
            long_ok = long_ok & ok_confirm
            short_ok = short_ok & ok_confirm

        dataframe.loc[long_ok & (dataframe["volume"] > 0), "enter_long"] = 1
        if bool(self.buy_enable_short.value):
            dataframe.loc[short_ok & (dataframe["volume"] > 0), "enter_short"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["exit_long"] = 0
        dataframe["exit_short"] = 0

        if dataframe is None or dataframe.empty:
            return dataframe

        final_sig = dataframe.get("timing_final_sig")
        final_exit_sig = dataframe.get("timing_final_exit_sig")
        if final_sig is None:
            return dataframe
        if final_exit_sig is None:
            final_exit_sig = final_sig

        # 退出规则（迟滞）：使用融合后的 final_exit_sig 判定是否“仍然保持同向”。
        exit_long = final_exit_sig.astype("float64") != 1.0
        exit_short = final_exit_sig.astype("float64") != -1.0

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
        最后一层准入：
        1. 自动降风险闭环（crit / 恢复期）可直接禁止新开仓
        2. 做空信号强度过滤：只有当 short_score >= buy_short_score_min 时才允许做空
        """
        side_l = str(side).strip().lower()
        if side_l not in {"long", "short"}:
            return True

        dp = getattr(self, "dp", None)
        if dp is None:
            return True

        # 做空信号强度过滤
        if side_l == "short":
            short_min = float(self.buy_short_score_min.value)
            if short_min > 0:
                try:
                    df = get_analyzed_dataframe_upto_time(dp, pair=pair, timeframe=str(self.timeframe), current_time=current_time)
                    if df is not None and not df.empty and "timing_main_short_score" in df.columns:
                        short_score = float(df["timing_main_short_score"].iloc[-1])
                        if not np.isfinite(short_score) or short_score < short_min:
                            logger.info("做空信号强度不足 (%.3f < %.3f)，跳过做空: %s", short_score, short_min, pair)
                            return False
                except Exception as e:
                    logger.debug("做空过滤检查异常: %s", e)

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
