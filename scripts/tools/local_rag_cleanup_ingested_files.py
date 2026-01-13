"""
批量清理 mcp-local-rag（Local RAG）向量库中已入库的文件条目。

动机：
- mcp-local-rag 的 `ingest_file` 为了安全，会限制只能 ingest `BASE_DIR` 目录内的文件；
- 随着目录迁移/路径变更，可能出现“旧路径重复入库”的情况（例如：`.../project_docs/...`）；
- 本脚本通过 MCP 的 `list_files` + `delete_file` 工具，按前缀批量删除旧条目。

用法示例：
  # 仅预览（不删除）
  python -X utf8 scripts/tools/local_rag_cleanup_ingested_files.py ^
    --db-path ".vibe/local-rag/lancedb" ^
    --prefix "C:/.../project_docs/" ^
    --dry-run

  # 实际删除
  python -X utf8 scripts/tools/local_rag_cleanup_ingested_files.py ^
    --db-path ".vibe/local-rag/lancedb" ^
    --prefix "C:/.../project_docs/"

说明：
- `--db-path` 支持相对路径（相对仓库根目录）或绝对路径。
- 默认会尽量读取 `codex mcp get local_rag --json` 来对齐 MODEL/CACHE_DIR 等参数。
- 仅使用 Python 标准库，便于跨设备运行。
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
    parser = argparse.ArgumentParser(description="按前缀清理 local_rag 已入库文件（delete_file）")
    parser.add_argument(
        "--db-path",
        default=".vibe/local-rag/lancedb",
        help="Local RAG DB 路径（相对仓库根目录，或绝对路径）。默认：.vibe/local-rag/lancedb",
    )
    parser.add_argument(
        "--prefix",
        action="append",
        default=[],
        help="要删除的 filePath 前缀（可重复）。示例：C:/.../project_docs/",
    )
    parser.add_argument(
        "--base-dir",
        default="",
        help=(
            "覆盖 local_rag 的 BASE_DIR（用于通过 delete_file 的路径校验）。"
            "不传则尽量跟随 `codex mcp get local_rag` 的 BASE_DIR。"
        ),
    )
    parser.add_argument("--dry-run", action="store_true", help="仅预览将删除哪些条目，不执行删除。")
    parser.add_argument(
        "--timeout-sec",
        type=int,
        default=900,
        help="单次 MCP 调用超时秒数（默认 900s）。",
    )
    parser.add_argument("--no-progress", action="store_true", help="禁用进度输出（默认启用）。")
    return parser.parse_args()


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _normalize_path(p: str) -> str:
    # 用于前缀匹配：统一斜杠与大小写（Windows 路径不区分大小写）
    return str(p).replace("\\", "/").lower()


def _try_get_codex_mcp_env(server_name: str) -> dict[str, str]:
    """
    尝试读取 `codex mcp get <name> --json` 的 env 配置，便于对齐 MODEL_NAME/CACHE_DIR 等参数。
    失败则返回空 dict（不作为硬依赖）。
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
    Windows 下 pipe 的 readline() 可能阻塞；用后台线程 + queue 实现“可超时读取”。
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


def _print_progress(line: str) -> None:
    cols = 160
    try:
        cols = int(shutil.get_terminal_size(fallback=(160, 20)).columns)
    except Exception:
        cols = 160
    try:
        sys.stdout.write("\r" + line.ljust(cols))
        sys.stdout.flush()
    except OSError:
        print(line)


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


def _start_local_rag(
    *,
    repo_root: Path,
    base_dir: str,
    db_path: Path,
    cache_dir: str,
    model_name: str,
) -> subprocess.Popen[str]:
    npm_cache_dir = repo_root / ".vibe" / "npm-cache"
    npm_cache_dir.mkdir(parents=True, exist_ok=True)
    db_path.mkdir(parents=True, exist_ok=True)
    if cache_dir:
        Path(cache_dir).expanduser().mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env["npm_config_cache"] = str(npm_cache_dir)
    if base_dir:
        env["BASE_DIR"] = str(base_dir)
    env["DB_PATH"] = str(db_path)
    if cache_dir:
        env["CACHE_DIR"] = str(cache_dir)
    if model_name:
        env["MODEL_NAME"] = str(model_name)
    env.setdefault("RAG_HYBRID_WEIGHT", "0.7")
    env.setdefault("RAG_GROUPING", "similar")

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


def _extract_list_files_result(resp: dict[str, Any]) -> list[dict[str, Any]]:
    result = resp.get("result")
    if isinstance(result, list):
        return [x for x in result if isinstance(x, dict)]
    if isinstance(result, dict):
        # mcp-local-rag 的返回常见形态：{"content":[{"type":"text","text":"[...]"}]}
        content_obj = result.get("content")
        if isinstance(content_obj, list):
            for item in content_obj:
                if not isinstance(item, dict):
                    continue
                if str(item.get("type", "")).strip().lower() != "text":
                    continue
                text = item.get("text")
                if not isinstance(text, str) or not text.strip():
                    continue
                try:
                    parsed = json.loads(text)
                except Exception:
                    continue
                if isinstance(parsed, list):
                    return [x for x in parsed if isinstance(x, dict)]

        files_obj = result.get("files")
        if isinstance(files_obj, list):
            return [x for x in files_obj if isinstance(x, dict)]
    return []


