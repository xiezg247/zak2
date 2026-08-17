from __future__ import annotations

from app.schemas.team import TeamFinancial, TeamPrefetch, TeamRisk, TeamStrategy
from app.services.team_scoring import compute_team_scores, score_financial, score_risk, score_strategy


def test_score_financial_pe() -> None:
    out = score_financial(TeamFinancial(pe_ttm=12, pb=1.5, total_mv_yi=500))
    assert out.score >= 50
    assert out.highlights


def test_score_risk_vol() -> None:
    low = score_risk(TeamRisk(volatility_annualized_pct=18, max_drawdown_pct=12, return_pct_60d=5))
    high = score_risk(TeamRisk(volatility_annualized_pct=55, max_drawdown_pct=45, return_pct_60d=-20))
    assert low.score > high.score


def test_score_strategy_emotion() -> None:
    bad = score_strategy(TeamStrategy(emotion_stage="recession", emotion_stage_label="退潮", allow_new_positions=False))
    good = score_strategy(
        TeamStrategy(
            ma_alignment="均线多头排列",
            signal="buy",
            emotion_stage="startup",
            emotion_stage_label="启动",
            allow_new_positions=True,
            period_change_pct=8,
        )
    )
    assert good.score > bad.score


def test_compute_team_scores_weighted() -> None:
    scores = compute_team_scores(
        TeamPrefetch(
            vt_symbol="600519.SSE",
            financial=TeamFinancial(pe_ttm=15),
            risk=TeamRisk(volatility_annualized_pct=20, max_drawdown_pct=15),
            strategy=TeamStrategy(ma_alignment="均线多头排列", signal="buy", emotion_stage="startup"),
        )
    )
    assert 0 <= scores.weighted <= 100
    assert set(scores.weights) == {"financial", "risk", "strategy"}
