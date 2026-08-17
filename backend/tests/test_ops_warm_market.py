from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.services.ops import warm_market as warm


def test_warm_market_summary_success() -> None:
    db = MagicMock()
    snap = SimpleNamespace(stage="startup", stage_label="启动", source="redis")
    with (
        patch("app.services.ops.warm_market.build_emotion_cycle", return_value=snap) as build,
        patch("app.services.ops.warm_market.save_job_run_meta") as save_meta,
    ):
        out = warm.warm_market_summary(db)

    build.assert_called_once_with(db, force=True)
    save_meta.assert_called_once_with(
        db,
        warm.JOB_ID,
        last_message="已预热情绪周期：启动",
        last_success=True,
    )
    assert out.success is True
    assert out.message == "已预热情绪周期：启动"
    assert out.extra["stage"] == "startup"
    assert out.extra["stage_label"] == "启动"
    assert out.extra["source"] == "redis"
