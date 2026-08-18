"""MCP 客户端纯逻辑与 mock 调用测试（不打真网）。"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.ai import mcp_client as mc


def test_parse_allowlist_empty_means_default() -> None:
    assert mc.parse_allowlist("") is None
    assert mc.parse_allowlist("  ") is None
    assert mc.parse_allowlist("a, b ,c") == ["a", "b", "c"]


def test_tool_allowed_default_diagnose() -> None:
    assert mc.tool_allowed("diagnose_sector", None) is True
    assert mc.tool_allowed("DiagnoseX", None) is True
    assert mc.tool_allowed("write_file", None) is False
    assert mc.tool_allowed("write_file", ["write_file"]) is True
    assert mc.tool_allowed("diagnose_x", ["other"]) is False


def test_agent_tool_name_roundtrip() -> None:
    assert mc.agent_tool_name("diagnose_foo") == "mcp_diagnose_foo"
    assert mc.remote_tool_name("mcp_diagnose_foo") == "diagnose_foo"
    assert mc.remote_tool_name("get_watchlist") is None


def test_build_headers() -> None:
    assert mc.build_headers("") == {}
    assert mc.build_headers(" secret ") == {"Authorization": "Bearer secret"}


def test_serialize_tool_result_text() -> None:
    block = SimpleNamespace(text="hello")
    result = SimpleNamespace(content=[block], structured_content=None, is_error=False)
    assert mc._serialize_tool_result(result) == "hello"


def test_serialize_tool_result_error() -> None:
    block = SimpleNamespace(text="boom")
    result = SimpleNamespace(content=[block], structured_content=None, is_error=True)
    out = mc._serialize_tool_result(result)
    assert "error" in out and "boom" in out


def test_list_allowed_tools_filters(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = SimpleNamespace(
        mcp_enabled=True,
        mcp_url="https://example.test/mcp",
        mcp_api_key="k",
        mcp_tool_allowlist="",
    )
    remote = [
        mc.McpToolInfo("diagnose_a", "a", {"type": "object"}),
        mc.McpToolInfo("write_b", "b", {"type": "object"}),
    ]
    monkeypatch.setattr(mc, "list_remote_tools", lambda *a, **k: remote)
    tools = mc.list_allowed_tools(settings)  # type: ignore[arg-type]
    assert [t.name for t in tools] == ["diagnose_a"]


def test_call_allowed_tool_rejects_non_whitelist(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = SimpleNamespace(
        mcp_enabled=True,
        mcp_url="https://example.test/mcp",
        mcp_api_key="",
        mcp_tool_allowlist="diagnose_ok",
    )
    with pytest.raises(mc.McpClientError, match="白名单"):
        mc.call_allowed_tool("other", {}, settings=settings)  # type: ignore[arg-type]


def test_call_allowed_tool_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = SimpleNamespace(
        mcp_enabled=True,
        mcp_url="https://example.test/mcp",
        mcp_api_key="k",
        mcp_tool_allowlist="",
    )
    monkeypatch.setattr(mc, "call_remote_tool", lambda *a, **k: '{"ok":true}')
    out = mc.call_allowed_tool("diagnose_x", {"q": 1}, settings=settings)  # type: ignore[arg-type]
    assert out == '{"ok":true}'


def test_probe_disabled() -> None:
    settings = SimpleNamespace(mcp_enabled=False, mcp_url="", mcp_api_key="", mcp_tool_allowlist="")
    snap = mc.probe_connection(settings)  # type: ignore[arg-type]
    assert snap["status"] == "未启用"
    assert snap["configured"] is False


def test_probe_connected(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = SimpleNamespace(
        mcp_enabled=True,
        mcp_url="https://example.test/mcp",
        mcp_api_key="",
        mcp_tool_allowlist="",
    )
    monkeypatch.setattr(
        mc,
        "list_allowed_tools",
        lambda s, timeout=8.0: [mc.McpToolInfo("diagnose_a", "", {})],
    )
    snap = mc.probe_connection(settings)  # type: ignore[arg-type]
    assert snap["status"] == "已连接"
    assert snap["tool_count"] == 1


def test_probe_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = SimpleNamespace(
        mcp_enabled=True,
        mcp_url="https://example.test/mcp",
        mcp_api_key="",
        mcp_tool_allowlist="",
    )

    def boom(_s: object, timeout: float = 8.0) -> list[mc.McpToolInfo]:
        raise mc.McpClientError("无法连接")

    monkeypatch.setattr(mc, "list_allowed_tools", boom)
    snap = mc.probe_connection(settings)  # type: ignore[arg-type]
    assert "连接失败" in snap["status"]
