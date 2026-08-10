from __future__ import annotations

import json
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.core.db import get_db
from app.core.security import hash_password
from app.main import create_app
from app.models.user import User
from app.services import recipe_weights as rw


def test_normalize_sums_to_one() -> None:
    out = rw.normalize_weights(
        "intraday_multi",
        {"momentum": 2, "turnover": 2, "volume_ratio": 2, "surge": 2},
    )
    assert abs(sum(out.values()) - 1.0) < 1e-6
    assert all(abs(v - 0.25) < 1e-4 for v in out.values())


def test_normalize_rejects_unknown_key() -> None:
    with pytest.raises(ValueError):
        rw.normalize_weights("intraday_multi", {"nope": 1})


def test_normalize_rejects_all_zero() -> None:
    with pytest.raises(ValueError):
        rw.normalize_weights(
            "intraday_multi",
            {k: 0 for k in rw.DEFAULT_WEIGHTS["intraday_multi"]},
        )


def test_normalize_rejects_invalid_recipe() -> None:
    with pytest.raises(ValueError, match="配方"):
        rw.normalize_weights("radar_leader", {"momentum": 1})


def test_normalize_rejects_nan() -> None:
    with pytest.raises(ValueError, match="有限"):
        rw.normalize_weights("intraday_multi", {"momentum": float("nan")})


def test_normalize_rejects_negative() -> None:
    with pytest.raises(ValueError, match="负数"):
        rw.normalize_weights("intraday_multi", {"momentum": -1})


def test_meta_key() -> None:
    assert rw.meta_key("u1") == "screener/recipe_weights/u1"


def test_default_weights_sum_to_one() -> None:
    for recipe_id in rw.EDITABLE_RECIPES:
        total = sum(rw.DEFAULT_WEIGHTS[recipe_id].values())
        assert abs(total - 1.0) < 1e-6


def test_ultra_short_in_editable_recipes() -> None:
    assert "ultra_short_unified" in rw.EDITABLE_RECIPES


def test_normalize_ultra_short_defaults_sum_to_one() -> None:
    defaults = rw.DEFAULT_WEIGHTS["ultra_short_unified"]
    out = rw.normalize_weights("ultra_short_unified", defaults)
    assert abs(sum(out.values()) - 1.0) < 1e-6
    assert out == defaults


def test_save_merge_submitted_over_defaults_then_normalize() -> None:
    db = MagicMock()
    db.execute.return_value.scalar.return_value = None
    out = rw.save_recipe_weights(
        db,
        "u1",
        "intraday_multi",
        {"momentum": 4, "turnover": 1, "volume_ratio": 1, "surge": 1},
    )
    assert abs(sum(out.values()) - 1.0) < 1e-3  # 四位小数舍入误差
    params = db.execute.call_args[0][1]
    stored = json.loads(params["v"])
    assert "intraday_multi" in stored
    assert stored["intraday_multi"]["momentum"] == out["momentum"]
    assert db.commit.called


def test_save_partial_override_keeps_other_defaults() -> None:
    db = MagicMock()
    db.execute.return_value.scalar.return_value = None
    out = rw.save_recipe_weights(db, "u1", "intraday_multi", {"momentum": 1})
    defaults = rw.DEFAULT_WEIGHTS["intraday_multi"]
    merged_raw = {
        "momentum": 1.0,
        "turnover": defaults["turnover"],
        "volume_ratio": defaults["volume_ratio"],
        "surge": defaults["surge"],
    }
    expected = rw.normalize_weights("intraday_multi", merged_raw)
    assert out == expected


def test_save_empty_deletes_recipe_override() -> None:
    db = MagicMock()
    db.execute.return_value.scalar.return_value = json.dumps(
        {
            "intraday_multi": {"momentum": 0.5, "turnover": 0.2, "volume_ratio": 0.2, "surge": 0.1},
            "post_close_multi": {"moneyflow": 0.4, "momentum": 0.3, "turnover": 0.2, "valuation": 0.1},
        }
    )
    out = rw.save_recipe_weights(db, "u1", "intraday_multi", {})
    sql = str(db.execute.call_args[0][0])
    assert "INSERT" in sql.upper()
    params = db.execute.call_args[0][1]
    stored = json.loads(params["v"])
    assert "intraday_multi" not in stored
    assert "post_close_multi" in stored
    assert out == rw.DEFAULT_WEIGHTS["intraday_multi"]
    assert db.commit.called


def test_save_empty_deletes_whole_meta_when_last_recipe() -> None:
    db = MagicMock()
    db.execute.return_value.scalar.return_value = json.dumps(
        {
            "intraday_multi": {"momentum": 0.5, "turnover": 0.2, "volume_ratio": 0.2, "surge": 0.1},
        }
    )
    rw.save_recipe_weights(db, "u1", "intraday_multi", {})
    sql = str(db.execute.call_args[0][0])
    assert "DELETE" in sql.upper()
    assert db.commit.called


