"""ops_sync_bilibili_feed 单测（mock 网络，不打真 B 站）。"""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

from sqlalchemy.exc import IntegrityError

from app.integrations.bilibili.client import BilibiliApiError
from app.integrations.bilibili.normalize import FeedItemDraft
from app.services.ops import sync_bilibili_feed as svc


def test_in_sync_window() -> None:
    tz = ZoneInfo("Asia/Shanghai")
    assert svc.in_sync_window(datetime(2026, 8, 10, 8, 0, tzinfo=tz)) is True
    assert svc.in_sync_window(datetime(2026, 8, 10, 19, 59, tzinfo=tz)) is True
    assert svc.in_sync_window(datetime(2026, 8, 10, 7, 59, tzinfo=tz)) is False
    assert svc.in_sync_window(datetime(2026, 8, 10, 20, 0, tzinfo=tz)) is False


def test_skip_outside_window(monkeypatch) -> None:
    monkeypatch.setattr(svc, "in_sync_window", lambda now=None: False)
    db = MagicMock()
    with patch.object(svc, "save_job_run_meta") as meta:
        out = svc.sync_bilibili_feed(db, force=False)
    assert out.skipped is True
    assert out.success is True
    assert "08:00" in out.message
    meta.assert_called_once()


def test_skip_no_cookies(monkeypatch) -> None:
    monkeypatch.setattr(
        svc,
        "get_settings",
        lambda: SimpleNamespace(bilibili_cookies=""),
    )
    db = MagicMock()
    with patch.object(svc, "save_job_run_meta"):
        out = svc.sync_bilibili_feed(db, force=True)
    assert out.skipped is True
    assert out.success is True
    assert "BILIBILI_COOKIES" in out.message


def test_skip_no_subscriptions(monkeypatch) -> None:
    monkeypatch.setattr(
        svc,
        "get_settings",
        lambda: SimpleNamespace(bilibili_cookies="SESSDATA=x"),
    )
    db = MagicMock()
    db.scalars.return_value = []
    with patch.object(svc, "save_job_run_meta"):
        out = svc.sync_bilibili_feed(db, force=True)
    assert out.skipped is True
    assert "订阅" in out.message


def test_insert_new_item(monkeypatch) -> None:
    monkeypatch.setattr(
        svc,
        "get_settings",
        lambda: SimpleNamespace(bilibili_cookies="SESSDATA=x"),
    )
    monkeypatch.setattr(svc, "SUBSCRIPTION_SLEEP_SEC", 0)

    sub = SimpleNamespace(
        id="sub1",
        source_id="12345",
        source_type="bilibili_up",
        display_name="UP名",
    )
    draft = FeedItemDraft(
        external_id="dyn1",
        item_type="video",
        title="标题",
        summary="简介",
        url="https://www.bilibili.com/video/BV1xx",
        author_name="UP名",
        published_at="2024-01-01T00:00:00",
        payload={"cover_url": ""},
    )

    db = MagicMock()
    db.scalars.return_value = [sub]
    db.scalar.return_value = None

    client = MagicMock()
    with (
        patch.object(svc, "BilibiliClient", return_value=client),
        patch.object(svc, "list_recent_dynamics", return_value=[{"id_str": "dyn1"}]) as list_dyn,
        patch.object(svc, "normalize_dynamic", return_value=draft) as norm,
        patch.object(svc, "save_job_run_meta"),
    ):
        out = svc.sync_bilibili_feed(db, force=True)

    assert out.success is True
    assert out.extra["new_items"] == 1
    assert out.skipped is not True
    list_dyn.assert_called_once()
    norm.assert_called_once()
    db.add.assert_called_once()
    item = db.add.call_args[0][0]
    assert item.external_id == "dyn1"
    assert item.subscription_id == "sub1"
    assert item.source_type == "bilibili_up"
    assert item.title == "标题"
    db.commit.assert_called()
    client.close.assert_called_once()


