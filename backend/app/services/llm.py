"""OpenAI 兼容 Chat Completions（支持流式与 tools）。"""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

import httpx
from fastapi import HTTPException

from app.core.settings import get_settings


def llm_status() -> dict[str, Any]:
    s = get_settings()
    return {
        "configured": bool(s.llm_api_key.strip()),
        "model": s.llm_model,
        "api_base": s.llm_api_base.rstrip("/"),
    }


def _headers() -> dict[str, str]:
    s = get_settings()
    if not s.llm_api_key.strip():
        raise HTTPException(status_code=503, detail="未配置 LLM_API_KEY")
    return {
        "Authorization": f"Bearer {s.llm_api_key}",
        "Content-Type": "application/json",
    }


def _base_payload(
    messages: list[dict[str, Any]], *, stream: bool, tools: list[dict[str, Any]] | None
) -> dict[str, Any]:
    s = get_settings()
    payload: dict[str, Any] = {
        "model": s.llm_model,
        "messages": messages,
        "max_tokens": s.llm_max_tokens,
        "temperature": s.llm_temperature,
        "stream": stream,
    }
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"
    return payload


def chat_completion(
    messages: list[dict[str, Any]],
    *,
    stream: bool = False,
    tools: list[dict[str, Any]] | None = None,
) -> Any:
    """stream=False 且无 tools 时返回 content 字符串；有 tools 时请用 chat_message。"""
    if stream:
        return stream_completion(messages, tools=None)
    if tools:
        msg = chat_message(messages, tools=tools)
        if msg.get("tool_calls"):
            return msg
        return str(msg.get("content") or "")
    url = f"{get_settings().llm_api_base.rstrip('/')}/chat/completions"
    payload = _base_payload(messages, stream=False, tools=None)
    with httpx.Client(timeout=120.0) as client:
        resp = client.post(url, headers=_headers(), json=payload)
        if resp.status_code >= 400:
            raise HTTPException(status_code=502, detail=f"LLM 错误：{resp.status_code} {resp.text[:300]}")
        data = resp.json()
    try:
        return str(data["choices"][0]["message"]["content"] or "")
    except (KeyError, IndexError, TypeError) as exc:
        raise HTTPException(status_code=502, detail="LLM 响应格式异常") from exc


def chat_message(
    messages: list[dict[str, Any]],
    *,
    tools: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """非流式，返回 assistant message dict（可含 tool_calls）。"""
    url = f"{get_settings().llm_api_base.rstrip('/')}/chat/completions"
    payload = _base_payload(messages, stream=False, tools=tools)
    with httpx.Client(timeout=120.0) as client:
        resp = client.post(url, headers=_headers(), json=payload)
        if resp.status_code >= 400:
            raise HTTPException(status_code=502, detail=f"LLM 错误：{resp.status_code} {resp.text[:300]}")
        data = resp.json()
    try:
        msg = data["choices"][0]["message"]
        if not isinstance(msg, dict):
            raise TypeError("message not dict")
        return msg
    except (KeyError, IndexError, TypeError) as exc:
        raise HTTPException(status_code=502, detail="LLM 响应格式异常") from exc


def stream_completion(
    messages: list[dict[str, Any]],
    *,
    tools: list[dict[str, Any]] | None = None,
) -> Iterator[str]:
    url = f"{get_settings().llm_api_base.rstrip('/')}/chat/completions"
    payload = _base_payload(messages, stream=True, tools=tools)
    return _stream(url, payload)


def chat_completion_stream(messages: list[dict[str, Any]]) -> Iterator[str]:
    """兼容旧调用。"""
    return stream_completion(messages)


def _stream(url: str, payload: dict[str, Any]) -> Iterator[str]:
    with httpx.Client(timeout=120.0) as client, client.stream("POST", url, headers=_headers(), json=payload) as resp:
        if resp.status_code >= 400:
            body = resp.read().decode("utf-8", errors="ignore")
            raise HTTPException(status_code=502, detail=f"LLM 错误：{resp.status_code} {body[:300]}")
        for line in resp.iter_lines():
            if not line:
                continue
            if line.startswith("data: "):
                data = line[6:].strip()
                if data == "[DONE]":
                    break
                try:
                    obj = json.loads(data)
                    delta = obj["choices"][0].get("delta") or {}
                    content = delta.get("content")
                    if content:
                        yield str(content)
                except (json.JSONDecodeError, KeyError, IndexError, TypeError):
                    continue
