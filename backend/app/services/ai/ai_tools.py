"""投研工具编排入口：只读 + 需确认的写操作，供 Agent tool-calling。

实现拆分为 app/services/ai/tools/ 子包，本模块聚合注册表并提供执行编排。
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.services.ai.tools._common import (
    MAX_RESULT_CHARS as MAX_RESULT_CHARS,
)
from app.services.ai.tools._common import (
    ToolHandler,
    _parse_args,
    _truncate,
)
from app.services.ai.tools.read import READ_DEFINITIONS, READ_HANDLERS
from app.services.ai.tools.skills import SKILL_DEFINITIONS, SKILL_HANDLERS
from app.services.ai.tools.write import (
    WRITE_DEFINITIONS,
    WRITE_HANDLERS,
    WRITE_TOOL_NAMES,
)
from app.services.ai.tools.write import (
    summarize_write_tool as summarize_write_tool,
)

# 写工具只能经 execute_write_tool 在用户确认后执行；execute_tool 依赖 WRITE_TOOL_NAMES 先行拦截，写工具不会命中本表。
TOOL_HANDLERS: dict[str, ToolHandler] = {**READ_HANDLERS, **SKILL_HANDLERS, **WRITE_HANDLERS}
TOOL_DEFINITIONS: list[dict[str, Any]] = [*READ_DEFINITIONS, *SKILL_DEFINITIONS, *WRITE_DEFINITIONS]


def _mcp_tool_definitions() -> list[dict[str, Any]]:
    """白名单 MCP 工具 → OpenAI tools 定义；失败时静默为空。"""
    from app.services.ai import mcp_client

    if not mcp_client.mcp_configured():
        return []
    try:
        tools = mcp_client.list_allowed_tools()
    except Exception:
        return []
    defs: list[dict[str, Any]] = []
    for tool in tools:
        schema = tool.input_schema or {"type": "object", "properties": {}}
        if not isinstance(schema, dict):
            schema = {"type": "object", "properties": {}}
        desc = tool.description or f"MCP 工具 {tool.name}"
        defs.append(
            {
                "type": "function",
                "function": {
                    "name": mcp_client.agent_tool_name(tool.name),
                    "description": f"[MCP] {desc}",
                    "parameters": schema,
                },
            }
        )
    return defs


def get_tool_definitions() -> list[dict[str, Any]]:
    """本地工具 +（可选）MCP 白名单工具。"""
    return [*TOOL_DEFINITIONS, *_mcp_tool_definitions()]


def execute_write_tool(db: Session, user_id: str, name: str, arguments: dict[str, Any] | str | None) -> Any:
    """仅由确认 API 调用；直接落库。"""
    handler = WRITE_HANDLERS.get(name)
    if not handler:
        return {"error": f"未知写工具：{name}"}
    args = _parse_args(arguments)
    try:
        return handler(db, user_id, args)
    except Exception as exc:
        return {"error": str(exc)}


def _execute_mcp_tool(name: str, arguments: dict[str, Any] | str | None) -> str:
    from app.services.ai import mcp_client

    remote = mcp_client.remote_tool_name(name)
    if not remote:
        return _truncate({"error": f"未知工具：{name}"})
    args = _parse_args(arguments)
    try:
        return mcp_client.call_allowed_tool(remote, args)
    except mcp_client.McpClientError as exc:
        return _truncate({"error": str(exc)})
    except Exception as exc:
        return _truncate({"error": str(exc)})


def execute_tool(db: Session, user_id: str, name: str, arguments: dict[str, Any] | str | None) -> str:
    if name in WRITE_TOOL_NAMES:
        return _truncate(
            {
                "error": "写操作须经用户确认，不能直接执行",
                "hint": "agent 应走 proposal 流程",
            }
        )
    if name.startswith("mcp_"):
        return _execute_mcp_tool(name, arguments)
    handler = TOOL_HANDLERS.get(name)
    if not handler:
        return _truncate({"error": f"未知工具：{name}"})
    args = _parse_args(arguments)
    try:
        result = handler(db, user_id, args)
    except Exception as exc:
        result = {"error": str(exc)}
    return _truncate(result)
