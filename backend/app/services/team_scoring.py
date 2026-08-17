"""投研团队：基于预取事实的规则评分。"""

from __future__ import annotations

from app.schemas.team import AgentScore, TeamFinancial, TeamPrefetch, TeamRisk, TeamScores, TeamStrategy


def _clamp(score: int) -> int:
    return max(0, min(100, score))


def score_financial(financial: TeamFinancial) -> AgentScore:
    if financial.error:
        return AgentScore(score=40, summary="财务数据不可用", risks=["财务预取失败"])

    score = 50
    highlights: list[str] = []
    risks: list[str] = []

    pe = financial.pe_ttm
    if pe is not None and pe > 0:
        if pe < 20:
            score += 12
            highlights.append(f"PE(TTM) {pe:.1f}")
        elif pe > 50:
            score -= 10
            risks.append(f"PE(TTM) 偏高 {pe:.1f}")

    pb = financial.pb
    if pb is not None and pb > 0:
        if pb < 2:
            score += 5
        elif pb > 8:
            score -= 5
            risks.append(f"PB 偏高 {pb:.1f}")

    mv = financial.total_mv_yi
    if mv is not None:
        if mv >= 200:
            score += 5
            highlights.append(f"市值约 {mv:.0f} 亿")
        elif mv < 30:
            score -= 5
            risks.append(f"小市值 {mv:.0f} 亿")

    if not highlights and not risks:
        return AgentScore(score=50, summary="财务数据有限（仅估值切片）")

    return AgentScore(
        score=_clamp(score),
        summary="；".join(highlights) if highlights else "估值中性",
        highlights=highlights,
        risks=risks,
    )


def score_risk(risk: TeamRisk) -> AgentScore:
    if risk.error:
        return AgentScore(score=40, summary="风险数据不可用", risks=["风险预取失败"])

    score = 60
    highlights: list[str] = []
    risks: list[str] = []

    vol = risk.volatility_annualized_pct
    if vol is not None:
        if vol < 25:
            score += 15
            highlights.append(f"年化波动 {vol:.1f}%")
        elif vol > 40:
            score -= 15
            risks.append(f"波动偏高 {vol:.1f}%")

    dd = risk.max_drawdown_pct
    if dd is not None:
        if dd < 20:
            score += 10
            highlights.append(f"最大回撤 {dd:.1f}%")
        elif dd > 35:
            score -= 15
            risks.append(f"回撤较大 {dd:.1f}%")

    ret = risk.return_pct_60d
    if ret is not None:
        if ret >= 10:
            score += 5
        elif ret <= -15:
            score -= 10
            risks.append(f"近60日跌 {ret:.1f}%")

    fg = risk.fear_greed_index
    if fg is not None:
        if fg >= 75:
            score -= 5
            risks.append(f"市场贪婪 {fg:.0f}")
        elif fg <= 25:
            score += 5
            highlights.append(f"市场恐惧 {fg:.0f}")

    return AgentScore(
        score=_clamp(score),
        summary="；".join(highlights) if highlights else "风险指标有限",
        highlights=highlights,
        risks=risks,
    )


def score_strategy(strategy: TeamStrategy) -> AgentScore:
    score = 50
    highlights: list[str] = []
    risks: list[str] = []

    alignment = strategy.ma_alignment
    if "多头" in alignment:
        score += 20
        highlights.append(alignment)
    elif "空头" in alignment:
        score -= 15
        risks.append(alignment)

    signal = strategy.signal
    if signal == "buy":
        score += 15
        highlights.append("策略信号偏多")
    elif signal == "sell":
        score -= 15
        risks.append("策略信号偏空")

    ret = strategy.period_change_pct
    if ret is not None and ret >= 5:
        score += 5

    stage = strategy.emotion_stage or ""
    stage_label = strategy.emotion_stage_label or stage
    if stage == "recession":
        score -= 20
        risks.append(f"情绪{stage_label or '退潮'}，宜谨慎")
    elif stage == "ice":
        score -= 12
        risks.append(f"情绪{stage_label or '冰点'}，仅宜小仓试错")
    elif stage in {"startup", "climax"}:
        score += 5
        highlights.append(f"情绪{stage_label or stage}，短线窗口尚可")

    if strategy.allow_new_positions is False:
        score -= 8
        risks.append("情绪周期建议不开新仓")

    return AgentScore(
        score=_clamp(score),
        summary="；".join(highlights) if highlights else "技术面中性",
        highlights=highlights,
        risks=risks,
    )


def compute_team_scores(prefetch: TeamPrefetch) -> TeamScores:
    financial = score_financial(prefetch.financial)
    risk = score_risk(prefetch.risk)
    strategy = score_strategy(prefetch.strategy)

    weighted = round(
        financial.score * 0.4 + risk.score * 0.3 + strategy.score * 0.3,
        1,
    )
    return TeamScores(
        financial=financial,
        risk=risk,
        strategy=strategy,
        weighted=weighted,
        weights={"financial": 0.4, "risk": 0.3, "strategy": 0.3},
    )
