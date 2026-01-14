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
- 使用官方 MCP Python SDK，避免重复实现 JSON-RPC 2.0/pipe 超时读取等细节。
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from mcp_stdio_client import mcp_call_tool, mcp_list_tools, mcp_stdio_session, print_progress


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


def _tool_result_to_obj(result: Any) -> object:
    try:
        dump = result.model_dump()  # type: ignore[attr-defined]
        return dump
    except Exception:
        return result


def _tool_result_text(result: Any) -> str:
    obj = _tool_result_to_obj(result)
    if isinstance(obj, dict):
        content = obj.get("content")
        if isinstance(content, list):
            texts: list[str] = []
            for item in content:
                if not isinstance(item, dict):
                    continue
                if str(item.get("type", "")).strip().lower() != "text":
                    continue
                text = item.get("text")
                if isinstance(text, str) and text.strip():
                    texts.append(text.strip())
            if texts:
                return "\n".join(texts)
        sc = obj.get("structuredContent")
        if sc is not None:
            try:
                return json.dumps(sc, ensure_ascii=False)
            except Exception:
                return str(sc)
    return str(obj)


def _local_rag_stdio_config(
    *,
    repo_root: Path,
    base_dir: str,
    db_path: Path,
    cache_dir: str,
    model_name: str,
) -> tuple[str, list[str], dict[str, str]]:
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

    command = "cmd"
    args = ["/c", "npx", "-y", "mcp-local-rag@0.5.3"]
    return command, args, env


def _extract_list_files_result(call_result: Any) -> list[dict[str, Any]]:
    obj = _tool_result_to_obj(call_result)

    if isinstance(obj, list):
        return [x for x in obj if isinstance(x, dict)]

    if not isinstance(obj, dict):
        return []

    sc = obj.get("structuredContent")
    if isinstance(sc, list):
        return [x for x in sc if isinstance(x, dict)]
    if isinstance(sc, dict):
        files_obj = sc.get("files")
        if isinstance(files_obj, list):
            return [x for x in files_obj if isinstance(x, dict)]

    # mcp-local-rag 的返回常见形态：{"content":[{"type":"text","text":"[...]"}]}
    content_obj = obj.get("content")
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

    files_obj = obj.get("files")
    if isinstance(files_obj, list):
        return [x for x in files_obj if isinstance(x, dict)]

    return []


async def _amain() -> int:
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

    command, cmd_args, env = _local_rag_stdio_config(
        repo_root=repo_root,
        base_dir=base_dir,
        db_path=db_path,
        cache_dir=cache_dir,
        model_name=model_name,
    )

    log_dir = repo_root / ".vibe" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    errlog_path = log_dir / f"mcp-local-rag-{int(time.time())}.log"

    try:
        with errlog_path.open("w", encoding="utf-8", errors="replace") as errlog:
            async with mcp_stdio_session(
                command=command,
                args=cmd_args,
                cwd=repo_root,
                env=env,
                init_timeout_sec=float(args.timeout_sec),
                show_progress=show_progress,
                errlog=errlog,
            ) as session:
                tools = await mcp_list_tools(session, timeout_sec=float(args.timeout_sec), show_progress=show_progress)
                tool_names = {t.name for t in tools.tools}
                missing = [name for name in ("list_files", "delete_file") if name not in tool_names]
                if missing:
                    print(f"local_rag 缺少必要工具：{missing}，tools={sorted(tool_names)}", file=sys.stderr)
                    print(f"MCP stderr 日志：{errlog_path}", file=sys.stderr)
                    return 1

                list_result = await mcp_call_tool(
                    session,
                    name="list_files",
                    arguments={},
                    timeout_sec=float(args.timeout_sec),
                    show_progress=show_progress,
                )
                if bool(getattr(list_result, "isError", False)):
                    print(f"list_files 失败：{_tool_result_text(list_result)}", file=sys.stderr)
                    print(f"MCP stderr 日志：{errlog_path}", file=sys.stderr)
                    return 1

                files = _extract_list_files_result(list_result)
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
                        print_progress(
                            f"[{idx-1:>3}/{len(candidates):<3}] ok={deleted:<3d} fail={len(failed):<3d} {label}  t={elapsed:>.1f}s"
                        )

                    result = await mcp_call_tool(
                        session,
                        name="delete_file",
                        arguments={"filePath": fp},
                        timeout_sec=float(args.timeout_sec),
                        show_progress=show_progress,
                    )
                    if bool(getattr(result, "isError", False)):
                        failed.append(f"{fp}: {_tool_result_text(result)}")
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

                verify_result = await mcp_call_tool(
                    session,
                    name="list_files",
                    arguments={},
                    timeout_sec=float(args.timeout_sec),
                    show_progress=show_progress,
                )
                verify_files = _extract_list_files_result(verify_result)
                left = 0
                for item in verify_files:
                    fp = item.get("filePath")
                    if not isinstance(fp, str):
                        continue
                    if any(_normalize_path(fp).startswith(p) for p in prefixes_norm):
                        left += 1
                print(f"复核：前缀剩余 {left} 条（应为 0）")
                if left != 0:
                    print(f"MCP stderr 日志：{errlog_path}", file=sys.stderr)
                return 0 if left == 0 else 1
    except Exception as exc:
        print(f"运行失败：{exc}", file=sys.stderr)
        print(f"MCP stderr 日志：{errlog_path}", file=sys.stderr)
        return 1


def main() -> int:
    return asyncio.run(_amain())


if __name__ == "__main__":
    raise SystemExit(main())
