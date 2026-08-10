from unittest.mock import MagicMock, patch

from app.services import ops_scheduler


def test_list_merges_default_cron() -> None:
    db = MagicMock()
    with patch.object(ops_scheduler, "load_scheduler_config", return_value={"config": {}}), patch.object(
        ops_scheduler, "load_job_run_meta", return_value=None
    ):
        rows = {r["job_id"]: r for r in ops_scheduler.list_scheduler_jobs(db)}
    assert rows["purge_stale_cache"]["cron_hour"] == 19
    assert rows["purge_stale_cache"]["cron_minute"] == 15
    assert rows["screen_intraday"]["cron_hours"] == "10,14"
    assert rows["sync_bilibili_feed"]["cron_hours"] == ",".join(map(str, range(8, 20)))
    assert rows["sync_bilibili_feed"]["cron_minute"] == 15
    assert rows["sync_bilibili_feed"]["runnable"] is True
