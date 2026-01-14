"""
Local RAG 嵌入模型评估脚本（不换 MCP）

目标：
- 在不破坏现有 `.vibe/local-rag/lancedb/` 的前提下，对比多个可用（ONNX）的嵌入模型检索效果
- 采用“查询回归集 + TopK 命中率/MRR”做可复现评估，输出可追溯报告到 `artifacts/`

设计原则：
- 使用官方 MCP Python SDK，避免重复实现 JSON-RPC 2.0/pipe 超时读取等细节
- 每个模型使用独立的 DB_PATH（默认 `.vibe/local-rag/model_dbs/<model_slug>/`），避免向量维度冲突

用法（仓库根目录）：
  python -X utf8 scripts/tools/local_rag_eval_models.py

对比推荐模型（并在缺索引时自动构建）：
  python -X utf8 scripts/tools/local_rag_eval_models.py --models "Xenova/multilingual-e5-large,Xenova/multilingual-e5-base,Xenova/bge-m3,Xenova/all-MiniLM-L6-v2"

仅对比“重建速度”（不跑回归集评估；用于选型时权衡 ingest 成本）：
  python -X utf8 scripts/tools/local_rag_eval_models.py --mode build --build rebuild --file-limit 50 --models "Xenova/multilingual-e5-large,Xenova/multilingual-e5-base,Xenova/bge-m3,Xenova/all-MiniLM-L6-v2"

强制重建（只影响评估用 profile DB，不影响主 DB）：
  python -X utf8 scripts/tools/local_rag_eval_models.py --build rebuild
"""

from __future__ import annotations

import argparse
import asyncio
import fnmatch
import json
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from shutil import which
from typing import Any

_TOOLS_DIR = Path(__file__).resolve().parent
if str(_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOLS_DIR))

from mcp_stdio_client import (
    mcp_call_tool,
    mcp_list_tools,
    mcp_stdio_session,
    print_progress,
    tool_result_text,
    tool_result_to_obj,
)


@dataclass(frozen=True)
class _EvalCase:
    case_id: str
    query: str
    expect_any: tuple[str, ...]


@dataclass(frozen=True)
class _EvalSuite:
    version: int
    default_k: int
    cases: tuple[_EvalCase, ...]


@dataclass
class _ModelMetrics:
    model: str
    db_path: str
    built: bool
    build_mode: str
    build_files: int
    build_skipped: int
    build_seconds: float
    hit_at_k: float
    mrr_at_k: float
    case_count: int
    failures: list[dict[str, Any]]
    error: str | None = None


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _utc_ts_compact() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


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


def _normalize_path_for_match(path: str) -> str:
    s = (path or "").replace("\\", "/")
    # Windows 路径可能带盘符：统一小写用于匹配
    return s.strip().lower()


def _model_slug(model_name: str) -> str:
    """
    将模型名转成可用于目录名的 slug（稳定、可读、跨平台）。
    """
    s = (model_name or "").strip()
    if not s:
        return "unknown"
    s = s.replace("\\", "/")
    s = s.replace("/", "__")
    s = re.sub(r"[^0-9a-zA-Z._-]+", "_", s)
    return s.strip("._-").lower() or "unknown"


def _match_any_expected(file_path: str, expect_any: tuple[str, ...]) -> bool:
    fp = _normalize_path_for_match(file_path)
    for pat in expect_any:
        p = _normalize_path_for_match(pat)
        if not p:
            continue
        # 允许用户给出精确路径或 glob（用 fnmatch）
        is_glob = any(ch in p for ch in "*?[]")
        if is_glob:
            if fnmatch.fnmatchcase(fp, p) or fnmatch.fnmatchcase(fp, f"*{p}"):
                return True
        else:
            # 期望值通常是 repo 相对路径；绝对路径应当以其作为后缀
            if fp.endswith(p):
                return True
    return False