def main() -> int:
    args = _parse_args()
    repo_root = _repo_root()

    if not args.prefix:
        print("错误：必须至少提供一个 --prefix。", file=sys.stderr)
        return 2

    db_path = Path(args.db_path).expanduser()
    if not db_path.is_absolute():
        db_path = (repo_root / db_path).resolve()

    env_from_codex = _try_get_codex_mcp_env("local_rag")
    base_dir = str(args.base_dir or env_from_codex.get("BASE_DIR", "docs")).strip()
    cache_dir = str(env_from_codex.get("CACHE_DIR", "")).strip()
    model_name = str(env_from_codex.get("MODEL_NAME", "")).strip()

    show_progress = not bool(args.no_progress)
    prefixes_norm = [_normalize_path(p) for p in args.prefix if str(p).strip()]

    print(f"DB_PATH={db_path}")
    print(f"BASE_DIR={base_dir}")
    print(f"PREFIX={args.prefix}")
    print(f"DRY_RUN={bool(args.dry_run)}")

    proc = _start_local_rag(
        repo_root=repo_root,
        base_dir=base_dir,
        db_path=db_path,
        cache_dir=cache_dir,
        model_name=model_name,
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
                "clientInfo": {"name": "freqtrade_demo_local_rag_cleanup", "version": "0.1.0"},
            },
            timeout_sec=args.timeout_sec,
            progress_label="initialize",
            show_progress=show_progress,
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
            show_progress=show_progress,
        )
        tool_names = {t.get("name") for t in tools_resp.get("result", {}).get("tools", [])}
        missing = [name for name in ("list_files", "delete_file") if name not in tool_names]
        if missing:
            print(f"local_rag 缺少必要工具：{missing}，tools={sorted(tool_names)}", file=sys.stderr)
            return 1

        list_resp = _mcp_call(
            proc,
            reader,
            request_id=3,
            method="tools/call",
            params={"name": "list_files", "arguments": {}},
            timeout_sec=args.timeout_sec,
            progress_label="list_files",
            show_progress=show_progress,
        )
        if "error" in list_resp:
            print(f"list_files 失败：{list_resp['error']}", file=sys.stderr)
            return 1

        files = _extract_list_files_result(list_resp)
        candidates: list[str] = []
        for item in files:
            fp = item.get("filePath")
            if not isinstance(fp, str) or not fp.strip():
                continue
            fp_norm = _normalize_path(fp)
            if any(fp_norm.startswith(p) for p in prefixes_norm):
                candidates.append(fp)

        print(f"匹配条目：{len(candidates)} / 总计 {len(files)}")
        if not candidates:
            print("没有需要删除的条目。")
            return 0

        if args.dry_run:
            print("将删除以下 filePath：")
            for fp in candidates[:200]:
                print(f"- {fp}")
            if len(candidates) > 200:
                print(f"- ... 其余 {len(candidates) - 200} 条已省略")
            return 0

        deleted = 0
        failed: list[str] = []
        start_ts = time.time()
        for idx, fp in enumerate(candidates, start=1):
            label = f"delete_file {idx}/{len(candidates)}"
            if show_progress:
                elapsed = time.time() - start_ts
                _print_progress(f"[{idx-1:>3}/{len(candidates):<3}] ok={deleted:<3d} fail={len(failed):<3d} {label}  t={elapsed:>.1f}s")
            resp = _mcp_call(
                proc,
                reader,
                request_id=1000 + idx,
                method="tools/call",
                params={"name": "delete_file", "arguments": {"filePath": fp}},
                timeout_sec=args.timeout_sec,
                progress_label=label,
                show_progress=show_progress,
            )
            if "error" in resp:
                failed.append(f"{fp}: {resp['error']}")
                continue
            deleted += 1

        if show_progress:
            print("")

        print(f"删除完成：成功 {deleted} / 失败 {len(failed)}")
        if failed:
            print("失败明细：")
            for item in failed[:50]:
                print(f"- {item}")
            if len(failed) > 50:
                print(f"- ... 其余 {len(failed) - 50} 条已省略")

        # 复核：再次 list_files，确认目标前缀已清空
        verify_resp = _mcp_call(
            proc,
            reader,
            request_id=9000,
            method="tools/call",
            params={"name": "list_files", "arguments": {}},
            timeout_sec=args.timeout_sec,
            progress_label="verify/list_files",
            show_progress=show_progress,
        )
        verify_files = _extract_list_files_result(verify_resp)
        left = 0
        for item in verify_files:
            fp = item.get("filePath")
            if not isinstance(fp, str):
                continue
            if any(_normalize_path(fp).startswith(p) for p in prefixes_norm):
                left += 1
        print(f"复核：前缀剩余 {left} 条（应为 0）")
        return 0 if left == 0 else 1
    finally:
        try:
            proc.terminate()
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
