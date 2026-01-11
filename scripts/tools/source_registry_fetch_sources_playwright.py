"""
使用 Playwright MCP（浏览器渲染）批量抓取 source_registry.md 中的来源，并落盘为本地缓存。

适用场景：
- 目标网页需要 JS 渲染（markitdown 只能拿到壳/空白）
- 目标网页对非浏览器 UA 更敏感（markitdown 403/robot，但真实浏览器可能可访问）

输出（默认，均在 .vibe/knowledge/sources/<S-xxx>/ 下）：
- playwright_snapshot.md：可读性更好的可访问性快照（文本为主，适合后续提炼）
- playwright_dom.html：浏览器渲染后的 DOM（更高保真，适合后续做二次清洗/提炼）
- playwright_network.json：网络请求清单（用于复现/排障/后续抓 API）
- screenshot.png：可选（用于人工核对）
- meta_playwright.json：抓取元信息（日期、状态、错误等）

注意：
- Playwright 首次运行可能需要下载浏览器组件，耗时较长（脚本会显示进度提示）。
- 遇到验证码/登录墙/订阅墙，本脚本只会记录为 blocked，不会尝试绕过。

用法（仓库根目录）：
  python -X utf8 scripts/tools/source_registry_fetch_sources_playwright.py --ids "S-003,S-005"
  python -X utf8 scripts/tools/source_registry_fetch_sources_playwright.py --only-failed --limit 10

可选（人工介入）：
- 当检测到登录/订阅/验证码等阻断时，如果你拥有合法访问权限，可用 `--interactive` 启用“手动导出 → 离线转写”流程。
  脚本会提示你把网页正文导出为 HTML/PDF 文件，并自动转写为 `manual_markitdown.md` 作为后续提炼输入。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from base64 import b64decode
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from queue import Empty, Queue
from typing import Any


@dataclass(frozen=True)
class SourceEntry:
    source_id: str
    title: str
    url: str
    block_start: int
    block_end: int
    status_line: str


@dataclass(frozen=True)
class ManualTask:
    entry: SourceEntry
    hint: str
    reason: str


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _utc_date_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="用 Playwright（浏览器渲染）抓取 source_registry 来源到本地缓存")
    parser.add_argument("--registry", default="project_docs/knowledge/source_registry.md", help="来源登记文件（相对仓库根）")
    parser.add_argument("--out-dir", default=".vibe/knowledge/sources", help="缓存输出目录（相对仓库根）")
    parser.add_argument("--limit", type=int, default=0, help="最多抓取条目数（0=不限制）")
    parser.add_argument("--ids", default="", help="仅抓取指定 S-ID（逗号分隔），如 S-003,S-701")
    parser.add_argument("--only-failed", action="store_true", help="仅抓取登记里标注为 blocked/js-required 的条目")
    parser.add_argument("--force", action="store_true", help="强制重抓（忽略已有缓存）")
    parser.add_argument("--no-screenshot", action="store_true", help="不保存截图（默认保存）")
    parser.add_argument("--no-dom", action="store_true", help="不保存 DOM（默认保存 playwright_dom.html）")
    parser.add_argument("--no-network", action="store_true", help="不保存网络请求清单（默认保存 playwright_network.json）")
    parser.add_argument(
        "--user-agent",
        default="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        help="模拟标准桌面浏览器 UA（默认 Windows Chrome），空字符串表示不覆盖",
    )
    parser.add_argument(
        "--accept-language",
        default="",
        help="可选：设置 accept-language（例如 zh-CN,zh;q=0.9,en;q=0.8），空表示不设置",
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help=(
            "遇到可能需要合法访问权限/人工验证的 blocked 条目时，提示你人工介入（浏览器窗口验证/登录后重试抓取；必要时可手动导出 HTML/PDF 离线转写）"
        ),
    )
    parser.add_argument(
        "--interactive-mode",
        choices=["deferred", "immediate"],
        default="deferred",
        help=(
            "--interactive 的介入时机："
            "deferred=先抓完其它条目再逐个处理（默认，不阻塞其它抓取）；"
            "immediate=遇到阻断立刻暂停等待人工介入"
        ),
    )
    parser.add_argument(
        "--playwright-user-data-dir",
        default=".vibe/playwright/user-data",
        help="Playwright user data 目录（保存/复用登录态与会话；默认放在 .vibe 下并建议 gitignore；空字符串表示使用临时目录）",
    )
    parser.add_argument(
        "--manual-timeout-sec",
        type=int,
        default=600,
        help="--interactive 时等待人工介入解除阻断的最长秒数（默认 600s）",
    )
    parser.add_argument(
        "--manual-poll-sec",
        type=float,
        default=2.0,
        help="--interactive 时轮询页面状态的间隔秒数（默认 2s）",
    )
    parser.add_argument("--update-registry", action="store_true", help="将抓取方式/状态/日期/本地缓存写回来源登记（最小改动）")
    parser.add_argument("--startup-timeout-sec", type=int, default=900, help="启动/初始化超时（默认 900s）")
    parser.add_argument("--timeout-sec", type=int, default=180, help="单次工具调用超时（默认 180s）")
    parser.add_argument("--wait-sec", type=int, default=3, help="导航后额外等待秒数（默认 3s）")
    parser.add_argument("--no-progress", action="store_true", help="禁用进度/等待提示（默认启用）")
    return parser.parse_args()


def _normalize_sid_list(s: str) -> set[str]:
    if not s or not s.strip():
        return set()
    return {p.strip().upper() for p in s.split(",") if p.strip()}


def _read_text(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8").splitlines(keepends=False)


def _write_text(path: Path, lines: list[str]) -> None:
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


_ENTRY_HEADER_RE = re.compile(r"^###\s+(S-\d{3})(?:\s*[:：]?\s*)(.*)\s*$")
_URL_RE = re.compile(r"^\s*-\s*URL\s*[:：]\s*(\S+)\s*$")
_STATUS_RE = re.compile(r"^\s*-\s*抓取状态\s*[:：]\s*(.*)\s*$")


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
        status_line = ""
        for j in range(start, end):
            um = _URL_RE.match(lines[j])
            if um:
                url = um.group(1).strip()
            sm = _STATUS_RE.match(lines[j])
            if sm:
                status_line = (sm.group(1) or "").strip()

        if url:
            entries.append(
                SourceEntry(
                    source_id=source_id,
                    title=title,
                    url=url,
                    block_start=start,
                    block_end=end,
                    status_line=status_line,
                )
            )
        i = end
    return entries


def _render_progress(done: int, total: int, start_ts: float, current: str) -> str:
    elapsed = max(0.0, time.time() - start_ts)
    rate = done / elapsed if elapsed > 0 else 0.0
    eta = (total - done) / rate if rate > 0 else 0.0
    return f"[{done:>3}/{total:<3}] elapsed={elapsed:>6.1f}s eta={eta:>6.1f}s  {current}"


def _print_progress(line: str) -> None:
    cols = 160
    try:
        sys.stdout.write("\r" + line.ljust(cols))
        sys.stdout.flush()
    except OSError:
        # 某些执行环境（例如外部强制终止/关闭 stdout）可能导致 flush 失败；忽略即可。
        return


class _LineReader:
    def __init__(self, stream: Any) -> None:
        self._q: "Queue[str]" = Queue()
        self._t = threading.Thread(target=self._run, args=(stream,), daemon=True)
        self._t.start()

    def _run(self, stream: Any) -> None:
        try:
            for line in stream:
                self._q.put(line)
        except Exception:
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


def _start_playwright_mcp(*, user_data_dir: str) -> tuple[subprocess.Popen[str], _LineReader]:
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env["npm_config_cache"] = ".vibe/npm-cache"

    cmd = ["cmd", "/c", "npx", "-y", "@playwright/mcp@0.0.55"]
    udd = (user_data_dir or "").strip()
    if udd:
        cmd.extend(["--user-data-dir", udd])
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
        raise RuntimeError("playwright MCP stdout 不可用")
    return proc, _LineReader(proc.stdout)


def _resolve_repo_path(repo_root: Path, path_str: str) -> Path:
    p = Path(path_str)
    if p.is_absolute():
        return p
    return repo_root / p


def _start_markitdown_mcp() -> tuple[subprocess.Popen[str], _LineReader]:
    """
    启动 markitdown MCP：用于把“手动导出的 HTML/PDF”离线转写为 Markdown。

    说明：
    - 这里使用 uvx 运行固定版本的 markitdown-mcp，避免全局依赖污染。
    """
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


def _init_markitdown_mcp(
    proc: subprocess.Popen[str],
    reader: _LineReader,
    *,
    startup_timeout_sec: int,
    show_progress: bool,
) -> None:
    init_resp = _mcp_call(
        proc,
        reader,
        request_id=1,
        method="initialize",
        params={
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "freqtrade_demo_source_registry_markitdown", "version": "0.1.0"},
        },
        timeout_sec=startup_timeout_sec,
        progress_label="markitdown initialize",
        show_progress=show_progress,
    )
    if "result" not in init_resp:
        raise RuntimeError(f"markitdown initialize 失败：{init_resp}")
    _mcp_notify(proc, method="notifications/initialized", params={})

    tools_resp = _mcp_call(
        proc,
        reader,
        request_id=2,
        method="tools/list",
        params={},
        timeout_sec=startup_timeout_sec,
        progress_label="markitdown tools/list",
        show_progress=show_progress,
    )
    names = {t.get("name") for t in tools_resp.get("result", {}).get("tools", [])}
    if "convert_to_markdown" not in names:
        raise RuntimeError(f"markitdown tools 缺失：need=convert_to_markdown got={sorted(names)}")


def _markitdown_convert_to_markdown(
    proc: subprocess.Popen[str],
    reader: _LineReader,
    *,
    request_id: int,
    uri: str,
    timeout_sec: int,
    progress_label: str,
    show_progress: bool,
) -> str:
    resp = _mcp_call(
        proc,
        reader,
        request_id=request_id,
        method="tools/call",
        params={"name": "convert_to_markdown", "arguments": {"uri": uri}},
        timeout_sec=timeout_sec,
        progress_label=progress_label,
        show_progress=show_progress,
    )
    if "error" in resp:
        raise RuntimeError(str(resp["error"]))
    return _extract_markdown_from_markitdown_result(resp.get("result"))


def _classify_snapshot(markdown: str) -> tuple[str, str]:
    md = (markdown or "").strip()
    if not md:
        return "blocked", "empty"

    low = md.lower()

    m = re.search(r"(?im)^-\s*page url:\s*(\S+)\s*$", md)
    page_url = (m.group(1).strip() if m else "").lower()
    if page_url and ("/login" in page_url or "/signin" in page_url or "/sign-in" in page_url):
        return "blocked", "login_redirect"
    signals: list[tuple[str, str]] = [
        ("verifying that you are not a robot", "robot_check"),
        ("captcha", "captcha"),
        ("cloudflare", "cloudflare"),
        ("access denied", "access_denied"),
        ("forbidden", "forbidden"),
        ('heading "sign in"', "login_page"),
        ('heading "log in"', "login_page"),
        ('heading "login"', "login_page"),
        ("subscribe to continue", "paywall"),
        ("subscription required", "paywall"),
    ]
    for token, reason in signals:
        if token in low:
            return "blocked", reason

    if len(md) < 200:
        return "blocked", "too_short"

    return "ok", "content"


def _is_manual_candidate(reason: str) -> bool:
    """
    哪些阻断更可能通过“合法访问 + 人工导出”解决。

    注意：
    - 这里只做“需要人工介入”的提示，不提供任何绕过/对抗站点风控的方案。
    """
    r = (reason or "").strip().lower()
    return r in {
        "login_redirect",
        "login_page",
        "paywall",
        "captcha",
        "robot_check",
        "cloudflare",
        "access_denied",
        "forbidden",
    }


def _manual_hint(reason: str) -> str:
    r = (reason or "").strip().lower()
    if r in {"login_redirect", "login_page"}:
        return "检测到登录阻断（需要账号权限）"
    if r == "paywall":
        return "检测到订阅/付费墙（需要订阅或合法访问权限）"
    if r in {"captcha", "robot_check", "cloudflare"}:
        return "检测到人机验证/风控页面（需要人工验证）"
    if r in {"access_denied", "forbidden"}:
        return "检测到权限/访问拒绝（可能需要授权或站点限制）"
    return f"检测到阻断（reason={reason}）"


def _safe_input(prompt: str) -> str:
    try:
        return input(prompt)
    except EOFError:
        return ""


def _ask_yes(prompt: str) -> bool:
    s = _safe_input(prompt).strip().lower()
    if not s:
        return False
    return s in {"y", "yes", "是", "确认", "继续", "1"}


def _ask_existing_file_path(prompt: str, *, max_tries: int = 3) -> Path | None:
    for _ in range(max(1, max_tries)):
        raw = _safe_input(prompt).strip()
        if not raw:
            return None
        raw = raw.strip("\"' ")
        p = Path(raw)
        try:
            p = p.expanduser().resolve()
        except Exception:
            pass
        if p.exists() and p.is_file():
            return p
        print(f"未找到文件：{p}")
    return None


def _extract_markdown_from_markitdown_result(result: Any) -> str:
    if isinstance(result, str) and result.strip():
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
    raise ValueError("无法从 markitdown MCP 返回中提取 Markdown")


def _classify_markdown(markdown: str) -> tuple[str, str]:
    md = (markdown or "").strip()
    if not md:
        return "blocked", "empty"
    low = md.lower()
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
        ("request blocked", "request_blocked"),
    ]
    for token, reason in blocked_signals:
        if token in low:
            return "blocked", reason
    if len(md) < 120:
        return "blocked", "too_short"
    return "ok", "content"


def _extract_text_from_mcp_result(resp: dict[str, Any]) -> str:
    result = resp.get("result", {})
    return _extract_text_from_call_result(result)


def _extract_text_from_call_result(result: Any) -> str:
    if not isinstance(result, dict):
        return ""
    content = result.get("content", [])
    if not isinstance(content, list):
        return ""
    parts: list[str] = []
    for item in content:
        if not isinstance(item, dict):
            continue
        if item.get("type") != "text":
            continue
        text = item.get("text")
        if isinstance(text, str) and text.strip():
            parts.append(text)
    return "\n".join(parts)


def _extract_image_from_mcp_result(resp: dict[str, Any]) -> tuple[bytes, str] | None:
    result = resp.get("result", {})
    content = result.get("content", [])
    if not isinstance(content, list):
        return None
    for item in content:
        if not isinstance(item, dict):
            continue
        if item.get("type") != "image":
            continue
        data = item.get("data")
        mime = item.get("mimeType") or "image/png"
        if isinstance(data, str) and data.strip():
            try:
                return b64decode(data), str(mime)
            except Exception:
                return None
    return None


_PAGE_URL_RE = re.compile(r"(?im)^-\s*page url:\s*(\S+)\s*$")
_PAGE_TITLE_RE = re.compile(r"(?im)^-\s*page title:\s*(.*)\s*$")


def _extract_page_state(snapshot_markdown: str) -> tuple[str, str]:
    md = snapshot_markdown or ""
    url_m = _PAGE_URL_RE.search(md)
    title_m = _PAGE_TITLE_RE.search(md)
    url = (url_m.group(1).strip() if url_m else "").strip()
    title = (title_m.group(1).strip() if title_m else "").strip()
    return url, title


_NET_LINE_RE = re.compile(r"^\[(?P<method>[A-Z]+)\]\s+(?P<url>\S+)\s+=>\s+\[(?P<status>\d{3})\]", re.MULTILINE)


def _parse_network_summary(text: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for m in _NET_LINE_RE.finditer(text or ""):
        out.append(
            {
                "method": m.group("method"),
                "url": m.group("url"),
                "status": int(m.group("status")),
            }
        )
    return out


def _cache_paths(repo_root: Path, out_dir: str, source_id: str) -> tuple[Path, Path, Path, Path, Path]:
    base = Path(out_dir)
    if not base.is_absolute():
        base = repo_root / base
    entry_dir = base / source_id
    snapshot_path = entry_dir / "playwright_snapshot.md"
    dom_path = entry_dir / "playwright_dom.html"
    network_path = entry_dir / "playwright_network.json"
    meta_path = entry_dir / "meta_playwright.json"
    return entry_dir, snapshot_path, dom_path, network_path, meta_path


def _manual_paths(entry_dir: Path, src_path: Path) -> tuple[Path, Path, Path]:
    suffix = src_path.suffix if src_path.suffix else ".bin"
    manual_src = entry_dir / f"manual_source{suffix}"
    manual_md = entry_dir / "manual_markitdown.md"
    manual_meta = entry_dir / "manual_meta.json"
    return manual_src, manual_md, manual_meta


def _run_manual_export_workflow(
    entry: SourceEntry,
    entry_dir: Path,
    repo_root: Path,
    *,
    hint: str,
    md_proc: subprocess.Popen[str] | None,
    md_reader: _LineReader | None,
    markitdown_ready: bool,
    startup_timeout_sec: int,
    timeout_sec: int,
    show_progress: bool,
) -> tuple[bool, dict[str, Any], subprocess.Popen[str] | None, _LineReader | None, bool]:
    """
    人工导出 → 离线转写（需要你拥有合法访问权限）。

    返回：
    - manual_ok：是否得到可用正文 Markdown
    - meta_updates：应写入 meta_playwright.json 的补充字段
    - md_proc/md_reader/markitdown_ready：markitdown MCP 进程状态（可能被延迟启动）
    """
    print(f"⚠️ {entry.source_id} 可能需要人工介入：{hint}")
    print(f"- URL: {entry.url}")
    print("如你拥有该内容的合法访问权限（账号/订阅/允许保存），可以手动导出网页正文文件后让脚本离线转写。")
    print("推荐导出方式：浏览器“另存为网页（完整）”或“打印为 PDF”。")
    if not _ask_yes("是否现在人工介入并提供导出文件路径？[y/N]: "):
        return False, {}, md_proc, md_reader, markitdown_ready

    src_path = _ask_existing_file_path("请输入导出的 HTML/PDF 文件路径（留空取消）： ")
    if not src_path:
        return False, {}, md_proc, md_reader, markitdown_ready

    manual_src, manual_md, manual_meta = _manual_paths(entry_dir, src_path)
    entry_dir.mkdir(parents=True, exist_ok=True)

    manual_meta_obj: dict[str, Any] = {
        "source_id": entry.source_id,
        "url": entry.url,
        "hint": hint,
        "exported_file_original": str(src_path),
        "exported_file_copied": str(manual_src),
        "generated_markdown": str(manual_md),
    }

    meta_updates: dict[str, Any] = {}
    try:
        shutil.copy2(src_path, manual_src)
        meta_updates["cache_manual_source"] = str(manual_src.relative_to(repo_root)).replace("\\", "/")

        if md_proc is None or md_reader is None:
            print("启动 markitdown MCP（用于离线转写手动导出文件）…")
            md_proc, md_reader = _start_markitdown_mcp()
            markitdown_ready = False

        if not markitdown_ready:
            _init_markitdown_mcp(
                md_proc,
                md_reader,
                startup_timeout_sec=startup_timeout_sec,
                show_progress=show_progress,
            )
            markitdown_ready = True

        md = _markitdown_convert_to_markdown(
            md_proc,
            md_reader,
            request_id=10_000 + int(entry.source_id.split("-")[1]),
            uri=manual_src.as_uri(),
            timeout_sec=max(120, timeout_sec),
            progress_label=f"{entry.source_id} manual markitdown",
            show_progress=show_progress,
        )
        manual_md.write_text(md, encoding="utf-8")

        m_status, m_reason = _classify_markdown(md)
        manual_meta_obj["status"] = m_status
        manual_meta_obj["reason"] = m_reason
        manual_meta_obj["content_length"] = len(md)
        meta_updates["cache_manual_markdown"] = str(manual_md.relative_to(repo_root)).replace("\\", "/")
        meta_updates["manual_markdown_status"] = m_status
        meta_updates["manual_markdown_reason"] = m_reason
        meta_updates["manual_markdown_length"] = len(md)
        meta_updates["manual_status"] = "ok" if m_status == "ok" else "blocked"
        return m_status == "ok", meta_updates, md_proc, md_reader, markitdown_ready
    except Exception as e:
        manual_meta_obj["status"] = "blocked"
        manual_meta_obj["error"] = str(e)
        meta_updates["manual_status"] = "blocked"
        meta_updates["manual_error"] = str(e)
        return False, meta_updates, md_proc, md_reader, markitdown_ready
    finally:
        try:
            manual_meta.write_text(json.dumps(manual_meta_obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        except Exception:
            pass


def _update_registry_block(
    lines: list[str],
    entry: SourceEntry,
    cache_rel: str,
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
    cache_line = f"- 本地缓存：{cache_rel}"

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
                # 避免把纯 ok/blocked 的重复行当作备注保留
                if note and note != status:
                    # 若备注与当前状态类别冲突（例如 ok 条目里残留 blocked 行），视为历史错位噪声，丢弃。
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


def _js_str(v: str) -> str:
    return json.dumps(v, ensure_ascii=False)


def _try_set_ua(
    proc: subprocess.Popen[str],
    reader: _LineReader,
    request_id: int,
    *,
    user_agent: str,
    accept_language: str,
    timeout_sec: int,
    progress_label: str,
    show_progress: bool,
) -> None:
    """
    使用 CDP 设置 UA/语言，属于“正常模拟”，不做反检测/绕过风控。
    """
    ua = (user_agent or "").strip()
    al = (accept_language or "").strip()
    if not ua and not al:
        return

    args: list[str] = []
    if ua:
        args.append(f"userAgent: {_js_str(ua)}")
    if al:
        args.append(f"acceptLanguage: {_js_str(al)}")
    args_obj = "{ " + ", ".join(args) + " }"

    js_code = (
        "async (page) => {\n"
        "  const session = await page.context().newCDPSession(page);\n"
        "  await session.send('Network.enable');\n"
        f"  await session.send('Network.setUserAgentOverride', {args_obj});\n"
        "  return true;\n"
        "}\n"
    )

    resp = _mcp_call(
        proc,
        reader,
        request_id=request_id,
        method="tools/call",
        params={"name": "browser_run_code", "arguments": {"code": js_code}},
        timeout_sec=timeout_sec,
        progress_label=progress_label,
        show_progress=show_progress,
    )
    if "error" in resp:
        raise RuntimeError(str(resp["error"]))


def _try_capture_dom(
    proc: subprocess.Popen[str],
    reader: _LineReader,
    request_id: int,
    *,
    timeout_sec: int,
    progress_label: str,
    show_progress: bool,
) -> str:
    resp = _mcp_call(
        proc,
        reader,
        request_id=request_id,
        method="tools/call",
        params={
            "name": "browser_evaluate",
            "arguments": {
                "function": "() => document.documentElement ? document.documentElement.outerHTML : ''",
            },
        },
        timeout_sec=timeout_sec,
        progress_label=progress_label,
        show_progress=show_progress,
    )
    if "error" in resp:
        raise RuntimeError(str(resp["error"]))
    result = resp.get("result", {})
    value = None
    if isinstance(result, dict):
        value = result.get("value")
    if isinstance(value, str):
        return value

    # 兼容：部分 MCP 实现会把 evaluate 结果塞进 text content（可能是 JSON 字符串）
    text = _extract_text_from_mcp_result(resp).strip()
    if not text:
        return ""
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, str) else str(parsed)
    except Exception:
        return text


def _try_capture_page_meta(
    proc: subprocess.Popen[str],
    reader: _LineReader,
    request_id: int,
    *,
    timeout_sec: int,
    progress_label: str,
    show_progress: bool,
) -> dict[str, Any]:
    resp = _mcp_call(
        proc,
        reader,
        request_id=request_id,
        method="tools/call",
        params={
            "name": "browser_evaluate",
            "arguments": {
                "function": "() => ({ url: location.href, title: document.title })",
            },
        },
        timeout_sec=timeout_sec,
        progress_label=progress_label,
        show_progress=show_progress,
    )
    if "error" in resp:
        raise RuntimeError(str(resp["error"]))
    result = resp.get("result", {})
    value = None
    if isinstance(result, dict):
        value = result.get("value")
    if isinstance(value, dict):
        return value

    text = _extract_text_from_mcp_result(resp).strip()
    if not text:
        return {}
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def _try_capture_network_requests(
    proc: subprocess.Popen[str],
    reader: _LineReader,
    request_id: int,
    *,
    include_static: bool,
    timeout_sec: int,
    progress_label: str,
    show_progress: bool,
) -> dict[str, Any]:
    resp = _mcp_call(
        proc,
        reader,
        request_id=request_id,
        method="tools/call",
        params={
            "name": "browser_network_requests",
            "arguments": {"includeStatic": bool(include_static)},
        },
        timeout_sec=timeout_sec,
        progress_label=progress_label,
        show_progress=show_progress,
    )
    if "error" in resp:
        raise RuntimeError(str(resp["error"]))
    result = resp.get("result", {})
    if isinstance(result, dict):
        return result
    text = _extract_text_from_mcp_result(resp).strip()
    if not text:
        return {}
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else {"value": parsed}
    except Exception:
        return {"text": text}


def _wait_for_manual_unblock(
    proc: subprocess.Popen[str],
    reader: _LineReader,
    request_id_base: int,
    *,
    timeout_sec: int,
    poll_sec: float,
    progress_label: str,
    show_progress: bool,
) -> tuple[str, str, str]:
    """
    等待你在浏览器窗口完成“合法登录/验证”等人工介入后，页面恢复可访问。

    返回：
    - last_snapshot_text
    - last_status: ok/blocked
    - last_reason
    """
    start_ts = time.time()
    poll = max(0.2, float(poll_sec))
    limit = max(1, int(timeout_sec))

    last_text = ""
    last_status = "blocked"
    last_reason = "manual_wait_start"

    attempt = 0
    while True:
        elapsed = time.time() - start_ts
        if elapsed >= limit:
            break

        attempt += 1
        if show_progress:
            _print_progress(f"[wait] {progress_label} elapsed={elapsed:>6.1f}s last={last_reason}")

        sleep_for = min(poll, max(0.0, limit - elapsed))
        if sleep_for > 0:
            _mcp_call(
                proc,
                reader,
                request_id=request_id_base + attempt * 10 + 1,
                method="tools/call",
                params={"name": "browser_wait_for", "arguments": {"time": float(sleep_for)}},
                timeout_sec=max(30, int(sleep_for) + 30),
                progress_label=f"{progress_label} wait",
                show_progress=False,
            )

        snap = _mcp_call(
            proc,
            reader,
            request_id=request_id_base + attempt * 10 + 2,
            method="tools/call",
            params={"name": "browser_snapshot", "arguments": {}},
            timeout_sec=max(60, int(poll) + 60),
            progress_label=f"{progress_label} snapshot",
            show_progress=False,
        )
        if "error" in snap:
            last_text = ""
            last_status = "blocked"
            last_reason = "snapshot_error"
            continue

        text = _extract_text_from_mcp_result(snap)
        status, reason = _classify_snapshot(text)
        last_text = text
        last_status = status
        last_reason = reason
        if status == "ok":
            break

    if show_progress:
        print("")
    return last_text, last_status, last_reason


def _capture_current_page(
    proc: subprocess.Popen[str],
    reader: _LineReader,
    *,
    entry: SourceEntry,
    repo_root: Path,
    entry_dir: Path,
    snapshot_path: Path,
    dom_path: Path,
    network_path: Path,
    snapshot_rel: str,
    dom_rel: str,
    network_rel: str,
    request_id_base: int,
    timeout_sec: int,
    can_eval: bool,
    can_net: bool,
    can_shot: bool,
    no_dom: bool,
    no_network: bool,
    no_screenshot: bool,
    show_progress: bool,
    meta: dict[str, Any],
) -> tuple[str, str, str]:
    snap = _mcp_call(
        proc,
        reader,
        request_id=request_id_base + 3,
        method="tools/call",
        params={"name": "browser_snapshot", "arguments": {}},
        timeout_sec=timeout_sec,
        progress_label=f"{entry.source_id} snapshot",
        show_progress=show_progress,
    )
    if "error" in snap:
        raise RuntimeError(str(snap["error"]))

    snapshot_text = _extract_text_from_mcp_result(snap)
    snapshot_path.write_text(snapshot_text, encoding="utf-8")

    page_url, page_title = _extract_page_state(snapshot_text)
    if page_url:
        meta["final_url"] = page_url
    if page_title:
        meta["page_title"] = page_title

    if not no_dom and can_eval:
        dom_html = _try_capture_dom(
            proc,
            reader,
            request_id=request_id_base + 32,
            timeout_sec=max(timeout_sec, 240),
            progress_label=f"{entry.source_id} dom",
            show_progress=show_progress,
        )
        dom_path.write_text(dom_html, encoding="utf-8")
        meta["cache_dom"] = dom_rel
        meta["dom_length"] = len(dom_html)

    if not no_network and can_net:
        net = _try_capture_network_requests(
            proc,
            reader,
            request_id=request_id_base + 33,
            include_static=False,
            timeout_sec=max(timeout_sec, 240),
            progress_label=f"{entry.source_id} network",
            show_progress=show_progress,
        )
        network_path.write_text(json.dumps(net, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        meta["cache_network"] = network_rel
        if isinstance(net, dict):
            meta["network_keys"] = sorted([k for k in net.keys() if isinstance(k, str)])[:50]
            net_text = _extract_text_from_call_result(net).strip()
            if net_text:
                meta["network_text_length"] = len(net_text)
                parsed = _parse_network_summary(net_text)
                if parsed:
                    meta["network_request_count"] = len(parsed)
                    status_hist: dict[str, int] = {}
                    for item in parsed:
                        status_hist[str(item.get("status"))] = status_hist.get(str(item.get("status")), 0) + 1
                    meta["network_status_hist"] = status_hist

    if not no_screenshot and can_shot:
        png_path = entry_dir / "screenshot.png"
        shot = _mcp_call(
            proc,
            reader,
            request_id=request_id_base + 4,
            method="tools/call",
            params={
                "name": "browser_take_screenshot",
                "arguments": {"fullPage": True},
            },
            timeout_sec=max(timeout_sec, 300),
            progress_label=f"{entry.source_id} screenshot",
            show_progress=show_progress,
        )
        if "error" in shot:
            raise RuntimeError(str(shot["error"]))
        img = _extract_image_from_mcp_result(shot)
        if img:
            png_bytes, mime = img
            png_path.write_bytes(png_bytes)
            meta["cache_screenshot"] = str(png_path.relative_to(repo_root)).replace("\\", "/")
            meta["cache_screenshot_mime"] = mime

    auto_status, auto_reason = _classify_snapshot(snapshot_text)
    return snapshot_text, auto_status, auto_reason


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

    wanted = _normalize_sid_list(args.ids)
    if wanted:
        entries = [e for e in entries if e.source_id in wanted]

    if args.only_failed:

        def is_failed(e: SourceEntry) -> bool:
            s = (e.status_line or "").lower()
            return ("blocked" in s) or ("js-required" in s) or ("js_required" in s)

        entries = [e for e in entries if is_failed(e)]

    if args.limit and args.limit > 0:
        entries = entries[: args.limit]

    if not entries:
        print("无可抓取条目（过滤后为空）。", file=sys.stderr)
        return 2

    print(f"将用浏览器抓取 {len(entries)} 条来源到本地缓存：{args.out_dir}")
    print("提示：首次运行 Playwright 可能需要下载浏览器组件（较大），脚本会显示等待进度。")

    playwright_user_data_dir = (args.playwright_user_data_dir or "").strip()
    if playwright_user_data_dir:
        resolved = _resolve_repo_path(repo_root, playwright_user_data_dir)
        resolved.mkdir(parents=True, exist_ok=True)
        playwright_user_data_dir = str(resolved).replace("\\", "/")

    print("启动 playwright MCP（可能需要首次下载依赖/浏览器，请稍候）…")
    proc, reader = _start_playwright_mcp(user_data_dir=playwright_user_data_dir)
    md_proc: subprocess.Popen[str] | None = None
    try:
        init = _mcp_call(
            proc,
            reader,
            request_id=1,
            method="initialize",
            params={
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "freqtrade_demo_source_registry_fetch_playwright", "version": "0.1.0"},
            },
            timeout_sec=args.startup_timeout_sec,
            progress_label="initialize",
            show_progress=not args.no_progress,
        )
        if "result" not in init:
            print(f"initialize 失败：{init}", file=sys.stderr)
            return 1
        _mcp_notify(proc, method="notifications/initialized", params={})

        tools = _mcp_call(
            proc,
            reader,
            request_id=2,
            method="tools/list",
            params={},
            timeout_sec=args.startup_timeout_sec,
            progress_label="tools/list",
            show_progress=not args.no_progress,
        )
        names = {t.get("name") for t in tools.get("result", {}).get("tools", [])}
        base_required = {"browser_navigate", "browser_snapshot", "browser_wait_for"}
        missing = sorted(base_required - names)
        if missing:
            print(f"playwright tools 缺失：need={sorted(base_required)} missing={missing}", file=sys.stderr)
            return 1

        can_run_code = "browser_run_code" in names
        can_eval = "browser_evaluate" in names
        can_net = "browser_network_requests" in names
        can_shot = "browser_take_screenshot" in names

        if not args.no_screenshot and not can_shot:
            print("警告：playwright MCP 不支持 browser_take_screenshot，将自动跳过截图。", file=sys.stderr)
            args.no_screenshot = True
        if not args.no_dom and not can_eval:
            print("警告：playwright MCP 不支持 browser_evaluate，将自动跳过 DOM 采集。", file=sys.stderr)
            args.no_dom = True
        if not args.no_network and not can_net:
            print("警告：playwright MCP 不支持 browser_network_requests，将自动跳过网络请求清单。", file=sys.stderr)
            args.no_network = True
        if (args.user_agent or args.accept_language) and not can_run_code:
            print("警告：playwright MCP 不支持 browser_run_code，将无法覆盖 UA/语言。", file=sys.stderr)

        start_ts = time.time()
        results: dict[str, tuple[str, str]] = {}
        manual_queue: list[ManualTask] = []
        manual_queue_ids: set[str] = set()
        manual_needed: list[tuple[str, str, str]] = []
        manual_succeeded_browser: list[str] = []
        manual_succeeded_export: list[str] = []
        fetched_date = _utc_date_str()
        updated_lines = lines
        md_reader: _LineReader | None = None
        markitdown_ready = False

        def enqueue_manual(entry: SourceEntry, *, hint: str, reason: str) -> None:
            if entry.source_id in manual_queue_ids:
                return
            manual_queue_ids.add(entry.source_id)
            manual_queue.append(ManualTask(entry=entry, hint=hint, reason=reason))

        for idx, entry in enumerate(entries, start=1):
            entry_dir, snapshot_path, dom_path, network_path, meta_path = _cache_paths(repo_root, args.out_dir, entry.source_id)
            snapshot_rel = str(snapshot_path.relative_to(repo_root)).replace("\\", "/")
            dom_rel = str(dom_path.relative_to(repo_root)).replace("\\", "/")
            network_rel = str(network_path.relative_to(repo_root)).replace("\\", "/")
            meta_rel = str(meta_path.relative_to(repo_root)).replace("\\", "/")
            manual_md_path = entry_dir / "manual_markitdown.md"

            if snapshot_path.exists() and meta_path.exists() and not args.force:
                try:
                    cached_meta = json.loads(meta_path.read_text(encoding="utf-8"))
                except Exception:
                    cached_meta = {}

                cached_status = str(cached_meta.get("status", "blocked"))
                cached_reason = str(cached_meta.get("reason", "")).strip()
                auto_reason = str(cached_meta.get("auto_reason") or cached_reason).strip()

                manual_candidate = cached_status != "ok" and _is_manual_candidate(auto_reason)
                if manual_candidate:
                    hint = _manual_hint(auto_reason)
                    cached_meta["manual_candidate"] = True
                    cached_meta["manual_hint"] = hint
                    enqueue_manual(entry, hint=hint, reason=auto_reason)

                    if not args.interactive:
                        manual_needed.append((entry.source_id, entry.url, hint))

                # 回写 meta（可能包含 manual_hint / manual_export 结果）
                try:
                    meta_path.write_text(json.dumps(cached_meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                except Exception:
                    pass

                if (
                    manual_candidate
                    and bool(args.interactive)
                    and str(args.interactive_mode).strip().lower() == "immediate"
                ):
                    # immediate 模式下：即使已有缓存，也允许重新抓取/人工介入（不在这里 continue）
                    pass
                else:
                    results[entry.source_id] = (cached_status, cached_reason or auto_reason)

                    if args.update_registry:
                        cache_for_registry = snapshot_rel
                        if cached_status == "ok" and cached_reason == "manual_export":
                            cmm = cached_meta.get("cache_manual_markdown")
                            if isinstance(cmm, str) and cmm.strip():
                                cache_for_registry = cmm.strip()

                        if cached_status == "ok" and cached_reason == "manual_export":
                            status_line = "ok（manual-export，见本地缓存）"
                        elif cached_status == "ok":
                            status_line = "ok"
                        else:
                            if manual_candidate:
                                hint = str(cached_meta.get("manual_hint") or _manual_hint(auto_reason))
                                status_line = f"blocked（{hint}；如有合法访问权限可用 --interactive）"
                            else:
                                reason_text = cached_reason or "抓取失败"
                                status_line = f"blocked（{reason_text}，详见本地缓存 meta_playwright.json）"

                        updated_lines = _update_registry_block(
                            updated_lines,
                            entry=entry,
                            cache_rel=cache_for_registry,
                            method="MCP `playwright`",
                            status=status_line,
                            fetched_date=fetched_date,
                        )

                    if not args.no_progress:
                        _print_progress(_render_progress(idx, len(entries), start_ts, f"skip {entry.source_id}"))
                    continue

            if args.no_progress:
                print(f"[{idx}/{len(entries)}] fetch {entry.source_id}: {entry.url}")
            else:
                _print_progress(_render_progress(idx - 1, len(entries), start_ts, f"fetch {entry.source_id}"))

            entry_dir.mkdir(parents=True, exist_ok=True)
            meta: dict[str, Any] = {
                "source_id": entry.source_id,
                "title": entry.title,
                "url": entry.url,
                "fetched_date_utc": fetched_date,
                "tool": "playwright(browser_snapshot)",
                "cache_snapshot": snapshot_rel,
                "meta_path": meta_rel,
                "ua_override": bool((args.user_agent or "").strip() or (args.accept_language or "").strip()),
                "user_agent": (args.user_agent or "").strip() if (args.user_agent or "").strip() else None,
                "accept_language": (args.accept_language or "").strip() if (args.accept_language or "").strip() else None,
            }

            try:
                if can_run_code and ((args.user_agent or "").strip() or (args.accept_language or "").strip()):
                    _try_set_ua(
                        proc,
                        reader,
                        request_id=1000 + idx * 10 + 0,
                        user_agent=args.user_agent,
                        accept_language=args.accept_language,
                        timeout_sec=args.timeout_sec,
                        progress_label=f"{entry.source_id} ua",
                        show_progress=not args.no_progress,
                    )

                nav = _mcp_call(
                    proc,
                    reader,
                    request_id=1000 + idx * 10 + 1,
                    method="tools/call",
                    params={"name": "browser_navigate", "arguments": {"url": entry.url}},
                    timeout_sec=args.timeout_sec,
                    progress_label=f"{entry.source_id} navigate",
                    show_progress=not args.no_progress,
                )
                if "error" in nav:
                    raise RuntimeError(str(nav["error"]))

                if args.wait_sec and args.wait_sec > 0:
                    _mcp_call(
                        proc,
                        reader,
                        request_id=1000 + idx * 10 + 2,
                        method="tools/call",
                        params={"name": "browser_wait_for", "arguments": {"time": int(args.wait_sec)}},
                        timeout_sec=max(args.timeout_sec, args.wait_sec + 10),
                        progress_label=f"{entry.source_id} wait",
                        show_progress=not args.no_progress,
                    )

                snapshot_text, auto_status, auto_reason = _capture_current_page(
                    proc,
                    reader,
                    entry=entry,
                    repo_root=repo_root,
                    entry_dir=entry_dir,
                    snapshot_path=snapshot_path,
                    dom_path=dom_path,
                    network_path=network_path,
                    snapshot_rel=snapshot_rel,
                    dom_rel=dom_rel,
                    network_rel=network_rel,
                    request_id_base=1000 + idx * 10,
                    timeout_sec=args.timeout_sec,
                    can_eval=can_eval,
                    can_net=can_net,
                    can_shot=can_shot,
                    no_dom=bool(args.no_dom),
                    no_network=bool(args.no_network),
                    no_screenshot=bool(args.no_screenshot),
                    show_progress=not args.no_progress,
                    meta=meta,
                )
                meta["auto_status"] = auto_status
                meta["auto_reason"] = auto_reason

                status = auto_status
                reason = auto_reason
                manual_candidate = status != "ok" and _is_manual_candidate(reason)
                if manual_candidate:
                    hint = _manual_hint(reason)
                    meta["manual_candidate"] = True
                    meta["manual_hint"] = hint
                    enqueue_manual(entry, hint=hint, reason=reason)
                    if not args.interactive:
                        manual_needed.append((entry.source_id, entry.url, hint))
                    elif str(args.interactive_mode).strip().lower() == "immediate":
                        if not args.no_progress:
                            print("")
                        print(f"⚠️ {entry.source_id} 需要人工介入：{hint}")
                        print(f"- URL: {entry.url}")
                        if _ask_yes("你是否拥有该内容的合法访问权限，并愿意现在人工介入？[y/N]: "):
                            meta["manual_intervention"] = True
                            meta["manual_intervention_mode"] = "immediate"
                            meta["manual_intervention_confirmed"] = True
                            meta["manual_wait_timeout_sec"] = int(args.manual_timeout_sec)
                            meta["manual_wait_poll_sec"] = float(args.manual_poll_sec)
                            print(
                                "请在弹出的浏览器窗口中完成验证/登录/订阅确认等操作。"
                                f"脚本将自动等待最多 {meta['manual_wait_timeout_sec']}s，并在检测到页面可访问后继续抓取…"
                            )
                            _, wait_status, wait_reason = _wait_for_manual_unblock(
                                proc,
                                reader,
                                request_id_base=310_000 + idx * 100,
                                timeout_sec=int(args.manual_timeout_sec),
                                poll_sec=float(args.manual_poll_sec),
                                progress_label=f"{entry.source_id} manual",
                                show_progress=not args.no_progress,
                            )
                            meta["manual_wait_last_status"] = wait_status
                            meta["manual_wait_last_reason"] = wait_reason

                            snapshot_text, auto_status, auto_reason = _capture_current_page(
                                proc,
                                reader,
                                entry=entry,
                                repo_root=repo_root,
                                entry_dir=entry_dir,
                                snapshot_path=snapshot_path,
                                dom_path=dom_path,
                                network_path=network_path,
                                snapshot_rel=snapshot_rel,
                                dom_rel=dom_rel,
                                network_rel=network_rel,
                                request_id_base=320_000 + idx * 100,
                                timeout_sec=args.timeout_sec,
                                can_eval=can_eval,
                                can_net=can_net,
                                can_shot=can_shot,
                                no_dom=bool(args.no_dom),
                                no_network=bool(args.no_network),
                                no_screenshot=bool(args.no_screenshot),
                                show_progress=not args.no_progress,
                                meta=meta,
                            )
                            meta["auto_status"] = auto_status
                            meta["auto_reason"] = auto_reason
                            status = auto_status
                            reason = auto_reason
                            if status == "ok":
                                manual_succeeded_browser.append(entry.source_id)
                            else:
                                if _ask_yes("仍受阻，是否改用导出 HTML/PDF 离线转写？[y/N]: "):
                                    manual_ok, updates, md_proc, md_reader, markitdown_ready = _run_manual_export_workflow(
                                        entry,
                                        entry_dir,
                                        repo_root,
                                        hint=hint,
                                        md_proc=md_proc,
                                        md_reader=md_reader,
                                        markitdown_ready=markitdown_ready,
                                        startup_timeout_sec=args.startup_timeout_sec,
                                        timeout_sec=args.timeout_sec,
                                        show_progress=not args.no_progress,
                                    )
                                    meta.update(updates)
                                    if manual_ok:
                                        status = "ok"
                                        reason = "manual_export"
                                        manual_succeeded_export.append(entry.source_id)
                                    else:
                                        manual_needed.append((entry.source_id, entry.url, hint))
                                else:
                                    manual_needed.append((entry.source_id, entry.url, hint))
                        else:
                            meta["manual_intervention"] = False
                            meta["manual_intervention_confirmed"] = False
                            manual_needed.append((entry.source_id, entry.url, hint))
                    else:
                        # deferred：不阻塞当前批量抓取，稍后统一提示人工介入
                        if not args.no_progress:
                            print("")
                        print(f"⚠️ {entry.source_id} 受阻：{hint}。已加入人工队列，自动抓取继续…")

                meta["status"] = status
                meta["reason"] = reason
                meta["content_length"] = len(snapshot_text)
            except Exception as e:
                meta["status"] = "blocked"
                meta["reason"] = "exception"
                meta["error"] = str(e)
            finally:
                meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                status_text = str(meta.get("status", "blocked"))
                reason_text = str(meta.get("reason", "")).strip()
                if reason_text == "exception":
                    reason_text = str(meta.get("error", "")).strip() or "exception"
                results[entry.source_id] = (status_text, reason_text)

            if args.update_registry:
                status_text = str(meta.get("status", "blocked"))
                reason = str(meta.get("reason", "")).strip()
                cache_for_registry = snapshot_rel
                if status_text == "ok" and reason == "manual_export":
                    cmm = meta.get("cache_manual_markdown")
                    if isinstance(cmm, str) and cmm.strip():
                        cache_for_registry = cmm.strip()

                if status_text == "ok" and reason == "manual_export":
                    status_line = "ok（manual-export，见本地缓存）"
                elif status_text == "ok":
                    status_line = "ok"
                else:
                    if bool(meta.get("manual_candidate")):
                        hint = str(meta.get("manual_hint") or _manual_hint(reason))
                        status_line = f"blocked（{hint}；如有合法访问权限可用 --interactive）"
                    else:
                        reason_text = f"{reason}" if reason else "抓取失败"
                        status_line = f"blocked（{reason_text}，详见本地缓存 meta_playwright.json）"
                updated_lines = _update_registry_block(
                    updated_lines,
                    entry=entry,
                    cache_rel=cache_for_registry,
                    method="MCP `playwright`",
                    status=status_line,
                    fetched_date=fetched_date,
                )

            if not args.no_progress:
                _print_progress(_render_progress(idx, len(entries), start_ts, f"done {entry.source_id}"))

        if args.interactive and str(args.interactive_mode).strip().lower() == "deferred" and manual_queue:
            if not args.no_progress:
                print("")
            print(f"开始处理需要人工介入的条目：{len(manual_queue)}（deferred：不会阻塞前面的自动抓取）")

            manual_remaining: list[tuple[str, str, str]] = []
            for m_idx, task in enumerate(manual_queue, start=1):
                sid = task.entry.source_id
                current_status, _ = results.get(sid, ("blocked", task.reason))
                if current_status == "ok":
                    continue

                if not args.no_progress:
                    print(f"\n[{m_idx}/{len(manual_queue)}] manual {sid}: {task.hint}")
                else:
                    print(f"[manual {m_idx}/{len(manual_queue)}] {sid}: {task.hint}")

                entry = task.entry
                entry_dir, snapshot_path, dom_path, network_path, meta_path = _cache_paths(repo_root, args.out_dir, entry.source_id)
                snapshot_rel = str(snapshot_path.relative_to(repo_root)).replace("\\", "/")
                dom_rel = str(dom_path.relative_to(repo_root)).replace("\\", "/")
                network_rel = str(network_path.relative_to(repo_root)).replace("\\", "/")
                meta_rel = str(meta_path.relative_to(repo_root)).replace("\\", "/")

                entry_dir.mkdir(parents=True, exist_ok=True)
                snapshot_text = ""
                status = "blocked"
                reason = task.reason

                try:
                    try:
                        meta = json.loads(meta_path.read_text(encoding="utf-8"))
                    except Exception:
                        meta = {}

                    meta.update(
                        {
                            "source_id": entry.source_id,
                            "title": entry.title,
                            "url": entry.url,
                            "fetched_date_utc": fetched_date,
                            "tool": "playwright(browser_snapshot)",
                            "cache_snapshot": snapshot_rel,
                            "meta_path": meta_rel,
                            "ua_override": bool((args.user_agent or "").strip() or (args.accept_language or "").strip()),
                            "user_agent": (args.user_agent or "").strip() if (args.user_agent or "").strip() else None,
                            "accept_language": (args.accept_language or "").strip() if (args.accept_language or "").strip() else None,
                            "manual_candidate": True,
                            "manual_hint": task.hint,
                            "manual_intervention": True,
                            "manual_intervention_mode": "deferred",
                        }
                    )

                    request_id_base = 200_000 + m_idx * 100
                    if can_run_code and ((args.user_agent or "").strip() or (args.accept_language or "").strip()):
                        _try_set_ua(
                            proc,
                            reader,
                            request_id=request_id_base + 0,
                            user_agent=args.user_agent,
                            accept_language=args.accept_language,
                            timeout_sec=args.timeout_sec,
                            progress_label=f"{entry.source_id} ua",
                            show_progress=not args.no_progress,
                        )

                    nav = _mcp_call(
                        proc,
                        reader,
                        request_id=request_id_base + 1,
                        method="tools/call",
                        params={"name": "browser_navigate", "arguments": {"url": entry.url}},
                        timeout_sec=args.timeout_sec,
                        progress_label=f"{entry.source_id} navigate",
                        show_progress=not args.no_progress,
                    )
                    if "error" in nav:
                        raise RuntimeError(str(nav["error"]))

                    if args.wait_sec and args.wait_sec > 0:
                        _mcp_call(
                            proc,
                            reader,
                            request_id=request_id_base + 2,
                            method="tools/call",
                            params={"name": "browser_wait_for", "arguments": {"time": int(args.wait_sec)}},
                            timeout_sec=max(args.timeout_sec, args.wait_sec + 10),
                            progress_label=f"{entry.source_id} wait",
                            show_progress=not args.no_progress,
                        )

                    snapshot_text, auto_status, auto_reason = _capture_current_page(
                        proc,
                        reader,
                        entry=entry,
                        repo_root=repo_root,
                        entry_dir=entry_dir,
                        snapshot_path=snapshot_path,
                        dom_path=dom_path,
                        network_path=network_path,
                        snapshot_rel=snapshot_rel,
                        dom_rel=dom_rel,
                        network_rel=network_rel,
                        request_id_base=request_id_base,
                        timeout_sec=args.timeout_sec,
                        can_eval=can_eval,
                        can_net=can_net,
                        can_shot=can_shot,
                        no_dom=bool(args.no_dom),
                        no_network=bool(args.no_network),
                        no_screenshot=bool(args.no_screenshot),
                        show_progress=not args.no_progress,
                        meta=meta,
                    )
                    meta["auto_status"] = auto_status
                    meta["auto_reason"] = auto_reason
                    status = auto_status
                    reason = auto_reason

                    if status == "ok":
                        manual_succeeded_browser.append(entry.source_id)
                    else:
                        if not _is_manual_candidate(reason):
                            manual_remaining.append((entry.source_id, entry.url, task.hint))
                        elif not _ask_yes("是否有该内容的合法访问权限，并愿意现在人工介入？[y/N]: "):
                            meta["manual_intervention_confirmed"] = False
                            manual_remaining.append((entry.source_id, entry.url, task.hint))
                        else:
                            meta["manual_intervention_confirmed"] = True
                            meta["manual_wait_timeout_sec"] = int(args.manual_timeout_sec)
                            meta["manual_wait_poll_sec"] = float(args.manual_poll_sec)
                            print(
                                "请在弹出的浏览器窗口中完成验证/登录/订阅确认等操作。"
                                f"脚本将自动等待最多 {meta['manual_wait_timeout_sec']}s，并在检测到页面可访问后继续抓取…"
                            )
                            _, wait_status, wait_reason = _wait_for_manual_unblock(
                                proc,
                                reader,
                                request_id_base=request_id_base + 200,
                                timeout_sec=int(args.manual_timeout_sec),
                                poll_sec=float(args.manual_poll_sec),
                                progress_label=f"{entry.source_id} manual",
                                show_progress=not args.no_progress,
                            )
                            meta["manual_wait_last_status"] = wait_status
                            meta["manual_wait_last_reason"] = wait_reason

                            snapshot_text, auto_status, auto_reason = _capture_current_page(
                                proc,
                                reader,
                                entry=entry,
                                repo_root=repo_root,
                                entry_dir=entry_dir,
                                snapshot_path=snapshot_path,
                                dom_path=dom_path,
                                network_path=network_path,
                                snapshot_rel=snapshot_rel,
                                dom_rel=dom_rel,
                                network_rel=network_rel,
                                request_id_base=request_id_base + 300,
                                timeout_sec=args.timeout_sec,
                                can_eval=can_eval,
                                can_net=can_net,
                                can_shot=can_shot,
                                no_dom=bool(args.no_dom),
                                no_network=bool(args.no_network),
                                no_screenshot=bool(args.no_screenshot),
                                show_progress=not args.no_progress,
                                meta=meta,
                            )
                            meta["auto_status"] = auto_status
                            meta["auto_reason"] = auto_reason
                            status = auto_status
                            reason = auto_reason
                            if status == "ok":
                                manual_succeeded_browser.append(entry.source_id)
                            else:
                                if _ask_yes("仍受阻，是否改用导出 HTML/PDF 离线转写？[y/N]: "):
                                    manual_ok, updates, md_proc, md_reader, markitdown_ready = _run_manual_export_workflow(
                                        entry,
                                        entry_dir,
                                        repo_root,
                                        hint=task.hint,
                                        md_proc=md_proc,
                                        md_reader=md_reader,
                                        markitdown_ready=markitdown_ready,
                                        startup_timeout_sec=args.startup_timeout_sec,
                                        timeout_sec=args.timeout_sec,
                                        show_progress=not args.no_progress,
                                    )
                                    meta.update(updates)
                                    if manual_ok:
                                        status = "ok"
                                        reason = "manual_export"
                                        manual_succeeded_export.append(entry.source_id)
                                    else:
                                        manual_remaining.append((entry.source_id, entry.url, task.hint))
                                else:
                                    manual_remaining.append((entry.source_id, entry.url, task.hint))
                except Exception as e:
                    status = "blocked"
                    reason = "exception"
                    meta["status"] = status
                    meta["reason"] = reason
                    meta["error"] = str(e)
                    manual_remaining.append((entry.source_id, entry.url, task.hint))
                finally:
                    meta["status"] = status
                    meta["reason"] = reason
                    meta["content_length"] = len(snapshot_text)
                    try:
                        meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                    except Exception:
                        pass

                    status_text = str(meta.get("status", "blocked"))
                    reason_text = str(meta.get("reason", "")).strip()
                    if reason_text == "exception":
                        reason_text = str(meta.get("error", "")).strip() or "exception"
                    results[entry.source_id] = (status_text, reason_text)

                    if args.update_registry:
                        cache_for_registry = snapshot_rel
                        if status_text == "ok" and str(meta.get("reason", "")).strip() == "manual_export":
                            cmm = meta.get("cache_manual_markdown")
                            if isinstance(cmm, str) and cmm.strip():
                                cache_for_registry = cmm.strip()

                        if status_text == "ok" and str(meta.get("reason", "")).strip() == "manual_export":
                            status_line = "ok（manual-export，见本地缓存）"
                        elif status_text == "ok":
                            status_line = "ok"
                        else:
                            if bool(meta.get("manual_candidate")):
                                hint = str(meta.get("manual_hint") or task.hint)
                                status_line = f"blocked（{hint}；如有合法访问权限可用 --interactive）"
                            else:
                                reason_text_line = str(meta.get("reason") or "抓取失败")
                                status_line = f"blocked（{reason_text_line}，详见本地缓存 meta_playwright.json）"

                        updated_lines = _update_registry_block(
                            updated_lines,
                            entry=entry,
                            cache_rel=cache_for_registry,
                            method="MCP `playwright`",
                            status=status_line,
                            fetched_date=fetched_date,
                        )

            manual_needed.extend(manual_remaining)

        if not args.no_progress:
            print("")

        ok_count = 0
        failed_items: list[str] = []
        for entry in entries:
            status, reason = results.get(entry.source_id, ("blocked", "unknown"))
            if status == "ok":
                ok_count += 1
            else:
                failed_items.append(f"{entry.source_id}: {status} ({reason})")

        print(f"完成：成功 {ok_count} / 失败 {len(failed_items)}")
        if failed_items:
            print("失败条目：")
            for item in failed_items[:50]:
                print(f"- {item}")
            if len(failed_items) > 50:
                print(f"- ... 其余 {len(failed_items) - 50} 条已省略")

        if manual_succeeded_browser:
            print("已人工介入并成功继续抓取：")
            for sid in manual_succeeded_browser[:50]:
                print(f"- {sid}")
            if len(manual_succeeded_browser) > 50:
                print(f"- ... 其余 {len(manual_succeeded_browser) - 50} 条已省略")

        if manual_succeeded_export:
            print("已人工介入并成功离线转写：")
            for sid in manual_succeeded_export[:50]:
                print(f"- {sid}")
            if len(manual_succeeded_export) > 50:
                print(f"- ... 其余 {len(manual_succeeded_export) - 50} 条已省略")

        if manual_needed:
            if args.interactive:
                print("仍未抓取成功且可能需要人工介入的条目（已标记 blocked）：")
            else:
                print("需要人工介入的条目（如你有合法访问权限，可用 --interactive 处理）：")
            for sid, url, hint in manual_needed[:50]:
                print(f"- {sid}: {hint} -> {url}")
            if len(manual_needed) > 50:
                print(f"- ... 其余 {len(manual_needed) - 50} 条已省略")

        if args.update_registry and updated_lines != lines:
            _write_text(registry_path, updated_lines)
            print(f"已写回来源登记：{str(registry_path).replace('\\\\', '/')}")

        return 0 if not failed_items else 1
    finally:
        try:
            proc.kill()
        except Exception:
            pass
        try:
            if md_proc is not None:
                md_proc.kill()
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
