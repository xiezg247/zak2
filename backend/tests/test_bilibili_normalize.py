"""Bilibili normalize / cookies_configured 单测（不打真网）。"""

from __future__ import annotations

from app.integrations.bilibili.client import BilibiliClient
from app.integrations.bilibili.normalize import normalize_dynamic


def test_normalize_video_archive() -> None:
    raw = {
        "id_str": "123",
        "type": "DYNAMIC_TYPE_AV",
        "modules": {
            "module_author": {"pub_ts": 1700000000},
            "module_dynamic": {
                "major": {
                    "archive": {
                        "bvid": "BV1xx",
                        "title": "标题",
                        "desc": "简介",
                        "cover": "http://c",
                    }
                }
            },
        },
    }
    d = normalize_dynamic(raw, author_name="UP")
    assert d is not None
    assert d.external_id == "123"
    assert d.item_type == "video"
    assert d.title == "标题"
    assert "BV1xx" in d.url
    assert d.author_name == "UP"


def test_normalize_missing_id_returns_none() -> None:
    assert normalize_dynamic({"modules": {}}, author_name="x") is None


def test_cookies_configured() -> None:
    assert BilibiliClient(cookies="").cookies_configured is False
    assert BilibiliClient(cookies="SESSDATA=x").cookies_configured is True
