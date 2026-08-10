"""feed 关键词搜索 UP（mock）。"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.services import feed as feed_svc


def _settings(cookies: str = "SESSDATA=x") -> SimpleNamespace:
    return SimpleNamespace(bilibili_cookies=cookies)


def test_search_requires_cookies(monkeypatch) -> None:
    monkeypatch.setattr(feed_svc, "get_settings", lambda: _settings(""))
    with pytest.raises(HTTPException) as ei:
        feed_svc.search_bilibili_ups("量化")
    assert ei.value.status_code == 400
    assert "BILIBILI" in ei.value.detail or "COOKIE" in ei.value.detail.upper()


def test_search_empty_q_returns_empty(monkeypatch) -> None:
    monkeypatch.setattr(feed_svc, "get_settings", lambda: _settings())
    with patch.object(feed_svc, "search_users") as su:
        assert feed_svc.search_bilibili_ups("  ") == []
        su.assert_not_called()


def test_search_success_clamps_limit(monkeypatch) -> None:
    monkeypatch.setattr(feed_svc, "get_settings", lambda: _settings())
    hits = [{"mid": "1", "name": "A", "avatar": "", "sign": ""}]
    with (
        patch.object(feed_svc, "BilibiliClient") as client_cls,
        patch.object(feed_svc, "search_users", return_value=hits) as su,
    ):
        client_cls.return_value = MagicMock()
        out = feed_svc.search_bilibili_ups("量化", limit=99)
    assert out == hits
    su.assert_called_once()
    assert su.call_args.kwargs.get("limit") == 20 or su.call_args[1].get("limit") == 20


def test_search_maps_bilibili_error(monkeypatch) -> None:
    from app.integrations.bilibili.client import BilibiliApiError

    monkeypatch.setattr(feed_svc, "get_settings", lambda: _settings())
    with (
        patch.object(feed_svc, "BilibiliClient") as client_cls,
        patch.object(feed_svc, "search_users", side_effect=BilibiliApiError("boom")),
    ):
        client_cls.return_value = MagicMock()
        with pytest.raises(HTTPException) as ei:
            feed_svc.search_bilibili_ups("量化")
    assert ei.value.status_code == 502
    assert "boom" in ei.value.detail
