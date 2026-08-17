"""分页收尾：feed/notes/reports 的 list_xxx_page service 层单测。"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.repositories.pagination import Page
from app.services import feed as feed_svc
from app.services import notes as notes_svc
from app.services import team_reports


def _feed_item(**kw: object) -> SimpleNamespace:
    base = SimpleNamespace(
        id="item-1",
        subscription_id="sub-1",
        source_type="bilibili",
        item_type="video",
        title="标题",
        summary="摘要",
        url="https://x",
        author_name="作者",
        published_at="2026-08-17T00:00:00",
        read_at=None,
    )
    for k, v in kw.items():
        setattr(base, k, v)
    return base


def test_feed_items_page_empty_no_subs() -> None:
    db = MagicMock()
    with patch.object(feed_svc, "list_subscriptions", return_value=[]):
        out = feed_svc.list_feed_items_page(db, "u1", page=1, page_size=20)
    assert out.total == 0
    assert out.items == []
    assert out.page == 1


def test_feed_items_page_wraps() -> None:
    db = MagicMock()
    item = _feed_item()
    with (
        patch.object(feed_svc, "list_subscriptions", return_value=[SimpleNamespace(id="sub-1", enabled=True)]),
        patch.object(feed_svc, "paginate", return_value=Page(items=[item], total=5, page=1, page_size=20)) as pg,
    ):
        out = feed_svc.list_feed_items_page(db, "u1", page=1, page_size=20)
    pg.assert_called_once()
    assert out.total == 5
    assert out.pages == 1
    assert len(out.items) == 1
    assert out.items[0].id == "item-1"
    assert out.items[0].title == "标题"
    assert out.items[0].is_read is False


def test_notes_entries_page_wraps() -> None:
    db = MagicMock()
    entry = SimpleNamespace(id=7, symbol="600519", exchange="SSE", body="笔记", created_at="t")
    with (
        patch.object(notes_svc, "resolve_symbol_pair", return_value=("600519", "SSE")),
        patch.object(notes_svc, "to_vt_symbol", return_value="600519.SSE"),
        patch.object(notes_svc, "paginate", return_value=Page(items=[entry], total=3, page=2, page_size=1)) as pg,
    ):
        out = notes_svc.list_entries_page(db, "u1", "600519.SSE", page=2, page_size=1)
    pg.assert_called_once()
    assert out.total == 3
    assert out.pages == 3
    assert out.items[0].id == 7
    assert out.items[0].vt_symbol == "600519.SSE"


def test_reports_page_wraps() -> None:
    db = MagicMock()
    row = SimpleNamespace(id=9, title="t", summary="s", mode="fast", created_at="c", vt_symbol="600519.SSE")
    with (
        patch.object(team_reports, "parse_flexible_symbol", return_value=("600519", "SSE")),
        patch.object(team_reports, "paginate", return_value=Page(items=[row], total=1, page=1, page_size=20)) as pg,
    ):
        out = team_reports.list_reports_page(db, "u1", "600519.SSE", page=1, page_size=20)
    pg.assert_called_once()
    assert out.total == 1
    assert out.items[0].id == 9
    assert out.items[0].vt_symbol == "600519.SSE"


def test_reports_page_bad_symbol() -> None:
    db = MagicMock()
    with (
        patch.object(team_reports, "parse_flexible_symbol", side_effect=ValueError("bad")),
        pytest.raises(ValueError),
    ):
        team_reports.list_reports_page(db, "u1", "!!!")
