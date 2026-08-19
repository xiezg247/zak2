from __future__ import annotations

from pydantic import BaseModel, Field


class AutoScheduleCreate(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    recipe_id: str = Field(min_length=1)
    days_of_week: str = Field(min_length=1)
    times: list[str] = Field(min_length=1)


class AutoScheduleUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=64)
    recipe_id: str | None = None
    days_of_week: str | None = None
    times: list[str] | None = None


class AutoScheduleEnabledPatch(BaseModel):
    enabled: bool


class AutoScheduleOut(BaseModel):
    id: int
    name: str
    recipe_id: str
    days_of_week: str
    times: list[str]
    enabled: bool
    last_run_at: str | None = None
    last_message: str | None = None
    last_success: bool | None = None
    created_at: str
    updated_at: str


class AutoScheduleListOut(BaseModel):
    items: list[AutoScheduleOut]
