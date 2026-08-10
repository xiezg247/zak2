import json
from unittest.mock import MagicMock, patch

from app.services.ai_tools import WRITE_TOOL_NAMES, execute_tool


def test_list_skills_includes_watchlist() -> None:
    out = execute_tool(MagicMock(), "u", "list_skills", {})
    data = json.loads(out)
    ids = {s["id"] for s in data["skills"]}
    assert "watchlist" in ids


def test_read_skill_unknown_returns_error() -> None:
    out = execute_tool(MagicMock(), "u", "read_skill", {"skill_id": "nope"})
    data = json.loads(out)
    assert "error" in data


def test_skills_not_write_tools() -> None:
    assert "list_skills" not in WRITE_TOOL_NAMES
    assert "read_skill" not in WRITE_TOOL_NAMES
    assert "run_skill" not in WRITE_TOOL_NAMES


def test_run_skill_not_write() -> None:
    assert "run_skill" not in WRITE_TOOL_NAMES


def test_run_skill_market_emotion_mocked() -> None:
    with patch(
        "app.services.skill_runtime.run_skill_module",
        return_value={"emotion": {"phase": "x"}, "overview": {}},
    ) as m:
        out = execute_tool(MagicMock(), "u", "run_skill", {"skill_id": "market-emotion"})
    data = json.loads(out)
    assert "emotion" in data
    m.assert_called_once()


def test_run_skill_missing_id() -> None:
    out = execute_tool(MagicMock(), "u", "run_skill", {})
    data = json.loads(out)
    assert "error" in data
