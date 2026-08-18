"""team_reports 单测。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.schemas.content import TeamReportListItem
from app.schemas.team import AgentScore, TeamEmotion, TeamPrefetch, TeamScores
from app.services.team.team_orchestrator import _fallback_report, stream_team_analysis_with_persist
from app.services.team.team_reports import should_persist_report


def test_should_persist_requires_section() -> None:
    assert should_persist_report("") is False
    assert should_persist_report("随便一段") is False
    assert should_persist_report("## 综合研判\n看好") is True


def test_fallback_contains_综合研判() -> None:
    text = _fallback_report(
        TeamPrefetch(vt_symbol="600519.SSE", name="茅台", emotion=TeamEmotion()),
        TeamScores(
            weighted=60,
            financial=AgentScore(summary="a"),
            risk=AgentScore(summary="b"),
            strategy=AgentScore(summary="c"),
        ),
    )
    assert "综合研判" in text


def test_stream_persist_emits_report_saved() -> None:
    db = MagicMock()
    events = [
        {"type": "team", "agent": "system", "kind": "started"},
        {
            "type": "team",
            "agent": "system",
            "kind": "done",
            "vt_symbol": "600519.SSE",
            "name": "茅台",
            "report": "## 综合研判\n正文",
            "mode": "fast",
            "weighted": 70,
            "scores": {},
        },
    ]
    with (
        patch(
            "app.services.team.team_orchestrator.stream_team_analysis",
            return_value=iter(events),
        ),
        patch(
            "app.services.team.team_reports.persist_team_report",
            return_value=TeamReportListItem(id=9, title="t", vt_symbol="600519.SSE"),
        ) as persist,
    ):
        out = list(stream_team_analysis_with_persist(db, "u1", "600519.SSE", mode="fast"))
    persist.assert_called_once()
    assert out[-1]["type"] == "report_saved"
    assert out[-1]["report_id"] == 9
