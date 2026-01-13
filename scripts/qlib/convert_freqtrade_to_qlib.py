"""
convert_freqtrade_to_qlib.py - 将 Freqtrade feather 数据转换为“Qlib 研究层”数据集（pkl）

目标：
- 从 `01_freqtrade/data/<exchange>/*.feather` 读取 OHLCV
- 输出到 `02_qlib_research/qlib_data/<exchange>/<timeframe>/<symbol>.pkl`
- 生成 `manifest.json`，便于追溯与批量处理

说明：
- 本脚本不要求安装真正的 Qlib；输出格式遵循 remp_research 的“按交易对 pkl 存储”约定，
  方便后续接入 Qlib 或其他研究框架。
- 交易对可能包含 futures 后缀（如 "BTC/USDT:USDT"），会自动映射为文件符号 "BTC_USDT"。

用法：
    uv run python -X utf8 scripts/qlib/convert_freqtrade_to_qlib.py --help
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

# 确保可导入 03_integration/trading_system（脚本以文件路径运行时，sys.path[0] 会变为 scripts/qlib）
_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "03_integration"))

from trading_system.domain.symbols import freqtrade_pair_to_data_filename, freqtrade_pair_to_symbol
from trading_system.infrastructure.config_loader import get_config


REQUIRED_COLS = ("date", "open", "high", "low", "close", "volume")


@dataclass(frozen=True)
class ExportItem:
    pair: str
    symbol: str
    source: str
    output: str
    rows: int
    start: str
    end: str


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="将 Freqtrade feather 数据转换为研究层 pkl 数据集。")
    p.add_argument(
        "--pairs",
        nargs="*",
        default=None,
        help="交易对列表（空则读取 04_shared/config/symbols.yaml 的 pairs）。示例：\"BTC/USDT:USDT\" \"ETH/USDT:USDT\"",
    )
    p.add_argument("--timeframe", default="4h", help="时间周期（对应 feather 文件名后缀），例如 1h/4h/1d。")
    p.add_argument("--exchange", default="", help="交易所子目录名（默认读取配置：FREQTRADE_EXCHANGE / paths.yaml）。")
    p.add_argument(
        "--datadir",
        default="",
        help="Freqtrade 数据目录（可直接指向 01_freqtrade/data/okx）。留空则按配置自动推断。",
    )
    p.add_argument(
        "--outdir",
        default="",
        help="输出目录（默认：02_qlib_research/qlib_data/<exchange>/<timeframe>）。",
    )
    p.add_argument("--force", action="store_true", help="强制覆盖已存在的输出文件。")
    return p.parse_args()


def _resolve_datadir(*, cfg, datadir_arg: str, exchange: str) -> Path:
    if str(datadir_arg or "").strip():
        return Path(str(datadir_arg)).expanduser().resolve()

    # 兼容两种配置：FREQTRADE_DATA_DIR=./01_freqtrade/data 或 ./01_freqtrade/data/okx
    base = cfg.freqtrade_data_dir
    cand = base / exchange
    if cand.is_dir():
        return cand.resolve()
    return base.resolve()


def _read_ohlcv_feather(path: Path) -> pd.DataFrame:
    df = pd.read_feather(path)
    if df is None or df.empty:
        raise ValueError(f"数据为空：{path.as_posix()}")

    missing = [c for c in REQUIRED_COLS if c not in df.columns]
    if missing:
        raise ValueError(f"数据缺少必要列 {missing}：{path.as_posix()}")

    df = df[list(REQUIRED_COLS)].copy()
    df["date"] = pd.to_datetime(df["date"], utc=True, errors="coerce")
    df = df.dropna(subset=["date"])
    if df.empty:
        raise ValueError(f"date 全部无法解析：{path.as_posix()}")

    df = df.sort_values("date").drop_duplicates(subset=["date"], keep="last")
    df = df.replace([np.inf, -np.inf], np.nan)
    return df


def main() -> int:
    args = _parse_args()
    cfg = get_config()

    exchange = str(args.exchange or "").strip() or cfg.freqtrade_exchange
    timeframe = str(args.timeframe or "").strip()
    if not timeframe:
        raise ValueError("timeframe 不能为空")

    pairs = args.pairs if args.pairs is not None else cfg.pairs()
    pairs = [str(p).strip() for p in (pairs or []) if str(p).strip()]
    if not pairs:
        raise ValueError("pairs 为空：请传入 --pairs 或配置 04_shared/config/symbols.yaml")

    datadir = _resolve_datadir(cfg=cfg, datadir_arg=str(args.datadir), exchange=exchange)

    outdir = Path(str(args.outdir)).expanduser() if str(args.outdir or "").strip() else (cfg.qlib_data_dir / exchange / timeframe)
    outdir = outdir.resolve()
    outdir.mkdir(parents=True, exist_ok=True)

    exported: list[ExportItem] = []
    skipped_missing: list[str] = []
    skipped_existing: list[str] = []

    for pair in pairs:
        symbol = freqtrade_pair_to_symbol(pair)
        filename = freqtrade_pair_to_data_filename(pair, timeframe)
        src = datadir / filename
        if not src.is_file():
            skipped_missing.append(pair)
            continue

        df = _read_ohlcv_feather(src)

        out = outdir / f"{symbol}.pkl"
        if out.exists() and not bool(args.force):
            skipped_existing.append(pair)
            continue

        df.to_pickle(out)

        exported.append(
            ExportItem(
                pair=pair,
                symbol=symbol,
                source=src.as_posix(),
                output=out.as_posix(),
                rows=int(len(df)),
                start=str(df["date"].iloc[0]),
                end=str(df["date"].iloc[-1]),
            )
        )

    manifest = {
        "exchange": exchange,
        "timeframe": timeframe,
        "datadir": datadir.as_posix(),
        "outdir": outdir.as_posix(),
        "exported": [e.__dict__ for e in exported],
        "skipped_missing_pairs": skipped_missing,
        "skipped_existing_pairs": skipped_existing,
    }
    (outdir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    print("")
    print(cfg.display())
    print("")
    print(f"已输出：{outdir.as_posix()}")
    print(f"- 导出成功：{len(exported)}")
    print(f"- 已存在跳过：{len(skipped_existing)}")
    print(f"- 源数据缺失：{len(skipped_missing)}")
    if skipped_existing:
        print(
            f"  已存在示例（前 10 个）：{', '.join(skipped_existing[:10])}"
            + (" ..." if len(skipped_existing) > 10 else "")
        )
    if skipped_missing:
        print(
            f"  缺失示例（前 10 个）：{', '.join(skipped_missing[:10])}"
            + (" ..." if len(skipped_missing) > 10 else "")
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
