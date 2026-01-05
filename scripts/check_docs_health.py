"""
文档自检脚本：用于保证 freqtrade_book / freqtrade_docs 的“可查阅性与安全性”。

检查项：
1) 本地链接：Markdown 内的相对路径链接是否存在（避免跳转断链）。
2) 脱敏风险：检测是否误写入高置信度的敏感 Token / Secret（默认只扫描 freqtrade_book）。

运行方式（本仓库推荐）：
  uv run python "scripts/check_docs_health.py"

可选：
  uv run python "scripts/check_docs_health.py" --include-reference-secrets
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from urllib.parse import unquote


DEFAULT_LINK_ROOTS = (Path("freqtrade_book"), Path("freqtrade_docs"))
DEFAULT_SECRET_ROOTS = (Path("freqtrade_book"),)


INLINE_LINK_RE = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")

SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "Telegram Bot Token",
        re.compile(r"\b\d{8,12}:[A-Za-z0-9_-]{30,}\b"),
    ),
    (
        "JWT Token",
        re.compile(r"\beyJ[A-Za-z0-9_-]*\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b"),
    ),
    (
        "长 Hex Token（≥64）",
        re.compile(r"\b[a-fA-F0-9]{64,}\b"),
    ),
)


def iter_markdown_files(roots: tuple[Path, ...]) -> list[Path]:
    files: list[Path] = []
    for root in roots:
        if not root.exists():
            continue
        files.extend([p for p in root.rglob("*.md") if p.is_file()])
    return sorted(files)


def normalize_link_target(raw_target: str) -> str:
    target = raw_target.strip()
    if target.startswith("<") and target.endswith(">"):
        target = target[1:-1]
    target = unquote(target)
    if " " in target:
        target = target.split()[0]
    return target.strip()


def is_external_link(target: str) -> bool:
    lowered = target.lower()
    return lowered.startswith(("http://", "https://", "mailto:"))


def iter_inline_links(markdown_text: str) -> list[str]:
    return [normalize_link_target(t) for t in INLINE_LINK_RE.findall(markdown_text)]


def check_local_links(md_files: list[Path]) -> list[str]:
    issues: list[str] = []
    for md_file in md_files:
        text = md_file.read_text(encoding="utf-8")
        for target in iter_inline_links(text):
            if not target or target.startswith("#") or is_external_link(target):
                continue
            path_part = target.split("#", 1)[0].split("?", 1)[0]
            if not path_part:
                continue
            resolved = (md_file.parent / path_part).resolve()
            if not resolved.exists():
                issues.append(f"{md_file.as_posix()} -> {target}")
    return issues


def check_secrets(md_files: list[Path]) -> list[str]:
    issues: list[str] = []
    for md_file in md_files:
        text = md_file.read_text(encoding="utf-8")
        lines = text.splitlines()
        for line_no, line in enumerate(lines, start=1):
            for label, pattern in SECRET_PATTERNS:
                if pattern.search(line):
                    snippet = line.strip()
                    if len(snippet) > 180:
                        snippet = snippet[:180] + "..."
                    issues.append(f"{md_file.as_posix()}:{line_no} [{label}] {snippet}")
    return issues


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="文档自检（断链 + 脱敏风险）")
    parser.add_argument(
        "--include-reference-secrets",
        action="store_true",
        help="同时扫描 freqtrade_docs 的脱敏风险（默认只扫 freqtrade_book）。",
    )
    return parser


def main() -> int:
    args = build_arg_parser().parse_args()

    link_files = iter_markdown_files(DEFAULT_LINK_ROOTS)
    link_issues = check_local_links(link_files)

    secret_roots = DEFAULT_SECRET_ROOTS
    if args.include_reference_secrets:
        secret_roots = (Path("freqtrade_book"), Path("freqtrade_docs"))
    secret_files = iter_markdown_files(secret_roots)
    secret_issues = check_secrets(secret_files)

    if link_issues:
        print("发现本地链接断链：")
        for item in link_issues:
            print(f"- {item}")
        print()

    if secret_issues:
        print("发现疑似敏感信息（高置信度匹配）：")
        for item in secret_issues:
            print(f"- {item}")
        print()

    if link_issues or secret_issues:
        print("自检未通过。请修复以上问题后重试。")
        return 1

    print("自检通过：未发现断链或高置信度敏感信息。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
