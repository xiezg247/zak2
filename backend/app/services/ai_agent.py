"""轻量 Agent：tool-calling 循环 + 最终回答。"""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

from sqlalchemy.orm import Session

from app.services import ai_proposals, llm as llm_svc
from app.services.ai_tools import (
    WRITE_TOOL_NAMES,
    _parse_args,
    execute_tool,
    get_tool_definitions,
    summarize_write_tool,
)

MAX_TOOL_ROUNDS = 4


def _assistant_message_for_history(msg: dict[str, Any]) -> dict[str, Any]:
    """规范化写入 messages 的 assistant 消息。"""
    out: dict[str, Any] = {"role": "assistant", "content": msg.get("content") or None}
    tool_calls = msg.get("tool_calls")
    if tool_calls:
        out["tool_calls"] = tool_calls
    return out


def run_tool_rounds(
    db: Session,
    user_id: str,
    messages: list[dict[str, Any]],
    *,
    use_tools: bool = True,
) -> Iterator[dict[str, Any]]:
    """
    执行 tool loop，yield 事件：
    - {"type": "tool_started", "name", "arguments"}
    - {"type": "tool_finished", "name", "ok"}
    - {"type": "confirm_required", "proposal_id", "tool", "summary", "args"}
    - {"type": "ready", "messages"}
    """
    working = list(messages)
    if not use_tools:
        yield {"type": "ready", "messages": working}
        return

    for _ in range(MAX_TOOL_ROUNDS):
        msg = llm_svc.chat_message(working, tools=get_tool_definitions())
        tool_calls = msg.get("tool_calls") or []
        if not tool_calls:
            content = str(msg.get("content") or "")
            yield {"type": "final_text", "content": content, "messages": working}
            return

        working.append(_assistant_message_for_history(msg))
        for tc in tool_calls:
            if not isinstance(tc, dict):
                continue
            fn = tc.get("function") or {}
            name = str(fn.get("name") or "")
            raw_args = fn.get("arguments") or "{}"
            yield {
                "type": "tool_started",
                "name": name,
                "arguments": raw_args if isinstance(raw_args, str) else str(raw_args),
            }

            if name in WRITE_TOOL_NAMES:
                args = _parse_args(raw_args)
                summary = summarize_write_tool(name, args)
                proposal = ai_proposals.create_proposal(
                    user_id=user_id,
                    tool=name,
                    args=args,
                    summary=summary,
                )
                yield {
                    "type": "confirm_required",
                    "proposal_id": proposal.id,
                    "tool": name,
                    "summary": summary,
                    "args": args,
                }
                result = json.dumps(
                    {
                        "status": "awaiting_confirm",
                        "proposal_id": proposal.id,
                        "summary": summary,
                        "message": (
                            "已向用户展示确认卡。请用一两句话提示用户点击「确认」或「拒绝」；"
                            "在用户确认前不要声称已写入。"
                        ),
                    },
                    ensure_ascii=False,
                )
                ok = True
            else:
                result = execute_tool(db, user_id, name, raw_args)
                ok = not result.startswith('{"error"')

            yield {"type": "tool_finished", "name": name, "ok": ok}
            working.append(
                {
                    "role": "tool",
                    "tool_call_id": str(tc.get("id") or name),
                    "content": result,
                }
            )

    yield {"type": "ready", "messages": working}


def complete_with_tools(
    db: Session,
    user_id: str,
    messages: list[dict[str, Any]],
    *,
    use_tools: bool = True,
) -> tuple[str, list[dict[str, Any]]]:
    """非流式：返回 (reply_text, tool_events)。"""
    events: list[dict[str, Any]] = []
    for event in run_tool_rounds(db, user_id, messages, use_tools=use_tools):
        if event["type"] == "final_text":
            return str(event.get("content") or ""), events
        if event["type"] == "ready":
            reply = llm_svc.chat_completion(event["messages"], stream=False)
            return str(reply), events
        events.append(event)
    return "", events


def stream_with_tools(
    db: Session,
    user_id: str,
    messages: list[dict[str, Any]],
    *,
    use_tools: bool = True,
) -> Iterator[dict[str, Any]]:
    """流式：yield SSE 友好事件 dict。"""
    for event in run_tool_rounds(db, user_id, messages, use_tools=use_tools):
        if event["type"] == "final_text":
            content = str(event.get("content") or "")
            if content:
                yield {"type": "delta", "content": content}
            yield {"type": "reply_done", "content": content}
            return
        if event["type"] == "ready":
            chunks: list[str] = []
            for piece in llm_svc.stream_completion(event["messages"]):
                chunks.append(piece)
                yield {"type": "delta", "content": piece}
            yield {"type": "reply_done", "content": "".join(chunks)}
            return
        yield event
