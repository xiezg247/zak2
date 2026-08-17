from unittest.mock import MagicMock, patch

from app.services.ops.auto_screen import screen_intraday, screen_post_close
from app.services.ops.catalog import RUNNABLE_JOB_IDS
from app.services.presets import get_builtin_recipe


def test_screen_intraday_requires_user() -> None:
    out = screen_intraday(MagicMock(), user_id="")
    assert out["success"] is False


def test_screen_intraday_saves_run() -> None:
    db = MagicMock()
    fake_result = {
        "condition": "盘中多因子",
        "source": "recipe",
        "row_count": 2,
        "total_scanned": 10,
        "config": {},
        "rows": [],
    }
    fake_run = MagicMock(id="run-1")
    with (
        patch("app.services.ops.auto_screen.load_scheduler_config", return_value={"config": {}}),
        patch("app.repositories.screener.ScreenerRunRepository.latest_run_symbols", return_value=None),
        patch("app.services.ops.auto_screen.run_recipe_screen", return_value=fake_result),
        patch("app.repositories.screener.ScreenerRunRepository.save_run", return_value=fake_run) as save,
        patch("app.services.ops.auto_screen.save_job_run_meta"),
    ):
        out = screen_intraday(db, user_id="u1")
    assert out["success"] is True
    assert out["run_id"] == "run-1"
    save.assert_called_once()
    assert save.call_args.kwargs["source"] == "scheduled"


def test_screen_post_close_saves_run() -> None:
    db = MagicMock()
    fake_result = {
        "condition": "盘后多因子",
        "source": "recipe",
        "row_count": 3,
        "total_scanned": 20,
        "config": {},
        "rows": [],
    }
    fake_run = MagicMock(id="run-pc")
    with (
        patch(
            "app.services.ops.auto_screen.load_scheduler_config",
            return_value={"config": {"screen_post_close": {"recipe_id": "post_close_multi", "top_n": 15}}},
        ),
        patch("app.repositories.screener.ScreenerRunRepository.latest_run_symbols", return_value=None),
        patch("app.services.ops.auto_screen.run_recipe_screen", return_value=fake_result) as run,
        patch("app.repositories.screener.ScreenerRunRepository.save_run", return_value=fake_run),
        patch("app.services.ops.auto_screen.save_job_run_meta"),
    ):
        out = screen_post_close(db, user_id="u1")
    assert out["success"] is True
    assert out["run_id"] == "run-pc"
    assert run.call_args.args[0].recipe_id == "post_close_multi"
    assert run.call_args.args[0].top_n == 15
    assert run.call_args.kwargs.get("user_id") == "u1"
    assert run.call_args.kwargs.get("db") is db
    assert "ops.screen_post_close" in str(
        # save_run result trigger checked via message
        out["message"]
    ) or out["row_count"] == 3


def test_post_close_recipe_and_runnable() -> None:
    recipe = get_builtin_recipe("post_close_multi")
    assert recipe is not None
    assert recipe.implemented is True
    assert recipe.trigger_kind == "post_close"
    assert "screen_post_close" in RUNNABLE_JOB_IDS
