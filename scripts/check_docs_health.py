"""
文档自检脚本：用于保证 freqtrade_book / freqtrade_docs 的“可查阅性与安全性”。

检查项：
1) 本地链接：Markdown 内的相对路径链接是否存在（避免跳转断链）。
2) 脱敏风险：检测是否误写入高置信度的敏感 Token / Secret（默认只扫描 freqtrade_book）。
3) 手册结构：章节导航/目标/完成标准是否齐全，目录是否覆盖所有章节（默认开启）。

运行方式（本仓库推荐）：
  uv run python "scripts/check_docs_health.py"

可选：
  uv run python "scripts/check_docs_health.py" --include-reference-secrets
  uv run python "scripts/check_docs_health.py" --check-config-examples
"""

from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path
from urllib.parse import unquote


DEFAULT_LINK_ROOTS = (Path("freqtrade_book"), Path("freqtrade_docs"))
DEFAULT_SECRET_ROOTS = (Path("freqtrade_book"),)

BOOK_DIR = Path("freqtrade_book")
BOOK_CHAPTERS_DIR = BOOK_DIR / "chapters"
BOOK_SUMMARY_PATH = BOOK_DIR / "SUMMARY.zh-CN.md"

INLINE_LINK_RE = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")
CHAPTER_PREFIX_RE = re.compile(r"^(\d{2})_")

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


def check_no_bash_fences(md_files: list[Path]) -> list[str]:
    issues: list[str] = []
    for md_file in md_files:
        text = md_file.read_text(encoding="utf-8")
        if "```bash" in text:
            issues.append(f"{md_file.as_posix()}: 检测到 ```bash（手册建议统一为 powershell/json）")
    return issues


def check_book_structure() -> list[str]:
    issues: list[str] = []

    if not BOOK_CHAPTERS_DIR.exists():
        return [f"{BOOK_CHAPTERS_DIR.as_posix()}: 目录不存在"]

    chapter_files = sorted(p for p in BOOK_CHAPTERS_DIR.glob("*.zh-CN.md") if p.is_file())
    if not chapter_files:
        return [f"{BOOK_CHAPTERS_DIR.as_posix()}: 未找到任何章节文件 (*.zh-CN.md)"]

    for chapter in chapter_files:
        text = chapter.read_text(encoding="utf-8")
        lines = text.splitlines()
        head = "\n".join(lines[:20])
        tail = "\n".join(lines[-20:])

        prefix_match = CHAPTER_PREFIX_RE.match(chapter.name)
        chapter_index = int(prefix_match.group(1)) if prefix_match else None
        is_learning_chapter = chapter_index is not None and chapter_index < 90

        if "返回目录" not in head:
            issues.append(f"{chapter.as_posix()}: 顶部缺少导航（应包含“返回目录”）")
        if "上一章" not in head or "下一章" not in head:
            issues.append(f"{chapter.as_posix()}: 顶部导航缺少“上一章/下一章”")
        if "返回目录" not in tail:
            issues.append(f"{chapter.as_posix()}: 底部缺少导航（应包含“返回目录”）")

        if "## 本章目标" not in text:
            issues.append(f"{chapter.as_posix()}: 缺少“## 本章目标”小节")
        if "## 本章完成标准" not in text:
            issues.append(f"{chapter.as_posix()}: 缺少“## 本章完成标准”小节")

        if is_learning_chapter:
            if "## 0)" not in text:
                issues.append(f"{chapter.as_posix()}: 学习章节缺少“## 0) 最小命令模板”入口")
            if "```powershell" not in text:
                issues.append(f"{chapter.as_posix()}: 学习章节缺少 powershell 命令块（```powershell）")
            if "## 延伸阅读（参考库）" not in text:
                issues.append(f"{chapter.as_posix()}: 学习章节缺少“## 延伸阅读（参考库）”小节")
            if "../../freqtrade_docs/" not in text:
                issues.append(f"{chapter.as_posix()}: 学习章节缺少指向 freqtrade_docs 的链接")

        for line_no, line in enumerate(lines, start=1):
            stripped = line.strip()
            if not stripped.startswith("uv run freqtrade "):
                continue
            remainder = stripped.removeprefix("uv run freqtrade ").strip()
            if not remainder:
                continue
            first_token = remainder.split()[0]
            if first_token.startswith("-"):
                continue
            if "--userdir" not in stripped:
                issues.append(
                    f"{chapter.as_posix()}:{line_no}: 命令示例缺少 --userdir（本仓库约定必须明确 userdir）"
                )

    if BOOK_SUMMARY_PATH.exists():
        summary = BOOK_SUMMARY_PATH.read_text(encoding="utf-8")
        missing = []
        for chapter in chapter_files:
            rel = f"chapters/{chapter.name}"
            if rel not in summary:
                missing.append(rel)
        if missing:
            issues.append(
                f"{BOOK_SUMMARY_PATH.as_posix()}: 目录未覆盖以下章节：{', '.join(missing)}"
            )
    else:
        issues.append(f"{BOOK_SUMMARY_PATH.as_posix()}: 目录文件不存在")

    return issues


