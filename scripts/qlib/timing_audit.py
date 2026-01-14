"""
timing_audit.py - 择时因子体检（单币种时间序列）

目标（用“大白话”说）：
- 你不关心“同一时刻 40 个币谁更强”（截面），你关心的是：
  “这个币，用这个因子做择时，到底能不能在短期赚到超额？”

因此本脚本做的是：
- 对每个币、每个因子、每个 horizon（持仓 K 线数）：
  1) 自动选方向（pos/neg）
  2) 用滚动分位阈值构造一个极简择时策略（多/空/空仓）
  3) 扣手续费/滑点，输出 30/60 天滚动稳定性
  4) 同时强制报告相对 BTC 的超额（若 BTC 数据可用）

用法示例：
  # 用研究币池（OKX Top40）做择时因子筛选
  uv run python -X utf8 scripts/qlib/timing_audit.py ^
    --exchange okx ^
    --timeframe 15m ^
    --symbols-yaml 04_shared/config/symbols_research_okx_futures_top40.yaml ^
    --feature-set timing_pool_v1 ^
    --horizons 1 4 ^
    --lookback-days 30 ^
    --rolling-days 30 60 ^
    --fee 0.0006
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "03_integration"))

from trading_system.application.factor_sets import get_factor_templates, render_factor_names  # noqa: E402
from trading_system.application.timing_audit import (  # noqa: E402
    TimingAuditParams,
    choose_timing_direction,
    choose_timing_direction_with_thresholds,
    precompute_quantile_thresholds,
)
from trading_system.application.factor_audit import normalize_weights, rolling_return_summary  # noqa: E402
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
    lookback_days: int
    fee_rate: float
    slippage_rate: float
    rolling_days: list[int]
    min_roll_median: float
    min_roll_p10: float
    min_ic_ir: float
    min_alpha_btc_net: float
    benchmark_symbol: str
    outdir: Path
    export_series: bool


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="择时因子体检（单币时间序列）：批量筛因子 + 30/60天滚动稳定性。")
    p.add_argument("--timeframe", default="15m", help="时间周期，例如 15m/1h/4h。")
    p.add_argument("--exchange", default="", help="交易所名（默认读取配置）。")
    p.add_argument("--symbols-yaml", default="", help="包含 pairs/weights 的 YAML 文件路径（留空则用 symbols.yaml）。")
    p.add_argument("--pairs", nargs="*", default=None, help="直接传入交易对列表（优先级最高）。")

    p.add_argument("--feature-set", default="timing_pool_v1", help="特征集合名称（04_shared/config/factors.yaml）。")
    p.add_argument("--strategy-params", default="", help="策略参数 JSON（用于渲染占位符）。")
    p.add_argument("--var", action="append", default=[], help="额外渲染变量（可重复），格式 key=value。")
    p.add_argument("--factors", nargs="*", default=None, help="只评估指定因子名（默认评估 feature-set 全部因子）。")

    p.add_argument("--horizons", nargs="*", type=int, default=[1, 4], help="持仓步长（K 线数），例如 1 4。")
    p.add_argument("--quantiles", type=int, default=5, help="分位数组数（默认 5）。")
    p.add_argument("--lookback-days", type=int, default=30, help="分位阈值回看天数（默认 30）。")

    p.add_argument("--fee", type=float, default=0.0006, help="单边手续费率（默认 0.0006）。")
    p.add_argument("--slippage", type=float, default=0.0, help="单边滑点率（默认 0）。")
    p.add_argument("--rolling-days", nargs="*", type=int, default=[30, 60], help="滚动窗口天数，例如 30 60。")

    # 验收阈值（默认：收益优先）
    p.add_argument("--min-roll-median", type=float, default=0.0, help="通过阈值：roll_30d_median（基于 net_ret）。")
    p.add_argument("--min-roll-p10", type=float, default=-0.15, help="通过阈值：roll_30d_p10（默认 -0.15，约 -15 个百分点）。")
    p.add_argument("--min-ic-ir", type=float, default=0.0, help="通过阈值：ICIR（若为空则不检查）。")
    p.add_argument("--min-alpha-btc-net", type=float, default=0.0, help="通过阈值：alpha_btc_net_mean（若 BTC 不可用则不检查）。")
    p.add_argument("--benchmark-symbol", default="BTC_USDT", help="基准符号（默认 BTC_USDT）。")

    p.add_argument("--outdir", default="", help="输出目录（默认 artifacts/timing_audit/<run_id>）。")
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
                vv = float(v)
            except Exception:
                continue
            if not math.isfinite(vv) or vv <= 0:
                continue
            weights[kk] = float(vv)

    return out_pairs, weights


def _parse_key_value_pairs(items: list[str]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for raw in items:
        s = str(raw or "").strip()
        if not s or "=" not in s:
            continue
        k, v = s.split("=", 1)
        k = k.strip()
        v = v.strip()
        if not k:
            continue
        try:
            out[k] = int(v)
            continue
        except Exception:
            pass
        try:
            out[k] = float(v)
            continue
        except Exception:
            pass
        if v.lower() in {"true", "false"}:
            out[k] = v.lower() == "true"
        else:
            out[k] = v
    return out


def _load_strategy_vars(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"未找到策略参数：{path.as_posix()}")
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"策略参数必须是 JSON object：{path.as_posix()}")
    return raw


def _resolve_factor_names(*, feature_set: str, strategy_vars: dict[str, Any]) -> list[str]:
    templates = get_factor_templates(feature_set)
    if not templates:
        raise ValueError(f"未找到 feature_set：{feature_set}")
    return render_factor_names(templates, strategy_vars)


def _resolve_outdir(*, outdir_arg: str, run_id: str) -> Path:
    if str(outdir_arg or "").strip():
        return Path(str(outdir_arg)).expanduser().resolve()
    from datetime import datetime

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    suffix = f"_{str(run_id).strip()}" if str(run_id).strip() else ""
    return (_REPO_ROOT / "artifacts" / "timing_audit" / f"timing_audit_{ts}{suffix}").resolve()


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

    need = ["open", "high", "low", "close", "volume"]
    missing = [c for c in need if c not in work.columns]
    if missing:
        raise ValueError(f"数据缺少必要列 {missing}：{p.as_posix()}")

    return work[need].astype("float64").replace([np.inf, -np.inf], np.nan)


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


def _effective_timeframe(*, timeframe: str, horizon: int) -> str:
    from trading_system.application.timing_audit import _effective_timeframe as _eff  # noqa: E402

    return _eff(timeframe=timeframe, horizon=int(horizon))


def _verdict_row(r: pd.Series, *, cfg: AuditConfig, roll_day: int | None) -> str:
    roll_median_key = f"roll_{int(roll_day)}d_median" if roll_day else ""
    roll_p10_key = f"roll_{int(roll_day)}d_p10" if roll_day else ""

    def _to_float(v: Any) -> float:
        try:
            fv = float(v)
        except Exception:
            return float("nan")
        return fv if math.isfinite(fv) else float("nan")

    if not roll_median_key or roll_median_key not in r.index:
        return "drop"
    roll_med = _to_float(r.get(roll_median_key))
    if not math.isfinite(roll_med) or roll_med < float(cfg.min_roll_median):
        return "drop"

    ok = True
    roll_p10 = _to_float(r.get(roll_p10_key))
    if math.isfinite(roll_p10) and roll_p10 < float(cfg.min_roll_p10):
        ok = False

    ic_ir = _to_float(r.get("ic_ir"))
    if math.isfinite(ic_ir) and ic_ir < float(cfg.min_ic_ir):
        ok = False

    alpha_btc = _to_float(r.get("alpha_btc_net_mean"))
    if math.isfinite(alpha_btc) and alpha_btc < float(cfg.min_alpha_btc_net):
        ok = False

    return "pass" if ok else "watch"


def main() -> int:
    args = _parse_args()
    cfg = get_config()

    exchange = str(args.exchange or "").strip() or cfg.freqtrade_exchange
    timeframe = str(args.timeframe or "").strip()
    if not timeframe:
        raise ValueError("timeframe 不能为空")

    # 解析 pairs：--pairs > --symbols-yaml > 默认 symbols.yaml
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

    strategy_vars: dict[str, Any] = {}
    if str(args.strategy_params or "").strip():
        strategy_vars = _load_strategy_vars((_REPO_ROOT / Path(str(args.strategy_params))).resolve())
    strategy_vars.update(_parse_key_value_pairs(list(args.var or [])))

    factor_names = _resolve_factor_names(feature_set=str(args.feature_set), strategy_vars=strategy_vars)
    if args.factors is not None:
        factors = [str(f).strip() for f in (args.factors or []) if str(f).strip()]
        if not factors:
            raise ValueError("--factors 为空：要么不传，要么至少提供一个因子名")
        factor_names = [f for f in factor_names if f in set(factors)]
        if not factor_names:
            raise ValueError("指定的 --factors 未命中 feature-set 渲染结果")

    horizons = sorted({int(h) for h in (args.horizons or []) if int(h) > 0})
    if not horizons:
        raise ValueError("horizons 不能为空")

    quantiles = int(args.quantiles)
    if quantiles < 2:
        raise ValueError("quantiles 至少为 2")

    lookback_days = int(args.lookback_days)
    if lookback_days <= 0:
        raise ValueError("lookback-days 必须为正整数")

    fee_rate = float(args.fee)
    slippage_rate = float(args.slippage)
    rolling_days = sorted({int(d) for d in (args.rolling_days or []) if int(d) > 0})

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
        lookback_days=lookback_days,
        fee_rate=fee_rate,
        slippage_rate=slippage_rate,
        rolling_days=rolling_days,
        min_roll_median=float(args.min_roll_median),
        min_roll_p10=float(args.min_roll_p10),
        min_ic_ir=float(args.min_ic_ir),
        min_alpha_btc_net=float(args.min_alpha_btc_net),
        benchmark_symbol=str(args.benchmark_symbol).strip() or "BTC_USDT",
        outdir=outdir,
        export_series=bool(args.export_series),
    )

    print("")
    print("=== 择时因子体检参数 ===")
    print(f"- exchange: {audit_cfg.exchange}")
    print(f"- timeframe: {audit_cfg.timeframe}")
    print(f"- pairs: {len(audit_cfg.pairs)}")
    print(f"- feature_set: {args.feature_set}")
    print(f"- factors: {len(audit_cfg.factor_names)}")
    print(f"- horizons: {audit_cfg.horizons}")
    print(f"- quantiles: {audit_cfg.quantiles}")
    print(f"- lookback_days: {audit_cfg.lookback_days}")
    print(f"- fee(one-way): {audit_cfg.fee_rate}")
    print(f"- slippage(one-way): {audit_cfg.slippage_rate}")
    print(f"- rolling_days: {audit_cfg.rolling_days}")
    print(f"- benchmark_symbol: {audit_cfg.benchmark_symbol}")

    print("")
    print("=== 验收阈值（默认口径） ===")
    print(f"- min_roll_median: {audit_cfg.min_roll_median}")
    print(f"- min_roll_p10   : {audit_cfg.min_roll_p10}")
    print(f"- min_ic_ir      : {audit_cfg.min_ic_ir}")
    print(f"- min_alpha_btc_net: {audit_cfg.min_alpha_btc_net}")
    print(f"- outdir: {audit_cfg.outdir.as_posix()}")

    # 1) 加载数据（每个币一个数据集）
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

    # 2) 基准（BTC）数据：若不存在则 alpha_btc 为空，不影响流程
    btc_df: pd.DataFrame | None = None
    try:
        btc_df = _load_dataset(cfg=cfg, pair=audit_cfg.benchmark_symbol, exchange=audit_cfg.exchange, timeframe=audit_cfg.timeframe)
    except Exception:
        btc_df = None

    btc_fwd: dict[int, pd.Series] = {}
    if btc_df is not None and not btc_df.empty:
        btc_close = btc_df["close"].astype("float64")
        for h in audit_cfg.horizons:
            hh = int(h)
            btc_fwd[hh] = (btc_close.shift(-hh) / btc_close.replace(0, np.nan)) - 1.0

    # 3) 逐币、逐因子、逐 horizon 体检
    summary_rows: list[dict[str, Any]] = []
    roll_day = 30 if 30 in set(audit_cfg.rolling_days or []) else (audit_cfg.rolling_days[0] if audit_cfg.rolling_days else None)

    for pair, ohlcv in datasets.items():
        feats = compute_features(ohlcv, feature_cols=audit_cfg.factor_names)
        close = ohlcv["close"].astype("float64")

        # 预计算滚动分位阈值（一次性算全列），用于加速“多因子批量体检”
        threshold_params = TimingAuditParams(
            timeframe=audit_cfg.timeframe,
            horizon=1,
            quantiles=audit_cfg.quantiles,
            lookback_days=audit_cfg.lookback_days,
            fee_rate=audit_cfg.fee_rate,
            slippage_rate=audit_cfg.slippage_rate,
            rolling_days=list(audit_cfg.rolling_days or []),
        )
        q_high_df, q_low_df = precompute_quantile_thresholds(X=feats, params=threshold_params)

        fwd_map: dict[int, pd.Series] = {}
        for h in audit_cfg.horizons:
            hh = int(h)
            fwd_map[hh] = (close.shift(-hh) / close.replace(0, np.nan)) - 1.0

        for h in audit_cfg.horizons:
            hh = int(h)
            fwd_ret = fwd_map[hh]
            btc_ret = btc_fwd.get(hh) if btc_fwd else None

            params = TimingAuditParams(
                timeframe=audit_cfg.timeframe,
                horizon=hh,
                quantiles=audit_cfg.quantiles,
                lookback_days=audit_cfg.lookback_days,
                fee_rate=audit_cfg.fee_rate,
                slippage_rate=audit_cfg.slippage_rate,
                rolling_days=list(audit_cfg.rolling_days or []),
            )
            eff_tf = _effective_timeframe(timeframe=audit_cfg.timeframe, horizon=hh)

            for factor in audit_cfg.factor_names:
                if factor not in feats.columns:
                    # compute_features 会因 supports 检查提前报错；这里理论上不会发生
                    continue

                if (q_high_df is not None and not q_high_df.empty and factor in q_high_df.columns) and (
                    q_low_df is not None and not q_low_df.empty and factor in q_low_df.columns
                ):
                    direction, side, ic, ret_df = choose_timing_direction_with_thresholds(
                        x=feats[factor],
                        fwd_ret=fwd_ret,
                        btc_ret=btc_ret,
                        params=params,
                        q_high=q_high_df[factor],
                        q_low=q_low_df[factor],
                    )
                else:
                    # 兜底：阈值预计算失败时，回退到单因子计算（更慢，但能跑通）
                    direction, side, ic, ret_df = choose_timing_direction(
                        x=feats[factor],
                        fwd_ret=fwd_ret,
                        btc_ret=btc_ret,
                        params=params,
                    )

                row: dict[str, Any] = {
                    "exchange": audit_cfg.exchange,
                    "timeframe": audit_cfg.timeframe,
                    "pair": str(pair),
                    "horizon": int(hh),
                    "factor": str(factor),
                    "direction": str(direction),
                    "side": str(side),
                    "n_rows": int(len(ret_df)) if ret_df is not None else 0,
                }
                row.update(_ic_stats(ic))

                if ret_df is None or ret_df.empty:
                    row["net_ret_mean"] = float("nan")
                    row["gross_ret_mean"] = float("nan")
                    row["turnover_mean"] = float("nan")
                    row["alpha_btc_net_mean"] = float("nan")
                else:
                    row["net_ret_mean"] = _safe_mean(ret_df["net_ret"])
                    row["gross_ret_mean"] = _safe_mean(ret_df["gross_ret"])
                    row["turnover_mean"] = _safe_mean(ret_df["trade_size"])
                    if "alpha_btc_net" in ret_df.columns:
                        row["alpha_btc_net_mean"] = _safe_mean(ret_df["alpha_btc_net"])
                    else:
                        row["alpha_btc_net_mean"] = float("nan")

                    row.update(rolling_return_summary(ret_df["net_ret"], timeframe=eff_tf, days=audit_cfg.rolling_days))

                summary_rows.append(row)

                if audit_cfg.export_series and ret_df is not None and not ret_df.empty:
                    safe_pair = str(pair).replace("/", "_").replace(":", "_").replace("\\", "_")
                    safe_factor = str(factor).replace("/", "_").replace(":", "_").replace("\\", "_")
                    ret_df.to_csv(audit_cfg.outdir / f"timing_{safe_pair}_{safe_factor}_h{hh}.csv", encoding="utf-8")

    summary = pd.DataFrame(summary_rows)
    if summary.empty:
        raise RuntimeError("summary 为空：请检查数据/因子列表")

    summary["verdict"] = summary.apply(_verdict_row, axis=1, cfg=audit_cfg, roll_day=roll_day)
    summary_path = audit_cfg.outdir / "timing_summary.csv"
    summary.to_csv(summary_path, index=False, encoding="utf-8")

    # 4) Markdown 摘要
    def _df_to_md_table(df: pd.DataFrame, cols: list[str], *, max_rows: int = 30) -> str:
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

    md_lines: list[str] = []
    md_lines.append("# 择时因子体检摘要")
    md_lines.append("")
    md_lines.append(f"- exchange: `{audit_cfg.exchange}`")
    md_lines.append(f"- timeframe: `{audit_cfg.timeframe}`")
    md_lines.append(f"- pairs_used: `{len(datasets)}` / `{len(audit_cfg.pairs)}`")
    md_lines.append(f"- horizons: `{audit_cfg.horizons}`")
    md_lines.append(f"- quantiles: `{audit_cfg.quantiles}`")
    md_lines.append(f"- lookback_days: `{audit_cfg.lookback_days}`")
    md_lines.append(f"- fee(one-way): `{audit_cfg.fee_rate}`")
    md_lines.append(f"- slippage(one-way): `{audit_cfg.slippage_rate}`")
    md_lines.append(f"- benchmark_symbol: `{audit_cfg.benchmark_symbol}`")
    md_lines.append("")
    md_lines.append("- direction: `pos`=因子值越大越偏多；`neg`=因子值越小越偏多（等价于对因子取负）。")
    md_lines.append("- side: `both`=多空都做；`long`=只做多；`short`=只做空（把长短腿拆开评估）。")
    md_lines.append("")

    roll_key = f"roll_{int(roll_day)}d_median" if roll_day else ""
    p10_key = f"roll_{int(roll_day)}d_p10" if roll_day else ""

    md_lines.append("## 验收规则（默认）")
    md_lines.append("")
    if roll_key:
        md_lines.append(f"- 主指标：`{roll_key}`（基于 `net_ret`，含手续费/滑点）")
    if p10_key:
        md_lines.append(f"- 稳健性：`{p10_key}`（P10）")
    md_lines.append(f"- 通过阈值：`{roll_key}` >= `{audit_cfg.min_roll_median}`")
    md_lines.append(f"- 通过阈值：`{p10_key}` >= `{audit_cfg.min_roll_p10}`（若为空则不检查）")
    md_lines.append(f"- 通过阈值：`ic_ir` >= `{audit_cfg.min_ic_ir}`（若为空则不检查）")
    md_lines.append(f"- 通过阈值：`alpha_btc_net_mean` >= `{audit_cfg.min_alpha_btc_net}`（若 BTC 不可用则不检查）")
    md_lines.append("")

    vc = summary["verdict"].value_counts(dropna=False).to_dict()
    md_lines.append("## 验收结果")
    md_lines.append("")
    md_lines.append(
        f"- 通过/待观察/淘汰：`{int(vc.get('pass', 0))}` / `{int(vc.get('watch', 0))}` / `{int(vc.get('drop', 0))}`（共 `{len(summary)}`）"
    )
    md_lines.append("")

    md_lines.append("## Top 结果（按 30 天滚动中位数）")
    md_lines.append("")
    top_all = summary.sort_values(roll_key, ascending=False) if roll_key in summary.columns else summary.copy()
    md_lines.append(
        _df_to_md_table(
            top_all,
            [
                "pair",
                "horizon",
                "factor",
                "direction",
                "side",
                roll_key,
                p10_key,
                "net_ret_mean",
                "alpha_btc_net_mean",
                "ic_ir",
                "turnover_mean",
                "verdict",
            ],
            max_rows=30,
        )
    )
    md_lines.append("")

    md_lines.append("## 每个币的最佳因子（按 30 天滚动中位数）")
    md_lines.append("")
    best_by_pair = top_all.groupby("pair", as_index=False).head(1)
    md_lines.append(
        _df_to_md_table(
            best_by_pair,
            [
                "pair",
                "horizon",
                "factor",
                "direction",
                "side",
                roll_key,
                p10_key,
                "net_ret_mean",
                "alpha_btc_net_mean",
                "ic_ir",
                "verdict",
            ],
            max_rows=60,
        )
    )
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
