"""Streamable HTTP MCP 客户端（同步封装，供 Agent / Ops 调用）。"""

from __future__ import annotations

import asyncio
import json
import threading
from dataclasses import dataclass
from typing import Any

from app.core.settings import Settings, get_settings

MAX_RESULT_CHARS = 6000


class McpClientError(Exception):
    """MCP 客户端可展示错误。"""


@dataclass(frozen=True)
class McpToolInfo:
    name: str
    description: str
    input_schema: dict[str, Any]


_NETWORK_ERROR_NAMES = frozenset(
    {"ConnectError", "ConnectTimeout", "ReadTimeout", "WriteTimeout", "TimeoutException"}
)
_STREAM_ERROR_NAMES = frozenset({"BrokenResourceError", "ClosedResourceError"})

_mcp_import_lock = threading.Lock()
_mcp_sdk: tuple[Any, Any, Any] | None = None

_loop: asyncio.AbstractEventLoop | None = None
_loop_thread: threading.Thread | None = None
_loop_ready = threading.Event()
_loop_lock = threading.Lock()
_mcp_call_lock = threading.Lock()


def _iter_exceptions(exc: BaseException) -> Any:
    yield exc
    nested = getattr(exc, "exceptions", None)
    if nested:
        for sub in nested:
            yield from _iter_exceptions(sub)
    cause = exc.__cause__
    if cause is not None and cause is not exc:
        yield from _iter_exceptions(cause)
    context = exc.__context__
    if context is not None and context is not exc and context is not cause:
        yield from _iter_exceptions(context)


def _friendly_client_error(exc: BaseException) -> str:
    network_hit = False
    stream_hit = False
    root = exc
    for item in _iter_exceptions(exc):
        root = item
        if isinstance(item, McpClientError):
            return str(item)
        type_name = type(item).__name__
        if type_name in _NETWORK_ERROR_NAMES:
            network_hit = True
        if type_name in _STREAM_ERROR_NAMES:
            stream_hit = True
    if network_hit:
        return "无法连接 MCP 服务（网络或 TLS 失败），请检查 MCP_URL / MCP_API_KEY"
    if stream_hit:
        return "MCP 连接已中断（远端未响应或 TLS 握手失败）"
    message = str(root).strip()
    if message:
        return message[:240]
    return type(root).__name__


def _load_mcp_sdk() -> tuple[Any, Any, Any]:
    global _mcp_sdk
    if _mcp_sdk is not None:
        return _mcp_sdk
    with _mcp_import_lock:
        if _mcp_sdk is not None:
            return _mcp_sdk
        try:
            import anyio  # noqa: F401
            from mcp import ClientSession
            from mcp.client.streamable_http import create_mcp_http_client, streamable_http_client
        except ImportError as ex:
            raise McpClientError("未安装 mcp 包，请在 backend 执行：uv add mcp") from ex
        except KeyError as ex:
            raise McpClientError("mcp/anyio 导入失败，请强制重装 anyio 与 mcp") from ex
        _mcp_sdk = (streamable_http_client, create_mcp_http_client, ClientSession)
        return _mcp_sdk


def _loop_runner() -> None:
    global _loop
    _loop = asyncio.new_event_loop()
    asyncio.set_event_loop(_loop)
    _loop_ready.set()
    _loop.run_forever()


def _ensure_event_loop() -> asyncio.AbstractEventLoop:
    global _loop_thread
    with _loop_lock:
        if _loop is not None and _loop.is_running():
            return _loop
        _loop_ready.clear()
        _loop_thread = threading.Thread(target=_loop_runner, name="mcp-async-loop", daemon=True)
        _loop_thread.start()
    if not _loop_ready.wait(timeout=10):
        raise McpClientError("MCP 异步事件循环启动超时")
    assert _loop is not None
    return _loop


def _run_async(coro: Any) -> Any:
    with _mcp_call_lock:
        loop = _ensure_event_loop()
        future = asyncio.run_coroutine_threadsafe(coro, loop)
        try:
            return future.result()
        except Exception as ex:
            raise McpClientError(_friendly_client_error(ex)) from ex


def _is_retriable_network_error(exc: BaseException) -> bool:
    return any(
        type(item).__name__ in _NETWORK_ERROR_NAMES | _STREAM_ERROR_NAMES for item in _iter_exceptions(exc)
    )


async def _with_retry(coro_factory: Any, *, attempts: int = 3, base_delay: float = 0.25) -> Any:
    last_exc: BaseException | None = None
    for attempt in range(attempts):
        try:
            return await coro_factory()
        except Exception as ex:
            last_exc = ex
            if not _is_retriable_network_error(ex) or attempt + 1 >= attempts:
                raise
            await asyncio.sleep(base_delay * (attempt + 1))
    assert last_exc is not None
    raise last_exc


def build_headers(api_key: str) -> dict[str, str]:
    key = (api_key or "").strip()
    if not key:
        return {}
    return {"Authorization": f"Bearer {key}"}


def parse_allowlist(raw: str) -> list[str] | None:
    """空串返回 None（表示默认 diagnose 规则）；否则返回去空白名称列表。"""
    text = (raw or "").strip()
    if not text:
        return None
    return [part.strip() for part in text.split(",") if part.strip()]


def tool_allowed(name: str, allowlist: list[str] | None) -> bool:
    if allowlist is None:
        return "diagnose" in name.lower()
    return name in allowlist


def mcp_configured(settings: Settings | None = None) -> bool:
    s = settings or get_settings()
    return bool(s.mcp_enabled and (s.mcp_url or "").strip())


def agent_tool_name(remote_name: str) -> str:
    return f"mcp_{remote_name}"


def remote_tool_name(agent_name: str) -> str | None:
    if not agent_name.startswith("mcp_"):
        return None
    remote = agent_name[4:]
    return remote or None


