from __future__ import annotations

"""
koopman_lite.py - Koopman eigenmode extraction using PyDMD HODMD

Goal:
- Extract Koopman operator eigenmodes from OHLCV data in qlib_data
- Output can be used by timing_audit.py for factor validation

Core approach (PyDMD-based):
1) HODMD (Higher Order DMD):
   - Automatic delay embedding, DMD in delay coordinate space
   - Extract eigenvalues (frequency, decay) and eigenmodes (amplitude)
2) Eigenmode linear combination prediction:
   - Formula: x(t) = sum_i phi_i(x0) * lambda_i^t * v_i
   - Output multi-step cumulative return predictions

Output factors:
- koop_spectral_radius: spectral radius (system stability)
- koop_reconstruction_error: reconstruction error (model fit quality)
- koop_mode_{i}_amp: amplitude of i-th eigenmode
- koop_mode_{i}_freq: frequency of i-th eigenmode
- koop_mode_{i}_decay: decay rate of i-th eigenmode
- koop_pred_ret_h{N}: N-step predicted return
"""

import argparse
import json
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
    n_modes: int
    max_bars: int


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Koopman eigenmode extraction using PyDMD HODMD")
    p.add_argument("--timeframe", default="15m", help="Timeframe, e.g. 15m/1h/4h")
    p.add_argument("--exchange", default="", help="Exchange name (default from config)")
    p.add_argument("--symbols-yaml", default="", help="YAML file with pairs/weights")
    p.add_argument("--pairs", nargs="*", default=None, help="Trading pairs list")

    # Koopman parameters (CLI overrides config)
    p.add_argument("--window", type=int, default=None, help="Rolling window length (bars)")
    p.add_argument("--embed-dim", type=int, default=None, help="Delay embedding dimension")
    p.add_argument("--stride", type=int, default=None, help="Operator update stride (bars)")
    p.add_argument("--ridge", type=float, default=None, help="Ridge regularization")
    p.add_argument("--pred-horizons", nargs="*", type=int, default=None, help="Prediction horizons")
    p.add_argument("--n-modes", type=int, default=3, help="Number of eigenmodes to extract")

    p.add_argument("--max-bars", type=int, default=0, help="Max bars to use (0=unlimited)")
    p.add_argument("--out", default="", help="Output pkl path")
    return p.parse_args()


def _read_symbols_yaml(path: Path) -> list[str]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise ValueError(f"symbols-yaml must be YAML dict: {path.as_posix()}")
    pairs = raw.get("pairs", []) or []
    if not isinstance(pairs, list):
        raise ValueError(f"symbols-yaml pairs must be list: {path.as_posix()}")
    out = [str(p).strip() for p in pairs if str(p).strip()]
    if not out:
        raise ValueError(f"symbols-yaml pairs is empty: {path.as_posix()}")
    return out


def _load_dataset(*, cfg, pair: str, exchange: str, timeframe: str) -> pd.DataFrame:
    symbol = freqtrade_pair_to_symbol(pair)
    if not symbol:
        raise ValueError(f"Cannot parse pair to symbol: {pair}")

    p = (cfg.qlib_data_dir / exchange / timeframe / f"{symbol}.pkl").resolve()
    if not p.is_file():
        raise FileNotFoundError(
            f"Dataset not found, please convert first:\n"
            f"- Expected path: {p.as_posix()}\n"
            "Example: uv run python -X utf8 scripts/qlib/convert_freqtrade_to_qlib.py --timeframe 15m\n"
        )

    df = pd.read_pickle(p)
    if df is None or df.empty:
        raise ValueError(f"Empty data: {p.as_posix()}")
    if "date" not in df.columns:
        raise ValueError(f"Missing date column: {p.as_posix()}")

    work = df.copy()
    work["date"] = pd.to_datetime(work["date"], utc=True, errors="coerce")
    work = work.dropna(subset=["date"]).sort_values("date").drop_duplicates(subset=["date"], keep="last")
    work = work.set_index("date", drop=True)

    need = ["open", "high", "low", "close", "volume"]
    missing = [c for c in need if c not in work.columns]
    if missing:
        raise ValueError(f"Missing required columns {missing}: {p.as_posix()}")

    return work[need].astype("float64").replace([np.inf, -np.inf], np.nan)


