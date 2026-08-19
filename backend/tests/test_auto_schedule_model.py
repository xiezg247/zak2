from __future__ import annotations

from app.models.auto_schedule import AutoSchedule


def test_model_columns() -> None:
    cols = AutoSchedule.__table__.columns
    assert "id" in cols
    assert "user_id" in cols
    assert "name" in cols
    assert "recipe_id" in cols
    assert "days_of_week" in cols
    assert "times" in cols
    assert "enabled" in cols
    assert "last_run_at" in cols
    assert "last_message" in cols
    assert "last_success" in cols
    assert "created_at" in cols
    assert "updated_at" in cols
    assert cols["id"].autoincrement is not False
