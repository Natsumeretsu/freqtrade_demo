"""
vbrain MCP Server（婴儿版）

目标：
- 把仓库内的 vbrain 高层动作（status / preheat / ingest / search / seed 等）以 MCP 工具形式暴露给客户端
- 复用已验证的脚本化流程（scripts/tools/vbrain.py），而不是在 MCP 层重复实现细节

设计约束：
- 仅使用 Python 标准库，便于复制到其它仓库作为“婴儿 vbrain”
- MCP 通讯采用“每行一个 JSON（JSON-RPC 2.0）”的 stdio 协议（与本仓库脚本一致）
- 服务器自身不输出非 JSON 到 stdout（日志仅写 stderr）
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class _Tool:
    name: str
    description: str
    input_schema: dict[str, Any]


def _send(obj: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def _repo_root() -> Path:
    env_root = os.environ.get("VBRAIN_REPO_ROOT", "").strip()
    if env_root:
        return Path(env_root).expanduser().resolve()
    # 默认按仓库内脚本布局推断：scripts/tools/ -> repo_root
    return Path(__file__).resolve().parents[2]


def _run_vbrain_cli(repo_root: Path, args: list[str], timeout_sec: int | None) -> tuple[int, str]:
    script = (repo_root / "scripts" / "tools" / "vbrain.py").resolve()
    if not script.exists():
        return 2, f"未找到 vbrain 入口脚本：{script}"

    env = os.environ.copy()
    env.setdefault("PYTHONUTF8", "1")
    env.setdefault("PYTHONIOENCODING", "utf-8")
    env.setdefault("PYTHONUNBUFFERED", "1")

    cmd = [sys.executable, "-X", "utf8", str(script)] + args
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(repo_root),
            env=env,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout_sec,
        )
        return int(proc.returncode or 0), (proc.stdout or "")
    except subprocess.TimeoutExpired:
        return 124, f"执行超时（{timeout_sec}s）：{' '.join(args)}"
    except Exception as e:
        return 1, f"执行失败：{e}"


def _truncate_text(text: str, limit: int = 20000) -> str:
    t = (text or "").strip()
    if len(t) <= limit:
        return t
    return t[:limit] + "\n\n（已截断，输出过长）"


def _tools() -> list[_Tool]:
    empty_schema: dict[str, Any] = {"type": "object", "additionalProperties": False}

    return [
        _Tool(
            name="vbrain.status",
            description="查看 vbrain 粗粒度状态（in-memoria / local-rag / sources / 文档等）",
            input_schema=empty_schema,
        ),
        _Tool(
            name="vbrain.doctor",
            description="运行 MCP/环境体检（优先复用 scripts/mcp/doctor.ps1）",
            input_schema={
                "type": "object",
                "additionalProperties": False,
                "properties": {"target": {"type": "string", "description": "体检目标：codex/claude/auto"}},
            },
        ),
        _Tool(
            name="vbrain.preheat",
            description="预热 vbrain：索引 docs（可选重建）+ 可选索引 sources（增量推荐）",
            input_schema={
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "rebuild_docs": {"type": "boolean", "default": False},
                    "docs_limit": {"type": "integer", "default": 0, "minimum": 0},
                    "skip_sources": {"type": "boolean", "default": False},
                    "only_new_sources": {"type": "boolean", "default": True},
                    "sources_limit": {"type": "integer", "default": 0, "minimum": 0},
                    "no_progress": {"type": "boolean", "default": False},
                    "timeout_sec": {"type": "integer", "default": 3600, "minimum": 1},
                },
            },
        ),
        _Tool(
            name="vbrain.ingest_project_docs",
            description="单独索引 docs（local-rag ingest）",
            input_schema={
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "rebuild": {"type": "boolean", "default": False},
                    "pattern": {"type": "string", "default": ""},
                    "limit": {"type": "integer", "default": 0, "minimum": 0},
                    "timeout_sec": {"type": "integer", "default": 3600, "minimum": 1},
                },
            },
        ),
        _Tool(
            name="vbrain.ingest_sources",
            description="单独索引外部材料缓存（.vibe/knowledge/sources → local-rag）",
            input_schema={
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "only_new": {"type": "boolean", "default": True},
                    "ids": {"type": "string", "default": ""},
                    "limit": {"type": "integer", "default": 0, "minimum": 0},
                    "timeout_sec": {"type": "integer", "default": 3600, "minimum": 1},
                },
            },
        ),
        _Tool(
            name="vbrain.eval_embeddings",
            description="评估 local-rag 嵌入模型（回归集 + hit@k/MRR；默认使用评估用 profile DB，不破坏主 DB）",
            input_schema={
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "models": {"type": "string", "default": "", "description": "逗号分隔模型列表（空则用默认对比集）"},
                    "build": {
                        "type": "string",
                        "default": "missing",
                        "enum": ["none", "missing", "update", "rebuild"],
                        "description": "是否构建索引：none/missing/rebuild",
                    },
                    "k": {"type": "integer", "default": 0, "minimum": 0, "description": "TopK（0 表示使用回归集默认）"},
                    "cases": {"type": "string", "default": "", "description": "回归集 JSON 路径（空则用仓库默认）"},
                    "query_timeout_sec": {
                        "type": "integer",
                        "default": 90,
                        "minimum": 1,
                        "description": "单次 query 超时秒数（默认 90）",
                    },
                    "timeout_sec": {
                        "type": "integer",
                        "default": 3600,
                        "minimum": 1,
                        "description": "整体子进程超时秒数（默认 3600；模型下载/索引可能较慢）",
                    },
                },
            },
        ),
        _Tool(
            name="vbrain.search",
            description="查询 local-rag（外部全文与 docs 的语义召回）",
            input_schema={
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "query": {"type": "string"},
                    "limit": {"type": "integer", "default": 5, "minimum": 1},
                    "timeout_sec": {"type": "integer", "default": 60, "minimum": 1},
                },
                "required": ["query"],
            },
        ),
        _Tool(
            name="vbrain.seed_insights",
            description="向 in-memoria 回灌可复用的套路/决策（种子包）",
            input_schema={
                "type": "object",
                "additionalProperties": False,
                "properties": {"timeout_sec": {"type": "integer", "default": 600, "minimum": 1}},
            },
        ),
        _Tool(
            name="vbrain.lint",
            description="vbrain 轻量质量闸门（manifest / S-xxx 引用 / 基本一致性）",
            input_schema={
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "strict": {"type": "boolean", "default": False},
                    "timeout_sec": {"type": "integer", "default": 120, "minimum": 1},
                },
            },
        ),
        _Tool(
            name="vbrain.dedupe_insights",
            description="去重/清理 in-memoria.db 的 ai_insights（默认 dry-run）",
            input_schema={
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "apply": {"type": "boolean", "default": False},
                    "backup": {"type": "boolean", "default": True},
                    "vacuum": {"type": "boolean", "default": False},
                    "timeout_sec": {"type": "integer", "default": 120, "minimum": 1},
                },
            },
        ),
        _Tool(
            name="vbrain.pack",
            description="打包“婴儿 vbrain”迁移包（用于复制到其它仓库）",
            input_schema={
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "profile": {"type": "string", "default": "default", "enum": ["default", "minimal"]},
                    "zip_path": {"type": "string", "default": ""},
                    "overwrite": {"type": "boolean", "default": False},
                    "timeout_sec": {"type": "integer", "default": 300, "minimum": 1},
                },
            },
        ),
    ]


def _tool_list_result() -> dict[str, Any]:
    return {
        "tools": [
            {
                "name": t.name,
                "description": t.description,
                "inputSchema": t.input_schema,
            }
            for t in _tools()
        ]
    }


def _as_bool(v: Any, default: bool = False) -> bool:
    if isinstance(v, bool):
        return v
    return default


def _as_int(v: Any, default: int) -> int:
    try:
        if v is None:
            return default
        return int(v)
    except Exception:
        return default


def _as_str(v: Any, default: str = "") -> str:
    if isinstance(v, str):
        return v
    return default


def _call_tool(repo_root: Path, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    # 统一通过 vbrain CLI 复用逻辑（并把 stdout/stderr 摘要化返回）
    timeout_sec = _as_int(arguments.get("timeout_sec"), default=600)

    if name == "vbrain.status":
        code, out = _run_vbrain_cli(repo_root, ["status"], timeout_sec)
        return _tool_text_result(code=code, text=out)

    if name == "vbrain.doctor":
        target = _as_str(arguments.get("target", ""), default="").strip()
        args = ["doctor"]
        if target:
            args += ["--target", target]
        code, out = _run_vbrain_cli(repo_root, args, timeout_sec)
        return _tool_text_result(code=code, text=out)

    if name == "vbrain.preheat":
        args = ["preheat"]
        if _as_bool(arguments.get("rebuild_docs"), False):
            args.append("--rebuild-docs")
        docs_limit = _as_int(arguments.get("docs_limit"), 0)
        if docs_limit > 0:
            args += ["--docs-limit", str(docs_limit)]
        if _as_bool(arguments.get("skip_sources"), False):
            args.append("--skip-sources")
        only_new_sources = _as_bool(arguments.get("only_new_sources"), True)
        args.append("--only-new-sources" if only_new_sources else "--no-only-new-sources")
        sources_limit = _as_int(arguments.get("sources_limit"), 0)
        if sources_limit > 0:
            args += ["--sources-limit", str(sources_limit)]
        if _as_bool(arguments.get("no_progress"), False):
            args.append("--no-progress")
        code, out = _run_vbrain_cli(repo_root, args, timeout_sec)
        return _tool_text_result(code=code, text=out)

    if name == "vbrain.ingest_project_docs":
        args = ["ingest-docs", "--"]
        if _as_bool(arguments.get("rebuild"), False):
            args.append("--rebuild")
        pattern = _as_str(arguments.get("pattern", ""), default="").strip()
        if pattern:
            args += ["--pattern", pattern]
        limit = _as_int(arguments.get("limit"), 0)
        if limit > 0:
            args += ["--limit", str(limit)]
        code, out = _run_vbrain_cli(repo_root, args, timeout_sec)
        return _tool_text_result(code=code, text=out)

    if name == "vbrain.ingest_sources":
        args = ["ingest-sources", "--"]
        if _as_bool(arguments.get("only_new"), True):
            args.append("--only-new")
        ids = _as_str(arguments.get("ids", ""), default="").strip()
        if ids:
            args += ["--ids", ids]
        limit = _as_int(arguments.get("limit"), 0)
        if limit > 0:
            args += ["--limit", str(limit)]
        code, out = _run_vbrain_cli(repo_root, args, timeout_sec)
        return _tool_text_result(code=code, text=out)

    if name == "vbrain.eval_embeddings":
        args = ["eval-embeddings", "--"]
        models = _as_str(arguments.get("models", ""), default="").strip()
        if models:
            args += ["--models", models]
        build = _as_str(arguments.get("build", ""), default="missing").strip() or "missing"
        if build not in {"none", "missing", "update", "rebuild"}:
            return _tool_text_result(code=2, text="参数错误：build 必须是 none/missing/update/rebuild")
        args += ["--build", build]
        k = _as_int(arguments.get("k"), 0)
        if k > 0:
            args += ["--k", str(k)]
        cases = _as_str(arguments.get("cases", ""), default="").strip()
        if cases:
            args += ["--cases", cases]
        q_to = _as_int(arguments.get("query_timeout_sec"), 90)
        if q_to > 0:
            args += ["--query-timeout-sec", str(q_to)]
        code, out = _run_vbrain_cli(repo_root, args, timeout_sec)
        return _tool_text_result(code=code, text=out)

    if name == "vbrain.search":
        query = _as_str(arguments.get("query", ""), default="").strip()
        if not query:
            return _tool_text_result(code=2, text="参数错误：query 不能为空")
        limit = max(1, _as_int(arguments.get("limit"), 5))
        # vbrain.py 的 search 自己会使用 MCP timeout；这里的 timeout_sec 用于整个子进程超时
        mcp_timeout = max(1, _as_int(arguments.get("timeout_sec"), 60))
        args = ["search", query, "--limit", str(limit), "--timeout-sec", str(mcp_timeout)]
        code, out = _run_vbrain_cli(repo_root, args, timeout_sec)
        return _tool_text_result(code=code, text=out)

    if name == "vbrain.seed_insights":
        code, out = _run_vbrain_cli(repo_root, ["seed-insights"], timeout_sec)
        return _tool_text_result(code=code, text=out)

    if name == "vbrain.lint":
        args = ["lint"]
        if _as_bool(arguments.get("strict"), False):
            args.append("--strict")
        code, out = _run_vbrain_cli(repo_root, args, timeout_sec)
        return _tool_text_result(code=code, text=out)

    if name == "vbrain.dedupe_insights":
        args = ["dedupe-insights"]
        if _as_bool(arguments.get("apply"), False):
            args.append("--apply")
        if not _as_bool(arguments.get("backup"), True):
            args.append("--no-backup")
        if _as_bool(arguments.get("vacuum"), False):
            args.append("--vacuum")
        code, out = _run_vbrain_cli(repo_root, args, timeout_sec)
        return _tool_text_result(code=code, text=out)

    if name == "vbrain.pack":
        profile = _as_str(arguments.get("profile", ""), default="default").strip() or "default"
        zip_path = _as_str(arguments.get("zip_path", ""), default="").strip()
        overwrite = _as_bool(arguments.get("overwrite"), False)
        args = ["pack", "--profile", profile]
        if zip_path:
            args += ["--zip-path", zip_path]
        if overwrite:
            args.append("--overwrite")
        code, out = _run_vbrain_cli(repo_root, args, timeout_sec)
        return _tool_text_result(code=code, text=out)

    return _tool_text_result(code=2, text=f"未知工具：{name}")


def _tool_text_result(*, code: int, text: str) -> dict[str, Any]:
    is_error = code != 0
    summary = _truncate_text(text)
    if not summary:
        summary = "(无输出)"
    return {"content": [{"type": "text", "text": summary}], "isError": is_error}


def _handle_request(msg: dict[str, Any]) -> dict[str, Any] | None:
    method = msg.get("method")
    if not isinstance(method, str) or not method.strip():
        return None

    # 通知类消息：不响应
    if "id" not in msg:
        return None

    req_id = msg.get("id")
    params = msg.get("params", {})
    if not isinstance(params, dict):
        params = {}

    if method == "initialize":
        pv = params.get("protocolVersion")
        protocol_version = pv if isinstance(pv, str) and pv.strip() else "2024-11-05"
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": protocol_version,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "vbrain", "version": "0.1.2"},
            },
        }

    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": req_id, "result": _tool_list_result()}

    if method == "tools/call":
        name = params.get("name")
        arguments = params.get("arguments", {})
        if not isinstance(name, str) or not name.strip():
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": _tool_text_result(code=2, text="参数错误：tools/call.name 不能为空"),
            }
        if not isinstance(arguments, dict):
            arguments = {}
        repo_root = _repo_root()
        try:
            result = _call_tool(repo_root, name.strip(), arguments)
        except Exception as e:
            result = _tool_text_result(code=1, text=f"工具执行异常：{e}")
        return {"jsonrpc": "2.0", "id": req_id, "result": result}

    # 兼容：返回空列表，避免客户端报错
    if method in ("prompts/list", "resources/list"):
        return {"jsonrpc": "2.0", "id": req_id, "result": {method.split('/')[0]: []}}

    return {"jsonrpc": "2.0", "id": req_id, "result": {}}


def main() -> int:
    # 仅 stderr 输出日志（避免污染 MCP stdout 协议）
    sys.stderr.write("vbrain MCP server started (stdio, json-per-line)\n")
    sys.stderr.flush()

    for line in sys.stdin:
        s = (line or "").strip()
        if not s:
            continue
        try:
            msg = json.loads(s)
        except Exception:
            continue
        if not isinstance(msg, dict):
            continue
        resp = _handle_request(msg)
        if resp is not None:
            _send(resp)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