def main() -> int:
    args = _parse_args()
    cfg = get_config()

    # Load Koopman defaults from config
    koop_cfg = cfg.koopman_config()

    exchange = str(args.exchange or "").strip() or cfg.freqtrade_exchange
    timeframe = str(args.timeframe or "").strip()
    if not timeframe:
        raise ValueError("timeframe cannot be empty")

    if args.pairs is not None and len(args.pairs) > 0:
        pairs = [str(p).strip() for p in args.pairs if str(p).strip()]
    elif str(args.symbols_yaml or "").strip():
        sym_path = (_REPO_ROOT / Path(str(args.symbols_yaml))).resolve()
        pairs = _read_symbols_yaml(sym_path)
    else:
        pairs = cfg.pairs()

    pairs = [str(p).strip() for p in (pairs or []) if str(p).strip()]
    if not pairs:
        raise ValueError("pairs is empty: use --pairs or --symbols-yaml, or configure 04_shared/config/symbols.yaml")

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    if str(args.out or "").strip():
        out_path = (_REPO_ROOT / Path(str(args.out))).resolve()
    else:
        out_path = (_REPO_ROOT / "artifacts" / "koopman_lite" / f"koopman_lite_{exchange}_{timeframe}_{ts}.pkl").resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # CLI overrides config
    window = args.window if args.window is not None else koop_cfg.get("window", 512)
    embed_dim = args.embed_dim if args.embed_dim is not None else koop_cfg.get("embed_dim", 16)
    stride = args.stride if args.stride is not None else koop_cfg.get("stride", 10)
    ridge = args.ridge if args.ridge is not None else koop_cfg.get("ridge", 0.001)
    n_modes = args.n_modes

    if args.pred_horizons is not None:
        pred_h = sorted({int(h) for h in args.pred_horizons if int(h) > 0})
    else:
        pred_h = sorted({int(h) for h in koop_cfg.get("pred_horizons", [1, 4]) if int(h) > 0})
    if not pred_h:
        pred_h = [1, 4]

    kl_cfg = KoopmanLiteConfig(
        exchange=exchange,
        timeframe=timeframe,
        pairs=pairs,
        out_path=out_path,
        window=int(window),
        embed_dim=int(embed_dim),
        stride=int(stride),
        ridge=float(ridge),
        pred_horizons=pred_h,
        n_modes=int(n_modes),
        max_bars=int(args.max_bars),
    )

    print("")
    print("=== Koopman Eigenmode Extraction (PyDMD HODMD) ===")
    print(f"- exchange: {kl_cfg.exchange}")
    print(f"- timeframe: {kl_cfg.timeframe}")
    print(f"- pairs: {len(kl_cfg.pairs)}")
    print(f"- window: {kl_cfg.window}")
    print(f"- embed_dim: {kl_cfg.embed_dim}")
    print(f"- stride: {kl_cfg.stride}")
    print(f"- ridge: {kl_cfg.ridge}")
    print(f"- pred_horizons: {kl_cfg.pred_horizons}")
    print(f"- n_modes: {kl_cfg.n_modes}")
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
            "n_modes": kl_cfg.n_modes,
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
                fft_window=0,  # No longer used
                fft_topk=0,
                n_modes=int(kl_cfg.n_modes),
            )
            out["pairs"][str(pair)] = feats
        except Exception as e:
            skipped[str(pair)] = str(getattr(e, "args", [repr(e)])[0])

    if not out["pairs"]:
        raise RuntimeError("No usable data: check qlib_data exists and pair/timeframe match.")

    pd.to_pickle(out, kl_cfg.out_path)

    print("")
    print("=== Output ===")
    print(f"- pairs_done: {len(out['pairs'])}")
    if skipped:
        print(f"- pairs_skipped: {len(skipped)} (first 5: {', '.join(list(skipped.keys())[:5])})")
    print(f"- out: {kl_cfg.out_path.as_posix()}")
    meta_path = kl_cfg.out_path.with_suffix(".meta.json")
    meta_path.write_text(json.dumps(out.get("__meta__", {}), ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"- meta: {meta_path.as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
