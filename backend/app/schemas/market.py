from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class EmotionSnapshot(BaseModel):
    """市场情绪快照（market.load_emotion 产出的固定结构）。"""

    trade_date: str
    max_limit_times: int
    max_board_vt_symbol: str
    linked_board_count: int
    linked_board_vt_symbols: list[str] = Field(default_factory=list)
    updated_at: str


class MarketOverview(BaseModel):
    redis_available: bool
    quote_count: int
    updated_at: str | None = None
    is_trading: bool = False
    emotion: EmotionSnapshot | None = None
    emotion_cycle: EmotionCycleOut | None = None
    ranks_available: list[str] = Field(default_factory=list)


class EmotionThresholdsOut(BaseModel):
    recession_limit_down: int
    ice_max_boards: int
    ice_limit_down: int
    ice_up_ratio_max: float
    climax_ladder_depth: int
    climax_limit_up: int
    divergence_limit_up_min: int
    divergence_limit_spread: int
    startup_max_boards: int
    startup_limit_up: int
    amount_floor_yuan: float
    recession_break_rate: float
    fear_greed_overheat: float
    hysteresis_enabled: bool
    is_default: bool = True


class EmotionThresholdsPut(BaseModel):
    recession_limit_down: int | None = None
    ice_max_boards: int | None = None
    ice_limit_down: int | None = None
    ice_up_ratio_max: float | None = None
    climax_ladder_depth: int | None = None
    climax_limit_up: int | None = None
    divergence_limit_up_min: int | None = None
    divergence_limit_spread: int | None = None
    startup_max_boards: int | None = None
    startup_limit_up: int | None = None
    amount_floor_yuan: float | None = None
    recession_break_rate: float | None = None
    fear_greed_overheat: float | None = None
    hysteresis_enabled: bool | None = None


class EmotionCycleInputs(BaseModel):
    """情绪周期判定输入（build_emotion_cycle 的 inputs 子结构）。"""

    limit_up_count: int = 0
    limit_down_count: int = 0
    up_ratio: float = 0.0
    total_amount: float = 0.0
    max_limit_times: int = 0
    limit_ladder_depth: int = 0
    prev_leader_limit_down: bool = False
    limit_break_rate: float | None = None
    index_above_ma5: bool | None = None
    fear_greed_index: float = 0.0
    fear_greed_source: str = ""
    sample_size: int = 0


class EmotionCycleOut(BaseModel):
    stage: str
    stage_label: str
    position_factor: float
    position_pct_min: float
    position_pct_max: float
    allow_new_positions: bool
    allowed_modes: list[str] = Field(default_factory=list)
    allowed_mode_labels: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    source: str = ""
    trade_date: str | None = None
    raw_stage: str | None = None
    inputs: EmotionCycleInputs = Field(default_factory=EmotionCycleInputs)


class RankRow(BaseModel):
    rank: int
    symbol: str
    exchange: str
    vt_symbol: str
    tf_symbol: str
    name: str = ""
    score: float
    last_price: float | None = None
    change_pct: float | None = None
    turnover_rate: float | None = None
    amount: float | None = None
    volume_ratio: float | None = None
    limit_times: float | None = None


class SectorFlowRow(BaseModel):
    trade_date: str
    sector_kind: str
    sector_id: str
    name: str
    change_pct: float
    net_flow_yi: float
    flow_source: str = ""


class SectorIntradayPoint(BaseModel):
    bucket_time: str
    clock_minutes: int
    net_flow_yi: float
    change_pct: float


class RadarCardOut(BaseModel):
    card_id: str
    title: str
    subtitle: str = ""
    source: str  # cache | synthesized
    computed_at: str = ""
    empty_message: str = ""
    # 异构卡片行：不同 card_id 行结构不同（板块/连板/涨幅榜/放量/龙头…），前端按 card_id 渲染，故保留开放结构。
    rows: list[dict[str, Any]] = Field(default_factory=list)


class RadarResonanceEntry(BaseModel):
    vt_symbol: str
    name: str = ""
    card_count: int
    card_titles: list[str] = Field(default_factory=list)
    resonance_score: float
    change_pct: float | None = None
    last_price: float | None = None
    seal_time_label: str = ""


class RadarResonanceOut(BaseModel):
    min_cards: int
    top_n: int
    total: int
    entries: list[RadarResonanceEntry] = Field(default_factory=list)


class RadarResonanceWeightItem(BaseModel):
    card_id: str
    title: str
    weight: float
    default_weight: float


class RadarResonanceWeightsOut(BaseModel):
    items: list[RadarResonanceWeightItem] = Field(default_factory=list)
    weights: dict[str, float] = Field(default_factory=dict)


class RadarResonanceWeightsPut(BaseModel):
    weights: dict[str, float] = Field(default_factory=dict)


class RadarHorizonRow(BaseModel):
    vt_symbol: str
    name: str = ""
    resonance_score: float = 0
    card_count: int = 0
    card_titles: list[str] = Field(default_factory=list)
    change_pct: float | None = None
    last_price: float | None = None
    seal_time_label: str = ""


class RadarHorizonOut(BaseModel):
    variant: str = "default"
    strategy_key: str = ""
    computed_at: str | None = None
    scanned_total: int = 0
    refined_total: int = 0
    rows: list[RadarHorizonRow] = Field(default_factory=list)
    empty: bool = True
    label: str = "启发式展望（基于共振）"


class RadarPredictRow(BaseModel):
    vt_symbol: str
    name: str = ""
    predict_score: float = 0
    resonance_score: float = 0
    card_count: int = 0
    card_titles: list[str] = Field(default_factory=list)
    change_pct: float | None = None
    last_price: float | None = None
    seal_time_label: str = ""
    reasons: list[str] = Field(default_factory=list)


class RadarPredictOut(BaseModel):
    variant: str = "default"
    model_label: str = ""
    computed_at: str | None = None
    scanned_total: int = 0
    refined_total: int = 0
    kline_missing: int = 0
    rows: list[RadarPredictRow] = Field(default_factory=list)
    empty: bool = True
    label: str = "规则预测（共振+可解释加分）"


class LimitListRow(BaseModel):
    trade_date: str = ""
    vt_symbol: str = ""
    ts_code: str = ""
    name: str = ""
    limit_times: float = 0
    first_time: str = ""
    last_time: str = ""
    fd_amount: float = 0
    open_times: float = 0
    strth: float = 0
    updated_at: str = ""
    seal_time_score: float = 0
    seal_time_label: str = ""


class LimitListOut(BaseModel):
    trade_date: str = ""
    total: int = 0
    rows: list[LimitListRow] = Field(default_factory=list)


class PlanDraftRequest(BaseModel):
    top_n: int | None = None
    trade_date: str | None = None


class PlanDraftSymbol(BaseModel):
    vt_symbol: str
    name: str = ""


class PlanDraftOut(BaseModel):
    plan_id: str
    trade_date: str
    status: str
    emotion_expected: str
    symbol_count: int
    symbols: list[PlanDraftSymbol] = Field(default_factory=list)
    replaced: bool
