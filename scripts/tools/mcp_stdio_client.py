"""
基于官方 MCP Python SDK 的 stdio 客户端封装。

目标：
- 统一处理：启动子进程、initialize 握手、超时、简易进度输出
- 避免在各脚本里重复实现 JSON-RPC 2.0/Windows pipe 超时读取等协议细节
"""

from __future__ import annotations

import asyncio
import json
import shutil
import sys
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncIterator, Awaitable, Mapping, Sequence, TextIO, TypeVar

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

_T = TypeVar("_T")


class McpTimeoutError(TimeoutError):
    pass


def print_progress(line: str) -> None:
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


async def _await_with_progress(
    awaitable: Awaitable[_T],
    *,
    timeout_sec: float,
    label: str,
    show_progress: bool,
) -> _T:
    """
    为 awaitable 加一个“整体超时 + 简易进度条”。

    说明：
    - 这里不重造 MCP 协议轮子，只是在等待时给用户可见反馈
    - 超时后会取消任务并抛出 McpTimeoutError
    """
    if timeout_sec <= 0:
        raise ValueError("timeout_sec 必须为正数")

    task = asyncio.create_task(awaitable)
    deadline = time.monotonic() + timeout_sec
    spinner = "|/-\\"
    spin_idx = 0
    last_draw = 0.0

    try:
        while True:
            now = time.monotonic()
            remaining = max(0.0, deadline - now)
            step = min(0.5, remaining)

            done, _ = await asyncio.wait({task}, timeout=step)
            if task in done:
                if show_progress:
                    print_progress("")
                return task.result()

            if remaining <= 0:
                if show_progress:
                    print_progress("")
                raise McpTimeoutError(f"MCP 调用超时（{timeout_sec:.0f}s）：{label}")

            if show_progress and now - last_draw >= 0.5:
                elapsed = timeout_sec - remaining
                ch = spinner[spin_idx % len(spinner)]
                spin_idx += 1
                last_draw = now
                print_progress(f"{ch} {label}  已等待 {elapsed:.0f}s / {timeout_sec:.0f}s")
    finally:
        if task.cancelled():
            return
        if not task.done():
            task.cancel()
            try:
                await task
            except Exception:
                pass


def tool_result_to_obj(result: Any) -> object:
    """
    将 MCP Tool 调用返回值转换为“便于处理/序列化”的 Python 对象。

    约定：
    - 优先使用 pydantic 的 model_dump()
    - 否则原样返回（可能是 list/dict/str）
    """
    try:
        dump = result.model_dump()  # type: ignore[attr-defined]
        return dump
    except Exception:
        return result


def tool_result_text(result: Any) -> str:
    """
    尽量从 MCP Tool 调用结果里提取可读文本（用于错误信息/日志）。
    """
    obj = tool_result_to_obj(result)
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


@asynccontextmanager
async def mcp_stdio_session(
    *,
    command: str,
    args: Sequence[str],
    cwd: str | Path | None = None,
    env: Mapping[str, str] | None = None,
    init_timeout_sec: float = 60,
    show_progress: bool = True,
    errlog: TextIO | None = None,
    encoding: str = "utf-8",
    encoding_error_handler: str = "strict",
) -> AsyncIterator[ClientSession]:
    """
    启动 stdio MCP 服务并返回已 initialize 的 ClientSession。
    """
    server_params = StdioServerParameters(
        command=str(command),
        args=[str(a) for a in args],
        env={str(k): str(v) for k, v in (env or {}).items()} or None,
        cwd=str(cwd) if cwd else None,
        encoding=str(encoding),
        encoding_error_handler=str(encoding_error_handler),
    )

    async with stdio_client(server_params, errlog=errlog or sys.stderr) as (read, write):
        async with ClientSession(read, write) as session:
            await _await_with_progress(
                session.initialize(),
                timeout_sec=init_timeout_sec,
                label="initialize",
                show_progress=show_progress,
            )
            yield session


async def mcp_list_tools(
    session: ClientSession,
    *,
    timeout_sec: float,
    show_progress: bool,
    progress_label: str = "tools/list",
) -> Any:
    return await _await_with_progress(
        session.list_tools(),
        timeout_sec=timeout_sec,
        label=str(progress_label or "tools/list"),
        show_progress=show_progress,
    )


async def mcp_call_tool(
    session: ClientSession,
    *,
    name: str,
    arguments: Mapping[str, Any] | None = None,
    timeout_sec: float,
    show_progress: bool,
    progress_label: str | None = None,
) -> Any:
    label = str(progress_label) if progress_label else f"tools/call {name}"
    return await _await_with_progress(
        session.call_tool(name, arguments=arguments or {}),
        timeout_sec=timeout_sec,
        label=label,
        show_progress=show_progress,
    )
