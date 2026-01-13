"""
vharvest 统一入口（采集层 CLI）

目标：
- 把“来源登记 → 采集落盘（feed）”收敛成一个命令入口，便于跨项目复用
- 采集产物默认落在 .vibe/knowledge/sources（可重建缓存，通常不提交）
- 仅使用 Python stdlib，便于复制到其它仓库作为“婴儿 vharvest”的一部分

用法（在仓库根目录）：
  python -X utf8 scripts/tools/vharvest.py status

透传到子脚本（推荐用 -- 分隔）：
  python -X utf8 scripts/tools/vharvest.py fetch -- --limit 5
  python -X utf8 scripts/tools/vharvest.py fetch-playwright -- --only-failed --limit 10
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _script_path(repo_root: Path, rel: str) -> Path:
    return (repo_root / rel).resolve()


def _strip_passthrough(argv: list[str]) -> list[str]:
    # 允许 `... cmd -- --limit 5` 或 `... cmd --limit 5` 两种写法
    if argv and argv[0] == "--":
        return argv[1:]
    return argv


def _fmt_bytes(n: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    size = float(max(n, 0))
    idx = 0
    while size >= 1024 and idx < len(units) - 1:
        size /= 1024
        idx += 1
    if idx == 0:
        return f"{int(size)}{units[idx]}"
    return f"{size:.2f}{units[idx]}"


def _fmt_mtime(ts: float) -> str:
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")


def _count_dirs_matching(root: Path, prefix: str) -> int:
    if not root.exists():
        return 0
    cnt = 0
    for p in root.iterdir():
        if p.is_dir() and p.name.upper().startswith(prefix.upper()):
            cnt += 1
    return cnt


def _run_python(repo_root: Path, script_rel: str, extra_args: list[str]) -> int:
    script = _script_path(repo_root, script_rel)
    if not script.exists():
        print(f"未找到脚本：{script_rel}", file=sys.stderr)
        return 2

    env = os.environ.copy()
    env.setdefault("PYTHONUTF8", "1")
    env.setdefault("PYTHONIOENCODING", "utf-8")
    env.setdefault("PYTHONUNBUFFERED", "1")

    cmd = [sys.executable, "-X", "utf8", str(script)] + extra_args
    return subprocess.call(cmd, cwd=str(repo_root), env=env)


def _cmd_status(repo_root: Path) -> int:
    source_registry = repo_root / "docs" / "knowledge" / "source_registry.md"
    sources_dir = repo_root / ".vibe" / "knowledge" / "sources"

    print("vharvest 状态（粗粒度）：")

    if source_registry.exists():
        st = source_registry.stat()
        print(f"- source_registry: ok  ({_fmt_bytes(st.st_size)}, mtime={_fmt_mtime(st.st_mtime)})")
    else:
        print("- source_registry: missing（建议先创建/维护 docs/knowledge/source_registry.md）")

    s_cnt = _count_dirs_matching(sources_dir, "S-")
    if sources_dir.exists():
        print(f"- .vibe/knowledge/sources: ok  (S-xxx={s_cnt})")
    else:
        print("- .vibe/knowledge/sources: missing（首次采集后会自动创建）")

    fetch_md = repo_root / "scripts" / "tools" / "source_registry_fetch_sources.py"
    fetch_pw = repo_root / "scripts" / "tools" / "source_registry_fetch_sources_playwright.py"
    print(f"- fetch script (markitdown): {'ok' if fetch_md.exists() else 'missing'}")
    print(f"- fetch script (playwright): {'ok' if fetch_pw.exists() else 'missing'}")

    return 0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="vharvest 统一入口（采集层 CLI）")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("status", help="显示 vharvest 关键路径与状态（粗粒度）")

    p_fetch = sub.add_parser("fetch", help="透传调用 source_registry_fetch_sources.py（静态采集优先）")
    p_fetch.add_argument("args", nargs=argparse.REMAINDER, help="透传参数（推荐用 -- 分隔）")

    p_fetch_pw = sub.add_parser("fetch-playwright", help="透传调用 source_registry_fetch_sources_playwright.py（浏览器渲染采集）")
    p_fetch_pw.add_argument("args", nargs=argparse.REMAINDER, help="透传参数（推荐用 -- 分隔）")

    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    repo_root = _repo_root()

    if args.cmd == "status":
        return _cmd_status(repo_root)
    if args.cmd == "fetch":
        return _run_python(
            repo_root,
            "scripts/tools/source_registry_fetch_sources.py",
            _strip_passthrough(list(args.args)),
        )
    if args.cmd == "fetch-playwright":
        return _run_python(
            repo_root,
            "scripts/tools/source_registry_fetch_sources_playwright.py",
            _strip_passthrough(list(args.args)),
        )

    print(f"未知命令：{args.cmd}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