def _serialize_tool_result(result: Any) -> str:
    """将 CallToolResult / 任意返回值压成字符串。"""
    if result is None:
        return ""
    is_error = bool(getattr(result, "is_error", False))
    content = getattr(result, "content", None)
    structured = getattr(result, "structured_content", None)
    parts: list[str] = []
    if content:
        for block in content:
            text = getattr(block, "text", None)
            if text is not None:
                parts.append(str(text))
            else:
                try:
                    parts.append(json.dumps(block.model_dump(), ensure_ascii=False, default=str))
                except Exception:  # noqa: BLE001
                    parts.append(str(block))
    if structured is not None and not parts:
        parts.append(json.dumps(structured, ensure_ascii=False, default=str))
    text = "\n".join(parts).strip() if parts else str(result)
    if is_error and text and not text.startswith("{"):
        text = json.dumps({"error": text}, ensure_ascii=False)
    elif is_error and not text:
        text = json.dumps({"error": "MCP 工具返回错误"}, ensure_ascii=False)
    if len(text) > MAX_RESULT_CHARS:
        return text[: MAX_RESULT_CHARS - 20] + "…(truncated)"
    return text


async def _session_call(
    url: str,
    headers: dict[str, str],
    *,
    timeout: float,
    action: Any,
) -> Any:
    streamable_http_client, create_mcp_http_client, ClientSession = _load_mcp_sdk()

    async with create_mcp_http_client(headers=headers or None) as http_client, streamable_http_client(
        url,
        http_client=http_client,
        terminate_on_close=True,
    ) as streams:
        read, write = streams[0], streams[1]
        async with ClientSession(read, write, read_timeout_seconds=timeout) as session:
            await session.initialize()
            return await action(session)


async def _list_tools_async(
    url: str,
    headers: dict[str, str],
    *,
    timeout: float = 30.0,
) -> list[McpToolInfo]:
    async def _once() -> list[McpToolInfo]:
        async def action(session: Any) -> list[McpToolInfo]:
            result = await session.list_tools()
            tools: list[McpToolInfo] = []
            for tool in result.tools:
                schema = getattr(tool, "input_schema", None) or {"type": "object", "properties": {}}
                tools.append(
                    McpToolInfo(
                        name=str(tool.name),
                        description=str(tool.description or ""),
                        input_schema=dict(schema),
                    )
                )
            return tools

        return await _session_call(url, headers, timeout=timeout, action=action)

    return await _with_retry(_once)


async def _call_tool_async(
    url: str,
    headers: dict[str, str],
    tool_name: str,
    arguments: dict[str, Any],
    *,
    timeout: float = 60.0,
) -> Any:
    async def _once() -> Any:
        async def action(session: Any) -> Any:
            return await session.call_tool(tool_name, arguments or None)

        return await _session_call(url, headers, timeout=timeout, action=action)

    return await _with_retry(_once)


def list_remote_tools(
    url: str,
    headers: dict[str, str] | None = None,
    *,
    timeout: float = 30.0,
) -> list[McpToolInfo]:
    return list(_run_async(_list_tools_async(url, headers or {}, timeout=timeout)))


def call_remote_tool(
    url: str,
    headers: dict[str, str] | None,
    tool_name: str,
    arguments: dict[str, Any],
    *,
    timeout: float = 60.0,
) -> str:
    result = _run_async(
        _call_tool_async(url, headers or {}, tool_name, arguments, timeout=timeout)
    )
    return _serialize_tool_result(result)


def list_allowed_tools(
    settings: Settings | None = None,
    *,
    timeout: float = 30.0,
) -> list[McpToolInfo]:
    s = settings or get_settings()
    if not mcp_configured(s):
        return []
    url = s.mcp_url.strip()
    headers = build_headers(s.mcp_api_key)
    allowlist = parse_allowlist(s.mcp_tool_allowlist)
    tools = list_remote_tools(url, headers, timeout=timeout)
    return [t for t in tools if tool_allowed(t.name, allowlist)]


def call_allowed_tool(
    remote_name: str,
    arguments: dict[str, Any],
    *,
    settings: Settings | None = None,
) -> str:
    s = settings or get_settings()
    if not mcp_configured(s):
        raise McpClientError("MCP 未启用或未配置 MCP_URL")
    allowlist = parse_allowlist(s.mcp_tool_allowlist)
    if not tool_allowed(remote_name, allowlist):
        raise McpClientError(f"工具不在白名单：{remote_name}")
    return call_remote_tool(
        s.mcp_url.strip(),
        build_headers(s.mcp_api_key),
        remote_name,
        arguments,
    )


def probe_connection(settings: Settings | None = None, *, timeout: float = 8.0) -> dict[str, Any]:
    """健康探测：返回 status / tool_count / error。"""
    s = settings or get_settings()
    if not s.mcp_enabled:
        return {"configured": False, "enabled": False, "status": "未启用", "tool_count": 0}
    if not (s.mcp_url or "").strip():
        return {
            "configured": False,
            "enabled": True,
            "status": "已启用但未配置 MCP_URL",
            "tool_count": 0,
        }
    try:
        tools = list_allowed_tools(s, timeout=timeout)
        return {
            "configured": True,
            "enabled": True,
            "status": "已连接",
            "tool_count": len(tools),
            "tools": [t.name for t in tools],
        }
    except McpClientError as ex:
        return {
            "configured": True,
            "enabled": True,
            "status": f"连接失败：{ex}",
            "tool_count": 0,
            "error": str(ex),
        }
    except Exception as ex:  # noqa: BLE001
        return {
            "configured": True,
            "enabled": True,
            "status": f"连接失败：{_friendly_client_error(ex)}",
            "tool_count": 0,
            "error": str(ex),
        }