def run_command(argv: list[str]) -> tuple[int, str]:
    result = subprocess.run(argv, text=True, capture_output=True)
    output = (result.stdout or "") + (result.stderr or "")
    return result.returncode, output.strip()


def check_config_examples() -> list[str]:
    issues: list[str] = []

    config_example = Path("config.example.json")
    if not config_example.exists():
        return [f"{config_example.as_posix()}: 不存在"]

    commands = [
        [
            "uv",
            "run",
            "freqtrade",
            "show-config",
            "--userdir",
            ".",
            "--config",
            config_example.as_posix(),
        ],
        [
            "uv",
            "run",
            "freqtrade",
            "list-strategies",
            "--userdir",
            ".",
            "--config",
            config_example.as_posix(),
        ],
    ]

    for argv in commands:
        code, output = run_command(argv)
        if code != 0:
            pretty = " ".join(argv)
            snippet = output.splitlines()[-30:]
            issues.append(f"命令失败：{pretty}\n" + "\n".join(snippet))

    return issues


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="文档自检（断链 + 脱敏风险）")
    parser.add_argument(
        "--include-reference-secrets",
        action="store_true",
        help="同时扫描 freqtrade_docs 的脱敏风险（默认只扫 freqtrade_book）。",
    )
    parser.add_argument(
        "--skip-structure",
        action="store_true",
        help="跳过 freqtrade_book 的章节结构与目录覆盖检查。",
    )
    parser.add_argument(
        "--check-config-examples",
        action="store_true",
        help="额外校验 config.example.json 是否能通过 show-config/list-strategies（需要已安装依赖）。",
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

    structure_issues: list[str] = []
    bash_fence_issues: list[str] = []
    if not args.skip_structure:
        structure_issues = check_book_structure()
        bash_fence_issues = check_no_bash_fences(iter_markdown_files((BOOK_DIR,)))

    config_issues: list[str] = []
    if args.check_config_examples:
        config_issues = check_config_examples()

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

    if structure_issues:
        print("发现手册结构问题：")
        for item in structure_issues:
            print(f"- {item}")
        print()

    if bash_fence_issues:
        print("发现手册代码块风格问题：")
        for item in bash_fence_issues:
            print(f"- {item}")
        print()

    if config_issues:
        print("发现配置模板可用性问题：")
        for item in config_issues:
            print(item)
            print()

    if link_issues or secret_issues or structure_issues or bash_fence_issues or config_issues:
        print("自检未通过。请修复以上问题后重试。")
        return 1

    success_parts = ["未发现断链", "未发现高置信度敏感信息"]
    if not args.skip_structure:
        success_parts.append("手册结构检查通过")
    if args.check_config_examples:
        success_parts.append("配置模板可用性检查通过")
    print("自检通过：" + "；".join(success_parts) + "。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
