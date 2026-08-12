from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.models.watchlist import WatchlistGroup
from app.services import watchlist_repo as repo


def _group(*, gid: str | None = None, name: str = "A", user_id: str = "u1") -> WatchlistGroup:
    g = WatchlistGroup(id=gid or str(uuid4()), user_id=user_id, name=name, sort_order=0)
    return g


def test_rename_success() -> None:
    db = MagicMock()
    g = _group(name="旧名")
    others: list[WatchlistGroup] = []
    with patch.object(repo, "list_groups", return_value=others):
        db.scalar.return_value = g
        out = repo.rename_group(db, "u1", g.id, "新名")
    assert out.name == "新名"
    db.commit.assert_called()
    db.refresh.assert_called()


def test_rename_empty() -> None:
    db = MagicMock()
    with pytest.raises(HTTPException) as ei:
        repo.rename_group(db, "u1", "g1", "  ")
    assert ei.value.status_code == 400


def test_rename_not_found() -> None:
    db = MagicMock()
    db.scalar.return_value = None
    with pytest.raises(HTTPException) as ei:
        repo.rename_group(db, "u1", "missing", "名")
    assert ei.value.status_code == 404


def test_rename_conflict() -> None:
    db = MagicMock()
    g = _group(name="旧")
    other = _group(name="已有")
    db.scalar.return_value = g
    with patch.object(repo, "list_groups", return_value=[g, other]):
        with pytest.raises(HTTPException) as ei:
            repo.rename_group(db, "u1", g.id, "已有")
    assert ei.value.status_code == 409


def test_reorder_groups_order() -> None:
    db = MagicMock()
    g1 = _group(gid="g1", name="A")
    g1.sort_order = 0
    g2 = _group(gid="g2", name="B")
    g2.sort_order = 1
    with patch.object(repo, "list_groups", return_value=[g1, g2]):
        out = repo.reorder_groups(db, "u1", ["g2", "g1"])
    assert [g.id for g in out] == ["g2", "g1"]
    assert g2.sort_order == 0
    assert g1.sort_order == 1
    db.commit.assert_called()


def test_reorder_groups_ignores_unknown_and_appends() -> None:
    db = MagicMock()
    g1 = _group(gid="g1", name="A")
    g2 = _group(gid="g2", name="B")
    with patch.object(repo, "list_groups", return_value=[g1, g2]):
        out = repo.reorder_groups(db, "u1", ["g2", "missing"])
    assert [g.id for g in out] == ["g2", "g1"]
    assert g2.sort_order == 0
    assert g1.sort_order == 1
