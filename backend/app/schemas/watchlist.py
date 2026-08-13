from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class WatchlistItemOut(BaseModel):
    symbol: str
    exchange: str
    name: str
    sort_order: int
    vt_symbol: str
    tf_symbol: str
    # 行情（可选 enrich）
    last_price: float | None = None
    change_pct: float | None = None
    turnover_rate: float | None = None
    volume: float | None = None
    amount: float | None = None
    volume_ratio: float | None = None
    industry: str = ""
    suspended: bool = False


class WatchlistAddRequest(BaseModel):
    symbol: str = Field(description="支持 600519.SSE / SHSE.600519 / 600519")
    name: str = ""
    exchange: str | None = None


class WatchlistReorderRequest(BaseModel):
    items: list[str] = Field(description="vt_symbol 列表，按期望顺序")


class GroupsReorderRequest(BaseModel):
    group_ids: list[str] = Field(min_length=1, description="分组 id 期望顺序")


class GroupOut(BaseModel):
    id: str
    name: str
    sort_order: int


class GroupCreate(BaseModel):
    name: str = Field(min_length=1, max_length=40)


class GroupRename(BaseModel):
    name: str = Field(min_length=1, max_length=40)


class GroupMemberRequest(BaseModel):
    symbol: str
    exchange: str | None = None


class GroupMembersBatchRequest(BaseModel):
    symbols: list[str] = Field(min_length=1, max_length=100)
    action: Literal["add", "remove"]


class GroupMembersBatchError(BaseModel):
    symbol: str
    detail: str


class GroupMembersBatchOut(BaseModel):
    ok: bool = True
    action: Literal["add", "remove"]
    added: int = 0
    removed: int = 0
    skipped: int = 0
    errors: list[GroupMembersBatchError] = Field(default_factory=list)


class QuoteOut(BaseModel):
    symbol: str
    exchange: str
    vt_symbol: str
    tf_symbol: str
    name: str = ""
    last_price: float = 0.0
    change_pct: float = 0.0
    turnover_rate: float = 0.0
    volume: float = 0.0
    amount: float = 0.0
    amplitude: float = 0.0
    volume_ratio: float = 0.0
    industry: str = ""


class BarOut(BaseModel):
    datetime: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    turnover: float


class BarsResponse(BaseModel):
    symbol: str
    exchange: str
    vt_symbol: str
    interval: str
    bars: list[BarOut]


class StrategySignalRow(BaseModel):
    vt_symbol: str
    name: str = ""
    last_price: float | None = None
    change_pct: float | None = None
    signal: str = "na"
    signal_label: str = "—"
    signal_date: str | None = None
    strength: float | None = None
    reason_summary: str = ""
    ref_buy_price: float | None = None
    ref_sell_price: float | None = None
    ma_gap_pct: float | None = None
    volume_ratio_5d: float | None = None
    bar_as_of: str | None = None
    updated_at: str | None = None


class StrategyPositionRow(BaseModel):
    vt_symbol: str
    name: str = ""
    cost_price: float
    volume: int
    buy_date: str
    notes: str = ""
    source: str = "manual"
    plan_pct: float | None = None
    last_price: float | None = None
    market_value: float | None = None
    unrealized_pnl: float | None = None
    unrealized_pnl_pct: float | None = None
    t1_locked: bool = False
    exit_signal: str = "na"
    exit_signal_label: str = "—"
    ref_sell_price: float | None = None
    reason_summary: str = ""
    risk_tags: list[str] = Field(default_factory=list)
    risk_primary: str = ""
    off_plan: bool = False


class PlanSymbolStatus(BaseModel):
    vt_symbol: str
    name: str = ""
    in_watchlist: bool = False
    in_position: bool = False


class RiskSummaryOut(BaseModel):
    total_capital: float | None = None
    actual_position_pct: float | None = None
    plan_max_pct: float | None = None
    off_plan_count: int = 0
    off_plan_symbols: list[str] = Field(default_factory=list)
    active_plan_date: str = ""
    plan_symbols: list[PlanSymbolStatus] = Field(default_factory=list)


class StrategyBoardOut(BaseModel):
    config_key: str
    as_of: str | None = None
    source: str = "none"
    note: str = ""
    panel_symbols: list[str] = Field(default_factory=list)
    signals: list[StrategySignalRow] = Field(default_factory=list)
    positions: list[StrategyPositionRow] = Field(default_factory=list)
    risk_summary: RiskSummaryOut | None = None


class SignalPanelOut(BaseModel):
    symbols: list[str] = Field(default_factory=list)
    max_symbols: int = 10
    count: int = 0


class SignalPanelReplaceRequest(BaseModel):
    symbols: list[str] = Field(default_factory=list)


class SignalPanelMemberRequest(BaseModel):
    symbol: str = Field(description="支持 600519.SSE / SHSE.600519 / 600519")


class FinancialSnapshotOut(BaseModel):
    end_date: str
    revenue: float | None = None
    net_income: float | None = None
    revenue_yoy: float | None = None
    net_income_yoy: float | None = None
    roe: float | None = None
    debt_ratio: float | None = None


class FinancialSyncOut(BaseModel):
    last_sync_at: str
    latest_end_date: str = ""
    periods_count: int = 0
    sync_status: str = "ok"
    error_message: str = ""


class DisclosureOut(BaseModel):
    end_date: str
    pre_date: str = ""
    ann_date: str = ""
    actual_date: str = ""


class FundamentalsOut(BaseModel):
    vt_symbol: str
    ts_code: str
    snapshot: FinancialSnapshotOut | None = None
    sync: FinancialSyncOut | None = None
    disclosures: list[DisclosureOut] = Field(default_factory=list)



class PositionOut(BaseModel):
    symbol: str
    exchange: str
    vt_symbol: str
    cost_price: float
    volume: int
    buy_date: str
    notes: str = ""
    source: str = "manual"
    plan_pct: float | None = None
    sort_order: int = 0
    created_at: str = ""
    updated_at: str = ""


class PositionUpsertRequest(BaseModel):
    symbol: str = Field(description="支持 600519.SSE / SHSE.600519 / 600519")
    exchange: str | None = None
    cost_price: float = Field(gt=0)
    volume: int = Field(gt=0, description="须为 100 股整手")
    buy_date: str = Field(description="YYYY-MM-DD")
    notes: str = ""
    plan_pct: float | None = None


class TradingRiskPrefsOut(BaseModel):
    total_capital: float | None = None
    stop_loss_pct: float = 0.05
    caution_float_pct: float = -5.0
    realized_pnl_today: float | None = None


class TradingRiskPrefsPut(BaseModel):
    total_capital: float | None = None
    stop_loss_pct: float | None = None
    caution_float_pct: float | None = None
    realized_pnl_today: float | None = None


class NotifyLogItem(BaseModel):
    id: str
    event_type: str
    channel: str
    status: str
    error: str = ""
    created_at: str
    payload: dict[str, Any] = Field(default_factory=dict)


class NotifyLogOut(BaseModel):
    items: list[NotifyLogItem] = Field(default_factory=list)
    limit: int = 50
    count: int = 0
