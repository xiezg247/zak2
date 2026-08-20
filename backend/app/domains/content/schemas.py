from __future__ import annotations

from pydantic import BaseModel, Field


class PlaybookSectionOut(BaseModel):
    section_id: str
    title: str
    body_md: str
    collapsed: bool
    sort_order: int
    updated_at: str


class PlaybookSectionUpdate(BaseModel):
    title: str | None = None
    body_md: str | None = None
    collapsed: bool | None = None


class DisciplineCheckOut(BaseModel):
    check_id: str
    label: str
    checked: bool


class DisciplineUpdate(BaseModel):
    checked: bool


class NoteSymbolOut(BaseModel):
    symbol: str
    exchange: str
    vt_symbol: str
    memo_preview: str = ""
    entry_count: int = 0
    updated_at: str = ""


class NoteMemoOut(BaseModel):
    symbol: str
    exchange: str
    vt_symbol: str
    body: str
    updated_at: str


class NoteMemoUpdate(BaseModel):
    body: str = ""


class NoteEntryOut(BaseModel):
    id: int
    symbol: str
    exchange: str
    vt_symbol: str
    body: str
    created_at: str


class NoteEntryCreate(BaseModel):
    body: str = Field(min_length=1)
    symbol: str | None = None
    exchange: str | None = None


class TeamReportListItem(BaseModel):
    id: int
    title: str
    summary: str = ""
    mode: str = ""
    created_at: str = ""
    vt_symbol: str = ""


class TeamReportOut(BaseModel):
    id: int
    symbol: str
    exchange: str
    vt_symbol: str
    title: str
    body: str
    summary: str = ""
    mode: str = ""
    context_json: str = ""
    created_at: str = ""


class FeedSubCreate(BaseModel):
    mid: str
    sync_now: bool = False


class BilibiliUserHit(BaseModel):
    mid: str
    name: str
    avatar: str = ""
    sign: str = ""


class BilibiliSearchOut(BaseModel):
    results: list[BilibiliUserHit]


class FeedSubOut(BaseModel):
    id: str
    source_type: str
    source_id: str
    display_name: str
    avatar_url: str
    enabled: bool
    sort_order: int
    sync_error: str | None = None


class FeedItemOut(BaseModel):
    id: str
    subscription_id: str
    source_type: str
    item_type: str
    title: str
    summary: str
    url: str
    author_name: str
    published_at: str
    is_read: bool
