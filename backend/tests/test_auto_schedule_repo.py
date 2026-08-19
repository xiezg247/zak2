from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from app.models.auto_schedule import AutoSchedule
from app.repositories.auto_schedule import AutoScheduleRepository


def _row() -> SimpleNamespace:
    return SimpleNamespace(
        id=7,
        user_id="u1",
        name="盘中自动",
        recipe_id="intraday_multi",
        days_of_week="mon-fri",
        times=["09:35", "14:00"],
        enabled=True,
        last_run_at=None,
        last_message=None,
        last_success=None,
        created_at="2026-08-19 10:00:00",
        updated_at="2026-08-19 10:00:00",
    )


def test_repo_create_task_generates_fields() -> None:
    db = MagicMock()
    repo = AutoScheduleRepository(db, "u1")
    repo.create_task(
        name="盘中自动",
        recipe_id="intraday_multi",
        days_of_week="mon-fri",
        times=["09:35", "14:00"],
    )
    added = db.add.call_args.args[0]
    assert isinstance(added, AutoSchedule)
    assert added.user_id == "u1"
    assert added.name == "盘中自动"
    assert added.recipe_id == "intraday_multi"
    assert added.days_of_week == "mon-fri"
    assert added.times == ["09:35", "14:00"]
    assert added.enabled is True
    assert added.last_success is None


def test_repo_get_any_cross_user() -> None:
    db = MagicMock()
    db.get.return_value = _row()
    repo = AutoScheduleRepository(db, "u-other")
    out = repo.get_any(7)
    assert out is not None
    assert out.id == 7
    assert db.get.call_args.args[0] is AutoSchedule
    assert db.get.call_args.args[1] == 7


def test_repo_to_out_maps() -> None:
    repo = AutoScheduleRepository(MagicMock(), "u1")
    out = repo.to_out(_row())
    assert out.id == 7
    assert out.name == "盘中自动"
    assert out.times == ["09:35", "14:00"]
    assert out.last_success is None


def test_repo_update_partial() -> None:
    db = MagicMock()
    row = _row()
    db.scalar.return_value = row
    db.refresh.side_effect = lambda _: None
    repo = AutoScheduleRepository(db, "u1")
    out = repo.update_task(7, {"times": ["09:35"]})
    assert out is row
    assert row.times == ["09:35"]
    db.commit.assert_called_once()
