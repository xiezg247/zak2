"""B 站用户搜索单测（mock，不打真站）。"""

from __future__ import annotations

from unittest.mock import MagicMock

from app.integrations.bilibili.user import (
    _iter_search_user_items,
    _normalize_search_user,
    search_users,
)


def test_iter_search_user_items_flat_wbi_result() -> None:
    rows = list(
        _iter_search_user_items(
            [
                {"type": "bili_user", "mid": 1, "uname": "A"},
                {"type": "video", "bvid": "BV1"},
            ]
        )
    )
    assert len(rows) == 1
    assert rows[0]["mid"] == 1


def test_iter_search_user_items_legacy_grouped_result() -> None:
    rows = list(
        _iter_search_user_items(
            [
                {
                    "result_type": "bili_user",
                    "data": [{"mid": 2, "uname": "B"}],
                }
            ]
        )
    )
    assert len(rows) == 1
    assert rows[0]["uname"] == "B"


def test_normalize_search_user_prefixes_avatar() -> None:
    user = _normalize_search_user({"mid": 3, "uname": "C", "upic": "//example.com/a.jpg"})
    assert user is not None
    assert user["avatar"] == "https://example.com/a.jpg"
    assert user["name"] == "C"
    assert user["mid"] == "3"


def test_normalize_search_user_skips_empty_mid() -> None:
    assert _normalize_search_user({"uname": "X"}) is None


def test_search_users_empty_keyword() -> None:
    client = MagicMock()
    assert search_users(client, "  ") == []
    client.get_json.assert_not_called()


def test_search_users_calls_signed_path_and_limits() -> None:
    client = MagicMock()
    client.get_json.return_value = {
        "result": [
            {"type": "bili_user", "mid": i, "uname": f"U{i}", "upic": ""}
            for i in range(1, 12)
        ]
    }
    out = search_users(client, "量化", limit=3)
    assert len(out) == 3
    assert out[0]["mid"] == "1"
    client.get_json.assert_called_once_with(
        "/x/web-interface/wbi/search/type",
        params={"search_type": "bili_user", "keyword": "量化", "page": 1},
        signed=True,
    )
