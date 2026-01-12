"""
批量将仓库内的 Markdown 文档 ingest 到 mcp-local-rag（本地向量库）。

默认仅索引 `project_docs/`（避免扫全仓库代码/数据），但也支持显式指定其它文档目录
（例如 `remp_research/research/`），用于把研究资料纳入“可检索知识层”。

设计目标：
- Local RAG 作为“资料索引加速器”，用于语义召回 + 关键词 boost
- 向量库落在 `.vibe/local-rag/lancedb/`（默认不提交，可随时重建）
- 模型/嵌入器缓存默认落在设备级目录（`$CODEX_HOME/cache/local-rag/models/` 或 `~/.codex/cache/local-rag/models/`）
- 不依赖任何第三方 Python 包（仅 stdlib），便于跨设备复用

用法（推荐在仓库根目录运行）：
  python -X utf8 scripts/tools/local_rag_ingest_project_docs.py

索引其它目录（示例）：
  python -X utf8 scripts/tools/local_rag_ingest_project_docs.py --base-dir "remp_research/research"

可选：
  python -X utf8 scripts/tools/local_rag_ingest_project_docs.py --limit 5
  python -X utf8 scripts/tools/local_rag_ingest_project_docs.py --rebuild
  python -X utf8 scripts/tools/local_rag_ingest_project_docs.py --rebuild --model-name "Xenova/all-MiniLM-L6-v2"
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path
from queue import Empty, Queue
from typing import Any


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="批量 ingest Markdown 文档到 mcp-local-rag")
    parser.add_argument(
        "--base-dir",
        default="project_docs",
        help=(
            "要 ingest 的文档根目录（相对仓库根目录，或绝对路径）。"
            "默认：project_docs（建议保持结论层/权威文档在此目录）。"
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
        help="要 ingest 的文件 glob（相对 project_docs）。默认：**/*.md",
    )
    parser.add_argument(
        "--timeout-sec",
        type=int,
        default=900,
        help="单个工具调用的超时秒数（默认 900s）。",
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

    if model_cache_dir and model_cache_dir.strip():
        cache_dir = Path(model_cache_dir).expanduser()
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
        stderr=subprocess.DEVNULL,
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


def _render_progress_line(done: int, total: int, start_ts: float, current: str) -> str:
    width = 24
    ratio = 0.0 if total <= 0 else min(1.0, max(0.0, done / total))
    filled = int(width * ratio)
    bar = "#" * filled + "-" * (width - filled)

    elapsed = time.time() - start_ts
    rate = done / elapsed if elapsed > 0 else 0.0
    eta = (total - done) / rate if rate > 0 else 0.0

    pct = int(ratio * 100)
    current_short = _truncate_middle(current, max_len=56)
    return (
        f"[{bar}] {pct:3d}%  {done:>3d}/{total:<3d}  "
        f"elapsed {_format_duration(elapsed)}  eta {_format_duration(eta)}  "
        f"cur {current_short}"
    )


def _print_progress(line: str) -> None:
    # 覆盖同一行，避免刷屏（Windows 终端兼容）
    cols = 160
    sys.stdout.write("\r" + line.ljust(cols))
    sys.stdout.flush()


def main() -> int:
    args = _parse_args()
    repo_root = _repo_root()
    raw_base = str(args.base_dir or "").strip() or "project_docs"
    base_dir = Path(raw_base).expanduser()
    if not base_dir.is_absolute():
        base_dir = (repo_root / base_dir).resolve()
    if not base_dir.exists():
        print(f"未找到目录：{base_dir}", file=sys.stderr)
        return 2

    files = sorted(base_dir.glob(args.pattern))
    files = [p for p in files if p.is_file()]
    if args.limit and args.limit > 0:
        files = files[: args.limit]
    if not files:
        print("未找到需要 ingest 的文件。", file=sys.stderr)
        return 2

    print(f"将 ingest {len(files)} 个文件到 Local RAG（BASE_DIR={base_dir}）")
    print("提示：首次运行可能会下载嵌入/分词等模型，耗时取决于网速与磁盘。")

    _, db_path, cache_dir = _local_rag_paths(repo_root, model_cache_dir=args.model_cache_dir)
    if args.model_name and not args.rebuild and db_path.exists():
        if any(db_path.rglob("*")):
            print("检测到你指定了 --model-name。为避免向量维度不一致，请加 --rebuild 重建向量库。", file=sys.stderr)
            return 2

    print(f"DB_PATH={db_path}")
    print(f"CACHE_DIR={cache_dir}")
    if args.model_name:
        print(f"MODEL_NAME={args.model_name}")
    if args.rebuild:
        print(f"重建模式：将清理 {db_path}")
        shutil.rmtree(db_path, ignore_errors=True)

    proc = _start_local_rag(
        repo_root=repo_root,
        base_dir=base_dir,
        db_path=db_path,
        cache_dir=cache_dir,
        model_name=args.model_name,
    )
    if not proc.stdout:
        print("local_rag MCP stdout 不可用", file=sys.stderr)
        return 1
    reader = _LineReader(proc.stdout)
    try:
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
        for idx, path in enumerate(files, start=1):
            abs_path = str(path.resolve())
            rel = str(path.relative_to(repo_root))
            if args.no_progress:
                print(f"[{idx}/{len(files)}] ingest: {rel}")
            else:
                _print_progress(_render_progress_line(done=idx - 1, total=len(files), start_ts=start_ts, current=rel))
            resp = _mcp_call(
                proc,
                reader,
                request_id=1000 + idx,
                method="tools/call",
                params={"name": "ingest_file", "arguments": {"filePath": abs_path}},
                timeout_sec=args.timeout_sec,
                show_progress=False,
            )
            if "error" in resp:
                failed.append(f"{path}: {resp['error']}")
                continue
            ok += 1
            if not args.no_progress:
                _print_progress(_render_progress_line(done=idx, total=len(files), start_ts=start_ts, current=rel))

        if not args.no_progress:
            print("")

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

        return 0 if not failed else 1
    finally:
        try:
            proc.kill()
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
