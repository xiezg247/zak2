"""feed add/delete 订阅单测（mock，不打真 B 站）。"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.services import feed as feed_svc


def _settings(cookies: str = "SESSDATA=x") -> SimpleNamespace:
    return SimpleNamespace(bilibili_cookies=cookies)


def test_add_requires_cookies(monkeypatch) -> None:
    monkeypatch.setattr(feed_svc, "get_settings", lambda: _settings(""))
    db = MagicMock()
    with pytest.raises(HTTPException) as ei:
        feed_svc.add_bilibili_up(db, "user-1", "12345")
    assert ei.value.status_code == 400
    assert "COOKIE" in ei.value.detail.upper() or "cookie" in ei.value.detail.lower() or "BILIBILI" in ei.value.detail


def test_add_duplicate(monkeypatch) -> None:
    monkeypatch.setattr(feed_svc, "get_settings", lambda: _settings())
    db = MagicMock()
    # count < 50
    db.scalar.side_effect = [
        1,  # count
        SimpleNamespace(id="existing"),  # duplicate row
    ]
    with pytest.raises(HTTPException) as ei:
        feed_svc.add_bilibili_up(db, "user-1", "12345")
    assert ei.value.status_code == 400
    assert "已订阅" in ei.value.detail


def test_add_success(monkeypatch) -> None:
    monkeypatch.setattr(feed_svc, "get_settings", lambda: _settings())
    db = MagicMock()
    db.scalar.side_effect = [
        0,  # count
        None,  # no duplicate
    ]

    profile = {"mid": "12345", "name": "测试UP", "avatar": "https://i.hdslb.com/bfs/face/x.jpg", "sign": ""}

    with (
        patch.object(feed_svc, "get_user_profile", return_value=profile) as prof,
        patch.object(feed_svc, "BilibiliClient") as client_cls,
        patch.object(feed_svc, "sync_one_subscription") as sync_one,
    ):
        client = MagicMock()
        client_cls.return_value = client
        client.__enter__ = MagicMock(return_value=client)
        client.__exit__ = MagicMock(return_value=False)

        out = feed_svc.add_bilibili_up(db, "user-1", " 12345 ", sync_now=True)

    assert out.source_id == "12345"
    assert out.display_name == "测试UP"
    assert out.avatar_url.startswith("https://")
    assert out.enabled is True
    assert out.sync_error is None
    db.add.assert_called_once()
    db.commit.assert_called()
    prof.assert_called_once()
    sync_one.assert_called_once()
    client.close.assert_called()


def test_add_count_limit(monkeypatch) -> None:
    monkeypatch.setattr(feed_svc, "get_settings", lambda: _settings())
    db = MagicMock()
    db.scalar.return_value = 50
    with pytest.raises(HTTPException) as ei:
        feed_svc.add_bilibili_up(db, "user-1", "12345")
    assert ei.value.status_code == 400
    assert "上限" in ei.value.detail


@pytest.mark.parametrize("mid", ["", "  ", "abc", "12x3"])
def test_add_invalid_mid(monkeypatch, mid: str) -> None:
    monkeypatch.setattr(feed_svc, "get_settings", lambda: _settings())
    db = MagicMock()
    with pytest.raises(HTTPException) as ei:
        feed_svc.add_bilibili_up(db, "user-1", mid)
    assert ei.value.status_code == 400
    assert "mid" in ei.value.detail.lower()


def test_add_profile_failure_still_creates(monkeypatch) -> None:
    monkeypatch.setattr(feed_svc, "get_settings", lambda: _settings())
    db = MagicMock()
    db.scalar.side_effect = [0, None]

    with (
        patch.object(feed_svc, "get_user_profile", side_effect=RuntimeError("profile down")),
        patch.object(feed_svc, "BilibiliClient") as client_cls,
        patch.object(feed_svc, "sync_one_subscription") as sync_one,
    ):
        client = MagicMock()
        client_cls.return_value = client
        client.__enter__ = MagicMock(return_value=client)
        client.__exit__ = MagicMock(return_value=False)

        out = feed_svc.add_bilibili_up(db, "user-1", "12345", sync_now=False)

    assert out.source_id == "12345"
    assert out.display_name == "12345"
    assert out.avatar_url == ""
    assert out.sync_error is None
    db.add.assert_called_once()
    db.commit.assert_called()
    sync_one.assert_not_called()
    client.close.assert_called()


def test_add_sync_now_failure_keeps_subscription(monkeypatch) -> None:
    monkeypatch.setattr(feed_svc, "get_settings", lambda: _settings())
    db = MagicMock()
    db.scalar.side_effect = [0, None]

    profile = {"mid": "12345", "name": "测试UP", "avatar": "", "sign": ""}

    with (
        patch.object(feed_svc, "get_user_profile", return_value=profile),
        patch.object(feed_svc, "BilibiliClient") as client_cls,
        patch.object(feed_svc, "sync_one_subscription", side_effect=RuntimeError("sync boom")),
    ):
        client = MagicMock()
        client_cls.return_value = client
        client.__enter__ = MagicMock(return_value=client)
        client.__exit__ = MagicMock(return_value=False)

        out = feed_svc.add_bilibili_up(db, "user-1", "12345", sync_now=True)

    assert out.source_id == "12345"
    assert out.display_name == "测试UP"
    assert out.sync_error == "sync boom"
    db.add.assert_called_once()
    db.commit.assert_called()
    client.close.assert_called()


def test_delete_removes_items(monkeypatch) -> None:
    _ = monkeypatch
    db = MagicMock()
    sub = SimpleNamespace(id="sub-1", user_id="user-1")
    db.scalar.return_value = sub
    item_ids = ["item-a", "item-b"]
    db.scalars.return_value = item_ids

    feed_svc.delete_subscription(db, "user-1", "sub-1")

    assert db.execute.call_count == 3  # reads + items + sub
    db.commit.assert_called_once()
    db.scalar.assert_called_once()


def test_delete_other_user_not_found(monkeypatch) -> None:
    _ = monkeypatch
    db = MagicMock()
    db.scalar.return_value = None

    with pytest.raises(HTTPException) as ei:
        feed_svc.delete_subscription(db, "user-1", "sub-other")

    assert ei.value.status_code == 404
    assert "订阅不存在" in ei.value.detail
    db.execute.assert_not_called()
    db.commit.assert_not_called()
