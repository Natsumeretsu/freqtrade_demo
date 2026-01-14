"""
factor_audit.py - 因子体检（短周期：15m / 1h）

目标：
- 用“研究层口径”回答：哪些因子在短周期上真的有边际信息（IC/分位收益/成本后收益/换手）？
- 同时输出 30/60 天滚动窗口的稳定性摘要，避免只看全样本平均数。

说明：
- 本仓库已引入真实 Qlib（pyqlib）作为研究层框架；但本脚本的指标口径是本仓库自定义的短周期体检：
  IC/分位收益/成本后收益/换手/滚动稳定性（Qlib 不直接提供完全等价的输出口径），因此仍保留自研实现。
- 输入为 convert_freqtrade_to_qlib.py 产出的单交易对 pkl（OHLCV）。
- 特征计算复用 trading_system.infrastructure.ml.features.compute_features，保证训练/在线一致。

用法示例：
  # 用默认 symbols.yaml 的 pairs（适合小规模）
  uv run python -X utf8 scripts/qlib/factor_audit.py --timeframe 4h --feature-set ml_core

  # 传入更大的研究币池 YAML（推荐）
  uv run python -X utf8 scripts/qlib/factor_audit.py ^
    --timeframe 15m ^
    --symbols-yaml 04_shared/config/symbols_research_okx_futures_top40.yaml ^
    --feature-set cta_core ^
    --horizons 1 4 ^
    --rolling-days 30 60
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd
import yaml

# 确保可导入 03_integration/trading_system（脚本以文件路径运行时，sys.path[0] 会变为 scripts/qlib）
_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "03_integration"))

from trading_system.application.factor_sets import get_factor_templates, render_factor_names  # noqa: E402
from trading_system.application.factor_audit import (  # noqa: E402
    choose_factor_direction,
    normalize_weights,
    rolling_return_summary,
)
from trading_system.domain.symbols import freqtrade_pair_to_symbol  # noqa: E402
from trading_system.infrastructure.config_loader import get_config  # noqa: E402
from trading_system.infrastructure.ml.features import compute_features  # noqa: E402


@dataclass(frozen=True)
class AuditConfig:
    exchange: str
    timeframe: str
    pairs: list[str]
    weights: dict[str, float]
    factor_names: list[str]
    horizons: list[int]
    quantiles: int
    fee_rate: float
    slippage_rate: float
    rolling_days: list[int]
    min_roll_median: float
    min_roll_p10: float
    min_ic_ir: float
    min_top_alpha_btc_net: float
    outdir: Path
    export_series: bool


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="短周期因子体检（IC/分位收益/成本后收益/换手/滚动稳定性）。")
    p.add_argument("--timeframe", default="15m", help="时间周期，例如 15m/1h/4h。")
    p.add_argument("--exchange", default="", help="交易所名（默认读取配置：FREQTRADE_EXCHANGE / paths.yaml）。")
    p.add_argument("--symbols-yaml", default="", help="包含 pairs/weights 的 YAML 文件路径（留空则用 symbols.yaml）。")
    p.add_argument("--pairs", nargs="*", default=None, help="直接传入交易对列表（优先级最高）。")

    p.add_argument(
        "--feature-set",
        default="ml_core",
        help="特征集合名称（来自 04_shared/config/factors.yaml 的 factor_sets）。例如 cta_core / ml_core / SmallAccountFuturesTrendV1。",
    )
    p.add_argument(
        "--strategy-params",
        default="",
        help="策略参数 JSON（例如 01_freqtrade/strategies/SmallAccountFuturesTrendV1.json），用于填充因子模板占位符。",
    )
    p.add_argument(
        "--var",
        action="append",
        default=[],
        help="额外渲染变量（可重复），格式 key=value；会覆盖 strategy-params 的同名变量。",
    )
    p.add_argument("--factors", nargs="*", default=None, help="只评估指定因子名（默认评估 feature-set 渲染出的全部因子）。")

    p.add_argument("--horizons", nargs="*", type=int, default=[1, 4], help="预测步长（K 线数），例如 1 4 16。")
    p.add_argument("--quantiles", type=int, default=5, help="分位数组数（默认 5）。")

    p.add_argument("--fee", type=float, default=0.0006, help="单边手续费率（默认 0.0006 = 6bps）。")
    p.add_argument("--slippage", type=float, default=0.0, help="单边滑点率（默认 0）。")
    p.add_argument("--rolling-days", nargs="*", type=int, default=[30, 60], help="滚动窗口天数，例如 30 60。")

    # --- 因子验收阈值（默认：收益优先，阈值保守；可按需要调严/调松） ---
    p.add_argument(
        "--min-roll-median",
        type=float,
        default=0.0,
        help="通过阈值：滚动窗口收益中位数（默认使用 30d，否则用 rolling-days 的第一个窗口）。",
    )
    p.add_argument(
        "--min-roll-p10",
        type=float,
        default=-0.15,
        help="通过阈值：滚动窗口收益 P10（10分位，越高越稳；默认允许 -0.15（约 -15 个百分点）的 30d 窗口）。",
    )
    p.add_argument(
        "--min-ic-ir",
        type=float,
        default=0.0,
        help="通过阈值：ICIR（=ic_mean/ic_std）最低值；设置为 0 表示不强制要求 ICIR 为正。",
    )
    p.add_argument(
        "--min-top-alpha-btc-net",
        type=float,
        default=0.0,
        help="通过阈值：Top 组合相对 BTC 的成本后超额均值（若 BTC 不在币池中则不参与判定）。",
    )

    p.add_argument("--outdir", default="", help="输出目录（默认 artifacts/factor_audit/<run_id>）。")
    p.add_argument("--run-id", default="", help="输出目录名后缀（可用于实验编号）。")
    p.add_argument("--export-series", action="store_true", help="输出每个因子的明细序列（会产生较多文件）。")
    return p.parse_args()


def _read_symbols_yaml(path: Path) -> tuple[list[str], dict[str, float]]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise ValueError(f"symbols-yaml 必须是 YAML dict：{path.as_posix()}")

    pairs = raw.get("pairs", []) or []
    if not isinstance(pairs, list):
        raise ValueError(f"symbols-yaml 的 pairs 必须是 list：{path.as_posix()}")

    out_pairs = [str(p).strip() for p in pairs if str(p).strip()]
    if not out_pairs:
        raise ValueError(f"symbols-yaml 的 pairs 为空：{path.as_posix()}")

    weights_raw = raw.get("weights", {}) or {}
    weights: dict[str, float] = {}
    if isinstance(weights_raw, dict):
        for k, v in weights_raw.items():
            kk = str(k).strip()
            if not kk:
                continue
            try:
                w = float(v)
            except Exception:
                continue
            if not math.isfinite(w) or w <= 0:
                continue
            weights[kk] = w
    return out_pairs, weights


def _parse_key_value_pairs(items: list[str]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for item in items or []:
        s = str(item).strip()
        if not s or "=" not in s:
            continue
        k, v = s.split("=", 1)
        k = k.strip()
        v = v.strip()
        if not k:
            continue

        # 尽量把数值解析成 int/float（方便因子模板渲染）
        parsed: Any = v
        if v.lower() in {"true", "false"}:
            parsed = v.lower() == "true"
        else:
            try:
                if v.isdigit() or (v.startswith("-") and v[1:].isdigit()):
                    parsed = int(v)
                else:
                    parsed = float(v)
            except Exception:
                parsed = v

        out[k] = parsed
    return out


def _load_strategy_vars(path: Path) -> dict[str, Any]:
    """
    从策略参数 JSON 中提取变量（用于渲染 factors.yaml 占位符）。

    约定：
    - 读取 params.buy 下的键：buy_ema_short_len -> ema_short_len
    - 同时保留原始键（可用于更复杂的模板）
    """
    if not path.is_file():
        raise FileNotFoundError(f"未找到策略参数：{path.as_posix()}")

    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        return {}

    params = raw.get("params", {}) or {}
    if not isinstance(params, dict):
        return {}

    buy = params.get("buy", {}) or {}
    if not isinstance(buy, dict):
        return {}

    out: dict[str, Any] = {}
    for k, v in buy.items():
        kk = str(k).strip()
        if not kk:
            continue
        out[kk] = v
        if kk.startswith("buy_"):
            out[kk[len("buy_") :]] = v
    return out


def _resolve_factor_names(*, feature_set: str, strategy_vars: dict[str, Any]) -> list[str]:
    templates = get_factor_templates(str(feature_set or "").strip())
    names = render_factor_names(templates, strategy_vars)
    if not names:
        raise ValueError(f"feature-set 渲染为空：{feature_set}")
    return names


def _resolve_outdir(*, outdir_arg: str, run_id: str) -> Path:
    if str(outdir_arg or "").strip():
        return Path(str(outdir_arg)).expanduser().resolve()
    suffix = str(run_id or "").strip()
    ts = pd.Timestamp.utcnow().strftime("%Y%m%d_%H%M%S")
    name = f"factor_audit_{ts}" if not suffix else f"factor_audit_{ts}_{suffix}"
    return (_REPO_ROOT / "artifacts" / "factor_audit" / name).resolve()


def _load_dataset(*, cfg, pair: str, exchange: str, timeframe: str) -> pd.DataFrame:
    symbol = freqtrade_pair_to_symbol(pair)
    if not symbol:
        raise ValueError(f"pair 无法解析为 symbol：{pair}")

    p = (cfg.qlib_data_dir / exchange / timeframe / f"{symbol}.pkl").resolve()
    if not p.is_file():
        raise FileNotFoundError(
            "未找到研究数据集，请先转换：\n"
            f"- 期望路径：{p.as_posix()}\n"
            "示例：uv run python -X utf8 scripts/qlib/convert_freqtrade_to_qlib.py --timeframe 15m\n"
        )

    df = pd.read_pickle(p)
    if df is None or df.empty:
        raise ValueError(f"数据为空：{p.as_posix()}")

    if "date" not in df.columns:
        raise ValueError(f"数据缺少 date 列：{p.as_posix()}")

    work = df.copy()
    work["date"] = pd.to_datetime(work["date"], utc=True, errors="coerce")
    work = work.dropna(subset=["date"]).sort_values("date").drop_duplicates(subset=["date"], keep="last")
    work = work.set_index("date", drop=True)

    # 只保留 OHLCV（避免携带不确定列）
    need = ["open", "high", "low", "close", "volume"]
    missing = [c for c in need if c not in work.columns]
    if missing:
        raise ValueError(f"数据缺少必要列 {missing}：{p.as_posix()}")

    return work[need].astype("float64").replace([np.inf, -np.inf], np.nan)


def _build_panel(
    *,
    datasets: dict[str, pd.DataFrame],
    factor_names: list[str],
    horizons: list[int],
) -> pd.DataFrame:
    rows: list[pd.DataFrame] = []
    for pair, ohlcv in datasets.items():
        feats = compute_features(ohlcv, feature_cols=factor_names)

        out = feats.copy()
        out["close"] = ohlcv["close"]
        for h in horizons:
            hh = int(h)
            if hh <= 0:
                continue
            out[f"fwd_ret_{hh}"] = (ohlcv["close"].shift(-hh) / ohlcv["close"].replace(0, np.nan)) - 1.0

        out["pair"] = str(pair)
        out = out.reset_index(names="date").set_index(["date", "pair"]).sort_index()
        rows.append(out)

    if not rows:
        return pd.DataFrame()

    panel = pd.concat(rows, axis=0).sort_index()
    return panel.replace([np.inf, -np.inf], np.nan)


def _cross_section_metrics(
    *,
    panel: pd.DataFrame,
    factor: str,
    horizon: int,
    quantiles: int,
    weights: dict[str, float],
    fee_rate: float,
    slippage_rate: float,
    timeframe: str,
    rolling_days: list[int],
) -> tuple[str, pd.Series, pd.DataFrame]:
    """
    返回：
    - ic_series: index=date, value=rankIC
    - ret_df:   index=date, columns=top_ret/bottom_ret/ls_ret/market_ret/top_alpha + turnover/cost 后版本
    """
    fwd_col = f"fwd_ret_{int(horizon)}"
    if factor not in panel.columns:
        raise ValueError(f"因子列不存在：{factor}")
    if fwd_col not in panel.columns:
        raise ValueError(f"forward return 列不存在：{fwd_col}")

    y_wide = panel[fwd_col].unstack("pair").sort_index()
    x_wide = panel[factor].unstack("pair").reindex(index=y_wide.index, columns=y_wide.columns)
    direction, ic, ret_df = choose_factor_direction(
        x_wide=x_wide,
        y_wide=y_wide,
        quantiles=int(quantiles),
        weights=weights,
        fee_rate=float(fee_rate),
        slippage_rate=float(slippage_rate),
        timeframe=str(timeframe),
        rolling_days=list(rolling_days or []),
    )

    if ret_df is None or ret_df.empty:
        return direction, ic, pd.DataFrame()

    def _find_benchmark_col(cols: Iterable[str], *, symbol: str) -> str | None:
        for c in cols:
            if freqtrade_pair_to_symbol(str(c)) == str(symbol):
                return str(c)
        return None

    # 基准：BTC（用于强制报告超额）
    btc_col = _find_benchmark_col(list(y_wide.columns), symbol="BTC_USDT")
    if btc_col is not None and btc_col in y_wide.columns:
        btc_ret = y_wide[btc_col].astype("float64")
    else:
        btc_ret = pd.Series(index=ret_df.index, dtype="float64")

    btc_ret = btc_ret.reindex(ret_df.index).astype("float64")
    ret_df["btc_ret"] = btc_ret
    ret_df["top_alpha_btc"] = (ret_df["top_ret"] - btc_ret).astype("float64")
    ret_df["bottom_alpha_btc"] = (ret_df["bottom_ret"] - btc_ret).astype("float64")

    # 成本后版本：用 top_ret_net / bottom_ret_net 对齐策略可执行口径
    if "top_ret_net" in ret_df.columns:
        ret_df["top_alpha_btc_net"] = (ret_df["top_ret_net"] - btc_ret).astype("float64")
    if "bottom_ret_net" in ret_df.columns:
        ret_df["bottom_alpha_btc_net"] = (ret_df["bottom_ret_net"] - btc_ret).astype("float64")

    if "market_ret" in ret_df.columns:
        if "top_ret_net" in ret_df.columns:
            ret_df["top_alpha_cmkt_net"] = (ret_df["top_ret_net"] - ret_df["market_ret"]).astype("float64")
        if "bottom_ret_net" in ret_df.columns:
            ret_df["bottom_alpha_cmkt_net"] = (ret_df["bottom_ret_net"] - ret_df["market_ret"]).astype("float64")

    return direction, ic, ret_df


def _ic_stats(ic: pd.Series) -> dict[str, Any]:
    s = ic.astype("float64").dropna()
    if s.empty:
        return {"ic_mean": float("nan"), "ic_std": float("nan"), "ic_ir": float("nan")}
    mean = float(s.mean())
    std = float(s.std(ddof=1))
    ir = float(mean / std) if (math.isfinite(mean) and math.isfinite(std) and std > 0) else float("nan")
    return {"ic_mean": mean, "ic_std": std, "ic_ir": ir}


def _safe_mean(series: pd.Series) -> float:
    s = series.astype("float64").dropna()
    return float(s.mean()) if not s.empty else float("nan")


def main() -> int:
    args = _parse_args()
    cfg = get_config()

    exchange = str(args.exchange or "").strip() or cfg.freqtrade_exchange
    timeframe = str(args.timeframe or "").strip()
    if not timeframe:
        raise ValueError("timeframe 不能为空")

    # 解析 pairs：--pairs > --symbols-yaml > 默认 symbols.yaml（config_loader）
    weights: dict[str, float] = {}
    if args.pairs is not None and len(args.pairs) > 0:
        pairs = [str(p).strip() for p in args.pairs if str(p).strip()]
    elif str(args.symbols_yaml or "").strip():
        sym_path = (_REPO_ROOT / Path(str(args.symbols_yaml))).resolve()
        pairs, weights = _read_symbols_yaml(sym_path)
    else:
        pairs = cfg.pairs()

    pairs = [str(p).strip() for p in (pairs or []) if str(p).strip()]
    if not pairs:
        raise ValueError("pairs 为空：请传入 --pairs 或 --symbols-yaml，或配置 04_shared/config/symbols.yaml")

    weights_norm = normalize_weights(pairs=pairs, weights=weights)

    # 特征集合 → 因子名列表（支持用策略参数填占位符）
    strategy_vars: dict[str, Any] = {}
    if str(args.strategy_params or "").strip():
        strategy_vars = _load_strategy_vars((_REPO_ROOT / Path(str(args.strategy_params))).resolve())
    # 额外变量（覆盖）
    strategy_vars.update(_parse_key_value_pairs(list(args.var or [])))

    factor_names = _resolve_factor_names(feature_set=str(args.feature_set), strategy_vars=strategy_vars)
    if args.factors is not None:
        factors = [str(f).strip() for f in (args.factors or []) if str(f).strip()]
        if not factors:
            raise ValueError("--factors 为空：要么不传，要么至少提供一个因子名")
        # 只评估子集（但仍需要保证 compute_features 能算）
        factor_names = [f for f in factor_names if f in set(factors)]
        if not factor_names:
            raise ValueError("指定的 --factors 未命中 feature-set 渲染结果")

    horizons = sorted({int(h) for h in (args.horizons or []) if int(h) > 0})
    if not horizons:
        raise ValueError("horizons 不能为空")

    quantiles = int(args.quantiles)
    if quantiles < 2:
        raise ValueError("quantiles 至少为 2")

    fee_rate = float(args.fee)
    slippage_rate = float(args.slippage)
    rolling_days = sorted({int(d) for d in (args.rolling_days or []) if int(d) > 0})
    min_roll_median = float(args.min_roll_median)
    min_roll_p10 = float(args.min_roll_p10)
    min_ic_ir = float(args.min_ic_ir)
    min_top_alpha_btc_net = float(args.min_top_alpha_btc_net)

    outdir = _resolve_outdir(outdir_arg=str(args.outdir), run_id=str(args.run_id))
    outdir.mkdir(parents=True, exist_ok=True)

    audit_cfg = AuditConfig(
        exchange=exchange,
        timeframe=timeframe,
        pairs=pairs,
        weights=weights_norm,
        factor_names=factor_names,
        horizons=horizons,
        quantiles=quantiles,
        fee_rate=fee_rate,
        slippage_rate=slippage_rate,
        rolling_days=rolling_days,
        min_roll_median=min_roll_median,
        min_roll_p10=min_roll_p10,
        min_ic_ir=min_ic_ir,
        min_top_alpha_btc_net=min_top_alpha_btc_net,
        outdir=outdir,
        export_series=bool(args.export_series),
    )

    print("")
    print("=== 因子体检参数 ===")
    print(f"- exchange: {audit_cfg.exchange}")
    print(f"- timeframe: {audit_cfg.timeframe}")
    print(f"- pairs: {len(audit_cfg.pairs)}")
    print(f"- feature_set: {args.feature_set}")
    print(f"- factors: {len(audit_cfg.factor_names)}")
    print(f"- horizons: {audit_cfg.horizons}")
    print(f"- quantiles: {audit_cfg.quantiles}")
    print(f"- fee(one-way): {audit_cfg.fee_rate}")
    print(f"- slippage(one-way): {audit_cfg.slippage_rate}")
    print(f"- rolling_days: {audit_cfg.rolling_days}")
    print("")
    print("=== 验收阈值（默认口径） ===")
    print(f"- min_roll_median: {audit_cfg.min_roll_median}")
    print(f"- min_roll_p10   : {audit_cfg.min_roll_p10}")
    print(f"- min_ic_ir      : {audit_cfg.min_ic_ir}")
    print(f"- min_top_alpha_btc_net: {audit_cfg.min_top_alpha_btc_net}")
    print(f"- outdir: {audit_cfg.outdir.as_posix()}")

    # 1) 加载数据
    datasets: dict[str, pd.DataFrame] = {}
    skipped: dict[str, str] = {}
    for pair in audit_cfg.pairs:
        try:
            datasets[pair] = _load_dataset(cfg=cfg, pair=pair, exchange=audit_cfg.exchange, timeframe=audit_cfg.timeframe)
        except Exception as e:
            skipped[pair] = str(getattr(e, "args", [repr(e)])[0])

    if not datasets:
        raise RuntimeError("没有任何可用数据集：请先运行 convert_freqtrade_to_qlib.py 转换对应 timeframe 的数据")

    if skipped:
        print(f"- 缺失/跳过：{len(skipped)}（示例前5个：{', '.join(list(skipped.keys())[:5])}）")

    # 2) 构建 panel（date,pair）→ 因子/forward returns
    panel = _build_panel(datasets=datasets, factor_names=audit_cfg.factor_names, horizons=audit_cfg.horizons)
    if panel.empty:
        raise RuntimeError("panel 为空：请检查数据长度/因子列表")

    # 3) 逐因子逐 horizon 评估
    summary_rows: list[dict[str, Any]] = []
    for h in audit_cfg.horizons:
        for factor in audit_cfg.factor_names:
            direction, ic, ret_df = _cross_section_metrics(
                panel=panel,
                factor=factor,
                horizon=h,
                quantiles=audit_cfg.quantiles,
                weights=audit_cfg.weights,
                fee_rate=audit_cfg.fee_rate,
                slippage_rate=audit_cfg.slippage_rate,
                timeframe=audit_cfg.timeframe,
                rolling_days=audit_cfg.rolling_days,
            )

            row: dict[str, Any] = {
                "exchange": audit_cfg.exchange,
                "timeframe": audit_cfg.timeframe,
                "horizon": int(h),
                "factor": str(factor),
                "direction": str(direction),
                "n_pairs": int(len(datasets)),
            }
            row.update(_ic_stats(ic))

            if not ret_df.empty:
                row["top_ret_mean"] = _safe_mean(ret_df["top_ret"])
                row["bottom_ret_mean"] = _safe_mean(ret_df["bottom_ret"])
                row["market_ret_mean"] = _safe_mean(ret_df["market_ret"])
                row["top_alpha_mean"] = _safe_mean(ret_df["top_alpha"])
                row["ls_ret_mean"] = _safe_mean(ret_df["ls_ret"])
                row["turnover_top_mean"] = _safe_mean(ret_df["turnover_top"])
                row["turnover_bottom_mean"] = _safe_mean(ret_df["turnover_bottom"])
                row["cost_top_mean"] = _safe_mean(ret_df["cost_top"])
                row["cost_bottom_mean"] = _safe_mean(ret_df["cost_bottom"])
                row["top_ret_net_mean"] = _safe_mean(ret_df["top_ret_net"])
                row["bottom_ret_net_mean"] = _safe_mean(ret_df["bottom_ret_net"])
                row["short_bottom_net_mean"] = _safe_mean(ret_df["short_bottom_net"])
                row["ls_ret_net_mean"] = _safe_mean(ret_df["ls_ret_net"])
                if "top_alpha_btc_net" in ret_df.columns:
                    row["top_alpha_btc_net_mean"] = _safe_mean(ret_df["top_alpha_btc_net"])
                if "bottom_alpha_btc_net" in ret_df.columns:
                    row["bottom_alpha_btc_net_mean"] = _safe_mean(ret_df["bottom_alpha_btc_net"])
                if "top_alpha_cmkt_net" in ret_df.columns:
                    row["top_alpha_cmkt_net_mean"] = _safe_mean(ret_df["top_alpha_cmkt_net"])
                if "bottom_alpha_cmkt_net" in ret_df.columns:
                    row["bottom_alpha_cmkt_net_mean"] = _safe_mean(ret_df["bottom_alpha_cmkt_net"])
                row.update(rolling_return_summary(ret_df["ls_ret_net"], timeframe=audit_cfg.timeframe, days=audit_cfg.rolling_days))
            else:
                row["top_ret_mean"] = float("nan")
                row["bottom_ret_mean"] = float("nan")
                row["market_ret_mean"] = float("nan")
                row["top_alpha_mean"] = float("nan")
                row["ls_ret_mean"] = float("nan")
                row["turnover_top_mean"] = float("nan")
                row["turnover_bottom_mean"] = float("nan")
                row["cost_top_mean"] = float("nan")
                row["cost_bottom_mean"] = float("nan")
                row["top_ret_net_mean"] = float("nan")
                row["bottom_ret_net_mean"] = float("nan")
                row["short_bottom_net_mean"] = float("nan")
                row["ls_ret_net_mean"] = float("nan")
                row["top_alpha_btc_net_mean"] = float("nan")
                row["bottom_alpha_btc_net_mean"] = float("nan")
                row["top_alpha_cmkt_net_mean"] = float("nan")
                row["bottom_alpha_cmkt_net_mean"] = float("nan")

            summary_rows.append(row)

            if audit_cfg.export_series:
                safe_factor = str(factor).replace("/", "_").replace(":", "_").replace("\\", "_")
                ic.to_csv(audit_cfg.outdir / f"ic_{safe_factor}_h{h}.csv", encoding="utf-8")
                if not ret_df.empty:
                    ret_df.to_csv(audit_cfg.outdir / f"returns_{safe_factor}_h{h}.csv", encoding="utf-8")

    summary = pd.DataFrame(summary_rows)

    # --- 验收/筛选（收益优先：用滚动窗口收益做主指标） ---
    rolling_days_cfg = list(audit_cfg.rolling_days or [])
    preferred_roll_day: int | None = 30 if 30 in rolling_days_cfg else (rolling_days_cfg[0] if rolling_days_cfg else None)
    roll_median_key = f"roll_{preferred_roll_day}d_median" if preferred_roll_day else ""
    roll_p10_key = f"roll_{preferred_roll_day}d_p10" if preferred_roll_day else ""

    def _to_float(v: Any) -> float:
        try:
            fv = float(v)
        except Exception:
            return float("nan")
        return fv if math.isfinite(fv) else float("nan")

    def _verdict_row(r: pd.Series) -> str:
        # 无滚动指标（或缺数据）直接淘汰：无法回答“30/60天稳定性”
        if not roll_median_key or roll_median_key not in r.index:
            return "drop"
        roll_median = _to_float(r.get(roll_median_key))
        if not math.isfinite(roll_median):
            return "drop"
        if roll_median < float(audit_cfg.min_roll_median):
            return "drop"

        ok = True

        if roll_p10_key and roll_p10_key in r.index:
            roll_p10 = _to_float(r.get(roll_p10_key))
            if math.isfinite(roll_p10) and roll_p10 < float(audit_cfg.min_roll_p10):
                ok = False

        ic_ir = _to_float(r.get("ic_ir"))
        if math.isfinite(ic_ir) and ic_ir < float(audit_cfg.min_ic_ir):
            ok = False

        # BTC 超额：若 BTC 不在币池（或缺数据）则字段为 NaN，不参与判定；但仍会在报告中展示为空。
        top_alpha_btc_net = _to_float(r.get("top_alpha_btc_net_mean"))
        if math.isfinite(top_alpha_btc_net) and top_alpha_btc_net < float(audit_cfg.min_top_alpha_btc_net):
            ok = False

        return "pass" if ok else "watch"

    summary["verdict"] = summary.apply(_verdict_row, axis=1)
    summary_path = audit_cfg.outdir / "factor_summary.csv"
    summary.to_csv(summary_path, index=False, encoding="utf-8")

    def _df_to_md_table(df: pd.DataFrame, cols: list[str], *, max_rows: int = 20) -> str:
        """
        轻量 Markdown 表格渲染（避免依赖 tabulate）。

        仅用于摘要展示：数值保留 6 位小数，NaN 显示为空。
        """
        if df is None or df.empty:
            return "_(空)_"
        use_cols = [c for c in cols if c in df.columns]
        if not use_cols:
            return "_(空)_"

        view = df[use_cols].head(int(max_rows)).copy()

        def _fmt(v: Any) -> str:
            if v is None:
                return ""
            try:
                fv = float(v)
                if math.isfinite(fv):
                    return f"{fv:.6f}"
                return ""
            except Exception:
                return str(v)

        header = "| " + " | ".join(use_cols) + " |"
        sep = "| " + " | ".join(["---"] * len(use_cols)) + " |"
        rows = []
        for _, r in view.iterrows():
            rows.append("| " + " | ".join(_fmt(r[c]) for c in use_cols) + " |")
        return "\n".join([header, sep] + rows)

    # 4) 生成简单 markdown（按 ICIR 与 30d 中位数排序）
    md_lines: list[str] = []
    md_lines.append("# 因子体检摘要")
    md_lines.append("")
    md_lines.append(f"- exchange: `{audit_cfg.exchange}`")
    md_lines.append(f"- timeframe: `{audit_cfg.timeframe}`")
    md_lines.append(f"- pairs_used: `{len(datasets)}` / `{len(audit_cfg.pairs)}`")
    md_lines.append(f"- horizons: `{audit_cfg.horizons}`")
    md_lines.append(f"- quantiles: `{audit_cfg.quantiles}`")
    md_lines.append(f"- fee(one-way): `{audit_cfg.fee_rate}`")
    md_lines.append(f"- slippage(one-way): `{audit_cfg.slippage_rate}`")
    md_lines.append("")
    md_lines.append("- direction: `pos`=因子值越大越看多；`neg`=因子值越小越看多（等价于对因子取负）。")
    md_lines.append("")

    # 验收规则与结果
    md_lines.append("## 验收规则（默认）")
    md_lines.append("")
    if preferred_roll_day is not None:
        md_lines.append(f"- 主指标：`{roll_median_key}`（基于 `ls_ret_net`，含手续费/滑点）")
        if roll_p10_key:
            md_lines.append(f"- 稳健性：`{roll_p10_key}`（P10）")
    if roll_median_key:
        md_lines.append(f"- 通过阈值：`{roll_median_key}` >= `{audit_cfg.min_roll_median}`")
    if roll_p10_key:
        md_lines.append(f"- 通过阈值：`{roll_p10_key}` >= `{audit_cfg.min_roll_p10}`（若为空则不检查）")
    md_lines.append(f"- 通过阈值：`ic_ir` >= `{audit_cfg.min_ic_ir}`（若为空则不检查）")
    md_lines.append(f"- 通过阈值：`top_alpha_btc_net_mean` >= `{audit_cfg.min_top_alpha_btc_net}`（若 BTC 为空则不检查）")
    md_lines.append("")

    vc = summary["verdict"].value_counts(dropna=False).to_dict() if "verdict" in summary.columns else {}
    md_lines.append("## 验收结果")
    md_lines.append("")
    md_lines.append(
        f"- 通过/待观察/淘汰：`{int(vc.get('pass', 0))}` / `{int(vc.get('watch', 0))}` / `{int(vc.get('drop', 0))}`（共 `{len(summary)}`）"
    )
    md_lines.append("")

    md_lines.append("## 通过清单（建议进入组合模型）")
    md_lines.append("")
    passed = summary[summary["verdict"] == "pass"].copy()
    if roll_median_key and roll_median_key in passed.columns:
        passed = passed.sort_values(roll_median_key, ascending=False)
    md_lines.append(
        _df_to_md_table(
            passed,
            [
                "horizon",
                "factor",
                "direction",
                roll_median_key,
                roll_p10_key,
                "ls_ret_net_mean",
                "top_alpha_btc_net_mean",
                "top_alpha_cmkt_net_mean",
                "turnover_top_mean",
                "cost_top_mean",
            ],
            max_rows=30,
        )
    )
    md_lines.append("")

    md_lines.append("## 待观察清单（建议进一步验证）")
    md_lines.append("")
    watching = summary[summary["verdict"] == "watch"].copy()
    if roll_median_key and roll_median_key in watching.columns:
        watching = watching.sort_values(roll_median_key, ascending=False)
    md_lines.append(
        _df_to_md_table(
            watching,
            [
                "horizon",
                "factor",
                "direction",
                roll_median_key,
                roll_p10_key,
                "ls_ret_net_mean",
                "top_alpha_btc_net_mean",
                "ic_ir",
            ],
            max_rows=30,
        )
    )
    md_lines.append("")

    md_lines.append("## 淘汰清单（不建议使用）")
    md_lines.append("")
    dropped = summary[summary["verdict"] == "drop"].copy()
    if roll_median_key and roll_median_key in dropped.columns:
        dropped = dropped.sort_values(roll_median_key, ascending=True)
    md_lines.append(
        _df_to_md_table(
            dropped,
            [
                "horizon",
                "factor",
                "direction",
                roll_median_key,
                "ls_ret_net_mean",
                "top_alpha_btc_net_mean",
            ],
            max_rows=30,
        )
    )
    md_lines.append("")

    if "ic_ir" in summary.columns:
        top_ic = summary.sort_values("ic_ir", ascending=False).head(15)
        md_lines.append("## Top 因子（按 ICIR）")
        md_lines.append("")
        md_lines.append(
            _df_to_md_table(
                top_ic,
                [
                    "horizon",
                    "factor",
                    "direction",
                    "ic_mean",
                    "ic_ir",
                    "top_ret_net_mean",
                    "ls_ret_net_mean",
                    "top_alpha_btc_net_mean",
                    "top_alpha_cmkt_net_mean",
                ],
                max_rows=15,
            )
        )
        md_lines.append("")

    if any(c.startswith("roll_30d_") for c in summary.columns):
        key = "roll_30d_median" if "roll_30d_median" in summary.columns else None
        if key:
            top_roll = summary.sort_values(key, ascending=False).head(15)
            md_lines.append("## Top 因子（按 30 天滚动中位数）")
            md_lines.append("")
            cols = [
                "horizon",
                "factor",
                "direction",
                key,
                "roll_30d_worst",
                "ls_ret_net_mean",
                "top_ret_net_mean",
                "top_alpha_btc_net_mean",
            ]
            cols = [c for c in cols if c in top_roll.columns]
            md_lines.append(_df_to_md_table(top_roll, cols, max_rows=15))
            md_lines.append("")

    if skipped:
        md_lines.append("## 缺失/跳过数据")
        md_lines.append("")
        for p, reason in list(skipped.items())[:30]:
            md_lines.append(f"- `{p}`: {reason}")
        if len(skipped) > 30:
            md_lines.append(f"- ... 共 {len(skipped)} 个")
        md_lines.append("")

    (audit_cfg.outdir / "summary.md").write_text("\n".join(md_lines), encoding="utf-8")

    print("")
    print("=== 完成 ===")
    print(f"- summary_csv: {summary_path.as_posix()}")
    print(f"- summary_md : {(audit_cfg.outdir / 'summary.md').as_posix()}")
    if skipped:
        print(f"- skipped: {len(skipped)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
