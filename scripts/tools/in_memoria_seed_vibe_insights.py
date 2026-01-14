"""
为本仓库的 In-Memoria 主脑写入一组“vibe coding 工作流”关键 insights。

目的：
- 让 In-Memoria 在未来跨会话时，优先记住本仓库的工作流/约定/坑点
- 这些内容偏“最佳实践/坑点修复”，而不是具体策略参数（策略参数仍以 docs 为权威）

用法（在仓库根目录运行）：
  python -X utf8 scripts/tools/in_memoria_seed_vibe_insights.py

可选：
  python -X utf8 scripts/tools/in_memoria_seed_vibe_insights.py --force
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
from pathlib import Path
from typing import Any

from mcp_stdio_client import mcp_call_tool, mcp_stdio_session, tool_result_text


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="为本仓库 In-Memoria 写入 vbrain 种子 insights（默认幂等）")
    parser.add_argument("--force", action="store_true", help="即使已存在也重复写入（不推荐）")
    return parser.parse_args()


def _extract_topic_prefix(text: str) -> str:
    t = (text or "").strip()
    if not t:
        return ""

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


def _load_existing_ai_insight_keys(db_path: Path) -> set[str]:
    if not db_path.exists():
        return set()
    con = sqlite3.connect(str(db_path))
    cur = con.cursor()
    try:
        cur.execute("select insight_type, source_agent, insight_content from ai_insights")
        rows = cur.fetchall()
    except Exception:
        return set()
    finally:
        con.close()

    keys: set[str] = set()
    for itype, agent, content in rows:
        keys.add(_ai_insight_topic_key(str(itype or ""), str(agent or ""), str(content or "")))
    return keys


def _in_memoria_stdio_config(repo_root: Path) -> tuple[str, list[str], dict[str, str]]:
    vibe_dir = repo_root / ".vibe"
    npm_cache_dir = vibe_dir / "npm-cache"
    npm_cache_dir.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env["npm_config_cache"] = str(npm_cache_dir)

    command = "cmd"
    args = ["/c", "npx", "-y", "in-memoria@0.6.0", "server"]
    return command, args, env


async def _amain() -> int:
    args = _parse_args()
    repo_root = _repo_root()

    # 先做幂等判断：避免跨设备/重复运行产生“记忆重复”
    db_path = repo_root / "in-memoria.db"
    existing_keys = set() if args.force else _load_existing_ai_insight_keys(db_path)

    all_insights: list[dict[str, Any]] = [
        {
            "type": "best_practice",
            "content": {
                "practice": "vibe coding 采用职责分离：In-Memoria 负责跨会话记忆/代码画像；Local RAG 只负责 docs 等资料语义召回；Serena 只负责符号级代码检索与固化流程/约定。",
                "reasoning": "把“可进化大脑”和“资料召回”交给专业 MCP，避免 Serena 记忆膨胀与检索噪声，提高跨会话一致性与检索命中率。",
                "files": [
                    "docs/setup/vibe_brain_workflow.md",
                    "docs/knowledge/source_registry.md",
                    ".serena/memories/freqai_index.md",
                ],
            },
            "confidence": 0.9,
            "sourceAgent": "codex",
        },
        {
            "type": "best_practice",
            "content": {
                "practice": "Local RAG 默认只索引 docs；向量库 `.vibe/local-rag/lancedb` 作为可重建缓存（默认 gitignore 忽略），跨设备用 `python -X utf8 scripts/tools/vbrain.py preheat --rebuild-docs --skip-sources` 预热重建即可；模型缓存 `CACHE_DIR` 设为设备级目录（默认 `$CODEX_HOME/cache/local-rag/models` 或 `~/.codex/cache/local-rag/models`），并可用 `MODEL_NAME` 切换嵌入模型（切换需重建 DB）。",
                "reasoning": "docs 是“结论落盘层”，索引面更干净；默认不提交向量库可以显著减轻 Git 同步负担（大量小文件），同时避免把第三方正文片段同步进仓库历史；把模型缓存上移到设备级能减少多仓库重复下载。",
                "mcpServer": "local_rag",
                "env": {
                    "BASE_DIR": "docs",
                    "DB_PATH": ".vibe/local-rag/lancedb",
                    "CACHE_DIR": "$CODEX_HOME/cache/local-rag/models",
                    "MODEL_NAME": "Xenova/all-MiniLM-L6-v2",
                },
            },
            "confidence": 0.85,
            "sourceAgent": "codex",
        },
        {
            "type": "bug_pattern",
            "content": {
                "bugPattern": "Windows 上 npx 可能出现 npm cache 损坏（ENOENT: package.json），导致 MCP server 无法启动。",
                "fix": "为所有 npx 相关 MCP 固化 npm_config_cache 到仓库级 .vibe/npm-cache，并通过 scripts/mcp/setup_codex.ps1 -Force 重建配置。",
                "files": ["scripts/lib/common.ps1", "scripts/mcp/setup_codex.ps1"],
            },
            "confidence": 0.8,
            "sourceAgent": "codex",
        },
        {
            "type": "best_practice",
            "content": {
                "practice": "Chrome 缺失时用 Playwright Chromium 做无管理员修复，恢复 playwright/chrome_devtools 抓取能力。",
                "reasoning": "被 403/robot/js-required 拦截的站点需要浏览器工具；企业策略/权限受限环境下，用用户级路径放置 chrome.exe 更可控。",
                "command": "./scripts/tools/fix_chrome_for_mcp.ps1",
                "files": [
                    "scripts/tools/fix_chrome_for_mcp.ps1",
                    "docs/setup/codex_mcp_sync.md",
                ],
            },
            "confidence": 0.8,
            "sourceAgent": "codex",
        },
    ]

    pending: list[dict[str, Any]] = []
    skipped = 0
    for ins in all_insights:
        itype = str(ins.get("type") or "")
        agent = str(ins.get("sourceAgent") or "")
        content_json = json.dumps(ins.get("content") or {}, ensure_ascii=False)
        k = _ai_insight_topic_key(itype, agent, content_json)
        if (not args.force) and k in existing_keys:
            skipped += 1
            continue
        pending.append(ins)

    if not pending:
        print(f"无需写入：已存在 {skipped}/{len(all_insights)}（如需强制写入请加 --force）")
        return 0

    command, cmd_args, env = _in_memoria_stdio_config(repo_root)

    log_dir = repo_root / ".vibe" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    errlog_path = log_dir / f"mcp-in-memoria-{int(time.time())}.log"
    with errlog_path.open("w", encoding="utf-8", errors="replace") as errlog:
        try:
            async with mcp_stdio_session(
                command=command,
                args=cmd_args,
                cwd=repo_root,
                env=env,
                init_timeout_sec=20,
                show_progress=True,
                errlog=errlog,
            ) as session:
                ok = 0
                for idx, insight in enumerate(pending, start=1):
                    result = await mcp_call_tool(
                        session,
                        name="contribute_insights",
                        arguments=insight,
                        timeout_sec=30,
                        show_progress=True,
                        progress_label=f"contribute_insights {idx}/{len(pending)}",
                    )
                    if bool(getattr(result, "isError", False)):
                        print(f"写入失败：{tool_result_text(result)}", file=sys.stderr)
                        continue
                    ok += 1
                print("")

                print(f"完成：写入 insights {ok}/{len(pending)}（跳过已存在 {skipped}/{len(all_insights)}）")
                if ok != len(pending):
                    print(f"MCP stderr 日志：{errlog_path}", file=sys.stderr)
                return 0 if ok == len(pending) else 1
        except Exception as exc:
            print(f"运行失败：{exc}", file=sys.stderr)
            print(f"MCP stderr 日志：{errlog_path}", file=sys.stderr)
            return 1


def main() -> int:
    return asyncio.run(_amain())


if __name__ == "__main__":
    raise SystemExit(main())