def _load_suite(path: Path) -> _EvalSuite:
    data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    if not isinstance(data, dict):
        raise ValueError("cases 文件必须是 JSON object")

    version = int(data.get("version", 0) or 0)
    default_k = int(data.get("default_k", 5) or 5)
    raw_cases = data.get("cases", [])
    if not isinstance(raw_cases, list) or not raw_cases:
        raise ValueError("cases 不能为空")

    cases: list[_EvalCase] = []
    for idx, item in enumerate(raw_cases, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"cases[{idx}] 不是 object")
        case_id = str(item.get("id") or f"Q{idx:03d}").strip()
        query = str(item.get("query") or "").strip()
        expect_any = item.get("expect_any") or []
        if not query:
            raise ValueError(f"cases[{idx}] 缺少 query")
        if not isinstance(expect_any, list) or not expect_any:
            raise ValueError(f"cases[{idx}] 缺少 expect_any")
        expect_any_t = tuple(str(x).strip() for x in expect_any if str(x).strip())
        if not expect_any_t:
            raise ValueError(f"cases[{idx}] expect_any 为空")
        cases.append(_EvalCase(case_id=case_id, query=query, expect_any=expect_any_t))

    if default_k <= 0:
        default_k = 5
    return _EvalSuite(version=version, default_k=default_k, cases=tuple(cases))


def _collect_docs(base_dir: Path, pattern: str, exclude_patterns: list[str]) -> list[Path]:
    files = sorted(base_dir.glob(pattern))
    files = [p for p in files if p.is_file()]
    if not exclude_patterns:
        return files
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
    return filtered


def _is_lancedb_ready(db_path: Path) -> bool:
    # LanceDB 默认会有 table 目录，例如 chunks.lance/
    chunks = db_path / "chunks.lance"
    return chunks.exists() and chunks.is_dir()


def _safe_rmtree_under(root: Path, target: Path) -> None:
    root_r = root.resolve()
    target_r = target.resolve()
    try:
        target_r.relative_to(root_r)
    except Exception as e:
        raise ValueError(f"拒绝删除：目标不在允许范围内：{target_r}") from e
    shutil.rmtree(target_r, ignore_errors=True)


def _file_sig(p: Path) -> tuple[int, int]:
    st = p.stat()
    mtime_ns = int(getattr(st, "st_mtime_ns", int(st.st_mtime * 1_000_000_000)))
    return mtime_ns, int(st.st_size)


def _ingest_state_path(db_path: Path) -> Path:
    return db_path / "ingest_state.json"


