"""
批量将仓库内的 Markdown 文档 ingest 到 mcp-local-rag（本地向量库）。

默认仅索引 `docs/`（避免扫全仓库代码/数据），但也支持显式指定其它文档目录
（例如 `docs/remp_research/research/`），用于把研究资料纳入“可检索知识层”。

设计目标：
- Local RAG 作为“资料索引加速器”，用于语义召回 + 关键词 boost
- 向量库落在 `.vibe/local-rag/lancedb/`（默认不提交，可随时重建）
- 模型/嵌入器缓存默认落在设备级目录（`$CODEX_HOME/cache/local-rag/models/` 或 `~/.codex/cache/local-rag/models/`）
- 不依赖任何第三方 Python 包（仅 stdlib），便于跨设备复用

用法（推荐在仓库根目录运行）：
  python -X utf8 scripts/tools/local_rag_ingest_project_docs.py

索引其它目录（示例）：
  python -X utf8 scripts/tools/local_rag_ingest_project_docs.py --base-dir "docs/remp_research/research"

可选：
  python -X utf8 scripts/tools/local_rag_ingest_project_docs.py --limit 5
  python -X utf8 scripts/tools/local_rag_ingest_project_docs.py --rebuild
  python -X utf8 scripts/tools/local_rag_ingest_project_docs.py --rebuild --model-name "Xenova/all-MiniLM-L6-v2"
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from queue import Empty, Queue
from typing import Any


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="批量 ingest Markdown 文档到 mcp-local-rag")
    parser.add_argument(
        "--base-dir",
        default="docs",
        help=(
            "要 ingest 的文档根目录（相对仓库根目录，或绝对路径）。"
            "默认：docs（建议保持结论层/权威文档在此目录）。"
        ),
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="最多 ingest 的文件数（0 表示不限制，用于调试/快速验证）。",
    )
    parser.add_argument(
        "--pattern",
        default="**/*.md",
        help="要 ingest 的文件 glob（相对 base-dir）。默认：**/*.md",
    )
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        help=(
            "排除文件 glob（相对 base-dir，可重复）。"
            "默认（base-dir=docs）：archive/**（避免把大量归档文档索引进向量库）。"
        ),
    )
    parser.add_argument(
        "--timeout-sec",
        type=int,
        default=900,
        help="单个工具调用的超时秒数（默认 900s）。",
    )
    parser.add_argument(
        "--only-changed",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="仅 ingest 新增/变更的文件（默认 true，推荐；可用 --no-only-changed 全量重新 ingest）。",
    )
    parser.add_argument(
        "--model-cache-dir",
        default="",
        help="MODEL cache 目录（映射到 local_rag 的 CACHE_DIR）。默认使用设备级目录；相对路径将以仓库根目录解析。",
    )
    parser.add_argument(
        "--model-name",
        default="",
        help="嵌入模型（映射到 local_rag 的 MODEL_NAME）。切换模型会改变向量维度，务必配合 --rebuild 重建 DB。",
    )
    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="重建索引：先删除 .vibe/local-rag/lancedb/ 再 ingest（可避免重复累积）。",
    )
    parser.add_argument(
        "--no-progress",
        action="store_true",
        help="禁用进度条（默认启用）。",
    )
    return parser.parse_args()


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _default_model_cache_dir() -> Path:
    codex_home = os.environ.get("CODEX_HOME")
    if codex_home and codex_home.strip():
        return Path(codex_home).expanduser() / "cache" / "local-rag" / "models"

    try:
        home = Path.home()
    except Exception:
        home = Path(os.environ.get("USERPROFILE", ""))
    if not str(home):
        return Path(".") / ".codex" / "cache" / "local-rag" / "models"

    return home / ".codex" / "cache" / "local-rag" / "models"


def _try_get_codex_mcp_env(server_name: str) -> dict[str, str]:
    """
    读取 `codex mcp get <name> --json` 的 env 配置，用于对齐 MODEL_NAME/CACHE_DIR，避免向量维度不一致。
    """
    from shutil import which

    if not which("codex"):
        return {}
    try:
        raw = subprocess.check_output(["codex", "mcp", "get", server_name, "--json"], text=True, encoding="utf-8")
        data = json.loads(raw)
        if not isinstance(data, dict):
            return {}
        env = data.get("transport", {}).get("env", {})
        if isinstance(env, dict):
            return {str(k): str(v) for k, v in env.items()}
        return {}
    except Exception:
        return {}


class _LineReader:
    """
    Windows 下 pipe 的 readline() 会阻塞；用后台线程 + queue 才能可靠实现“带超时读取”。
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
            return

    def read_line(self, timeout_sec: float) -> str | None:
        try:
            return self._q.get(timeout=timeout_sec)
        except Empty:
            return None


