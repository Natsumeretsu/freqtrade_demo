from __future__ import annotations

"""
koopman_lite.py - Koopa/Koopman 思路的“轻量原型”（不依赖 torch）

目标（工程闭环导向）：
- 在本仓库现有 `qlib_data`（OHLCV）上，生成一批“更接近本征模态/多尺度”的额外因子序列；
- 输出结果可被 `scripts/qlib/timing_audit.py` 读取并纳入同口径体检（成本后收益、滚动稳定性等）。

核心做法（Koopa-lite）：
1) FFT 低通/高通（近似 Koopa 的时不变/时变拆分）：
   - 在滚动窗口内选择能量最大的 TopK 频率分量，重建低通趋势；
   - 输出高通残差（更接近平稳）与低通斜率（趋势速度）。
2) Rolling DMD/EDMD（Koopman Predictor 的解析近似）：
   - 在 log-return 的延迟嵌入上做滚动线性算子估计（ridge 最小二乘）；
   - 输出多步预测的累计收益（与 timing_audit 的 fwd_ret 口径更接近）以及算子稳定性指标。

注意：
- 该脚本偏研究/原型，默认用 stride 降低计算频率，再用 ffill 保持“在线可用”的特征。
- 本脚本不尝试复刻 Koopa 的 MLP 编解码与分层残差块；我们先把“可验证闭环”跑通。
"""

import argparse
import json
import math
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "03_integration"))

from trading_system.domain.symbols import freqtrade_pair_to_symbol  # noqa: E402
from trading_system.infrastructure.config_loader import get_config  # noqa: E402
from trading_system.infrastructure.koopman_lite import compute_koopman_lite_features  # noqa: E402


@dataclass(frozen=True)
class KoopmanLiteConfig:
    exchange: str
    timeframe: str
    pairs: list[str]
    out_path: Path
    window: int
    embed_dim: int
    stride: int
    ridge: float
    pred_horizons: list[int]
    fft_window: int
    fft_topk: int
    max_bars: int


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Koopa-lite：FFT 拆分 + rolling DMD/EDMD 生成额外特征。")
    p.add_argument("--timeframe", default="15m", help="时间周期，例如 15m/1h/4h。")
    p.add_argument("--exchange", default="", help="交易所名（默认读取配置）。")
    p.add_argument("--symbols-yaml", default="", help="包含 pairs/weights 的 YAML 文件路径（留空则用 symbols.yaml）。")
    p.add_argument("--pairs", nargs="*", default=None, help="直接传入交易对列表（优先级最高）。")

    p.add_argument("--window", type=int, default=512, help="滚动窗口长度（bars）。")
    p.add_argument("--embed-dim", type=int, default=16, help="延迟嵌入维度（Takens embedding）。")
    p.add_argument("--stride", type=int, default=10, help="算子更新步长（bars）。")
    p.add_argument("--ridge", type=float, default=1e-3, help="rolling EDMD 的 ridge 正则系数（避免病态）。")
    p.add_argument(
        "--pred-horizons",
        nargs="*",
        type=int,
        default=[1, 4],
        help="输出多步预测累计收益的步数（bars），例如 1 4 16。",
    )

    p.add_argument("--fft-window", type=int, default=512, help="FFT 滚动窗口长度（bars）。")
    p.add_argument("--fft-topk", type=int, default=8, help="FFT 低通保留的 TopK 频率分量数（不含 DC）。")

    p.add_argument("--max-bars", type=int, default=0, help="最多使用最近 N 根 K 线（0=不限制）。")
    p.add_argument("--out", default="", help="输出 pkl 路径（默认 artifacts/koopman_lite/koopman_lite_<...>.pkl）。")
    return p.parse_args()


def _read_symbols_yaml(path: Path) -> list[str]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise ValueError(f"symbols-yaml 必须是 YAML dict：{path.as_posix()}")
    pairs = raw.get("pairs", []) or []
    if not isinstance(pairs, list):
        raise ValueError(f"symbols-yaml 的 pairs 必须是 list：{path.as_posix()}")
    out = [str(p).strip() for p in pairs if str(p).strip()]
    if not out:
        raise ValueError(f"symbols-yaml 的 pairs 为空：{path.as_posix()}")
    return out


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


