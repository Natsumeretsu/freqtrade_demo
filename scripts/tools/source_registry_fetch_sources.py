"""
批量抓取 docs/knowledge/source_registry.md 中登记的外部来源，并落盘为本地缓存。

设计目标：
- 让“来源登记（source_registry.md）”从“人工记录”进化为“可复现抓取 + 可追踪状态”。
- 抓取内容默认落在 .vibe/ 下（可重建缓存，默认 gitignore），避免把外部全文混进仓库历史。
- 只负责“抓取/落盘/写回登记字段（可选）”，不负责“摘要提炼/回灌设计文档”。

当前实现：
- 抓取工具：MCP `markitdown`（convert_to_markdown）
- 暂不自动使用 Playwright（403/robot/js-required 会记录为失败，后续可扩展）

用法（在仓库根目录）：
  python -X utf8 scripts/tools/source_registry_fetch_sources.py

可选：
  python -X utf8 scripts/tools/source_registry_fetch_sources.py --limit 5
  python -X utf8 scripts/tools/source_registry_fetch_sources.py --ids "S-001,S-002"
  python -X utf8 scripts/tools/source_registry_fetch_sources.py --force
  python -X utf8 scripts/tools/source_registry_fetch_sources.py --update-registry
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import threading
import time
from queue import Empty, Queue
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


@dataclass(frozen=True)
class SourceEntry:
    source_id: str
    title: str
    url: str
    block_start: int
    block_end: int


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="批量抓取 source_registry 外部来源到本地缓存（markitdown）")
    parser.add_argument(
        "--registry",
        default="docs/knowledge/source_registry.md",
        help="来源登记文件路径（相对仓库根目录）",
    )
    parser.add_argument(
        "--out-dir",
        default=".vibe/knowledge/sources",
        help="本地缓存输出目录（相对仓库根目录）",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="最多抓取的条目数（0 表示不限制）",
    )
    parser.add_argument(
        "--ids",
        default="",
        help="仅抓取指定 S-ID（逗号分隔），例如：S-001,S-105",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="强制重新抓取（即使本地已有缓存）",
    )
    parser.add_argument(
        "--update-registry",
        action="store_true",
        help="将抓取结果（方式/状态/日期/缓存路径）写回 source_registry.md",
    )
    parser.add_argument(
        "--startup-timeout-sec",
        type=int,
        default=600,
        help="启动/初始化 MCP 的超时秒数（默认 600s，首次运行可能需要下载依赖）",
    )
    parser.add_argument(
        "--timeout-sec",
        type=int,
        default=120,
        help="单次 MCP 工具调用超时秒数（默认 120s）",
    )
    parser.add_argument(
        "--no-progress",
        action="store_true",
        help="禁用进度条输出（默认启用）",
    )
    return parser.parse_args()


def _utc_date_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _normalize_sid_list(s: str) -> set[str]:
    if not s or not s.strip():
        return set()
    parts = [p.strip() for p in s.split(",") if p.strip()]
    return {p.upper() for p in parts}


def _read_text(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8").splitlines(keepends=False)


def _write_text(path: Path, lines: list[str]) -> None:
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


_ENTRY_HEADER_RE = re.compile(r"^###\s+(S-\d{3})(?:\s*[:：]?\s*)(.*)\s*$")
_URL_RE = re.compile(r"^\s*-\s*URL\s*[:：]\s*(\S+)\s*$")


def _parse_registry(lines: list[str]) -> list[SourceEntry]:
    entries: list[SourceEntry] = []
    i = 0
    while i < len(lines):
        m = _ENTRY_HEADER_RE.match(lines[i])
        if not m:
            i += 1
            continue
        source_id = m.group(1).upper()
        title = (m.group(2) or "").strip()
        start = i
        end = i + 1
        while end < len(lines) and not lines[end].startswith("### ") and not lines[end].startswith("## "):
            end += 1

        url = ""
        for j in range(start, end):
            um = _URL_RE.match(lines[j])
            if um:
                url = um.group(1).strip()
                break

        if url:
            entries.append(SourceEntry(source_id=source_id, title=title, url=url, block_start=start, block_end=end))
        i = end
    return entries


def _render_progress(done: int, total: int, start_ts: float, current: str) -> str:
    elapsed = max(0.0, time.time() - start_ts)
    rate = done / elapsed if elapsed > 0 else 0.0
    eta = (total - done) / rate if rate > 0 else 0.0
    return f"[{done:>3}/{total:<3}] elapsed={elapsed:>6.1f}s eta={eta:>6.1f}s  {current}"


def _print_progress(line: str) -> None:
    cols = 160
    sys.stdout.write("\r" + line.ljust(cols))
    sys.stdout.flush()


class _LineReader:
    """
    Windows 下 pipe 的 readline() 会阻塞，必须用后台线程 + queue 才能可靠实现超时。
    """

    def __init__(self, stream: Any) -> None:
        self._q: "Queue[str]" = Queue()
        self._t = threading.Thread(target=self._run, args=(stream,), daemon=True)
        self._t.start()

    def _run(self, stream: Any) -> None:
        try:
            for line in stream:
                self._q.put(line)
        except Exception:
            # 忽略；由调用方通过 proc.poll() 判断退出
            return

    def read_line(self, timeout_sec: float) -> str | None:
        try:
            return self._q.get(timeout=timeout_sec)
        except Empty:
            return None


def _read_json_line(
    reader: _LineReader,
    proc: subprocess.Popen[str],
    timeout_sec: int,
    *,
    progress_label: str = "",
    show_progress: bool = True,
) -> dict[str, Any]:
    start = time.time()
    spinner = "|/-\\"
    spin_idx = 0
    last_draw = 0.0
    while time.time() - start < timeout_sec:
        line = reader.read_line(timeout_sec=0.2)
        now = time.time()
        if show_progress and now - last_draw >= 0.5:
            elapsed = now - start
            label = progress_label.strip()
            if label:
                _print_progress(f"{spinner[spin_idx]} 等待 MCP 响应（{label}）… elapsed={elapsed:>.1f}s")
            else:
                _print_progress(f"{spinner[spin_idx]} 等待 MCP 响应… elapsed={elapsed:>.1f}s")
            spin_idx = (spin_idx + 1) % len(spinner)
            last_draw = now
        if line is None:
            if proc.poll() is not None:
                raise RuntimeError("MCP 进程已退出（未收到 JSON 响应）")
            continue
        s = line.strip()
        if not s or not s.startswith("{"):
            continue
        try:
            return json.loads(s)
        except Exception:
            continue
    raise TimeoutError("等待 MCP JSON 响应超时")


def _mcp_call(
    proc: subprocess.Popen[str],
    reader: _LineReader,
    request_id: int,
    method: str,
    params: dict[str, Any] | None,
    timeout_sec: int,
    *,
    progress_label: str = "",
    show_progress: bool = True,
) -> dict[str, Any]:
    req: dict[str, Any] = {"jsonrpc": "2.0", "id": request_id, "method": method}
    if params is not None:
        req["params"] = params
    if not proc.stdin:
        raise RuntimeError("MCP 进程 stdin 不可用")
    proc.stdin.write(json.dumps(req, ensure_ascii=False) + "\n")
    proc.stdin.flush()
    return _read_json_line(
        reader,
        proc=proc,
        timeout_sec=timeout_sec,
        progress_label=progress_label,
        show_progress=show_progress,
    )


def _mcp_notify(proc: subprocess.Popen[str], method: str, params: dict[str, Any]) -> None:
    msg: dict[str, Any] = {"jsonrpc": "2.0", "method": method, "params": params}
    if not proc.stdin:
        return
    proc.stdin.write(json.dumps(msg, ensure_ascii=False) + "\n")
    proc.stdin.flush()


def _start_markitdown_mcp() -> tuple[subprocess.Popen[str], _LineReader]:
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    cmd = ["uvx", "--python", "3.11", "markitdown-mcp==0.0.1a4"]
    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        encoding="utf-8",
        env=env,
    )
    if not proc.stdout:
        raise RuntimeError("markitdown MCP stdout 不可用")
    return proc, _LineReader(proc.stdout)


def _extract_markdown(result: Any) -> str:
    if isinstance(result, str):
        return result
    if isinstance(result, dict):
        for k in ("markdown", "content", "text"):
            v = result.get(k)
            if isinstance(v, str) and v.strip():
                return v
        content = result.get("content")
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text" and isinstance(item.get("text"), str):
                    parts.append(item["text"])
            if parts:
                return "\n".join(parts)
    raise ValueError("无法从 MCP 返回中提取 Markdown 内容")


def _classify_markdown(markdown: str) -> tuple[str, str]:
    """
    粗粒度判断抓取是否“真的拿到了正文”。

    注意：这是启发式规则，不追求 100% 准确，只用于把明显的 403/robot/captcha 页面标出来。
    """
    md = (markdown or "").strip()
    if not md:
        return "blocked", "empty"

    low = md.lower()

    # 常见“机器人/反爬/权限”页面特征
    blocked_signals: list[tuple[str, str]] = [
        ("verifying that you are not a robot", "robot_check"),
        ("verify that you are not a robot", "robot_check"),
        ("captcha", "captcha"),
        ("cloudflare", "cloudflare"),
        ("just a moment", "cloudflare"),
        ("attention required", "cloudflare"),
        ("access denied", "access_denied"),
        ("permission denied", "permission_denied"),
        ("forbidden", "forbidden"),
        ("403", "403"),
        ("error executing tool convert_to_markdown", "tool_error"),
        ("request blocked", "request_blocked"),
    ]
    for token, reason in blocked_signals:
        if token in low:
            return "blocked", reason

    # 常见“需要 JS 才能渲染正文”的页面
    js_signals: list[tuple[str, str]] = [
        ("please enable javascript", "enable_javascript"),
        ("enable javascript", "enable_javascript"),
        ("requires javascript", "requires_javascript"),
    ]
    for token, reason in js_signals:
        if token in low:
            return "js_required", reason

    # 太短的内容通常不是正文（例如只剩一个标题/一句提示）
    if len(md) < 120:
        return "blocked", "too_short"

    return "ok", "content"


def _cache_paths(repo_root: Path, out_dir: str, source_id: str) -> tuple[Path, Path]:
    base = Path(out_dir)
    if not base.is_absolute():
        base = repo_root / base
    entry_dir = base / source_id
    return entry_dir, (entry_dir / "markitdown.md")


def _write_meta(entry_dir: Path, meta: dict[str, Any]) -> None:
    entry_dir.mkdir(parents=True, exist_ok=True)
    meta_path = entry_dir / "meta.json"
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _update_registry_block(
    lines: list[str],
    entry: SourceEntry,
    cache_md_rel: str,
    method: str,
    status: str,
    fetched_date: str,
) -> list[str]:
    """
    仅在 entry.block_start..block_end 范围内做最小替换/插入，不改动摘要内容。
    """
    # 重要：不要依赖 parse 时记录的 block_start/block_end。
    # 当我们对前面的条目插入新行后，后续条目的行号会整体偏移，旧索引会把内容写进错误位置。
    start = -1
    end = -1
    for i, line in enumerate(lines):
        m = _ENTRY_HEADER_RE.match(line)
        if m and m.group(1).upper() == entry.source_id:
            start = i
            end = i + 1
            while end < len(lines) and not lines[end].startswith("### ") and not lines[end].startswith("## "):
                end += 1
            break
    if start < 0 or end < 0:
        return lines

    block = lines[start:end]

    method_line = f"- 抓取方式：{method}"
    status_line = f"- 抓取状态：{status}"
    date_line = f"- 抓取日期：{fetched_date}"
    cache_line = f"- 本地缓存：{cache_md_rel}"

    # 清理/去重：把自动写入字段统一成“URL 下方四行”，避免历史遗留重复/错位。
    status_notes: list[str] = []
    cleaned: list[str] = []

    def status_kind(s: str) -> str:
        low = (s or "").strip().lower()
        if low.startswith("ok"):
            return "ok"
        if low.startswith("blocked"):
            return "blocked"
        if low.startswith("js-required") or low.startswith("js_required"):
            return "js"
        return ""

    kind = status_kind(status)
    for line in block:
        s = line.strip()
        if s.startswith("- 抓取状态备注："):
            continue
        if s.startswith("- 抓取方式：") or s.startswith("- 抓取日期：") or s.startswith("- 本地缓存："):
            continue
        if s.startswith("- 抓取状态："):
            if s != status_line:
                note = s[len("- 抓取状态：") :].strip()
                if note and note != status:
                    if kind and status_kind(note) and status_kind(note) != kind:
                        continue
                    status_notes.append(f"- 抓取状态备注：{note}")
            continue
        cleaned.append(line)
    block = cleaned

    url_idx = -1
    for idx, line in enumerate(block):
        if line.strip().startswith("- URL"):
            url_idx = idx
            break
    insert_at = url_idx + 1 if url_idx >= 0 else 0

    block.insert(insert_at, method_line)
    insert_at += 1
    block.insert(insert_at, status_line)
    insert_at += 1
    for note in status_notes:
        block.insert(insert_at, note)
        insert_at += 1
    block.insert(insert_at, date_line)
    insert_at += 1
    block.insert(insert_at, cache_line)

    return lines[:start] + block + lines[end:]


def main() -> int:
    args = _parse_args()
    repo_root = _repo_root()

    registry_path = Path(args.registry)
    if not registry_path.is_absolute():
        registry_path = repo_root / registry_path
    if not registry_path.exists():
        print(f"未找到来源登记文件：{registry_path}", file=sys.stderr)
        return 2

    lines = _read_text(registry_path)
    entries = _parse_registry(lines)
    if not entries:
        print("未解析到任何 S-xxx 条目，请检查 source_registry.md 格式。", file=sys.stderr)
        return 2

    wanted_ids = _normalize_sid_list(args.ids)
    if wanted_ids:
        entries = [e for e in entries if e.source_id in wanted_ids]

    if args.limit and args.limit > 0:
        entries = entries[: args.limit]

    if not entries:
        print("无可抓取条目（过滤后为空）。", file=sys.stderr)
        return 2

    out_dir = args.out_dir
    print(f"将抓取 {len(entries)} 条来源到本地缓存：{out_dir}")
    print("提示：首次运行可能会下载依赖/模型，耗时取决于网速与磁盘。")

    print("启动 markitdown MCP（可能需要首次下载依赖，请稍候）…")
    proc, reader = _start_markitdown_mcp()
    try:
        init_resp = _mcp_call(
            proc,
            reader,
            request_id=1,
            method="initialize",
            params={
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "freqtrade_demo_source_registry_fetch", "version": "0.1.0"},
            },
            timeout_sec=args.startup_timeout_sec,
            progress_label="initialize",
            show_progress=not args.no_progress,
        )
        if "result" not in init_resp:
            print(f"initialize 失败：{init_resp}", file=sys.stderr)
            return 1
        _mcp_notify(proc, method="notifications/initialized", params={})

        tools_resp = _mcp_call(
            proc,
            reader,
            request_id=2,
            method="tools/list",
            params={},
            timeout_sec=args.startup_timeout_sec,
            progress_label="tools/list",
            show_progress=not args.no_progress,
        )
        tool_names = {t.get("name") for t in tools_resp.get("result", {}).get("tools", [])}
        if "convert_to_markdown" not in tool_names:
            print(f"markitdown 不支持 convert_to_markdown，tools={sorted(tool_names)}", file=sys.stderr)
            return 1

        start_ts = time.time()
        ok = 0
        failed: list[str] = []
        updated_lines = lines
        fetched_date = _utc_date_str()

        for idx, entry in enumerate(entries, start=1):
            entry_dir, md_path = _cache_paths(repo_root, out_dir=out_dir, source_id=entry.source_id)
            md_rel = str(md_path.relative_to(repo_root)).replace("\\", "/")

            meta_path = entry_dir / "meta.json"
            if meta_path.exists() and md_path.exists() and not args.force:
                ok += 1
                if not args.no_progress:
                    _print_progress(_render_progress(done=idx, total=len(entries), start_ts=start_ts, current=f"skip {entry.source_id}"))
                continue

            if args.no_progress:
                print(f"[{idx}/{len(entries)}] fetch {entry.source_id}: {entry.url}")
            else:
                _print_progress(_render_progress(done=idx - 1, total=len(entries), start_ts=start_ts, current=f"fetch {entry.source_id}"))

            meta: dict[str, Any] = {
                "source_id": entry.source_id,
                "title": entry.title,
                "url": entry.url,
                "fetched_date_utc": fetched_date,
                "tool": "markitdown(convert_to_markdown)",
                "cache_markdown": md_rel,
            }
            try:
                resp = _mcp_call(
                    proc,
                    reader,
                    request_id=1000 + idx,
                    method="tools/call",
                    params={"name": "convert_to_markdown", "arguments": {"uri": entry.url}},
                    timeout_sec=args.timeout_sec,
                    progress_label=f"{entry.source_id} convert_to_markdown",
                    show_progress=not args.no_progress,
                )
                if "error" in resp:
                    raise RuntimeError(str(resp["error"]))
                result = resp.get("result")
                md = _extract_markdown(result)
                status, reason = _classify_markdown(md)
                entry_dir.mkdir(parents=True, exist_ok=True)
                md_path.write_text(md, encoding="utf-8")
                meta["content_length"] = len(md)
                meta["status"] = status
                meta["reason"] = reason
                if status == "ok":
                    ok += 1
                else:
                    failed.append(f"{entry.source_id}: {status} ({reason})")
            except Exception as e:
                meta["status"] = "blocked"
                meta["error"] = str(e)
                failed.append(f"{entry.source_id}: {e}")
            finally:
                _write_meta(entry_dir=entry_dir, meta=meta)

            if args.update_registry:
                status_text = str(meta.get("status", "blocked"))
                reason = str(meta.get("reason", "")).strip()
                if status_text == "ok":
                    status_line = "ok"
                elif status_text == "js_required":
                    status_line = "js-required（建议用 playwright 抓取）"
                else:
                    status_line = "blocked（抓取失败，详见本地缓存 meta.json）"
                if reason and status_text != "ok":
                    status_line = f"{status_line}"
                updated_lines = _update_registry_block(
                    updated_lines,
                    entry=entry,
                    cache_md_rel=md_rel,
                    method="MCP `markitdown`",
                    status=status_line,
                    fetched_date=fetched_date,
                )

            if not args.no_progress:
                _print_progress(_render_progress(done=idx, total=len(entries), start_ts=start_ts, current=f"done {entry.source_id}"))

        if not args.no_progress:
            print("")

        print(f"完成：成功 {ok} / 失败 {len(failed)}")
        if failed:
            print("失败条目：")
            for item in failed[:50]:
                print(f"- {item}")
            if len(failed) > 50:
                print(f"- ... 其余 {len(failed) - 50} 条已省略")

        if args.update_registry and updated_lines != lines:
            _write_text(registry_path, updated_lines)
            print(f"已写回来源登记：{registry_path.as_posix()}")

        return 0 if not failed else 1
    finally:
        try:
            proc.kill()
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