def test_skip_duplicate_external_id(monkeypatch) -> None:
    monkeypatch.setattr(
        svc,
        "get_settings",
        lambda: SimpleNamespace(bilibili_cookies="SESSDATA=x"),
    )
    monkeypatch.setattr(svc, "SUBSCRIPTION_SLEEP_SEC", 0)

    sub = SimpleNamespace(
        id="sub1",
        source_id="12345",
        source_type="bilibili_up",
        display_name="UP",
    )
    draft = FeedItemDraft(
        external_id="dyn1",
        item_type="video",
        title="t",
        summary="s",
        url="https://t.bilibili.com/dyn1",
        author_name="UP",
        published_at="2024-01-01T00:00:00",
        payload={},
    )

    db = MagicMock()
    db.scalars.return_value = [sub]
    db.scalar.return_value = "existing-id"

    client = MagicMock()
    with (
        patch.object(svc, "BilibiliClient", return_value=client),
        patch.object(svc, "list_recent_dynamics", return_value=[{"id_str": "dyn1"}]),
        patch.object(svc, "normalize_dynamic", return_value=draft),
        patch.object(svc, "save_job_run_meta"),
    ):
        out = svc.sync_bilibili_feed(db, force=True)

    assert out.success is True
    assert out.extra["new_items"] == 0
    db.add.assert_not_called()
    client.close.assert_called_once()


def test_integrity_error_on_race_does_not_explode(monkeypatch) -> None:
    """并发下 UNIQUE(source_type, external_id) 冲突：吞掉 IntegrityError，已成功项仍计数。"""
    monkeypatch.setattr(
        svc,
        "get_settings",
        lambda: SimpleNamespace(bilibili_cookies="SESSDATA=x"),
    )
    monkeypatch.setattr(svc, "SUBSCRIPTION_SLEEP_SEC", 0)

    sub = SimpleNamespace(
        id="sub1",
        source_id="12345",
        source_type="bilibili_up",
        display_name="UP",
    )
    draft_ok = FeedItemDraft(
        external_id="dyn-ok",
        item_type="video",
        title="ok",
        summary="s",
        url="https://t.bilibili.com/dyn-ok",
        author_name="UP",
        published_at="2024-01-01T00:00:00",
        payload={},
    )
    draft_dup = FeedItemDraft(
        external_id="dyn-dup",
        item_type="video",
        title="dup",
        summary="s",
        url="https://t.bilibili.com/dyn-dup",
        author_name="UP",
        published_at="2024-01-01T00:00:00",
        payload={},
    )

    db = MagicMock()
    db.scalars.return_value = [sub]
    db.scalar.return_value = None  # 存在性检查未命中（竞态窗口）

    flush_calls = {"n": 0}

    def flush_side_effect() -> None:
        flush_calls["n"] += 1
        if flush_calls["n"] == 2:
            raise IntegrityError("INSERT", {}, Exception("unique_violation"))

    db.flush.side_effect = flush_side_effect

    client = MagicMock()
    with (
        patch.object(svc, "BilibiliClient", return_value=client),
        patch.object(
            svc,
            "list_recent_dynamics",
            return_value=[{"id_str": "dyn-ok"}, {"id_str": "dyn-dup"}],
        ),
        patch.object(svc, "normalize_dynamic", side_effect=[draft_ok, draft_dup]),
        patch.object(svc, "save_job_run_meta"),
    ):
        out = svc.sync_bilibili_feed(db, force=True)

    assert out.success is True
    assert out.extra["new_items"] == 1
    assert db.add.call_count == 2
    assert db.begin_nested.call_count == 2
    assert flush_calls["n"] == 2
    db.commit.assert_called()
    client.close.assert_called_once()


def test_api_error_success_false(monkeypatch) -> None:
    monkeypatch.setattr(
        svc,
        "get_settings",
        lambda: SimpleNamespace(bilibili_cookies="SESSDATA=x"),
    )
    monkeypatch.setattr(svc, "SUBSCRIPTION_SLEEP_SEC", 0)

    sub = SimpleNamespace(
        id="sub1",
        source_id="12345",
        source_type="bilibili_up",
        display_name="UP",
    )
    db = MagicMock()
    db.scalars.return_value = [sub]

    client = MagicMock()
    with (
        patch.object(svc, "BilibiliClient", return_value=client),
        patch.object(
            svc,
            "list_recent_dynamics",
            side_effect=BilibiliApiError("风控", code=-352),
        ),
        patch.object(svc, "save_job_run_meta") as meta,
    ):
        out = svc.sync_bilibili_feed(db, force=True)

    assert out.success is False
    assert out.extra["new_items"] == 0
    assert out.extra.get("errors")
    assert "风控" in out.message
    meta.assert_called_once()
    client.close.assert_called_once()
