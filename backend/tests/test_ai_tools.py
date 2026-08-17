import pytest

from app.services.ai_tools import (
    TOOL_DEFINITIONS,
    TOOL_HANDLERS,
    WRITE_TOOL_NAMES,
    execute_tool,
    get_tool_definitions,
)


def test_tools_registered() -> None:
    names = {t["function"]["name"] for t in TOOL_DEFINITIONS}
    write = {
        "add_watchlist",
        "remove_watchlist",
        "upsert_note_memo",
        "add_note_entry",
        "upsert_position",
        "delete_position",
        "add_signal_panel",
        "remove_signal_panel",
    }
    assert names == {
        "get_watchlist",
        "get_positions",
        "get_signal_panel",
        "get_trading_risk",
        "get_market_emotion",
        "get_recent_screening",
        "get_radar_snapshot",
        "get_bars_summary",
        "get_recent_backtest",
        "list_note_symbols",
        "get_stock_notes",
        "list_skills",
        "read_skill",
        "run_skill",
        *write,
    }
    assert set(TOOL_HANDLERS) == names - write


def test_read_position_tools_registered_not_write() -> None:
    names = {d["function"]["name"] for d in get_tool_definitions() if d.get("type") == "function"}
    for n in ("get_positions", "get_signal_panel", "get_trading_risk"):
        assert n in names
        assert n in TOOL_HANDLERS
        assert n not in WRITE_TOOL_NAMES


def test_unknown_tool_json() -> None:
    # db/user unused for unknown
    from unittest.mock import MagicMock

    out = execute_tool(MagicMock(), "u", "no_such_tool", {})
    assert "未知工具" in out


def test_get_tool_definitions_merges_mcp(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.services import mcp_client

    monkeypatch.setattr(mcp_client, "mcp_configured", lambda: True)
    monkeypatch.setattr(
        mcp_client,
        "list_allowed_tools",
        lambda: [mcp_client.McpToolInfo("diagnose_x", "desc", {"type": "object", "properties": {}})],
    )
    names = {t["function"]["name"] for t in get_tool_definitions()}
    assert "mcp_diagnose_x" in names
    assert "get_watchlist" in names


def test_execute_mcp_tool(monkeypatch: pytest.MonkeyPatch) -> None:
    from unittest.mock import MagicMock

    from app.services import mcp_client

    monkeypatch.setattr(mcp_client, "call_allowed_tool", lambda name, args: '{"ok":1}')
    out = execute_tool(MagicMock(), "u", "mcp_diagnose_x", {"a": 1})
    assert '"ok"' in out


def test_execute_mcp_tool_error(monkeypatch: pytest.MonkeyPatch) -> None:
    from unittest.mock import MagicMock

    from app.services import mcp_client

    def boom(name: str, args: dict) -> str:
        raise mcp_client.McpClientError("连不上")

    monkeypatch.setattr(mcp_client, "call_allowed_tool", boom)
    out = execute_tool(MagicMock(), "u", "mcp_diagnose_x", {})
    assert "连不上" in out
