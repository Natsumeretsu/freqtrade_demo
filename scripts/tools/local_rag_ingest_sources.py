"""
批量将本仓库抓取的外部来源缓存（.vibe/knowledge/sources） ingest 到 mcp-local-rag（本地向量库）。

设计目标：
- Local RAG 作为“资料索引加速器”：用于网页/文档/PDF 等外部资料的语义召回 + 关键词 boost
- 抓取缓存默认在 .vibe 下（可重建缓存，默认 gitignore），不把外部全文混进仓库历史
- ingest 优先使用 ingest_data：用 URL 作为 source，便于同一来源的增量更新（重复 ingest 会覆盖/更新）
- 默认只 ingest status=ok 的来源，并跳过“验证/工作流”类来源，避免把登录态页面索引进大脑

用法（在仓库根目录）：
  python -X utf8 scripts/tools/local_rag_ingest_sources.py

可选：
  python -X utf8 scripts/tools/local_rag_ingest_sources.py --limit 5
  python -X utf8 scripts/tools/local_rag_ingest_sources.py --ids "S-001,S-603"
  python -X utf8 scripts/tools/local_rag_ingest_sources.py --only-new
  python -X utf8 scripts/tools/local_rag_ingest_sources.py --include-workflow-sources
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from mcp_stdio_client import (
    mcp_call_tool,
    mcp_list_tools,
    mcp_stdio_session,
    print_progress,
    tool_result_text,
    tool_result_to_obj,
)


@dataclass(frozen=True)
class _SourceCandidate:
    source_id: str
    title: str
    url: str
    fetched_date_utc: str
    meta_path: Path
    content_path: Path
    content_format: str  # "html" | "markdown"
    pick_reason: str


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _utc_date_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="批量 ingest 抓取来源缓存到 mcp-local-rag")
    parser.add_argument(
        "--sources-dir",
        default=".vibe/knowledge/sources",
        help="抓取缓存目录（相对仓库根目录）。默认：.vibe/knowledge/sources",
    )
    parser.add_argument(
        "--ids",
        default="",
        help="仅 ingest 指定 S-ID（逗号分隔），例如：S-001,S-105",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="最多 ingest 的条目数（0 表示不限制，用于调试/快速验证）。",
    )
    parser.add_argument(
        "--include-non-ok",
        action="store_true",
        help="也 ingest meta.status!=ok 的来源（默认跳过，建议仅用于调试）。",
    )
    parser.add_argument(
        "--include-workflow-sources",
        action="store_true",
        help="也 ingest “验证/工作流”类来源（默认跳过，避免索引登录态页面）。",
    )
    parser.add_argument(
        "--only-new",
        action="store_true",
        help="仅 ingest 未 ingest 过或抓取日期更新过的来源（依赖 meta.local_rag_ingested_date_utc）。",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="强制重新 ingest（忽略 meta.local_rag_ingested_date_utc）。",
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
        help="嵌入模型（映射到 local_rag 的 MODEL_NAME）。切换模型会改变向量维度，务必先重建 DB。",
    )
    parser.add_argument(
        "--no-progress",
        action="store_true",
        help="禁用进度条输出（默认启用）。",
    )
    return parser.parse_args()


def _normalize_sid_list(s: str) -> set[str]:
    if not s or not s.strip():
        return set()
    parts = [p.strip() for p in s.split(",") if p.strip()]
    return {p.upper() for p in parts}


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


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


def _local_rag_stdio_config(
    *,
    repo_root: Path,
    base_dir: Path,
    db_path: Path,
    cache_dir: Path,
    model_name: str,
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
    if model_name and model_name.strip():
        env["MODEL_NAME"] = model_name.strip()
    env["RAG_HYBRID_WEIGHT"] = "0.7"
    env["RAG_GROUPING"] = "similar"

    command = "cmd"
    args = ["/c", "npx", "-y", "mcp-local-rag@0.5.3"]
    return command, args, env


_SID_DIR_RE = re.compile(r"^S-\d{3}$", re.IGNORECASE)


def _looks_like_workflow_source(title: str) -> bool:
    t = (title or "").strip()
    if not t:
        return False
    low = t.lower()
    return ("验证" in t) or ("workflow" in low) or ("访问受限" in t)


def _choose_candidate(repo_root: Path, entry_dir: Path) -> _SourceCandidate | None:
    meta_playwright_path = entry_dir / "meta_playwright.json"
    meta_markitdown_path = entry_dir / "meta.json"

    meta_playwright: dict[str, Any] | None = None
    if meta_playwright_path.exists():
        meta_playwright = _read_json(meta_playwright_path)

    meta_markitdown: dict[str, Any] | None = None
    if meta_markitdown_path.exists():
        meta_markitdown = _read_json(meta_markitdown_path)

    # 统一的“展示信息”尽量来自能提供 URL/title 的 meta
    base_meta = meta_playwright or meta_markitdown or {}
    source_id = str(base_meta.get("source_id") or entry_dir.name).upper()
    title = str(base_meta.get("title") or "").strip()
    url = str(base_meta.get("url") or "").strip()
    fetched_date_utc = str(base_meta.get("fetched_date_utc") or "").strip()

    # 1) Playwright DOM（最佳：可用于 HTML 清洗/正文提取）
    if meta_playwright and str(meta_playwright.get("status", "")).strip() == "ok":
        dom_rel = str(meta_playwright.get("cache_dom") or "").strip()
        if dom_rel:
            dom_path = repo_root / dom_rel
            if dom_path.exists():
                return _SourceCandidate(
                    source_id=source_id,
                    title=title,
                    url=url,
                    fetched_date_utc=str(meta_playwright.get("fetched_date_utc") or fetched_date_utc),
                    meta_path=meta_playwright_path,
                    content_path=dom_path,
                    content_format="html",
                    pick_reason="playwright_dom",
                )

    # 2) 手工兜底（用户导出 HTML/PDF 后离线转写）
    manual_path = entry_dir / "manual_markitdown.md"
    if manual_path.exists():
        meta_path = meta_playwright_path if meta_playwright_path.exists() else meta_markitdown_path
        return _SourceCandidate(
            source_id=source_id,
            title=title,
            url=url,
            fetched_date_utc=fetched_date_utc,
            meta_path=meta_path if meta_path.exists() else entry_dir / "meta_manual.json",
            content_path=manual_path,
            content_format="markdown",
            pick_reason="manual_markitdown",
        )

    # 3) Markitdown Markdown（静态正文）
    if meta_markitdown and str(meta_markitdown.get("status", "")).strip() == "ok":
        md_rel = str(meta_markitdown.get("cache_markdown") or "").strip()
        if md_rel:
            md_path = repo_root / md_rel
            if md_path.exists():
                return _SourceCandidate(
                    source_id=source_id,
                    title=title,
                    url=url,
                    fetched_date_utc=str(meta_markitdown.get("fetched_date_utc") or fetched_date_utc),
                    meta_path=meta_markitdown_path,
                    content_path=md_path,
                    content_format="markdown",
                    pick_reason="markitdown_md",
                )

    # 4) Playwright Snapshot（兜底：可见性快照，噪声可能较多）
    if meta_playwright and str(meta_playwright.get("status", "")).strip() == "ok":
        snap_rel = str(meta_playwright.get("cache_snapshot") or "").strip()
        if snap_rel:
            snap_path = repo_root / snap_rel
            if snap_path.exists():
                return _SourceCandidate(
                    source_id=source_id,
                    title=title,
                    url=url,
                    fetched_date_utc=str(meta_playwright.get("fetched_date_utc") or fetched_date_utc),
                    meta_path=meta_playwright_path,
                    content_path=snap_path,
                    content_format="markdown",
                    pick_reason="playwright_snapshot",
                )

    return None


def _should_skip_only_new(meta: dict[str, Any], fetched_date_utc: str) -> bool:
    """
    判断“是否已 ingest 且无需更新”。

    这里使用粗粒度日期（YYYY-MM-DD）比较即可，避免引入额外依赖。
    """
    ingested = str(meta.get("local_rag_ingested_date_utc") or "").strip()
    fetched = (fetched_date_utc or "").strip()
    if not ingested:
        return False
    if not fetched:
        return True
    return ingested >= fetched


async def _amain() -> int:
    args = _parse_args()
    repo_root = _repo_root()
    sources_dir = (repo_root / args.sources_dir).resolve()
    if not sources_dir.exists():
        print(f"未找到抓取缓存目录：{sources_dir.as_posix()}", file=sys.stderr)
        return 2

    ids = _normalize_sid_list(args.ids)
    source_dirs = sorted([p for p in sources_dir.iterdir() if p.is_dir() and _SID_DIR_RE.match(p.name or "")])
    if ids:
        source_dirs = [p for p in source_dirs if p.name.upper() in ids]
    if args.limit and args.limit > 0:
        source_dirs = source_dirs[: args.limit]

    if not source_dirs:
        print("未找到需要 ingest 的来源目录。", file=sys.stderr)
        return 2

    candidates: list[_SourceCandidate] = []
    skipped: list[str] = []
    only_ok = not bool(args.include_non_ok)
    for entry_dir in source_dirs:
        cand = _choose_candidate(repo_root, entry_dir)
        if not cand:
            skipped.append(f"{entry_dir.name}: no-cache")
            continue
        if not args.include_workflow_sources and _looks_like_workflow_source(cand.title):
            skipped.append(f"{cand.source_id}: workflow-skip")
            continue
        if only_ok:
            # manual_markitdown 允许在 meta 非 ok 时兜底 ingest
            if cand.pick_reason != "manual_markitdown":
                try:
                    meta = _read_json(cand.meta_path)
                except Exception:
                    skipped.append(f"{cand.source_id}: meta-missing")
                    continue
                if str(meta.get("status", "")).strip() != "ok":
                    skipped.append(f"{cand.source_id}: status={meta.get('status')}")
                    continue
        if args.only_new and not args.force:
            try:
                meta = _read_json(cand.meta_path)
            except Exception:
                meta = {}
            if _should_skip_only_new(meta, fetched_date_utc=cand.fetched_date_utc):
                skipped.append(f"{cand.source_id}: up-to-date")
                continue
        candidates.append(cand)

    if not candidates:
        print("没有可 ingest 的来源（全部被过滤或缺少缓存）。")
        if skipped:
            print("已跳过：")
            for item in skipped[:50]:
                print(f"- {item}")
        return 0

    print(f"将 ingest {len(candidates)} 个来源缓存到 Local RAG（SOURCES_DIR={sources_dir.as_posix()}）")
    print("提示：首次 ingest 可能会下载嵌入/分词等模型，耗时取决于网速与磁盘。")

    _, db_path, cache_dir = _local_rag_paths(repo_root, model_cache_dir=args.model_cache_dir)
    print(f"DB_PATH={db_path.as_posix()}")
    print(f"CACHE_DIR={cache_dir.as_posix()}")
    if args.model_name:
        print(f"MODEL_NAME={args.model_name}")

    command, cmd_args, env = _local_rag_stdio_config(
        repo_root=repo_root,
        # 注意：local_rag 的 ingest_data 内部会先把内容写入 DB_PATH/raw-data 再走 ingest_file，
        # 因此 BASE_DIR 必须覆盖 DB_PATH（否则会触发 “File path must be within BASE_DIR” 校验失败）。
        base_dir=repo_root,
        db_path=db_path,
        cache_dir=cache_dir,
        model_name=args.model_name,
    )

    log_dir = repo_root / ".vibe" / "local-rag" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    errlog_path = log_dir / f"local_rag_ingest_sources_{int(time.time())}.log"
    print(f"STDERR_LOG={errlog_path}")

    with errlog_path.open("w", encoding="utf-8", errors="replace") as errlog:
        async with mcp_stdio_session(
            command=command,
            args=cmd_args,
            cwd=repo_root,
            env=env,
            init_timeout_sec=float(args.timeout_sec),
            show_progress=not args.no_progress,
            errlog=errlog,
        ) as session:
            tools_resp = await mcp_list_tools(
                session,
                timeout_sec=float(args.timeout_sec),
                show_progress=not args.no_progress,
            )
            tool_names = {t.name for t in tools_resp.tools}
            if "ingest_data" not in tool_names:
                print(f"local_rag 不支持 ingest_data，tools={sorted(tool_names)}", file=sys.stderr)
                return 1

            start_ts = time.time()
            ok = 0
            failed: list[str] = []
            ingested_date = _utc_date_str()

            for idx, cand in enumerate(candidates, start=1):
                rel_path = str(cand.content_path.relative_to(repo_root)).replace("\\", "/")
                if args.no_progress:
                    print(f"[{idx}/{len(candidates)}] ingest {cand.source_id}: {rel_path}")
                else:
                    print_progress(
                        f"[{idx:>3}/{len(candidates):<3}] ingest {cand.source_id}  elapsed={time.time()-start_ts:>.1f}s  {rel_path}"
                    )

                try:
                    raw = cand.content_path.read_text(encoding="utf-8", errors="replace")
                    preamble = (
                        f"<!-- source_id: {cand.source_id}; title: {cand.title}; "
                        f"fetched_date_utc: {cand.fetched_date_utc}; pick: {cand.pick_reason} -->\n"
                    )
                    content = preamble + raw
                    source_key = cand.url if cand.url else f"source_registry://{cand.source_id}"
                    result = await mcp_call_tool(
                        session,
                        name="ingest_data",
                        arguments={
                            "content": content,
                            "metadata": {"format": cand.content_format, "source": source_key},
                        },
                        timeout_sec=float(args.timeout_sec),
                        show_progress=not args.no_progress,
                        progress_label=f"{cand.source_id} ingest_data",
                    )
                    if bool(getattr(result, "isError", False)):
                        raise RuntimeError(tool_result_text(result))
                    ok += 1

                    # 写回 meta：记录 ingest 时间与选用的缓存文件，便于 --only-new
                    meta: dict[str, Any] = {}
                    if cand.meta_path.exists():
                        try:
                            meta = _read_json(cand.meta_path)
                        except Exception:
                            meta = {}
                    meta["local_rag_ingested_date_utc"] = ingested_date
                    meta["local_rag_ingested_format"] = cand.content_format
                    meta["local_rag_ingested_reason"] = cand.pick_reason
                    meta["local_rag_ingested_content"] = rel_path
                    meta["local_rag_ingested_source"] = source_key
                    if not cand.meta_path.exists() and cand.meta_path.name == "meta_manual.json":
                        meta.setdefault("source_id", cand.source_id)
                        meta.setdefault("title", cand.title)
                        meta.setdefault("url", cand.url)
                        meta.setdefault("fetched_date_utc", cand.fetched_date_utc)
                        meta.setdefault("status", "ok")
                        meta.setdefault("tool", "manual(markitdown)")
                    _write_json(cand.meta_path, meta)
                except Exception as e:
                    failed.append(f"{cand.source_id}: {e}")

                if not args.no_progress:
                    print_progress(
                        f"[{idx:>3}/{len(candidates):<3}] done   {cand.source_id}  elapsed={time.time()-start_ts:>.1f}s  {rel_path}"
                    )

            if not args.no_progress:
                print("")

            status_result = await mcp_call_tool(
                session,
                name="status",
                arguments={},
                timeout_sec=float(args.timeout_sec),
                show_progress=not args.no_progress,
                progress_label="status",
            )

            print("")
            print(f"完成：成功 {ok} / 失败 {len(failed)} / 跳过 {len(skipped)}")
            if skipped:
                print("跳过条目：")
                for item in skipped[:50]:
                    print(f"- {item}")
                if len(skipped) > 50:
                    print(f"- ... 其余 {len(skipped) - 50} 条已省略")
            if failed:
                print("失败条目：")
                for item in failed[:50]:
                    print(f"- {item}")
                if len(failed) > 50:
                    print(f"- ... 其余 {len(failed) - 50} 条已省略")

            if bool(getattr(status_result, "isError", False)):
                print("")
                print(f"Local RAG status 失败：{tool_result_text(status_result)}", file=sys.stderr)
            else:
                status_obj = tool_result_to_obj(status_result)
                payload: object = status_obj
                if isinstance(status_obj, dict) and status_obj.get("structuredContent") is not None:
                    payload = status_obj.get("structuredContent")
                print("")
                print("Local RAG status：")
                print(json.dumps(payload, ensure_ascii=False, indent=2))

            return 0 if not failed else 1


def main() -> int:
    return asyncio.run(_amain())


if __name__ == "__main__":
    raise SystemExit(main())
