from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.schemas.ops import SyncResult
from app.services.ops.auto_schedule import run_task
from app.worker.tasks_auto_schedule import run_auto_schedule_task


def _task(*, enabled: bool = True) -> SimpleNamespace:
    return SimpleNamespace(
        id=7,
        user_id="u1",
        name="盘中自动",
        recipe_id="intraday_multi",
        days_of_week="mon-fri",
        times=["09:35"],
        enabled=enabled,
        last_run_at=None,
        last_message=None,
        last_success=None,
    )


def test_run_task_missing() -> None:
    db = MagicMock()
    with patch("app.repositories.auto_schedule.AutoScheduleRepository.get_any", return_value=None):
        out = run_task(db, 99)
    assert out.success is False
    assert out.skipped is True


def test_run_task_disabled() -> None:
    db = MagicMock()
    with patch("app.repositories.auto_schedule.AutoScheduleRepository.get_any", return_value=_task(enabled=False)):
        out = run_task(db, 7)
    assert out.success is False
    assert out.skipped is True


def test_run_task_success() -> None:
    db = MagicMock()
    fake_result = {
        "condition": "盘中多因子",
        "row_count": 2,
        "total_scanned": 10,
        "config": {},
        "rows": [],
    }
    fake_run = MagicMock(id="run-a")
    task = _task()
    with (
        patch("app.repositories.auto_schedule.AutoScheduleRepository.get_any", return_value=task),
        patch("app.repositories.screener.ScreenerRunRepository.latest_run_symbols", return_value=None),
        patch("app.services.ops.auto_schedule.run_recipe_screen", return_value=fake_result),
        patch("app.repositories.screener.ScreenerRunRepository.save_run", return_value=fake_run) as save,
        patch("app.services.ops.auto_schedule.notify_delivery.deliver_text") as deliver,
    ):
        out = run_task(db, 7)
    assert out.success is True
    assert out.extra["run_id"] == "run-a"
    assert task.last_success is True
    assert "盘中多因子" in task.last_message
    save.assert_called_once()
    assert save.call_args.kwargs["source"] == "auto_schedule"
    deliver.assert_called_once()
    assert deliver.call_args.kwargs["user_id"] == "u1"
    assert deliver.call_args.kwargs["event_type"] == "auto_schedule.7"


def test_run_task_unknown_recipe() -> None:
    db = MagicMock()
    task = _task()
    task.recipe_id = "nope"
    with (
        patch("app.repositories.auto_schedule.AutoScheduleRepository.get_any", return_value=task),
        patch("app.services.ops.auto_schedule.run_recipe_screen"),
    ):
        out = run_task(db, 7)
    assert out.success is False
    assert task.last_success is False
    assert "未知" in task.last_message


def test_run_task_push_failure_does_not_raise() -> None:
    db = MagicMock()
    fake_result = {"condition": "盘中多因子", "row_count": 0, "total_scanned": 10, "config": {}, "rows": []}
    fake_run = MagicMock(id="run-b")
    task = _task()
    with (
        patch("app.repositories.auto_schedule.AutoScheduleRepository.get_any", return_value=task),
        patch("app.repositories.screener.ScreenerRunRepository.latest_run_symbols", return_value=None),
        patch("app.services.ops.auto_schedule.run_recipe_screen", return_value=fake_result),
        patch("app.repositories.screener.ScreenerRunRepository.save_run", return_value=fake_run),
        patch(
            "app.services.ops.auto_schedule.notify_delivery.deliver_text",
            side_effect=Exception("db down"),
        ),
    ):
        out = run_task(db, 7)
    assert out.success is True


def test_worker_task_returns_dict() -> None:
    async def _go() -> dict:
        with patch(
            "app.worker.tasks_auto_schedule.ops_auto_schedule.run_task",
            return_value=SyncResult(success=True, message="ok"),
        ):
            return await run_auto_schedule_task({}, task_id="7")

    out = asyncio.run(_go())
    assert out["success"] is True