def test_load_recipe_weights_missing() -> None:
    db = MagicMock()
    db.execute.return_value.scalar.return_value = None
    out = rw.load_recipe_weights(db, "u1", "intraday_multi")
    assert out == rw.DEFAULT_WEIGHTS["intraday_multi"]


def test_load_recipe_weights_from_meta() -> None:
    db = MagicMock()
    db.execute.return_value.scalar.return_value = json.dumps(
        {
            "intraday_multi": {
                "momentum": 0.4,
                "turnover": 0.2,
                "volume_ratio": 0.2,
                "surge": 0.2,
            }
        }
    )
    out = rw.load_recipe_weights(db, "u1", "intraday_multi")
    assert out["momentum"] == 0.4
    assert abs(sum(out.values()) - 1.0) < 1e-6


def test_weights_payload() -> None:
    merged = rw.DEFAULT_WEIGHTS["post_close_multi"]
    payload = rw.weights_payload("post_close_multi", merged)
    assert payload["recipe_id"] == "post_close_multi"
    assert len(payload["items"]) == 4
    assert payload["items"][0]["label"] == "资金"
    assert payload["weights"] == merged


def test_normalize_last_key_compensation_sums_exactly_one() -> None:
    out = rw.normalize_weights(
        "intraday_multi",
        {"momentum": 1, "turnover": 1, "volume_ratio": 1, "surge": 1},
    )
    assert sum(out.values()) == 1.0


# --- engine scoring ---


def test_score_intraday_custom_weights_changes_ranking() -> None:
    from app.services.engine import _score_intraday_multi
    from app.services.quotes import QuoteRow

    high_mom = QuoteRow(
        symbol="A",
        change_pct=9.0,
        turnover_rate=1.0,
        volume_ratio=1.0,
        amount=1e7,
    )
    high_turn = QuoteRow(
        symbol="B",
        change_pct=1.0,
        turnover_rate=14.0,
        volume_ratio=1.0,
        amount=1e7,
    )
    default_a = _score_intraday_multi(high_mom)
    default_b = _score_intraday_multi(high_turn)
    assert default_a > default_b

    turn_heavy = {"momentum": 0.05, "turnover": 0.8, "volume_ratio": 0.1, "surge": 0.05}
    assert _score_intraday_multi(high_turn, turn_heavy) > _score_intraday_multi(high_mom, turn_heavy)


def test_score_ultra_short_custom_weights_changes_ranking() -> None:
    from app.services.engine import _score_ultra_short
    from app.services.quotes import QuoteRow

    high_board = QuoteRow(
        symbol="A",
        limit_times=3,
        change_pct=1.0,
        turnover_rate=1.0,
    )
    high_mom = QuoteRow(
        symbol="B",
        limit_times=0,
        change_pct=9.0,
        turnover_rate=1.0,
    )
    default_a = _score_ultra_short(high_board)
    default_b = _score_ultra_short(high_mom)
    assert default_a > default_b

    mom_heavy = {"board": 0.05, "momentum": 0.85, "turnover": 0.1}
    assert _score_ultra_short(high_mom, mom_heavy) > _score_ultra_short(high_board, mom_heavy)


def test_run_recipe_screen_loads_user_weights() -> None:
    from app.schemas.screener import HardFilterPrefs, RecipeRunRequest
    from app.services.engine import run_recipe_screen
    from app.services.quotes import QuoteRow

    class _Store:
        def available(self) -> bool:
            return True

        def meta(self) -> dict:
            return {"quote_count": 2, "available": True}

        def load_ranked_quotes(self, field: str, *, pool: int = 500) -> list[QuoteRow]:
            _ = field, pool
            return [
                QuoteRow(symbol="SHSE.A", name="动量强", change_pct=9.0, turnover_rate=1.0, volume_ratio=1.0, amount=1e7),
                QuoteRow(symbol="SHSE.B", name="换手强", change_pct=1.0, turnover_rate=14.0, volume_ratio=1.0, amount=1e7),
            ]

    custom = {"momentum": 0.05, "turnover": 0.8, "volume_ratio": 0.1, "surge": 0.05}
    db = MagicMock()
    with patch(
        "app.services.engine.recipe_weights_svc.load_recipe_weights",
        return_value=custom,
    ) as load:
        result = run_recipe_screen(
            RecipeRunRequest(
                recipe_id="intraday_multi",
                top_n=2,
                hard_filter=HardFilterPrefs(min_amount_wan=0, min_total_mv_yi=0),
            ),
            store=_Store(),  # type: ignore[arg-type]
            db=db,
            user_id="u1",
        )
    load.assert_called_once_with(db, "u1", "intraday_multi")
    assert result["rows"][0]["symbol"] == "SHSE.B"


