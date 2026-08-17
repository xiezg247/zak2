"""投研团队数据模型：预取事实 → 规则评分 → 流式事件。"""

from __future__ import annotations

from typing import Any, Literal, TypedDict

from pydantic import BaseModel, Field


class TeamBars(BaseModel):
    """日 K 摘要切片（prefetch 的 bars 子结构）。"""

    count: int = 0
    last_close: float | None = None
    period_change_pct: float | None = None
    high: float | None = None
    low: float | None = None
    error: str | None = None


class TeamFinancial(BaseModel):
    """估值切片（Tushare daily_basic，缺失时可能仅有 note/error）。"""

    pe_ttm: float | None = None
    pb: float | None = None
    total_mv_yi: float | None = None
    trade_date: str | None = None
    source: str | None = None
    note: str | None = None
    error: str | None = None


class TeamRisk(BaseModel):
    volatility_annualized_pct: float | None = None
    max_drawdown_pct: float | None = None
    return_pct_60d: float | None = None
    fear_greed_index: float | None = None
    error: str | None = None


class TeamStrategy(BaseModel):
    ma_alignment: str = ""
    signal: str = "na"
    signal_label: str = "—"
    period_change_pct: float | None = None
    emotion_stage: str | None = None
    emotion_stage_label: str | None = None
    allow_new_positions: bool | None = None


class TeamEmotion(BaseModel):
    stage: str | None = None
    stage_label: str | None = None
    warnings: list[str] = Field(default_factory=list)
    allow_new_positions: bool | None = None
    fear_greed_index: float | None = None


class TeamPrefetch(BaseModel):
    """单标的投研预取事实（team_prefetch.prefetch_team 的输出）。"""

    vt_symbol: str
    symbol: str = ""
    exchange: str = ""
    name: str = ""
    last_price: float | None = None
    change_pct: float | None = None
    bars: TeamBars = Field(default_factory=TeamBars)
    financial: TeamFinancial = Field(default_factory=TeamFinancial)
    risk: TeamRisk = Field(default_factory=TeamRisk)
    strategy: TeamStrategy = Field(default_factory=TeamStrategy)
    emotion: TeamEmotion = Field(default_factory=TeamEmotion)
    error: str | None = None


class AgentScore(BaseModel):
    """单个分析师维度的规则评分结果。"""

    score: int = 0
    summary: str = ""
    highlights: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)


class TeamScores(BaseModel):
    financial: AgentScore
    risk: AgentScore
    strategy: AgentScore
    weighted: float = 0.0
    weights: dict[str, float] = Field(default_factory=dict)


# ---- 流式事件：SSE 边界协议，字段随 kind/agent 异构，用 TypedDict 描述以保留 JSON 兼容 ----

TeamAgent = Literal["financial", "risk", "strategy", "chief", "system"]


class TeamStreamEvent(TypedDict, total=False):
    """投研团队 SSE 事件（字段按 kind/agent 可选出现）。"""

    type: str  # team | report_saved
    agent: TeamAgent
    kind: str  # started | score | delta | done | error
    label: str
    content: str
    vt_symbol: str
    name: str
    mode: str
    score: int
    summary: str
    highlights: list[str]
    risks: list[str]
    weighted: float
    weights: dict[str, float]
    scores: dict[str, Any]  # 事件内为 model_dump 后的评分 dict
    report: str
    detail: str
    fallback: bool
    report_id: int
    title: str