def _read_json_line(
    *,
    reader: _LineReader,
    proc: subprocess.Popen[str],
    timeout_sec: int,
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
    while True:
        resp = _read_json_line(
            reader=reader,
            proc=proc,
            timeout_sec=timeout_sec,
            progress_label=progress_label,
            show_progress=show_progress,
        )
        if resp.get("id") == request_id:
            return resp


def _mcp_notify(proc: subprocess.Popen[str], method: str, params: dict[str, Any] | None) -> None:
    msg: dict[str, Any] = {"jsonrpc": "2.0", "method": method}
    if params is not None:
        msg["params"] = params
    if not proc.stdin:
        raise RuntimeError("MCP 进程 stdin 不可用")
    proc.stdin.write(json.dumps(msg, ensure_ascii=False) + "\n")
    proc.stdin.flush()


def _local_rag_paths(repo_root: Path, model_cache_dir: str) -> tuple[Path, Path, Path]:
    vibe_dir = repo_root / ".vibe"
    npm_cache_dir = vibe_dir / "npm-cache"
    db_path = vibe_dir / "local-rag" / "lancedb"

    env_from_codex = _try_get_codex_mcp_env("local_rag")

    if model_cache_dir and model_cache_dir.strip():
        cache_dir = Path(model_cache_dir).expanduser()
        if not cache_dir.is_absolute():
            cache_dir = (repo_root / cache_dir).resolve()
    elif str(env_from_codex.get("CACHE_DIR", "")).strip():
        cache_dir = Path(str(env_from_codex["CACHE_DIR"])).expanduser()
        if not cache_dir.is_absolute():
            cache_dir = (repo_root / cache_dir).resolve()
    else:
        cache_dir = _default_model_cache_dir()

    return npm_cache_dir, db_path, cache_dir


def _start_local_rag(
    repo_root: Path,
    base_dir: Path,
    db_path: Path,
    cache_dir: Path,
    model_name: str,
    stderr_sink: Any | None,
) -> subprocess.Popen[str]:
    npm_cache_dir = repo_root / ".vibe" / "npm-cache"
    npm_cache_dir.mkdir(parents=True, exist_ok=True)
    db_path.mkdir(parents=True, exist_ok=True)
    cache_dir.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env["npm_config_cache"] = str(npm_cache_dir)
    env["BASE_DIR"] = str(base_dir)
    env["DB_PATH"] = str(db_path)
    env["CACHE_DIR"] = str(cache_dir)
    if model_name and model_name.strip():
        env["MODEL_NAME"] = model_name.strip()
    env["RAG_HYBRID_WEIGHT"] = "0.7"
    env["RAG_GROUPING"] = "similar"

    # 使用 cmd /c 保持与 Codex MCP 配置一致（Windows）
    cmd = ["cmd", "/c", "npx", "-y", "mcp-local-rag@0.5.3"]
    return subprocess.Popen(
        cmd,
        cwd=str(repo_root),
        env=env,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=stderr_sink if stderr_sink is not None else subprocess.DEVNULL,
        text=True,
        encoding="utf-8",
    )


def _format_duration(seconds: float) -> str:
    total = max(0, int(seconds))
    minutes, sec = divmod(total, 60)
    hours, minutes = divmod(minutes, 60)
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{sec:02d}"
    return f"{minutes:02d}:{sec:02d}"


def _truncate_middle(text: str, max_len: int) -> str:
    if max_len <= 0 or len(text) <= max_len:
        return text
    head = max(1, (max_len - 1) // 2)
    tail = max_len - head - 1
    return f"{text[:head]}…{text[-tail:]}"


def _render_progress_line(done: int, total: int, start_ts: float, current: str, *, ok: int, failed: int, skipped: int) -> str:
    width = 24
    ratio = 0.0 if total <= 0 else min(1.0, max(0.0, done / total))
    filled = int(width * ratio)
    bar = "#" * filled + "-" * (width - filled)

    elapsed = time.time() - start_ts
    rate = done / elapsed if elapsed > 0 else 0.0
    eta = (total - done) / rate if rate > 0 else 0.0
    total_est = elapsed + eta if (elapsed > 0 and rate > 0) else 0.0

    pct = int(ratio * 100)
    current_short = _truncate_middle(current, max_len=56)
    return (
        f"[{bar}] {pct:3d}%  {done:>3d}/{total:<3d}  "
        f"ok={ok:<3d} fail={failed:<3d} skip={skipped:<3d}  "
        f"t {_format_duration(elapsed)}  eta {_format_duration(eta)}  tot {_format_duration(total_est)}  "
        f"cur {current_short}"
    )


def _print_progress(line: str) -> None:
    # 覆盖同一行，避免刷屏（Windows 终端兼容）
    cols = 160
    try:
        cols = int(shutil.get_terminal_size(fallback=(160, 20)).columns)
    except Exception:
        cols = 160
    try:
        sys.stdout.write("\r" + line.ljust(cols))
        sys.stdout.flush()
    except OSError:
        # 某些终端/重定向场景下写入 \r 可能触发 Invalid argument，退化为普通输出
        print(line)


def _slugify(text: str) -> str:
    s = (text or "").strip()
    if not s:
        return "unknown"
    s = s.replace("\\", "/")
    s = re.sub(r"[^0-9a-zA-Z._/-]+", "_", s)
    s = s.replace("/", "__")
    s = s.strip("._-")
    return s.lower() or "unknown"


def _state_path(repo_root: Path, base_dir: Path) -> Path:
    state_dir = repo_root / ".vibe" / "local-rag" / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    try:
        rel = base_dir.relative_to(repo_root).as_posix()
    except Exception:
        rel = base_dir.as_posix()
    return state_dir / f"docs_ingest_{_slugify(rel)}.json"


def _stderr_log_path(repo_root: Path, *, base_dir: Path, model_name: str) -> Path:
    logs_dir = repo_root / ".vibe" / "local-rag" / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    try:
        base_rel = base_dir.relative_to(repo_root).as_posix()
    except Exception:
        base_rel = base_dir.as_posix()
    return logs_dir / f"ingest_{_slugify(base_rel)}_{_slugify(model_name)}_{ts}.log"


def _load_state(path: Path) -> dict[str, object] | None:
    if not path.exists():
        return None
    try:
        obj = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return None
    return obj if isinstance(obj, dict) else None


def _write_state(path: Path, data: dict[str, object]) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _file_sig(p: Path) -> tuple[int, int]:
    st = p.stat()
    mtime_ns = int(getattr(st, "st_mtime_ns", int(st.st_mtime * 1_000_000_000)))
    return mtime_ns, int(st.st_size)


def _is_lancedb_ready(db_path: Path) -> bool:
    return (db_path / "chunks.lance").exists()


def main() -> int:
    args = _parse_args()
    repo_root = _repo_root()
    raw_base = str(args.base_dir or "").strip() or "docs"
    base_dir = Path(raw_base).expanduser()
    if not base_dir.is_absolute():
        base_dir = (repo_root / base_dir).resolve()
    if not base_dir.exists():
        print(f"未找到目录：{base_dir}", file=sys.stderr)
        return 2

    exclude_patterns = [str(x).strip() for x in (args.exclude or []) if str(x).strip()]
    try:
        default_docs_dir = (repo_root / "docs").resolve()
        if not exclude_patterns and base_dir.resolve() == default_docs_dir:
            exclude_patterns = ["archive/**"]
    except Exception:
        pass

    files = sorted(base_dir.glob(args.pattern))
    files = [p for p in files if p.is_file()]

    if exclude_patterns:
        filtered: list[Path] = []
        for p in files:
            try:
                rel = p.relative_to(base_dir).as_posix()
            except Exception:
                filtered.append(p)
                continue
            if any(fnmatch.fnmatchcase(rel, pat) for pat in exclude_patterns):
                continue
            filtered.append(p)
        files = filtered

    if args.limit and args.limit > 0:
        files = files[: args.limit]
    if not files:
        print("未找到需要 ingest 的文件。", file=sys.stderr)
        return 2

    env_from_codex = _try_get_codex_mcp_env("local_rag")
    _, db_path, cache_dir = _local_rag_paths(repo_root, model_cache_dir=args.model_cache_dir)

    effective_model_name = str(args.model_name or "").strip()
    if not effective_model_name:
        effective_model_name = str(env_from_codex.get("MODEL_NAME", "")).strip()
    if not effective_model_name:
        effective_model_name = str(os.environ.get("MODEL_NAME", "")).strip()
    if not effective_model_name:
        effective_model_name = "Xenova/all-MiniLM-L6-v2"

    state_path = _state_path(repo_root, base_dir)
    to_ingest = files
    skipped = 0

    if args.rebuild:
        # 重建模式：DB 会被清空，增量状态也应清空
        try:
            state_path.unlink()
        except FileNotFoundError:
            pass
        except Exception:
            pass
    elif bool(args.only_changed) and _is_lancedb_ready(db_path):
        state = _load_state(state_path)
        prev_ok = False
        prev_files: dict[str, dict[str, int]] = {}
        if isinstance(state, dict):
            meta = state.get("meta")
            files_map = state.get("files")
            if isinstance(meta, dict) and isinstance(files_map, dict):
                prev_ok = (
                    str(meta.get("model_name", "")).strip() == effective_model_name
                    and str(meta.get("base_dir", "")).strip() == str(base_dir)
                    and str(meta.get("pattern", "")).strip() == str(args.pattern)
                    and list(meta.get("exclude", [])) == exclude_patterns
                    and str(meta.get("db_path", "")).strip() == str(db_path)
                )
                if prev_ok:
                    for k, v in files_map.items():
                        if isinstance(k, str) and isinstance(v, dict):
                            key = k.replace("\\", "/")
                            m = v.get("mtime_ns")
                            sz = v.get("size")
                            if isinstance(m, int) and isinstance(sz, int):
                                prev_files[key] = {"mtime_ns": m, "size": sz}

        filtered: list[Path] = []
        for p in files:
            rel = p.relative_to(repo_root).as_posix()
            mtime_ns, size = _file_sig(p)
            prev = prev_files.get(rel) if prev_ok else None
            if prev and int(prev.get("mtime_ns", -1)) == mtime_ns and int(prev.get("size", -1)) == size:
                skipped += 1
                continue
            filtered.append(p)
        to_ingest = filtered

    print(f"将 ingest {len(to_ingest)} 个文件到 Local RAG（BASE_DIR={base_dir}）")
    if exclude_patterns:
        print(f"排除规则：{exclude_patterns}")
    if bool(args.only_changed) and not args.rebuild:
        print(f"增量模式：跳过未变化文件（skipped={skipped}）")
    print("提示：首次运行可能会下载嵌入/分词等模型；大模型的嵌入/分块会更慢，请耐心等待。")

    if args.model_name and not args.rebuild and _is_lancedb_ready(db_path):
        state = _load_state(state_path)
        prev_model = ""
        if isinstance(state, dict):
            meta = state.get("meta")
            if isinstance(meta, dict):
                prev_model = str(meta.get("model_name", "")).strip()
        if prev_model and prev_model != effective_model_name:
            print(
                "检测到你指定了 --model-name，但现有向量库可能由其他模型生成。"
                "为避免向量维度不一致，请加 --rebuild 重建向量库。",
                file=sys.stderr,
            )
            return 2

    print(f"DB_PATH={db_path}")
    print(f"CACHE_DIR={cache_dir}")
    print(f"MODEL_NAME={effective_model_name}")
    print(f"STATE_PATH={state_path}")
    if args.rebuild:
        print(f"重建模式：将清理 {db_path}")
        shutil.rmtree(db_path, ignore_errors=True)

    if not to_ingest:
        print("没有需要 ingest 的变更文件（本次无需更新索引）。")
        return 0

    stderr_fh: Any | None = None
    stderr_log_path = _stderr_log_path(repo_root, base_dir=base_dir, model_name=effective_model_name)
    proc: subprocess.Popen[str] | None = None
    reader: _LineReader | None = None

    try:
        try:
            stderr_fh = open(stderr_log_path, "w", encoding="utf-8", errors="replace")
        except Exception:
            stderr_fh = None
        if stderr_fh is not None:
            print(f"STDERR_LOG={stderr_log_path}")

        proc = _start_local_rag(
            repo_root=repo_root,
            base_dir=base_dir,
            db_path=db_path,
            cache_dir=cache_dir,
            model_name=effective_model_name,
            stderr_sink=stderr_fh,
        )
        if not proc.stdout:
            print("local_rag MCP stdout 不可用", file=sys.stderr)
            return 1
        reader = _LineReader(proc.stdout)

        init_resp = _mcp_call(
            proc,
            reader,
            request_id=1,
            method="initialize",
            params={
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "freqtrade_demo_local_rag_ingest", "version": "0.1.0"},
            },
            timeout_sec=args.timeout_sec,
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
            timeout_sec=args.timeout_sec,
            progress_label="tools/list",
            show_progress=not args.no_progress,
        )
        tool_names = {t.get("name") for t in tools_resp.get("result", {}).get("tools", [])}
        if "ingest_file" not in tool_names:
            print(f"local_rag 不支持 ingest_file，tools={sorted(tool_names)}", file=sys.stderr)
            return 1

        start_ts = time.time()
        ok = 0
        failed: list[str] = []
        state_files: dict[str, dict[str, int]] = {}
        for idx, path in enumerate(to_ingest, start=1):
            abs_path = str(path.resolve())
            rel = path.relative_to(repo_root).as_posix()
            if args.no_progress:
                print(f"[{idx}/{len(to_ingest)}] ingest: {rel} (ok={ok} fail={len(failed)} skip={skipped})")
            else:
                _print_progress(
                    _render_progress_line(
                        done=idx - 1,
                        total=len(to_ingest),
                        start_ts=start_ts,
                        current=rel,
                        ok=ok,
                        failed=len(failed),
                        skipped=skipped,
                    )
                )
            wait_label = f"ingest_file {idx}/{len(to_ingest)}: {_truncate_middle(rel, max_len=72)}"
            resp = _mcp_call(
                proc,
                reader,
                request_id=1000 + idx,
                method="tools/call",
                params={"name": "ingest_file", "arguments": {"filePath": abs_path}},
                timeout_sec=args.timeout_sec,
                progress_label=wait_label,
                show_progress=not args.no_progress,
            )
            if "error" in resp:
                failed.append(f"{path}: {resp['error']}")
                continue
            ok += 1
            mtime_ns, size = _file_sig(path)
            state_files[rel] = {"mtime_ns": mtime_ns, "size": size}
            if not args.no_progress:
                _print_progress(
                    _render_progress_line(
                        done=idx,
                        total=len(to_ingest),
                        start_ts=start_ts,
                        current=rel,
                        ok=ok,
                        failed=len(failed),
                        skipped=skipped,
                    )
                )

        if not args.no_progress:
            print("")
        ingest_elapsed = float(max(0.0, time.time() - start_ts))
        print(f"索引耗时：{_format_duration(ingest_elapsed)}")

        status_resp = _mcp_call(
            proc,
            reader,
            request_id=9000,
            method="tools/call",
            params={"name": "status", "arguments": {}},
            timeout_sec=args.timeout_sec,
            progress_label="status",
            show_progress=not args.no_progress,
        )

        print("")
        print(f"完成：成功 {ok} / 失败 {len(failed)}")
        if failed:
            print("失败明细：")
            for item in failed[:50]:
                print(f"- {item}")
            if len(failed) > 50:
                print(f"- ... 其余 {len(failed) - 50} 条已省略")

        if "result" in status_resp:
            print("")
            print("Local RAG status：")
            print(json.dumps(status_resp["result"], ensure_ascii=False, indent=2))

        # 写入增量状态（仅当启用 only_changed，且不是 rebuild）
        if bool(args.only_changed) and not args.rebuild:
            prev = _load_state(state_path) or {}
            merged_files: dict[str, dict[str, int]] = {}
            prev_files_obj = prev.get("files")
            if isinstance(prev_files_obj, dict):
                for k, v in prev_files_obj.items():
                    if isinstance(k, str) and isinstance(v, dict):
                        key = k.replace("\\", "/")
                        m = v.get("mtime_ns")
                        sz = v.get("size")
                        if isinstance(m, int) and isinstance(sz, int):
                            merged_files[key] = {"mtime_ns": m, "size": sz}
            merged_files.update(state_files)
            _write_state(
                state_path,
                {
                    "version": 1,
                    "updated_date_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                    "meta": {
                        "base_dir": str(base_dir),
                        "pattern": str(args.pattern),
                        "exclude": exclude_patterns,
                        "db_path": str(db_path),
                        "model_name": effective_model_name,
                    },
                    "files": merged_files,
                },
            )

        return 0 if not failed else 1
    finally:
        try:
            if proc is not None:
                proc.kill()
        except Exception:
            pass
        try:
            if stderr_fh is not None:
                stderr_fh.close()
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
