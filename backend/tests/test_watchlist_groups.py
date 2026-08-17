from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.models.watchlist import WatchlistGroup
from app.repositories import watchlist as repo


def _group(*, gid: str | None = None, name: str = "A", user_id: str = "u1") -> WatchlistGroup:
    g = WatchlistGroup(id=gid or str(uuid4()), user_id=user_id, name=name, sort_order=0)
    return g


def test_rename_success() -> None:
    db = MagicMock()
    g = _group(name="旧名")
    others: list[WatchlistGroup] = []
    with patch.object(repo.WatchlistGroupRepository, "list_groups", return_value=others):
        db.scalar.return_value = g
        out = repo.WatchlistGroupRepository(db, "u1").rename_group(g.id, "新名")
    assert out.name == "新名"
    db.commit.assert_called()
    db.refresh.assert_called()


def test_rename_empty() -> None:
    db = MagicMock()
    with pytest.raises(HTTPException) as ei:
        repo.WatchlistGroupRepository(db, "u1").rename_group("g1", "  ")
    assert ei.value.status_code == 400


def test_rename_not_found() -> None:
    db = MagicMock()
    db.scalar.return_value = None
    with pytest.raises(HTTPException) as ei:
        repo.WatchlistGroupRepository(db, "u1").rename_group("missing", "名")
    assert ei.value.status_code == 404


def test_rename_conflict() -> None:
    db = MagicMock()
    g = _group(name="旧")
    other = _group(name="已有")
    db.scalar.return_value = g
    with (
        patch.object(repo.WatchlistGroupRepository, "list_groups", return_value=[g, other]),
        pytest.raises(HTTPException) as ei,
    ):
        repo.WatchlistGroupRepository(db, "u1").rename_group(g.id, "已有")
    assert ei.value.status_code == 409


def test_reorder_groups_order() -> None:
    db = MagicMock()
    g1 = _group(gid="g1", name="A")
    g1.sort_order = 0
    g2 = _group(gid="g2", name="B")
    g2.sort_order = 1
    with patch.object(repo.WatchlistGroupRepository, "list_groups", return_value=[g1, g2]):
        out = repo.WatchlistGroupRepository(db, "u1").reorder_groups(["g2", "g1"])
    assert [g.id for g in out] == ["g2", "g1"]
    assert g2.sort_order == 0
    assert g1.sort_order == 1
    db.commit.assert_called()


def test_reorder_groups_ignores_unknown_and_appends() -> None:
    db = MagicMock()
    g1 = _group(gid="g1", name="A")
    g2 = _group(gid="g2", name="B")
    with patch.object(repo.WatchlistGroupRepository, "list_groups", return_value=[g1, g2]):
        out = repo.WatchlistGroupRepository(db, "u1").reorder_groups(["g2", "missing"])
    assert [g.id for g in out] == ["g2", "g1"]
    assert g2.sort_order == 0
    assert g1.sort_order == 1


def test_batch_add_counts() -> None:
    db = MagicMock()
    g = _group(gid="g1")
    from app.models.watchlist import WatchlistItem

    item = WatchlistItem(symbol="600519", exchange="SSE", user_id="u1", name="", sort_order=0)

    with (
        patch.object(repo, "parse_flexible_symbol", return_value=("600519", "SSE")),
        patch.object(repo, "normalize_exchange", side_effect=lambda e: e),
    ):
        db.scalar.side_effect = [g, item, None]
        out = repo.WatchlistGroupMemberRepository(db, "u1").batch_group_members("g1", ["600519.SSE"], "add")
    assert out["ok"] is True
    assert out["action"] == "add"
    assert out["added"] == 1
    assert out["skipped"] == 0
    assert out["errors"] == []
    db.commit.assert_called()
    db.add.assert_called()


def test_batch_add_not_in_watchlist_error() -> None:
    db = MagicMock()
    g = _group(gid="g1")
    db.scalar.side_effect = [g, None]
    with patch.object(repo, "parse_flexible_symbol", return_value=("600519", "SSE")):
        out = repo.WatchlistGroupMemberRepository(db, "u1").batch_group_members("g1", ["600519.SSE"], "add")
    assert out["added"] == 0
    assert len(out["errors"]) == 1
    assert "自选" in out["errors"][0]["detail"]


def test_batch_remove_skips_missing() -> None:
    db = MagicMock()
    g = _group(gid="g1")
    db.scalar.side_effect = [g, None]
    with patch.object(repo, "parse_flexible_symbol", return_value=("600519", "SSE")):
        out = repo.WatchlistGroupMemberRepository(db, "u1").batch_group_members("g1", ["600519.SSE"], "remove")
    assert out["removed"] == 0
    assert out["skipped"] == 1
    db.commit.assert_called()


def test_batch_group_missing_404() -> None:
    db = MagicMock()
    db.scalar.return_value = None
    with pytest.raises(HTTPException) as ei:
        repo.WatchlistGroupMemberRepository(db, "u1").batch_group_members("missing", ["600519.SSE"], "add")
    assert ei.value.status_code == 404
