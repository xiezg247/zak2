from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class HardFilterPrefs(BaseModel):
    exclude_st: bool = True
    exclude_suspended: bool = True
    min_amount_wan: float = 3000.0
    min_total_mv_yi: float = 50.0
    exclude_new_listing: bool = False
    min_listing_days: int = 60
    exclude_limit_board: bool = False
    exclude_one_word: bool = False
    allowed_industries: str = ""
    allowed_market_boards: str = ""


class HardFilterTemplate(BaseModel):
    id: str
    name: str
    prefs: HardFilterPrefs


class IndustryListOut(BaseModel):
    items: list[str]


class PresetOut(BaseModel):
    name: str
    source: str
    rule_kind: str
    description: str
    implemented: bool = True


class SchemeCreate(BaseModel):
    name: str
    config: dict[str, Any] = Field(default_factory=dict)


class SchemeUpdate(BaseModel):
    name: str | None = None
    config: dict[str, Any] | None = None


class SchemeOut(BaseModel):
    id: str
    name: str
    config: dict[str, Any]
    created_at: str
    updated_at: str


class RecipeCreate(BaseModel):
    name: str
    trigger_kind: str = "intraday"
    config: dict[str, Any] = Field(default_factory=dict)


class RecipeUpdate(BaseModel):
    name: str | None = None
    trigger_kind: str | None = None
    config: dict[str, Any] | None = None


class RecipeOut(BaseModel):
    id: str
    name: str
    trigger_kind: str
    config: dict[str, Any]
    created_at: str
    updated_at: str


class BuiltinRecipeOut(BaseModel):
    recipe_id: str
    name: str
    trigger_kind: str
    top_n: int
    implemented: bool


class PatternOut(BaseModel):
    pattern_id: str
    name: str
    description: str


class PatternRunRequest(BaseModel):
    pattern_id: str = Field(description="ma_bull | w_bottom | old_duck | theme_hot")
    top_n: int = Field(default=20, ge=1, le=100)
    max_scan: int = Field(default=800, ge=50, le=1200)
    hard_filter: HardFilterPrefs | None = None
    hard_filter_template: str | None = None


class ReferencePeerRequest(BaseModel):
    vt_symbol: str = Field(min_length=1, description="标杆股，如 600519.SSE")
    top_n: int = Field(default=20, ge=1, le=100)
    reference_name: str = ""
    hard_filter: HardFilterPrefs | None = None
    hard_filter_template: str | None = None
    weights: dict[str, float] | None = None


class ConditionRunRequest(BaseModel):
    preset: str = "涨幅榜"
    top_n: int = Field(default=50, ge=1, le=500)
    hard_filter: HardFilterPrefs | None = None
    hard_filter_template: str | None = None
    min_change_pct: float | None = None
    max_change_pct: float | None = None
    min_turnover_rate: float | None = None
    max_turnover_rate: float | None = None


class RecipeRunRequest(BaseModel):
    recipe_id: str = "intraday_multi"
    top_n: int | None = Field(default=None, ge=1, le=200)
    hard_filter: HardFilterPrefs | None = None
    hard_filter_template: str | None = None
    variant: str | None = Field(default=None, description="radar_leader: mainline | all_market")


class RecipeWeightItem(BaseModel):
    key: str
    label: str
    weight: float
    default_weight: float


class RecipeWeightsOut(BaseModel):
    recipe_id: str
    items: list[RecipeWeightItem]
    weights: dict[str, float]


class RecipeWeightsPut(BaseModel):
    weights: dict[str, float] = Field(default_factory=dict)


class JobAccepted(BaseModel):
    job_id: str


class RunSummary(BaseModel):
    id: str
    condition: str
    source: str
    row_count: int
    total_scanned: int
    created_at: str


class RunDetail(RunSummary):
    config: dict[str, Any]
    result: dict[str, Any]


class JobOut(BaseModel):
    id: str
    kind: str
    status: str
    progress: float = 0.0
    error: str | None = None
    result_ref: str | None = None
    created_at: str
    updated_at: str
