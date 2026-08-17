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
from app.schemas.market import RadarCardOut
from app.services import radar_resonance as rr


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


def test_merge_weights_defaults() -> None:
    m = rr.merge_weights(None)
    assert m["leader_pick"] == 1.5
    assert m["sector_flow_hot"] == 0.0


def test_merge_weights_override() -> None:
    m = rr.merge_weights({"leader_pick": 3, "sector_flow_hot": 9})
    assert m["leader_pick"] == 3.0
    assert m["sector_flow_hot"] == 0.0  # 不可编，忽略覆盖


def test_validate_put_ok() -> None:
    out = rr.validate_put_weights({"leader_pick": 2.5, "discovery_limit_ladder": 1})
    assert out["leader_pick"] == 2.5
    assert "sector_flow_hot" not in out


def test_validate_put_rejects_unknown() -> None:
    with pytest.raises(ValueError, match="未知"):
        rr.validate_put_weights({"no_such_card": 1})


def test_validate_put_rejects_oob() -> None:
    with pytest.raises(ValueError, match="范围"):
        rr.validate_put_weights({"leader_pick": 6})


def test_validate_put_rejects_nan() -> None:
    with pytest.raises(ValueError, match="有限"):
        rr.validate_put_weights({"leader_pick": float("nan")})
    with pytest.raises(ValueError, match="有限"):
        rr.validate_put_weights({"leader_pick": float("inf")})


def test_merge_weights_clamps_oob_and_skips_nan() -> None:
    m = rr.merge_weights({"leader_pick": 9, "discovery_change_top": float("nan")})
    assert m["leader_pick"] == 5.0
    assert m["discovery_change_top"] == rr.CARD_WEIGHTS["discovery_change_top"]


def test_compute_resonance_custom_weights() -> None:
    cards = [
        RadarCardOut(
            card_id="leader_pick",
            title="龙头",
            source="synthesized",
            rows=[{"vt_symbol": "600519.SSE", "name": "茅台"}],
        ),
        RadarCardOut(
            card_id="discovery_change_top",
            title="涨幅",
            source="cache",
            rows=[{"vt_symbol": "600519.SSE", "name": "茅台"}],
        ),
    ]
    low = rr.compute_resonance(
        cards, min_cards=1, top_n=5, weights={**rr.CARD_WEIGHTS, "leader_pick": 0.1, "discovery_change_top": 0.1}
    )
    high = rr.compute_resonance(
        cards, min_cards=1, top_n=5, weights={**rr.CARD_WEIGHTS, "leader_pick": 5.0, "discovery_change_top": 5.0}
    )
    assert high.entries[0].resonance_score > low.entries[0].resonance_score


def test_weights_payload_items_only_editable() -> None:
    merged = rr.merge_weights({"leader_pick": 2})
    payload = rr.weights_payload(merged)
    ids = {i.card_id for i in payload.items}
    assert "leader_pick" in ids
    assert "sector_flow_hot" not in ids
    assert payload.weights["leader_pick"] == 2.0


def test_meta_key() -> None:
    assert rr.meta_key("u1") == "radar/resonance_weights/u1"


def test_save_empty_deletes() -> None:
    db = MagicMock()
    out = rr.save_user_weights(db, "u1", {})
    db.execute.assert_called_once()
    sql = str(db.execute.call_args[0][0])
    assert "DELETE" in sql.upper()
    assert db.commit.called
    assert out["leader_pick"] == 1.5


def test_save_upserts_editable_subset() -> None:
    db = MagicMock()
    out = rr.save_user_weights(db, "u1", {"leader_pick": 2.5})
    db.execute.assert_called_once()
    sql = str(db.execute.call_args[0][0])
    assert "INSERT" in sql.upper()
    params = db.execute.call_args[0][1]
    assert params["k"] == "radar/resonance_weights/u1"
    stored = json.loads(params["v"])
    assert stored["leader_pick"] == 2.5
    assert "discovery_limit_ladder" in stored
    assert "sector_flow_hot" not in stored
    assert db.commit.called
    assert out["leader_pick"] == 2.5


def test_load_user_weights_missing() -> None:
    db = MagicMock()
    db.execute.return_value.scalar.return_value = None
    out = rr.load_user_weights(db, "u1")
    assert out == rr.merge_weights(None)


def test_load_user_weights_from_meta() -> None:
    db = MagicMock()
    db.execute.return_value.scalar.return_value = json.dumps({"leader_pick": 3})
    out = rr.load_user_weights(db, "u1")
    assert out["leader_pick"] == 3.0


def test_get_resonance_weights_api() -> None:
    user = _make_user()
    client = _api_client(user)
    merged = rr.merge_weights({"leader_pick": 2.5})
    with patch("app.api.v1.market.resonance_svc.load_user_weights", return_value=merged):
        resp = client.get("/api/v1/radar/resonance/weights")
    assert resp.status_code == 200
    body = resp.json()
    assert body["data"]["weights"]["leader_pick"] == 2.5
    assert any(i["card_id"] == "leader_pick" for i in body["data"]["items"])
    assert all(i["card_id"] != "sector_flow_hot" for i in body["data"]["items"])


def test_put_resonance_weights_api_ok() -> None:
    user = _make_user()
    client = _api_client(user)
    merged = rr.merge_weights({"leader_pick": 3})
    with patch(
        "app.api.v1.market.resonance_svc.save_user_weights",
        return_value=merged,
    ) as save:
        resp = client.put(
            "/api/v1/radar/resonance/weights",
            json={"weights": {"leader_pick": 3}},
        )
    assert resp.status_code == 200
    save.assert_called_once()
    assert save.call_args[0][1] == str(user.id)
    assert resp.json()["data"]["weights"]["leader_pick"] == 3.0


def test_put_resonance_weights_api_reset() -> None:
    user = _make_user()
    client = _api_client(user)
    merged = rr.merge_weights(None)
    with patch(
        "app.api.v1.market.resonance_svc.save_user_weights",
        return_value=merged,
    ) as save:
        resp = client.put("/api/v1/radar/resonance/weights", json={"weights": {}})
    assert resp.status_code == 200
    save.assert_called_once_with(save.call_args[0][0], str(user.id), {})
    assert resp.json()["data"]["weights"]["leader_pick"] == rr.CARD_WEIGHTS["leader_pick"]


def test_put_resonance_weights_api_bad_request() -> None:
    client = _api_client()
    with patch(
        "app.api.v1.market.resonance_svc.save_user_weights",
        side_effect=ValueError("权重超出范围 [0, 5]"),
    ):
        resp = client.put(
            "/api/v1/radar/resonance/weights",
            json={"weights": {"leader_pick": 9}},
        )
    assert resp.status_code == 400
    assert "范围" in resp.json()["detail"]
