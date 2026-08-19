from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

from app.services.ops.auto_schedule import poll_due_tasks


def test_poll_enqueues_matching_tasks() -> None:
    db = MagicMock()
    now = datetime(2026, 8, 17, 9, 35)  # 周一 09:35
    task = MagicMock()
    task.id = 7
    task.enabled = True
    task.days_of_week = "mon-fri"
    task.times = ["09:35"]
    db.scalars.return_value.all.return_value = [task]
    with patch(
        "app.services.ops.auto_schedule.enqueue_auto_task_sync", return_value="auto:7"
    ) as enqueue:
        out = poll_due_tasks(db, now)
    assert out == [{"task_id": "7", "arq_id": "auto:7"}]
    enqueue.assert_called_once_with("7")


def test_poll_skips_non_matching() -> None:
    db = MagicMock()
    now = datetime(2026, 8, 17, 9, 35)  # 周一 09:35
    task = MagicMock()
    task.enabled = True
    task.days_of_week = "mon-fri"
    task.times = ["10:00"]
    db.scalars.return_value.all.return_value = [task]
    with patch("app.services.ops.auto_schedule.enqueue_auto_task_sync") as enqueue:
        out = poll_due_tasks(db, now)
    assert out == []
    enqueue.assert_not_called()


def test_poll_skips_disabled() -> None:
    db = MagicMock()
    now = datetime(2026, 8, 17, 9, 35)
    task = MagicMock()
    task.enabled = False
    task.days_of_week = "mon-fri"
    task.times = ["09:35"]
    db.scalars.return_value.all.return_value = [task]
    with patch("app.services.ops.auto_schedule.enqueue_auto_task_sync") as enqueue:
        out = poll_due_tasks(db, now)
    assert out == []
    enqueue.assert_not_called()


def test_poll_continues_on_enqueue_error() -> None:
    db = MagicMock()
    now = datetime(2026, 8, 17, 9, 35)
    ok_task = MagicMock()
    ok_task.id = 2
    ok_task.enabled = True
    ok_task.days_of_week = "mon-fri"
    ok_task.times = ["09:35"]
    bad_task = MagicMock()
    bad_task.id = 1
    bad_task.enabled = True
    bad_task.days_of_week = "mon-fri"
    bad_task.times = ["09:35"]
    db.scalars.return_value.all.return_value = [bad_task, ok_task]

    def _side_effect(task_id: str) -> str:
        if task_id == "1":
            raise RuntimeError("redis down")
        return f"auto:{task_id}"

    with patch(
        "app.services.ops.auto_schedule.enqueue_auto_task_sync", side_effect=_side_effect
    ) as enqueue:
        out = poll_due_tasks(db, now)
    assert out == [{"task_id": "2", "arq_id": "auto:2"}]
    assert enqueue.call_count == 2
