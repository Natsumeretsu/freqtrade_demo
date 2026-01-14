"""
vbrain 统一入口（控制平面 CLI）

目标：
- 用一个命令入口把 vbrain 的常用动作“收拢”起来，降低日常操作摩擦
- 不搬动数据平面（in-memoria.db / .serena / docs / .vibe），只做编排与状态查看
- 协议层使用官方 MCP Python SDK（通过 mcp_stdio_client.py），避免自研 JSON-RPC 轮子

用法（在仓库根目录）：
  python -X utf8 scripts/tools/vbrain.py status
  python -X utf8 scripts/tools/vbrain.py preheat --rebuild-docs

透传到子脚本（推荐用 -- 分隔）：
  python -X utf8 scripts/tools/vbrain.py ingest-docs -- --rebuild
  python -X utf8 scripts/tools/vbrain.py ingest-sources -- --only-new
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sqlite3
import subprocess
import sys
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from shutil import which

from mcp_stdio_client import mcp_call_tool, mcp_list_tools, mcp_stdio_session, tool_result_text


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _script_path(repo_root: Path, rel: str) -> Path:
    return (repo_root / rel).resolve()


def _strip_passthrough(argv: list[str]) -> list[str]:
    # 允许 `... cmd -- --rebuild` 或 `... cmd --rebuild` 两种写法
    if argv and argv[0] == "--":
        return argv[1:]
    return argv


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


def _fmt_bytes(n: int) -> str:
    if n < 0:
        return "?"
    units = ["B", "KB", "MB", "GB", "TB"]
    size = float(n)
    idx = 0
    while size >= 1024 and idx < len(units) - 1:
        size /= 1024
        idx += 1
    if idx == 0:
        return f"{int(size)}{units[idx]}"
    return f"{size:.2f}{units[idx]}"


def _fmt_mtime(ts: float) -> str:
    try:
        return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return "?"


def _count_dirs_matching(root: Path, prefix: str) -> int:
    if not root.exists():
        return 0
    cnt = 0
    for p in root.iterdir():
        if p.is_dir() and p.name.upper().startswith(prefix.upper()):
            cnt += 1
    return cnt


def _count_files_glob(root: Path, pattern: str) -> int:
    if not root.exists():
        return 0
    return sum(1 for p in root.glob(pattern) if p.is_file())


def _cmd_status(repo_root: Path) -> int:
    in_memoria_db = repo_root / "in-memoria.db"
    local_rag_db = repo_root / ".vibe" / "local-rag" / "lancedb"
    sources_dir = repo_root / ".vibe" / "knowledge" / "sources"
    docs_dir = repo_root / "docs"
    serena_memories = repo_root / ".serena" / "memories"
    manifest = repo_root / "docs" / "tools" / "vbrain" / "manifest.json"

    print("vbrain 状态（粗粒度）：")

    if manifest.exists():
        st = manifest.stat()
        print(f"- manifest: ok  ({_fmt_bytes(st.st_size)}, mtime={_fmt_mtime(st.st_mtime)})")
    else:
        print("- manifest: missing")

    if in_memoria_db.exists():
        st = in_memoria_db.stat()
        print(f"- in-memoria.db: ok  ({_fmt_bytes(st.st_size)}, mtime={_fmt_mtime(st.st_mtime)})")
    else:
        print("- in-memoria.db: missing（首次使用 in_memoria 后会自动生成）")

    if serena_memories.exists():
        md_cnt = _count_files_glob(serena_memories, "*.md")
        print(f"- .serena/memories: ok  (md={md_cnt})")
    else:
        print("- .serena/memories: missing")

    if docs_dir.exists():
        md_cnt = sum(1 for p in docs_dir.rglob("*.md") if p.is_file())
        print(f"- docs: ok  (md={md_cnt})")
    else:
        print("- docs: missing")

    if local_rag_db.exists():
        # 只做轻量检查：避免递归计算总大小（可能很慢）
        entries = list(local_rag_db.iterdir())
        print(f"- .vibe/local-rag/lancedb: ok  (entries={len(entries)})")
    else:
        print("- .vibe/local-rag/lancedb: missing（可用 preheat/ingest-docs 重建）")

    s_cnt = _count_dirs_matching(sources_dir, "S-")
    if sources_dir.exists():
        print(f"- .vibe/knowledge/sources: ok  (S-xxx={s_cnt})")
    else:
        print("- .vibe/knowledge/sources: missing（feed 缓存目录：仅当你有外部 feed 输入时才需要）")

    return 0


def _cmd_preheat(repo_root: Path, args: argparse.Namespace) -> int:
    print("vbrain preheat：开始…", flush=True)

    code = 0

    docs_args: list[str] = []
    if args.rebuild_docs:
        docs_args.append("--rebuild")
    if args.docs_limit > 0:
        docs_args += ["--limit", str(args.docs_limit)]
    if args.no_progress:
        docs_args.append("--no-progress")

    print("vbrain preheat：阶段 1/2：索引 docs…", flush=True)
    t0 = time.time()
    code = _run_python(repo_root, "scripts/tools/local_rag_ingest_project_docs.py", docs_args)
    if code != 0:
        elapsed = time.time() - t0
        print(f"vbrain preheat：阶段 1/2 失败（code={code}，elapsed={elapsed:.1f}s）", file=sys.stderr, flush=True)
        print(
            "建议：先运行 `python -X utf8 scripts/tools/vbrain.py doctor --target codex` 排查 MCP/依赖。",
            file=sys.stderr,
            flush=True,
        )
        return code
    print(f"vbrain preheat：阶段 1/2 完成（elapsed={time.time() - t0:.1f}s）", flush=True)

    if args.skip_sources:
        print("vbrain preheat：阶段 2/2：跳过 sources（按 --skip-sources）", flush=True)
        return 0

    src_args: list[str] = []
    if args.only_new_sources:
        src_args.append("--only-new")
    if args.sources_limit > 0:
        src_args += ["--limit", str(args.sources_limit)]
    if args.no_progress:
        src_args.append("--no-progress")

    print("vbrain preheat：阶段 2/2：索引 sources…", flush=True)
    t1 = time.time()
    code = _run_python(repo_root, "scripts/tools/local_rag_ingest_sources.py", src_args)
    if code != 0:
        elapsed = time.time() - t1
        print(f"vbrain preheat：阶段 2/2 失败（code={code}，elapsed={elapsed:.1f}s）", file=sys.stderr, flush=True)
        print(
            "建议：先运行 `python -X utf8 scripts/tools/vbrain.py doctor --target codex` 排查 MCP/依赖。",
            file=sys.stderr,
            flush=True,
        )
        return code

    print(f"vbrain preheat：阶段 2/2 完成（elapsed={time.time() - t1:.1f}s）", flush=True)
    print("vbrain preheat：完成。", flush=True)
    return 0


def _cmd_doctor(repo_root: Path, args: argparse.Namespace) -> int:
    """
    vbrain 体检：优先复用仓库内 scripts/mcp/doctor.ps1；在不可用时降级为轻量检查。
    """

    doctor_ps1 = repo_root / "scripts" / "mcp" / "doctor.ps1"
    pwsh = which("pwsh")
    powershell = which("powershell")

    if doctor_ps1.exists() and (pwsh or powershell):
        shell = pwsh or powershell
        cmd = [
            shell,
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(doctor_ps1),
            "-Target",
            str(args.target),
        ]
        if args.deep:
            cmd.append("-Deep")
        if args.show_config:
            cmd.append("-ShowConfig")
        return subprocess.call(cmd, cwd=str(repo_root))

    # 降级：最小可用性检查（不依赖 PowerShell / doctor.ps1）
    print("vbrain doctor（降级模式）：未找到可用的 PowerShell 或 scripts/mcp/doctor.ps1")
    required_cmds = ["npx"]
    optional_cmds = ["codex", "uvx", "node"]

    missing_required = [c for c in required_cmds if not which(c)]
    if missing_required:
        print(f"- 缺失必需命令：{', '.join(missing_required)}")
        return 1
    print("- 必需命令：ok")

    for c in optional_cmds:
        print(f"- {c}: {'ok' if which(c) else 'missing'}")

    checks: list[tuple[str, Path]] = [
        ("vbrain manifest", repo_root / "docs" / "tools" / "vbrain" / "manifest.json"),
        ("vbrain workflow", repo_root / ".serena" / "memories" / "vbrain_workflow.md"),
        ("docs", repo_root / "docs"),
        ("local_rag ingest docs", repo_root / "scripts" / "tools" / "local_rag_ingest_project_docs.py"),
        ("local_rag ingest sources", repo_root / "scripts" / "tools" / "local_rag_ingest_sources.py"),
    ]
    failed = False
    for name, path in checks:
        ok = path.exists()
        print(f"- {name}: {'ok' if ok else 'missing'}  ({path.as_posix()})")
        failed = failed or (not ok)
    return 0 if not failed else 1


def _cmd_seed_insights(repo_root: Path, _args: argparse.Namespace) -> int:
    return _run_python(repo_root, "scripts/tools/in_memoria_seed_vibe_insights.py", [])


def _extract_topic_prefix(text: str) -> str:
    t = (text or "").strip()
    if not t:
        return ""

    # 使用 Unicode 转义，避免在不同终端/编码下出现分隔符乱码导致去重失效
    seps = [
        "\uFF1A",  # ：
        ":",
        "\uFF1B",  # ；
        ";",
        "\uFF0C",  # ，
        ",",
        "\u3002",  # 。
        ".",
        "\uFF08",  # （
        "(",
    ]
    for sep in seps:
        if sep in t:
            t = t.split(sep, 1)[0]
            break
    return t.strip()


def _ai_insight_topic_key(insight_type: str, source_agent: str, insight_content: str) -> str:
    itype = (insight_type or "").strip()
    agent = (source_agent or "").strip()
    content = insight_content or ""

    obj: object | None
    try:
        obj = json.loads(content) if content.strip() else None
    except Exception:
        obj = None

    if isinstance(obj, dict):
        bug_pattern = obj.get("bugPattern")
        if isinstance(bug_pattern, str) and bug_pattern.strip():
            topic = _extract_topic_prefix(bug_pattern)
            if topic:
                return f"{itype}|{agent}|bugPattern|{topic}"

        practice = obj.get("practice")
        if isinstance(practice, str) and practice.strip():
            topic = _extract_topic_prefix(practice)
            if topic:
                return f"{itype}|{agent}|practice|{topic}"

        try:
            canon = json.dumps(obj, ensure_ascii=False, sort_keys=True)
        except Exception:
            canon = str(obj)
        return f"{itype}|{agent}|json|{canon}"

    raw = re.sub(r"\s+", " ", content.strip())
    topic = _extract_topic_prefix(raw) or raw
    return f"{itype}|{agent}|text|{topic}"


def _cmd_dedupe_insights(repo_root: Path, args: argparse.Namespace) -> int:
    """
    对 in-memoria.db 的 ai_insights 做去重与过时清理（仅处理 ai_insights 表）。

    规则：按 “insight_type + source_agent + topic_key” 分组，保留最新 created_at 的一条（并用 confidence/内容长度作为次序）。
    """

    db_path = repo_root / "in-memoria.db"
    if not db_path.exists():
        print("未找到 in-memoria.db：跳过（尚未启用 in_memoria 或未生成 DB）")
        return 0

    con = sqlite3.connect(str(db_path))
    cur = con.cursor()
    try:
        cur.execute(
            "select rowid, insight_id, insight_type, source_agent, confidence_score, created_at, insight_content from ai_insights"
        )
        rows = cur.fetchall()
    except Exception as e:
        print(f"读取 ai_insights 失败：{e}", file=sys.stderr)
        return 1
    finally:
        con.close()

    groups: dict[str, list[dict[str, object]]] = {}
    for rowid, insight_id, insight_type, agent, conf, created, content in rows:
        key = _ai_insight_topic_key(str(insight_type or ""), str(agent or ""), str(content or ""))
        groups.setdefault(key, []).append(
            {
                "rowid": int(rowid),
                "insight_id": str(insight_id or ""),
                "insight_type": str(insight_type or ""),
                "source_agent": str(agent or ""),
                "confidence_score": float(conf or 0.0),
                "created_at": str(created or ""),
                "content_len": len(str(content or "")),
            }
        )

    dup_groups = [(k, v) for k, v in groups.items() if len(v) > 1]
    to_delete: list[int] = []
    report_lines: list[str] = []

    def keep_sort_key(item: dict[str, object]) -> tuple[str, float, int]:
        created_at = str(item.get("created_at") or "")
        confidence = float(item.get("confidence_score") or 0.0)
        content_len = int(item.get("content_len") or 0)
        return (created_at, confidence, content_len)

    for key, items in sorted(dup_groups, key=lambda kv: len(kv[1]), reverse=True):
        keep = max(items, key=keep_sort_key)
        drops = [it for it in items if it["rowid"] != keep["rowid"]]
        for d in drops:
            to_delete.append(int(d["rowid"]))
        topic_hint = key.split("|")[-1]
        report_lines.append(
            f"- 主题：{topic_hint}  保留 created_at={keep.get('created_at')}  删除 {len(drops)} 条"
        )

    print(f"ai_insights：总计 {len(rows)} 条；重复组 {len(dup_groups)} 个；可删除 {len(to_delete)} 条。")
    if report_lines:
        print("去重摘要：")
        for line in report_lines[:200]:
            print(line)
        if len(report_lines) > 200:
            print(f"- ... 其余 {len(report_lines) - 200} 个重复组已省略")

    if not to_delete:
        print("无需去重：未发现重复或过时条目。")
        return 0

    if not args.apply:
        print("dry-run：未修改 DB。若确认执行，请加 `--apply`。")
        return 0

    if args.backup:
        ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        backup_dir = repo_root / ".vibe" / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        backup_path = backup_dir / f"in-memoria.db.bak-{ts}"
        try:
            import shutil

            shutil.copy2(db_path, backup_path)
            print(f"已备份：{backup_path.as_posix()}")
        except Exception as e:
            print(f"备份失败：{e}", file=sys.stderr)
            return 1

    con2 = sqlite3.connect(str(db_path))
    cur2 = con2.cursor()
    try:
        cur2.execute("begin")
        placeholders = ",".join(["?"] * len(to_delete))
        cur2.execute(f"delete from ai_insights where rowid in ({placeholders})", to_delete)
        con2.commit()
        if args.vacuum:
            cur2.execute("vacuum")
        cur2.execute("select count(*) from ai_insights")
        left = int(cur2.fetchone()[0])
    except Exception as e:
        con2.rollback()
        print(f"去重写入失败：{e}", file=sys.stderr)
        return 1
    finally:
        con2.close()

    print(f"完成：已删除 {len(to_delete)} 条，剩余 {left} 条。")
    return 0


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


def _local_rag_stdio_config(repo_root: Path) -> tuple[str, list[str], dict[str, str]]:
    npm_cache_dir = repo_root / ".vibe" / "npm-cache"
    npm_cache_dir.mkdir(parents=True, exist_ok=True)

    # 尽量对齐 codex mcp 配置（MODEL_NAME/CACHE_DIR 等），避免向量维度不一致
    env_from_codex = _try_get_codex_mcp_env("local_rag")

    env = os.environ.copy()
    env["npm_config_cache"] = str(npm_cache_dir)

    env.setdefault("BASE_DIR", env_from_codex.get("BASE_DIR", "docs"))
    env.setdefault("DB_PATH", env_from_codex.get("DB_PATH", ".vibe/local-rag/lancedb"))

    cache_dir = env_from_codex.get("CACHE_DIR", "")
    if not cache_dir.strip():
        cache_dir = str(_default_model_cache_dir())
    env.setdefault("CACHE_DIR", cache_dir)

    env.setdefault("MODEL_NAME", env_from_codex.get("MODEL_NAME", "Xenova/all-MiniLM-L6-v2"))
    env.setdefault("RAG_HYBRID_WEIGHT", env_from_codex.get("RAG_HYBRID_WEIGHT", "0.7"))
    env.setdefault("RAG_GROUPING", env_from_codex.get("RAG_GROUPING", "similar"))

    command = "cmd"
    args = ["/c", "npx", "-y", "mcp-local-rag@0.5.3"]
    return command, args, env


def _cmd_search(repo_root: Path, args: argparse.Namespace) -> int:
    return asyncio.run(_cmd_search_async(repo_root, args))


async def _cmd_search_async(repo_root: Path, args: argparse.Namespace) -> int:
    query = str(args.query or "").strip()
    if not query:
        print("缺少 query", file=sys.stderr)
        return 2

    command, cmd_args, env = _local_rag_stdio_config(repo_root)
    log_dir = repo_root / ".vibe" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    errlog_path = log_dir / f"mcp-local-rag-search-{int(time.time())}.log"
    with errlog_path.open("w", encoding="utf-8", errors="replace") as errlog:
        async with mcp_stdio_session(
            command=command,
            args=cmd_args,
            cwd=repo_root,
            env=env,
            init_timeout_sec=float(args.timeout_sec),
            show_progress=True,
            errlog=errlog,
        ) as session:
            tools_resp = await mcp_list_tools(
                session,
                timeout_sec=float(args.timeout_sec),
                show_progress=True,
                progress_label="tools/list",
            )
            tool_names = {t.name for t in tools_resp.tools}
            if "query_documents" not in tool_names:
                print(f"local_rag 不支持 query_documents，tools={sorted(tool_names)}", file=sys.stderr)
                return 1

            resp = await mcp_call_tool(
                session,
                name="query_documents",
                arguments={"query": query, "limit": int(args.limit)},
                timeout_sec=float(args.timeout_sec),
                show_progress=True,
                progress_label="query_documents",
            )
            if bool(getattr(resp, "isError", False)):
                print(f"query_documents 失败：{tool_result_text(resp)}", file=sys.stderr)
                return 1

            print("")
            text = tool_result_text(resp).strip()
            print(text if text else "[]")
            return 0


_SID_RE = re.compile(r"\bS-\d{3}\b")
_SID_HEADER_RE = re.compile(r"^###\s+(S-\d{3})\b", re.IGNORECASE)


def _load_registry_ids(registry_path: Path) -> set[str]:
    if not registry_path.exists():
        return set()
    ids: set[str] = set()
    for line in registry_path.read_text(encoding="utf-8", errors="replace").splitlines():
        m = _SID_HEADER_RE.match(line.strip())
        if m:
            ids.add(m.group(1).upper())
    return ids


def _scan_markdown_for_sids(path: Path) -> set[str]:
    text = path.read_text(encoding="utf-8", errors="replace")
    return {m.group(0).upper() for m in _SID_RE.finditer(text)}


def _cmd_lint(repo_root: Path, args: argparse.Namespace) -> int:
    """
    vbrain 轻量质量闸门：
    - 检查文档中的 S-xxx 引用是否都在 source_registry 中登记
    - 检查 docs/tools/vbrain/manifest.json 是否可解析，且 entrypoints 指向的脚本存在
    """

    warnings: list[str] = []
    errors: list[str] = []

    registry = repo_root / "docs" / "knowledge" / "source_registry.md"
    registry_ids = _load_registry_ids(registry)
    if not registry_ids:
        warnings.append("未解析到任何来源登记 S-xxx（或 source_registry.md 不存在）。")

    check_roots = [
        repo_root / "docs" / "design",
        repo_root / "docs" / "guidelines",
        repo_root / "docs" / "knowledge",
        repo_root / "docs" / "reports",
        repo_root / "docs" / "setup",
        repo_root / "docs" / "tools",
        repo_root / ".serena" / "memories",
    ]
    md_files: list[Path] = []
    for root in check_roots:
        if root.exists():
            md_files.extend([p for p in root.rglob("*.md") if p.is_file()])

    unknown_refs: dict[str, set[str]] = {}
    for p in md_files:
        if p.samefile(registry) if registry.exists() else False:
            continue
        refs = _scan_markdown_for_sids(p)
        unknown = {sid for sid in refs if sid not in registry_ids}
        if unknown:
            unknown_refs[str(p.relative_to(repo_root)).replace("\\", "/")] = unknown

    for rel, sids in sorted(unknown_refs.items()):
        warnings.append(f"{rel}: 未登记来源引用 {', '.join(sorted(sids))}")

    manifest = repo_root / "docs" / "tools" / "vbrain" / "manifest.json"
    if not manifest.exists():
        errors.append("缺少 docs/tools/vbrain/manifest.json")
    else:
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
            entrypoints = data.get("vbrain_core", {}).get("entrypoints", {})
            if isinstance(entrypoints, dict):
                required_entrypoints = [
                    "vbrain_cli",
                    "vbrain_mcp_server",
                    "ingest_project_docs",
                    "ingest_sources",
                ]
                for k in required_entrypoints:
                    if k not in entrypoints:
                        errors.append(f"manifest entrypoints 缺少必需项：{k}")

                for name, rel_path in entrypoints.items():
                    if not isinstance(rel_path, str):
                        continue
                    target = repo_root / rel_path
                    if not target.exists():
                        errors.append(f"manifest entrypoints 缺失：{name} -> {rel_path}")
        except Exception as e:
            errors.append(f"manifest.json 解析失败：{e}")

    if warnings:
        print("vbrain lint（警告）：")
        for w in warnings[:200]:
            print(f"- {w}")
        if len(warnings) > 200:
            print(f"- ... 其余 {len(warnings) - 200} 条已省略")

    if errors:
        print("")
        print("vbrain lint（错误）：")
        for e in errors[:200]:
            print(f"- {e}")
        if len(errors) > 200:
            print(f"- ... 其余 {len(errors) - 200} 条已省略")

    if errors:
        return 1
    if warnings and args.strict:
        return 1
    return 0


def _pack_file_list(profile: str) -> list[str]:
    """
    生成“婴儿 vbrain”迁移包的文件清单（相对仓库根目录）。

    说明：
    - 只打包控制平面与脚本化工作流，不包含任何缓存/DB（.vibe/、in-memoria.db 等）。
    - 新仓库落地后：按需调整 `.serena/memories/` 与 `docs/` 的索引入口即可。
    """

    minimal = [
        "docs/tools/vbrain/README.md",
        "docs/tools/vbrain/manifest.json",
        "docs/tools/vbrain/mcp_blueprint.md",
        "scripts/tools/vbrain.py",
        "scripts/tools/vbrain_mcp_server.py",
        "scripts/tools/mcp_stdio_client.py",
        "scripts/tools/local_rag_ingest_project_docs.py",
        "scripts/tools/local_rag_ingest_sources.py",
        "scripts/tools/in_memoria_seed_vibe_insights.py",
        ".serena/memories/vbrain_workflow.md",
    ]

    if profile == "minimal":
        return minimal

    if profile == "default":
        # 默认比 minimal 多带两份“入口记忆/检查清单”，方便新仓库直接跑起来
        return minimal + [
            ".serena/memories/task_completion_checklist.md",
            ".serena/memories/style_conventions.md",
        ]

    raise ValueError(f"未知 profile：{profile}")


def _cmd_pack(repo_root: Path, args: argparse.Namespace) -> int:
    files = _pack_file_list(args.profile)
    missing = [p for p in files if not (repo_root / p).exists()]
    if missing:
        print("pack 失败：缺少文件：", file=sys.stderr)
        for p in missing:
            print(f"- {p}", file=sys.stderr)
        return 1

    print("vbrain pack 文件清单：")
    for p in files:
        print(f"- {p}")

    zip_path = str(args.zip_path or "").strip()
    if not zip_path:
        return 0

    out = Path(zip_path).expanduser()
    if out.is_dir():
        out = out / f"vbrain_pack_{args.profile}.zip"
    if out.exists() and not args.overwrite:
        print(f"已存在：{out.as_posix()}（如需覆盖请加 --overwrite）", file=sys.stderr)
        return 2

    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for rel in files:
            abs_path = repo_root / rel
            zf.write(abs_path, arcname=rel.replace("\\", "/"))

    print("")
    print(f"已生成：{out.as_posix()}")
    return 0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="vbrain 统一入口（闭环编排 CLI）")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("status", help="显示 vbrain 关键路径与状态（粗粒度）")

    p_doctor = sub.add_parser("doctor", help="vbrain 体检（优先运行 scripts/mcp/doctor.ps1）")
    p_doctor.add_argument("--target", default="codex", choices=["codex", "claude", "both"], help="体检目标（默认 codex）")
    p_doctor.add_argument("--deep", action="store_true", help="深度检查（建议）")
    p_doctor.add_argument("--show-config", action="store_true", help="打印 MCP 配置 JSON（排查用）")

    sub.add_parser("seed-insights", help="写入 vbrain 的种子记忆（In-Memoria contribute_insights）")

    p_preheat = sub.add_parser("preheat", help="预热索引：docs +（可选）feed")
    p_preheat.add_argument("--rebuild-docs", action="store_true", help="重建 docs 的 Local RAG 索引")
    p_preheat.add_argument("--docs-limit", type=int, default=0, help="仅 ingest 前 N 个 docs 文件（0 表示不限制）")
    p_preheat.add_argument("--skip-sources", action="store_true", help="跳过 feed 索引（.vibe/knowledge/sources）")
    p_preheat.add_argument(
        "--only-new-sources",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="仅 ingest 新增/更新过的 feed 条目（默认 true，推荐）",
    )
    p_preheat.add_argument("--sources-limit", type=int, default=0, help="仅 ingest 前 N 个 feed 条目（0 表示不限制）")
    p_preheat.add_argument("--no-progress", action="store_true", help="禁用进度条输出（默认启用）")

    p_docs = sub.add_parser("ingest-docs", help="透传调用 local_rag_ingest_project_docs.py")
    p_docs.add_argument("args", nargs=argparse.REMAINDER, help="透传参数（推荐用 -- 分隔）")

    p_sources = sub.add_parser("ingest-sources", help="透传调用 local_rag_ingest_sources.py")
    p_sources.add_argument("args", nargs=argparse.REMAINDER, help="透传参数（推荐用 -- 分隔）")

    p_research = sub.add_parser("ingest-research", help="索引 remp_research/research（研究资料）到 Local RAG")
    p_research.add_argument("args", nargs=argparse.REMAINDER, help="透传参数（推荐用 -- 分隔）")

    p_eval = sub.add_parser("eval-embeddings", help="评估 Local RAG 嵌入模型（回归集 + hit@k/MRR）")
    p_eval.add_argument("args", nargs=argparse.REMAINDER, help="透传参数（推荐用 -- 分隔）")

    p_search = sub.add_parser("search", help="查询 Local RAG（vbrain 召回验收）")
    p_search.add_argument("query", help="查询语句")
    p_search.add_argument("--limit", type=int, default=5, help="返回结果条数（默认 5）")
    p_search.add_argument("--timeout-sec", type=int, default=60, help="MCP 调用超时秒数（默认 60）")

    p_dedupe = sub.add_parser("dedupe-insights", help="去重/清理 in-memoria.db 的 ai_insights（默认 dry-run）")
    p_dedupe.add_argument("--apply", action="store_true", help="实际执行删除（默认仅预览）")
    p_dedupe.add_argument(
        "--backup",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="执行前备份 DB 到 .vibe/backups（默认 true）",
    )
    p_dedupe.add_argument("--vacuum", action="store_true", help="执行后 vacuum 压缩 DB（默认关闭）")

    p_lint = sub.add_parser("lint", help="vbrain 轻量质量闸门（S-xxx 引用/manifest 校验）")
    p_lint.add_argument("--strict", action="store_true", help="将警告也视为失败（返回非 0）")

    p_pack = sub.add_parser("pack", help="生成“婴儿 vbrain”迁移包（可选输出 zip）")
    p_pack.add_argument("--profile", default="default", choices=["default", "minimal"], help="打包内容档位（默认 default）")
    p_pack.add_argument("--zip-path", default="", help="输出 zip 路径；可传目录（将自动命名）。不传则仅打印清单。")
    p_pack.add_argument("--overwrite", action="store_true", help="覆盖已存在的 zip")

    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    repo_root = _repo_root()

    if args.cmd == "status":
        return _cmd_status(repo_root)
    if args.cmd == "doctor":
        return _cmd_doctor(repo_root, args)
    if args.cmd == "seed-insights":
        return _cmd_seed_insights(repo_root, args)
    if args.cmd == "preheat":
        return _cmd_preheat(repo_root, args)
    if args.cmd == "search":
        return _cmd_search(repo_root, args)
    if args.cmd == "dedupe-insights":
        return _cmd_dedupe_insights(repo_root, args)
    if args.cmd == "lint":
        return _cmd_lint(repo_root, args)
    if args.cmd == "pack":
        return _cmd_pack(repo_root, args)
    if args.cmd == "ingest-docs":
        return _run_python(
            repo_root,
            "scripts/tools/local_rag_ingest_project_docs.py",
            _strip_passthrough(list(args.args)),
        )
    if args.cmd == "ingest-research":
        extra = ["--base-dir", "remp_research/research"] + _strip_passthrough(list(args.args))
        return _run_python(
            repo_root,
            "scripts/tools/local_rag_ingest_project_docs.py",
            extra,
        )
    if args.cmd == "ingest-sources":
        return _run_python(
            repo_root,
            "scripts/tools/local_rag_ingest_sources.py",
            _strip_passthrough(list(args.args)),
        )
    if args.cmd == "eval-embeddings":
        return _run_python(
            repo_root,
            "scripts/tools/local_rag_eval_models.py",
            _strip_passthrough(list(args.args)),
        )

    print(f"未知命令：{args.cmd}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