def test_run_recipe_screen_loads_ultra_short_user_weights() -> None:
    from app.schemas.screener import HardFilterPrefs, RecipeRunRequest
    from app.services.engine import run_recipe_screen
    from app.services.quotes import QuoteRow

    class _Store:
        def available(self) -> bool:
            return True

        def meta(self) -> dict:
            return {"quote_count": 2, "available": True}

        def load_ranked_quotes(self, field: str, *, pool: int = 500) -> list[QuoteRow]:
            _ = field, pool
            return [
                QuoteRow(symbol="SHSE.A", name="连板强", limit_times=3, change_pct=1.0, turnover_rate=1.0),
                QuoteRow(symbol="SHSE.B", name="动量强", limit_times=0, change_pct=9.0, turnover_rate=1.0),
            ]

    custom = {"board": 0.05, "momentum": 0.85, "turnover": 0.1}
    db = MagicMock()
    with patch(
        "app.services.engine.recipe_weights_svc.load_recipe_weights",
        return_value=custom,
    ) as load:
        result = run_recipe_screen(
            RecipeRunRequest(
                recipe_id="ultra_short_unified",
                top_n=2,
                hard_filter=HardFilterPrefs(min_amount_wan=0, min_total_mv_yi=0),
            ),
            store=_Store(),  # type: ignore[arg-type]
            db=db,
            user_id="u1",
        )
    load.assert_called_once_with(db, "u1", "ultra_short_unified")
    assert result["rows"][0]["symbol"] == "SHSE.B"


# --- API ---


def _make_user() -> User:
    now = datetime.now(UTC)
    return User(
        id=str(uuid4()),
        username="demo",
        display_name="Demo",
        password_hash=hash_password("demo-pass"),
        is_active=True,
        created_at=now,
        updated_at=now,
    )


def _api_client(user: User | None = None) -> TestClient:
    app = create_app()
    u = user or _make_user()

    def override_db():  # type: ignore[no-untyped-def]
        yield MagicMock()

    def override_user():  # type: ignore[no-untyped-def]
        return u

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user
    return TestClient(app)


def test_get_recipe_weights_api() -> None:
    user = _make_user()
    client = _api_client(user)
    merged = rw.DEFAULT_WEIGHTS["intraday_multi"]
    with patch("app.api.v1.screener.recipe_weights_svc.load_recipe_weights", return_value=merged):
        resp = client.get("/api/v1/screener/recipes/intraday_multi/weights")
    assert resp.status_code == 200
    body = resp.json()
    assert body["recipe_id"] == "intraday_multi"
    assert body["weights"]["momentum"] == 0.35
    assert any(i["key"] == "momentum" and i["label"] == "动量" for i in body["items"])


def test_get_recipe_weights_api_ultra_short() -> None:
    user = _make_user()
    client = _api_client(user)
    merged = rw.DEFAULT_WEIGHTS["ultra_short_unified"]
    with patch("app.api.v1.screener.recipe_weights_svc.load_recipe_weights", return_value=merged):
        resp = client.get("/api/v1/screener/recipes/ultra_short_unified/weights")
    assert resp.status_code == 200
    body = resp.json()
    assert body["recipe_id"] == "ultra_short_unified"
    assert body["weights"]["board"] == 0.4
    assert any(i["key"] == "board" and i["label"] == "连板" for i in body["items"])


def test_get_recipe_weights_api_bad_recipe() -> None:
    client = _api_client()
    resp = client.get("/api/v1/screener/recipes/radar_leader/weights")
    assert resp.status_code == 400
    assert "配方" in resp.json()["detail"]


def test_put_recipe_weights_api_ok() -> None:
    user = _make_user()
    client = _api_client(user)
    merged = rw.normalize_weights(
        "intraday_multi",
        {"momentum": 4, "turnover": 2, "volume_ratio": 2, "surge": 2},
    )
    with patch(
        "app.api.v1.screener.recipe_weights_svc.save_recipe_weights",
        return_value=merged,
    ) as save:
        resp = client.put(
            "/api/v1/screener/recipes/intraday_multi/weights",
            json={"weights": {"momentum": 4, "turnover": 2, "volume_ratio": 2, "surge": 2}},
        )
    assert resp.status_code == 200
    save.assert_called_once()
    assert save.call_args[0][1] == str(user.id)
    assert abs(sum(resp.json()["weights"].values()) - 1.0) < 1e-6


def test_put_recipe_weights_api_reset() -> None:
    user = _make_user()
    client = _api_client(user)
    merged = rw.DEFAULT_WEIGHTS["post_close_multi"]
    with patch(
        "app.api.v1.screener.recipe_weights_svc.save_recipe_weights",
        return_value=merged,
    ) as save:
        resp = client.put(
            "/api/v1/screener/recipes/post_close_multi/weights",
            json={"weights": {}},
        )
    assert resp.status_code == 200
    save.assert_called_once_with(save.call_args[0][0], str(user.id), "post_close_multi", {})
    assert resp.json()["weights"] == merged


def test_put_recipe_weights_api_bad_request() -> None:
    client = _api_client()
    with patch(
        "app.api.v1.screener.recipe_weights_svc.save_recipe_weights",
        side_effect=ValueError("未知因子：nope"),
    ):
        resp = client.put(
            "/api/v1/screener/recipes/intraday_multi/weights",
            json={"weights": {"nope": 1}},
        )
    assert resp.status_code == 400
    assert "因子" in resp.json()["detail"]
