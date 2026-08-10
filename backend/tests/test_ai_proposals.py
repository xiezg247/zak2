from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.services import ai_proposals
from app.services.ai_tools import WRITE_TOOL_NAMES, execute_tool, summarize_write_tool


@pytest.fixture(autouse=True)
def _clean_proposals() -> None:
    ai_proposals.clear_all()
    yield
    ai_proposals.clear_all()


def test_create_and_reject_proposal() -> None:
    p = ai_proposals.create_proposal(
        user_id="u1",
        tool="add_watchlist",
        args={"symbol": "600519.SSE"},
        summary="加自选：600519.SSE",
    )
    assert p.status == "pending"
    out = ai_proposals.reject_proposal(p.id, "u1")
    assert out.status == "rejected"
    with pytest.raises(HTTPException) as exc:
        ai_proposals.reject_proposal(p.id, "u1")
    assert exc.value.status_code == 409


def test_proposal_user_isolation() -> None:
    p = ai_proposals.create_proposal(
        user_id="u1",
        tool="add_watchlist",
        args={"symbol": "600519.SSE"},
        summary="x",
    )
    with pytest.raises(HTTPException) as exc:
        ai_proposals.get_proposal(p.id, "u2")
    assert exc.value.status_code == 404


def test_execute_tool_blocks_write() -> None:
    out = execute_tool(MagicMock(), "u", "add_watchlist", {"symbol": "600519.SSE"})
    assert "须经用户确认" in out


def test_summarize_write_tool() -> None:
    assert "加自选" in summarize_write_tool("add_watchlist", {"symbol": "600519.SSE", "name": "茅台"})
    assert "删自选" in summarize_write_tool("remove_watchlist", {"symbol": "600519.SSE"})
    assert "写备忘" in summarize_write_tool("upsert_note_memo", {"vt_symbol": "600519.SSE", "body": "观察"})
    assert "记流水" in summarize_write_tool("add_note_entry", {"vt_symbol": "600519.SSE", "body": "买入观察"})


def test_write_tools_registered() -> None:
    assert WRITE_TOOL_NAMES == {"add_watchlist", "remove_watchlist", "upsert_note_memo", "add_note_entry"}


def test_execute_tool_blocks_all_writes() -> None:
    for name in WRITE_TOOL_NAMES:
        out = execute_tool(MagicMock(), "u", name, {"symbol": "600519.SSE", "body": "x"})
        assert "须经用户确认" in out