def _load_ingest_state(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        obj = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return None
    return obj if isinstance(obj, dict) else None


def _write_ingest_state(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


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
    total_est = elapsed + eta if (elapsed > 0 and rate > 0) else 0.0

    pct = int(ratio * 100)
    current_short = _truncate_middle(current, max_len=56)
    return (
        f"[{bar}] {pct:3d}%  {done:>3d}/{total:<3d}  "
        f"t {_format_duration(elapsed)}  eta {_format_duration(eta)}  tot {_format_duration(total_est)}  "
        f"cur {current_short}"
    )


def _local_rag_stdio_config(
    *,
    repo_root: Path,
    base_dir: Path,
    db_path: Path,
    cache_dir: Path,
    model_name: str,
    rag_hybrid_weight: str,
    rag_grouping: str,
) -> tuple[str, list[str], dict[str, str]]:
    npm_cache_dir = repo_root / ".vibe" / "npm-cache"
    npm_cache_dir.mkdir(parents=True, exist_ok=True)
    db_path.mkdir(parents=True, exist_ok=True)
    cache_dir.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env["npm_config_cache"] = str(npm_cache_dir)
    env["BASE_DIR"] = str(base_dir)
    env["DB_PATH"] = str(db_path)
    env["CACHE_DIR"] = str(cache_dir)
    env["MODEL_NAME"] = model_name
    env["RAG_HYBRID_WEIGHT"] = str(rag_hybrid_weight or "0.7")
    env["RAG_GROUPING"] = str(rag_grouping or "similar")

    command = "cmd"
    args = ["/c", "npx", "-y", "mcp-local-rag@0.5.3"]
    return command, args, env


def _extract_query_results(result: Any) -> list[dict[str, Any]]:
    """
    local_rag 的 MCP 返回形态可能是：
    - list[dict]（直接返回）
    - {"content":[{"type":"text","text":"[...]"}]}（JSON 字符串包了一层）
    - 纯字符串（JSON 字符串）
    """
    obj = tool_result_to_obj(result)

    if isinstance(obj, dict):
        sc = obj.get("structuredContent")
        if isinstance(sc, list):
            return [x for x in sc if isinstance(x, dict)]
        if isinstance(sc, str):
            try:
                parsed = json.loads(sc)
            except Exception:
                parsed = None
            if isinstance(parsed, list):
                return [x for x in parsed if isinstance(x, dict)]

    if isinstance(obj, list):
        return [x for x in obj if isinstance(x, dict)]

    if isinstance(obj, dict):
        content = obj.get("content")
        if isinstance(content, list):
            texts: list[str] = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    t = item.get("text")
                    if isinstance(t, str) and t.strip():
                        texts.append(t)
            blob = "\n".join(texts).strip()
            if not blob:
                return []
            try:
                parsed = json.loads(blob)
            except Exception:
                return []
            if isinstance(parsed, list):
                return [x for x in parsed if isinstance(x, dict)]
            return []
        return []
    if isinstance(obj, str):
        try:
            parsed = json.loads(obj)
        except Exception:
            return []
        if isinstance(parsed, list):
            return [x for x in parsed if isinstance(x, dict)]
    return []


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _parse_args() -> argparse.Namespace:
    repo_root = _repo_root()
    default_cases = repo_root / "docs" / "tools" / "vbrain" / "local_rag_eval_cases.json"
    env = _try_get_codex_mcp_env("local_rag")

    default_base_dir = env.get("BASE_DIR", "docs") or "docs"
    default_model = env.get("MODEL_NAME", "Xenova/all-MiniLM-L6-v2") or "Xenova/all-MiniLM-L6-v2"

    parser = argparse.ArgumentParser(description="Local RAG 嵌入模型评估（不换 MCP）")
    parser.add_argument(
        "--cases",
        default=str(default_cases),
        help="查询回归集 JSON（默认：docs/tools/vbrain/local_rag_eval_cases.json）",
    )
    parser.add_argument(
        "--models",
        default="",
        help=(
            "要对比的模型列表（逗号分隔）。不传则默认只评估当前 local_rag 的模型："
            f"{default_model}。可选推荐：Xenova/multilingual-e5-base（更好但 ingest 更慢），"
            "Xenova/multilingual-e5-large（更强但更慢）"
        ),
    )
    parser.add_argument(
        "--base-dir",
        default=default_base_dir,
        help="要索引/检索的文档根目录（默认跟随 codex mcp local_rag.BASE_DIR；通常为 docs）",
    )
    parser.add_argument("--pattern", default="**/*.md", help="索引文件 glob（相对 base-dir，默认 **/*.md）")
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        help="排除文件 glob（相对 base-dir，可重复）。默认 base-dir=docs 时自动排除 archive/**",
    )
    parser.add_argument(
        "--k",
        type=int,
        default=0,
        help="query_documents 返回 TopK（0 表示在 cases 中取 default_k）",
    )
    parser.add_argument(
        "--db-root",
        default=".vibe/local-rag/model_dbs",
        help="评估用向量库根目录（相对仓库根目录；每个模型会建一个子目录）",
    )
    parser.add_argument(
        "--build",
        choices=["none", "missing", "update", "rebuild"],
        default="missing",
        help="是否构建索引：none=不构建，missing=缺失时构建，update=仅更新变更文件，rebuild=每次重建（仅影响评估 DB）",
    )
    parser.add_argument(
        "--mode",
        choices=["eval", "build"],
        default="eval",
        help="运行模式：eval=构建（可选）+ 用回归集评估；build=仅构建/更新索引并统计耗时（用于对比重建速度）",
    )
    parser.add_argument(
        "--file-limit",
        type=int,
        default=0,
        help="最多索引/评估的文件数（0 表示不限制；用于快速基准测试）。",
    )
    parser.add_argument("--timeout-sec", type=int, default=900, help="MCP 调用超时（默认 900s）")
    parser.add_argument("--query-timeout-sec", type=int, default=90, help="单次 query 超时（默认 90s）")
    parser.add_argument(
        "--out-dir",
        default="",
        help="输出目录（默认 artifacts/local_rag_eval/<utc_ts>/）。",
    )
    return parser.parse_args()


def _resolve_models(raw: str, baseline: str) -> list[str]:
    models: list[str] = []
    if raw and raw.strip():
        parts = [p.strip() for p in raw.split(",") if p.strip()]
        models = parts
    else:
        models = [baseline]

    seen: set[str] = set()
    out: list[str] = []
    for m in models:
        key = m.strip()
        if not key:
            continue
        if key in seen:
            continue
        seen.add(key)
        out.append(key)
    return out


async def _eval_one_model(
    *,
    repo_root: Path,
    suite: _EvalSuite,
    model_name: str,
    base_dir: Path,
    files: list[Path],
    db_root: Path,
    db_path: Path,
    cache_dir: Path,
    rag_hybrid_weight: str,
    rag_grouping: str,
    build_mode: str,
    mode: str,
    k: int,
    timeout_sec: int,
    query_timeout_sec: int,
    stderr_log_path: Path,
) -> _ModelMetrics:
    state_path = _ingest_state_path(db_path)
    to_ingest: list[Path] = []
    skipped = 0

    ready = _is_lancedb_ready(db_path)
    if build_mode == "rebuild":
        if db_path.exists():
            _safe_rmtree_under(db_root, db_path)
        try:
            state_path.unlink()
        except FileNotFoundError:
            pass
        except Exception:
            pass
        to_ingest = files
    elif build_mode == "none":
        to_ingest = []
    elif build_mode == "missing":
        if not ready:
            to_ingest = files
    elif build_mode == "update":
        if not ready:
            to_ingest = files
        else:
            prev = _load_ingest_state(state_path)
            prev_files: dict[str, dict[str, int]] = {}
            prev_ok = False
            if isinstance(prev, dict):
                meta = prev.get("meta")
                files_map = prev.get("files")
                if isinstance(meta, dict) and isinstance(files_map, dict):
                    prev_ok = (
                        str(meta.get("model_name", "")).strip() == str(model_name).strip()
                        and str(meta.get("base_dir", "")).strip() == str(base_dir).strip()
                    )
                    if prev_ok:
                        for k, v in files_map.items():
                            if isinstance(k, str) and isinstance(v, dict):
                                m = v.get("mtime_ns")
                                sz = v.get("size")
                                if isinstance(m, int) and isinstance(sz, int):
                                    prev_files[k] = {"mtime_ns": m, "size": sz}

            filtered: list[Path] = []
            for p in files:
                rel_repo = str(p.relative_to(repo_root)).replace("\\", "/")
                mtime_ns, size = _file_sig(p)
                prev_entry = prev_files.get(rel_repo) if prev_ok else None
                if (
                    prev_entry
                    and int(prev_entry.get("mtime_ns", -1)) == mtime_ns
                    and int(prev_entry.get("size", -1)) == size
                ):
                    skipped += 1
                    continue
                filtered.append(p)
            to_ingest = filtered

    built = bool(to_ingest)
    build_files = len(to_ingest)
    build_seconds = 0.0

    failures: list[dict[str, Any]] = []
    hit_sum = 0.0
    mrr_sum = 0.0

    stderr_log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(stderr_log_path, "w", encoding="utf-8", errors="replace") as stderr_fh:
        command, cmd_args, env = _local_rag_stdio_config(
            repo_root=repo_root,
            base_dir=base_dir,
            db_path=db_path,
            cache_dir=cache_dir,
            model_name=model_name,
            rag_hybrid_weight=rag_hybrid_weight,
            rag_grouping=rag_grouping,
        )

        async with mcp_stdio_session(
            command=command,
            args=cmd_args,
            cwd=repo_root,
            env=env,
            init_timeout_sec=float(timeout_sec),
            show_progress=False,
            errlog=stderr_fh,
        ) as session:
            tools_resp = await mcp_list_tools(session, timeout_sec=float(timeout_sec), show_progress=False)
            tool_names = {t.name for t in tools_resp.tools}
            if "query_documents" not in tool_names:
                raise RuntimeError(f"local_rag 不支持 query_documents，tools={sorted(tool_names)}")
            if built and "ingest_file" not in tool_names:
                raise RuntimeError(f"local_rag 不支持 ingest_file，tools={sorted(tool_names)}")

            state_files: dict[str, dict[str, int]] = {}
            if to_ingest:
                total = len(to_ingest)
                total_all = len(files)
                if build_mode == "update":
                    print(f"  - 更新索引：to_ingest={total}/{total_all}，skipped={skipped}", flush=True)
                else:
                    print(f"  - 构建索引：files={total}（可能需要下载模型，首次会较慢）", flush=True)
                start_ts = time.time()
                for idx, path in enumerate(to_ingest, start=1):
                    abs_path = str(path.resolve())
                    rel_repo = str(path.relative_to(repo_root)).replace("\\", "/")
                    print_progress(_render_progress_line(done=idx - 1, total=total, start_ts=start_ts, current=rel_repo))
                    wait_label = f"ingest_file {idx}/{total}: {_truncate_middle(rel_repo, max_len=72)}"
                    result = await mcp_call_tool(
                        session,
                        name="ingest_file",
                        arguments={"filePath": abs_path},
                        timeout_sec=float(timeout_sec),
                        show_progress=True,
                        progress_label=wait_label,
                    )
                    if bool(getattr(result, "isError", False)):
                        print("")
                        raise RuntimeError(f"ingest_file 失败：{rel_repo} -> {tool_result_text(result)}")

                    mtime_ns, size = _file_sig(path)
                    state_files[rel_repo] = {"mtime_ns": mtime_ns, "size": size}
                    print_progress(_render_progress_line(done=idx, total=total, start_ts=start_ts, current=rel_repo))
                print("")
                build_seconds = float(max(0.0, time.time() - start_ts))

                # 写入/更新索引增量状态（便于下次 update）
                prev = _load_ingest_state(state_path) or {}
                merged: dict[str, dict[str, int]] = {}
                if build_mode != "rebuild":
                    prev_files_obj = prev.get("files")
                    if isinstance(prev_files_obj, dict):
                        for k0, v0 in prev_files_obj.items():
                            if isinstance(k0, str) and isinstance(v0, dict):
                                m = v0.get("mtime_ns")
                                sz = v0.get("size")
                                if isinstance(m, int) and isinstance(sz, int):
                                    merged[k0] = {"mtime_ns": m, "size": sz}
                merged.update(state_files)
                _write_ingest_state(
                    state_path,
                    {
                        "version": 1,
                        "updated_date_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                        "meta": {"base_dir": str(base_dir), "model_name": str(model_name)},
                        "files": merged,
                    },
                )

            n = 0 if str(mode).lower() == "build" else len(suite.cases)
            for i, case in enumerate(suite.cases, start=1):
                if n == 0:
                    break
                try:
                    result = await mcp_call_tool(
                        session,
                        name="query_documents",
                        arguments={"query": case.query, "limit": int(k)},
                        timeout_sec=float(query_timeout_sec),
                        show_progress=False,
                    )
                except Exception as e:
                    failures.append({"case_id": case.case_id, "query": case.query, "error": str(e)})
                    continue

                if bool(getattr(result, "isError", False)):
                    failures.append({"case_id": case.case_id, "query": case.query, "error": tool_result_text(result)})
                    continue

                results = _extract_query_results(result)
                rank: int | None = None
                top_paths: list[str] = []
                for j, item in enumerate(results[:k], start=1):
                    fp = str(item.get("filePath") or "")
                    if fp:
                        top_paths.append(fp)
                    if rank is None and _match_any_expected(fp, case.expect_any):
                        rank = j

                if rank is None:
                    failures.append(
                        {
                            "case_id": case.case_id,
                            "query": case.query,
                            "expect_any": list(case.expect_any),
                            "top_paths": top_paths,
                        }
                    )
                    continue

                hit_sum += 1.0
                mrr_sum += 1.0 / float(rank)

            hit_at_k = hit_sum / n if n > 0 else 0.0
            mrr_at_k = mrr_sum / n if n > 0 else 0.0
            return _ModelMetrics(
                model=model_name,
                db_path=str(db_path),
                built=built,
                build_mode=str(build_mode),
                build_files=int(build_files),
                build_skipped=int(skipped),
                build_seconds=float(build_seconds),
                hit_at_k=hit_at_k,
                mrr_at_k=mrr_at_k,
                case_count=n,
                failures=failures,
            )


async def _amain() -> int:
    args = _parse_args()
    repo_root = _repo_root()

    if not which("npx"):
        print("未找到 npx：请先安装 Node.js（需要 npx 来启动 mcp-local-rag）。", file=sys.stderr)
        return 2

    cases_path = Path(str(args.cases)).expanduser()
    if not cases_path.is_absolute():
        cases_path = (repo_root / cases_path).resolve()
    if not cases_path.exists():
        print(f"未找到 cases：{cases_path}", file=sys.stderr)
        return 2

    suite = _load_suite(cases_path)
    k = int(args.k or 0)
    if k <= 0:
        k = int(suite.default_k or 5)
    mode = str(getattr(args, "mode", "eval") or "eval").strip().lower()

    env = _try_get_codex_mcp_env("local_rag")
    baseline_model = env.get("MODEL_NAME", "Xenova/all-MiniLM-L6-v2") or "Xenova/all-MiniLM-L6-v2"
    models = _resolve_models(str(args.models or ""), baseline=baseline_model)

    raw_base = str(args.base_dir or "").strip() or "docs"
    base_dir = Path(raw_base).expanduser()
    if not base_dir.is_absolute():
        base_dir = (repo_root / base_dir).resolve()
    if not base_dir.exists():
        print(f"未找到 base-dir：{base_dir}", file=sys.stderr)
        return 2

    exclude_patterns = [str(x).strip() for x in (args.exclude or []) if str(x).strip()]
    try:
        default_docs_dir = (repo_root / "docs").resolve()
        if not exclude_patterns and base_dir.resolve() == default_docs_dir:
            exclude_patterns = ["archive/**"]
    except Exception:
        pass

    files = _collect_docs(base_dir, pattern=str(args.pattern), exclude_patterns=exclude_patterns)
    if int(getattr(args, "file_limit", 0) or 0) > 0:
        files = files[: int(args.file_limit)]
    if not files:
        print("未找到需要索引的文件（pattern/exclude 可能写错了）。", file=sys.stderr)
        return 2

    db_root = Path(str(args.db_root or "")).expanduser()
    if not db_root.is_absolute():
        db_root = (repo_root / db_root).resolve()
    db_root.mkdir(parents=True, exist_ok=True)

    cache_dir = env.get("CACHE_DIR", "").strip()
    cache_dir_p = Path(cache_dir).expanduser() if cache_dir else _default_model_cache_dir()
    if not cache_dir_p.is_absolute():
        cache_dir_p = (repo_root / cache_dir_p).resolve()

    rag_hybrid_weight = env.get("RAG_HYBRID_WEIGHT", "0.7") or "0.7"
    rag_grouping = env.get("RAG_GROUPING", "similar") or "similar"

    raw_out = str(args.out_dir or "").strip()
    out_dir = Path(raw_out) if raw_out else (repo_root / "artifacts" / "local_rag_eval" / _utc_ts_compact())
    if not out_dir.is_absolute():
        out_dir = (repo_root / out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    meta = {
        "repo_root": str(repo_root),
        "cases_path": str(cases_path),
        "suite_version": suite.version,
        "k": k,
        "mode": mode,
        "file_limit": int(getattr(args, "file_limit", 0) or 0),
        "base_dir": str(base_dir),
        "pattern": str(args.pattern),
        "exclude": exclude_patterns,
        "db_root": str(db_root),
        "cache_dir": str(cache_dir_p),
        "rag_hybrid_weight": str(rag_hybrid_weight),
        "rag_grouping": str(rag_grouping),
        "build": str(args.build),
        "models": models,
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
    }

    print("Local RAG 嵌入模型评估：", flush=True)
    print(f"- cases: {cases_path}", flush=True)
    print(f"- mode: {mode}", flush=True)
    print(f"- base_dir: {base_dir}", flush=True)
    print(f"- files: {len(files)}（exclude={exclude_patterns or '[]'}）", flush=True)
    print(f"- models: {models}", flush=True)
    print(f"- build: {args.build}", flush=True)
    print(f"- out_dir: {out_dir}", flush=True)

    results: list[_ModelMetrics] = []
    for model in models:
        slug = _model_slug(model)
        db_path = db_root / slug
        stderr_log = out_dir / f"local_rag_{slug}_stderr.log"
        print("", flush=True)
        print(f"[{model}] db={db_path}", flush=True)
        try:
            metrics = await _eval_one_model(
                repo_root=repo_root,
                suite=suite,
                model_name=model,
                base_dir=base_dir,
                files=files,
                db_root=db_root,
                db_path=db_path,
                cache_dir=cache_dir_p,
                rag_hybrid_weight=rag_hybrid_weight,
                rag_grouping=rag_grouping,
                build_mode=str(args.build),
                mode=mode,
                k=k,
                timeout_sec=int(args.timeout_sec),
                query_timeout_sec=int(args.query_timeout_sec),
                stderr_log_path=stderr_log,
            )
            results.append(metrics)
            build_note = (
                f"build={metrics.build_mode} files={metrics.build_files} "
                f"skipped={metrics.build_skipped} time={metrics.build_seconds:.1f}s"
            )
            if mode == "build":
                print(f"  => {build_note}", flush=True)
            else:
                print(
                    f"  => {build_note} | hit@{k}={metrics.hit_at_k:.1%}, mrr@{k}={metrics.mrr_at_k:.3f}, "
                    f"fail={len(metrics.failures)}/{metrics.case_count}",
                    flush=True,
                )
        except Exception as e:
            results.append(
                _ModelMetrics(
                    model=model,
                    db_path=str(db_path),
                    built=(str(args.build) != "none"),
                    build_mode=str(args.build),
                    build_files=0,
                    build_skipped=0,
                    build_seconds=0.0,
                    hit_at_k=0.0,
                    mrr_at_k=0.0,
                    case_count=(0 if mode == "build" else len(suite.cases)),
                    failures=[],
                    error=f"{e}（详见：{stderr_log}）",
                )
            )
            print(f"  !! 模型评估失败：{e}", flush=True)
            print(f"     stderr: {stderr_log}", flush=True)

    # 选择 best：eval 看效果；build 看速度（越快越好）
    best: _ModelMetrics | None = None
    if mode == "build":
        for r in results:
            if r.error is not None:
                continue
            if r.build_files <= 0:
                continue
            if best is None:
                best = r
                continue
            if r.build_seconds < best.build_seconds - 1e-9:
                best = r
    else:
        for r in results:
            if best is None:
                best = r
                continue
            if r.hit_at_k > best.hit_at_k + 1e-12:
                best = r
                continue
            if abs(r.hit_at_k - best.hit_at_k) <= 1e-12 and r.mrr_at_k > best.mrr_at_k + 1e-12:
                best = r

    report = {
        "meta": meta,
        "results": [
            {
                "model": r.model,
                "db_path": r.db_path,
                "built": r.built,
                "build_mode": r.build_mode,
                "build_files": r.build_files,
                "build_skipped": r.build_skipped,
                "build_seconds": r.build_seconds,
                "hit_at_k": r.hit_at_k,
                "mrr_at_k": r.mrr_at_k,
                "case_count": r.case_count,
                "failures": r.failures,
                "error": r.error,
            }
            for r in results
        ],
        "best": (
            {
                "model": best.model,
                "db_path": best.db_path,
                "hit_at_k": best.hit_at_k,
                "mrr_at_k": best.mrr_at_k,
                "build_files": best.build_files,
                "build_skipped": best.build_skipped,
                "build_seconds": best.build_seconds,
            }
            if best
            else None
        ),
        "finished_at_utc": datetime.now(timezone.utc).isoformat(),
    }

    report_path = out_dir / "report.json"
    _write_json(report_path, report)

    print("", flush=True)
    print("评估完成：", flush=True)
    if best and mode == "build":
        avg = (best.build_seconds / best.build_files) if best.build_files > 0 else 0.0
        print(f"- fastest: {best.model}  (files={best.build_files}, time={best.build_seconds:.1f}s, avg={avg:.2f}s/file)", flush=True)
    elif best:
        print(f"- best: {best.model}  (hit@{k}={best.hit_at_k:.1%}, mrr@{k}={best.mrr_at_k:.3f})", flush=True)
    print(f"- report: {report_path}", flush=True)

    if mode == "build":
        ok_results = [r for r in results if r.error is None and r.build_files > 0]
        ok_results.sort(key=lambda r: r.build_seconds)
        if ok_results:
            print("", flush=True)
            print("重建速度排行（越快越靠前）：", flush=True)
            for r in ok_results:
                avg = (r.build_seconds / r.build_files) if r.build_files > 0 else 0.0
                fps = (r.build_files / r.build_seconds) if r.build_seconds > 0 else 0.0
                print(
                    f"- {r.model}: files={r.build_files}, time={r.build_seconds:.1f}s, avg={avg:.2f}s/file, {fps:.2f} files/s",
                    flush=True,
                )

    # exit code：至少有一个模型成功（hit@k > 0 或无 error）则返回 0
    if any((r.error is None) for r in results):
        return 0
    return 1


def main() -> int:
    return asyncio.run(_amain())


if __name__ == "__main__":
    raise SystemExit(main())
