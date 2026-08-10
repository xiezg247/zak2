from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.services import team_orchestrator


_PREFETCH = {
    "vt_symbol": "600519.SSE",
    "name": "茅台",
    "financial": {"pe_ttm": 20},
    "risk": {"volatility_annualized_pct": 22, "max_drawdown_pct": 18},
    "strategy": {"ma_alignment": "均线多头排列", "signal": "buy", "emotion_stage": "startup"},
    "emotion": {"stage": "startup", "stage_label": "启动"},
    "bars": {"count": 60},
}


def test_stream_team_analysis_error_symbol() -> None:
    db = MagicMock()
    events = list(team_orchestrator.stream_team_analysis(db, "u1", "!!!"))
    kinds = [e.get("kind") for e in events]
    assert "error" in kinds or "done" in kinds


def test_stream_team_with_prefetch_mock() -> None:
    db = MagicMock()
    with (
        patch.object(team_orchestrator, "prefetch_team", return_value=_PREFETCH),
        patch.object(
            team_orchestrator.llm_svc,
            "stream_completion",
            return_value=iter(["## 汇总\n", "加权参考规则分。"]),
        ),
    ):
        events = list(team_orchestrator.stream_team_analysis(db, "u1", "600519.SSE"))
    agents = {e.get("agent") for e in events}
    assert "financial" in agents and "chief" in agents and "system" in agents
    assert any(e.get("kind") == "score" and e.get("agent") == "financial" for e in events)
    # fast：子 Agent 无 LLM delta
    sub_deltas = [
        e
        for e in events
        if e.get("kind") == "delta" and e.get("agent") in ("financial", "risk", "strategy")
    ]
    assert not sub_deltas
    done = [e for e in events if e.get("agent") == "system" and e.get("kind") == "done"]
    assert done and "汇总" in str(done[0].get("report") or "")
    assert done[0].get("mode") == "fast"


def test_stream_team_deep_parallel_deltas() -> None:
    db = MagicMock()

    def fake_stream(messages: list) -> iter:
        sys = str((messages[0] or {}).get("content") or "")
        if "财务分析师" in sys:
            return iter(["财务要点A"])
        if "风险分析师" in sys:
            return iter(["风险要点B"])
        if "策略与情绪" in sys:
            return iter(["策略要点C"])
        return iter(["## 首席\n", "综合研判。"])

    with (
        patch.object(team_orchestrator, "prefetch_team", return_value=_PREFETCH),
        patch.object(team_orchestrator.llm_svc, "stream_completion", side_effect=fake_stream),
    ):
        events = list(team_orchestrator.stream_team_analysis(db, "u1", "600519.SSE", mode="deep"))

    by_agent_delta = {
        a: "".join(
            str(e.get("content") or "")
            for e in events
            if e.get("agent") == a and e.get("kind") == "delta"
        )
        for a in ("financial", "risk", "strategy", "chief")
    }
    assert "财务要点A" in by_agent_delta["financial"]
    assert "风险要点B" in by_agent_delta["risk"]
    assert "策略要点C" in by_agent_delta["strategy"]
    assert "首席" in by_agent_delta["chief"] or "综合" in by_agent_delta["chief"]
    done = [e for e in events if e.get("agent") == "system" and e.get("kind") == "done"]
    assert done and done[0].get("mode") == "deep"


def test_stream_team_deep_analyst_fallback() -> None:
    db = MagicMock()
    calls = {"n": 0}

    def fake_stream(messages: list) -> iter:
        calls["n"] += 1
        sys = str((messages[0] or {}).get("content") or "")
        if "财务分析师" in sys:
            raise RuntimeError("llm down")
        if "风险分析师" in sys:
            return iter(["风险OK"])
        if "策略与情绪" in sys:
            return iter(["策略OK"])
        return iter(["首席OK"])

    with (
        patch.object(team_orchestrator, "prefetch_team", return_value=_PREFETCH),
        patch.object(team_orchestrator.llm_svc, "stream_completion", side_effect=fake_stream),
    ):
        events = list(team_orchestrator.stream_team_analysis(db, "u1", "600519.SSE", mode="deep"))

    fin_done = [
        e for e in events if e.get("agent") == "financial" and e.get("kind") == "done"
    ]
    assert fin_done and fin_done[0].get("fallback") is True
    assert any(e.get("agent") == "system" and e.get("kind") == "done" for e in events)


def test_fallback_report() -> None:
    text = team_orchestrator._fallback_report(
        {"vt_symbol": "1.SSE", "name": "测", "emotion": {"stage_label": "启动"}},
        {
            "weighted": 66,
            "financial": {"summary": "估值中性"},
            "risk": {"summary": "波动可控"},
            "strategy": {"summary": "偏多"},
        },
    )
    assert "加权分" in text
    assert "启动" in text
