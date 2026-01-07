"""
下载 Freqtrade 官方文档 HTML 到 freqtrade_docs/raw_html/（用于离线保存 + 再生成 Markdown）。

背景：
- raw_html 体积较大，适合本地缓存，不一定要纳入 Git。
- scripts/generate_freqtrade_docs.py 会从 raw_html 提取 canonical 并生成/覆盖对应的 *.zh-CN.md。

运行（本仓库推荐）：
  uv run python "scripts/download_freqtrade_docs_html.py"

可选：
  uv run python "scripts/download_freqtrade_docs_html.py" --only "configuration,backtesting"
"""

from __future__ import annotations

import argparse
import time
from datetime import datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


BASE_URL_DEFAULT = "https://www.freqtrade.io/en/stable/"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="下载 Freqtrade 文档 HTML（写入 freqtrade_docs/raw_html）")
    parser.add_argument(
        "--output-dir",
        default="freqtrade_docs/raw_html",
        help="输出目录（默认：freqtrade_docs/raw_html）。",
    )
    parser.add_argument(
        "--base-url",
        default=BASE_URL_DEFAULT,
        help="文档基准 URL（默认：https://www.freqtrade.io/en/stable/）。",
    )
    parser.add_argument(
        "--only",
        default="",
        help='仅下载指定 slug（逗号分隔），例如："configuration,backtesting"。',
    )
    parser.add_argument(
        "--sleep",
        type=float,
        default=0.25,
        help="每次请求之间的休眠秒数（默认：0.25）。",
    )
    return parser


def _normalize_base_url(base_url: str) -> str:
    base = base_url.strip()
    if not base.endswith("/"):
        base += "/"
    return base


def _build_url(base_url: str, slug: str) -> str:
    if slug == "stable":
        return base_url
    return f"{base_url}{slug}/"


def _fetch(url: str) -> bytes:
    req = Request(
        url,
        headers={
            "User-Agent": "freqtrade_demo-docs-fetcher/1.0 (+https://www.freqtrade.io/)",
        },
    )
    with urlopen(req, timeout=30) as resp:
        return resp.read()


def main() -> int:
    args = build_arg_parser().parse_args()
    base_url = _normalize_base_url(args.base_url)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # scripts/ 同级导入
    import generate_freqtrade_docs as gen

    slugs = sorted(gen.TITLE_MAP.keys())
    if args.only.strip():
        wanted = {s.strip() for s in args.only.split(",") if s.strip()}
        slugs = [s for s in slugs if s in wanted]

    if not slugs:
        print("未选择任何 slug（--only 为空且 TITLE_MAP 为空）。")
        return 2

    failures: list[str] = []
    now = datetime.now().isoformat(timespec="seconds")

    for idx, slug in enumerate(slugs, start=1):
        url = _build_url(base_url, slug)
        out_path = output_dir / f"{slug}.html"
        try:
            data = _fetch(url)
        except (HTTPError, URLError, TimeoutError) as exc:
            failures.append(f"{slug}: {url} -> {exc}")
            continue

        # 追加一行 saved date，方便生成脚本提取（不依赖浏览器“离线保存”格式）。
        suffix = f"\n\nsaved date: {now}\n".encode("utf-8")
        out_path.write_bytes(data + suffix)

        print(f"[{idx}/{len(slugs)}] ok: {slug} -> {out_path.as_posix()}")
        if args.sleep > 0 and idx < len(slugs):
            time.sleep(args.sleep)

    if failures:
        print("下载失败：")
        for item in failures:
            print(f"- {item}")
        return 1

    print(f"下载完成：{len(slugs)} 个 HTML 已写入 {output_dir.as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

