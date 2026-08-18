from unittest.mock import MagicMock, patch

from app.schemas.ops import SchedulerConfigOut
from app.services.ops import scheduler as ops_scheduler


def test_run_hints_have_no_zak_cli() -> None:
    db = MagicMock()
    with (
        patch.object(ops_scheduler, "load_scheduler_config", return_value=SchedulerConfigOut(id="default", config={})),
        patch.object(ops_scheduler, "load_job_run_meta", return_value=None),
    ):
        rows = {r.job_id: r for r in ops_scheduler.list_scheduler_jobs(db)}
    assert "zak CLI" not in (rows["enrich_market_quotes"].run_hint or "")
    assert "collector" in (rows["collect_quotes"].run_hint or "").lower() or "quote_collector" in (
        rows["collect_quotes"].run_hint or ""
    )
    assert rows["purge_stale_cache"].run_hint is None
