from unittest.mock import MagicMock, patch

from app.services.ops_scheduler import job_kind_for, list_scheduler_jobs


def test_job_kind_mapping() -> None:
    assert job_kind_for("purge_stale_cache") == "runnable"
    assert job_kind_for("collect_quotes") == "process"
    assert job_kind_for("enrich_market_quotes") == "planned"


def test_list_jobs_includes_job_kind() -> None:
    db = MagicMock()
    with patch("app.services.ops_scheduler.load_scheduler_config", return_value={"config": {}}), patch(
        "app.services.ops_scheduler.load_job_run_meta", return_value=None
    ):
        rows = {r["job_id"]: r for r in list_scheduler_jobs(db)}
    assert rows["collect_quotes"]["job_kind"] == "process"
    assert rows["purge_stale_cache"]["job_kind"] == "runnable"
    assert rows["enrich_market_quotes"]["job_kind"] == "planned"