def main() -> int:
    args = _parse_args()
    cfg = get_config()

    exchange = str(args.exchange or "").strip() or cfg.freqtrade_exchange
    timeframe = str(args.timeframe or "").strip()
    if not timeframe:
        raise ValueError("timeframe 不能为空")

    if args.pairs is not None and len(args.pairs) > 0:
        pairs = [str(p).strip() for p in args.pairs if str(p).strip()]
    elif str(args.symbols_yaml or "").strip():
        sym_path = (_REPO_ROOT / Path(str(args.symbols_yaml))).resolve()
        pairs = _read_symbols_yaml(sym_path)
    else:
        pairs = cfg.pairs()

    pairs = [str(p).strip() for p in (pairs or []) if str(p).strip()]
    if not pairs:
        raise ValueError("pairs 为空：请传入 --pairs 或 --symbols-yaml，或配置 04_shared/config/symbols.yaml")

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    if str(args.out or "").strip():
        out_path = (_REPO_ROOT / Path(str(args.out))).resolve()
    else:
        out_path = (_REPO_ROOT / "artifacts" / "koopman_lite" / f"koopman_lite_{exchange}_{timeframe}_{ts}.pkl").resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    pred_h = sorted({int(h) for h in (args.pred_horizons or []) if int(h) > 0})
    if not pred_h:
        pred_h = [1, 4]

    kl_cfg = KoopmanLiteConfig(
        exchange=exchange,
        timeframe=timeframe,
        pairs=pairs,
        out_path=out_path,
        window=int(args.window),
        embed_dim=int(args.embed_dim),
        stride=int(args.stride),
        ridge=float(args.ridge),
        pred_horizons=pred_h,
        fft_window=int(args.fft_window),
        fft_topk=int(args.fft_topk),
        max_bars=int(args.max_bars),
    )

    print("")
    print("=== Koopa-lite 参数 ===")
    print(f"- exchange: {kl_cfg.exchange}")
    print(f"- timeframe: {kl_cfg.timeframe}")
    print(f"- pairs: {len(kl_cfg.pairs)}")
    print(f"- window: {kl_cfg.window}")
    print(f"- embed_dim: {kl_cfg.embed_dim}")
    print(f"- stride: {kl_cfg.stride}")
    print(f"- ridge: {kl_cfg.ridge}")
    print(f"- pred_horizons: {kl_cfg.pred_horizons}")
    print(f"- fft_window: {kl_cfg.fft_window}")
    print(f"- fft_topk: {kl_cfg.fft_topk}")
    print(f"- max_bars: {kl_cfg.max_bars}")
    print(f"- out: {kl_cfg.out_path.as_posix()}")

    out: dict[str, Any] = {
        "__meta__": {
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "exchange": kl_cfg.exchange,
            "timeframe": kl_cfg.timeframe,
            "window": kl_cfg.window,
            "embed_dim": kl_cfg.embed_dim,
            "stride": kl_cfg.stride,
            "ridge": kl_cfg.ridge,
            "pred_horizons": kl_cfg.pred_horizons,
            "fft_window": kl_cfg.fft_window,
            "fft_topk": kl_cfg.fft_topk,
            "max_bars": kl_cfg.max_bars,
        },
        "pairs": {},
    }

    skipped: dict[str, str] = {}
    for pair in kl_cfg.pairs:
        try:
            ohlcv = _load_dataset(cfg=cfg, pair=pair, exchange=kl_cfg.exchange, timeframe=kl_cfg.timeframe)
            if int(kl_cfg.max_bars) > 0 and len(ohlcv) > int(kl_cfg.max_bars):
                ohlcv = ohlcv.iloc[-int(kl_cfg.max_bars) :].copy()
            feats = compute_koopman_lite_features(
                close=ohlcv["close"],
                window=int(kl_cfg.window),
                embed_dim=int(kl_cfg.embed_dim),
                stride=int(kl_cfg.stride),
                ridge=float(kl_cfg.ridge),
                pred_horizons=list(kl_cfg.pred_horizons or []),
                fft_window=int(kl_cfg.fft_window),
                fft_topk=int(kl_cfg.fft_topk),
            )
            out["pairs"][str(pair)] = feats
        except Exception as e:
            skipped[str(pair)] = str(getattr(e, "args", [repr(e)])[0])

    if not out["pairs"]:
        raise RuntimeError("没有任何可用数据：请检查 qlib_data 是否已生成、pair/timeframe 是否匹配。")

    pd.to_pickle(out, kl_cfg.out_path)

    print("")
    print("=== Koopa-lite 输出 ===")
    print(f"- pairs_done: {len(out['pairs'])}")
    if skipped:
        print(f"- pairs_skipped: {len(skipped)}（示例前5个：{', '.join(list(skipped.keys())[:5])}）")
    print(f"- out: {kl_cfg.out_path.as_posix()}")
    meta_path = kl_cfg.out_path.with_suffix(".meta.json")
    meta_path.write_text(json.dumps(out.get("__meta__", {}), ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"- meta: {meta_path.as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
