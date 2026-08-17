from __future__ import annotations

import json
from unittest.mock import MagicMock

from app.services import emotion_thresholds as et
from app.services.emotion_cycle import DEFAULT_THRESHOLDS, Thresholds


def test_thresholds_fields_match_dataclass() -> None:
    assert set(et.THRESHOLDS_FIELDS) == {f.name for f in Thresholds.__dataclass_fields__.values()}


def test_thresholds_to_dict_roundtrip() -> None:
    d = et.thresholds_to_dict(DEFAULT_THRESHOLDS)
    assert d["recession_limit_down"] == DEFAULT_THRESHOLDS.recession_limit_down
    assert d["hysteresis_enabled"] is True
    assert set(d) == set(et.THRESHOLDS_FIELDS)


def test_merge_partial() -> None:
    t = et.merge_thresholds(DEFAULT_THRESHOLDS, {"recession_limit_down": 30})
    assert t.recession_limit_down == 30
    assert t.ice_max_boards == DEFAULT_THRESHOLDS.ice_max_boards


def test_merge_ignores_unknown_keys() -> None:
    t = et.merge_thresholds(DEFAULT_THRESHOLDS, {"nope": 99, "recession_limit_down": 25})
    assert t.recession_limit_down == 25
    assert not hasattr(t, "nope")


def test_merge_clamps_int_and_ratios() -> None:
    t = et.merge_thresholds(
        DEFAULT_THRESHOLDS,
        {
            "recession_limit_down": -5,
            "ice_up_ratio_max": 1.5,
            "recession_break_rate": -0.1,
            "fear_greed_overheat": 150,
        },
    )
    assert t.recession_limit_down == 0
    assert t.ice_up_ratio_max == 1.0
    assert t.recession_break_rate == 0.0
    assert t.fear_greed_overheat == 100.0


def test_merge_clamps_amount_floor() -> None:
    t = et.merge_thresholds(DEFAULT_THRESHOLDS, {"amount_floor_yuan": -1e9})
    assert t.amount_floor_yuan == 0.0


def test_merge_bool_hysteresis() -> None:
    t = et.merge_thresholds(DEFAULT_THRESHOLDS, {"hysteresis_enabled": False})
    assert t.hysteresis_enabled is False


def test_merge_skips_invalid_values() -> None:
    t = et.merge_thresholds(
        DEFAULT_THRESHOLDS,
        {"recession_limit_down": "bad", "startup_limit_up": float("nan")},
    )
    assert t == DEFAULT_THRESHOLDS


def test_load_default_when_empty() -> None:
    db = MagicMock()
    db.execute.return_value.scalar.return_value = None
    t, is_def = et.load_thresholds(db)
    assert is_def is True
    assert t == DEFAULT_THRESHOLDS


def test_load_invalid_json_returns_default() -> None:
    db = MagicMock()
    db.execute.return_value.scalar.return_value = "not-json"
    t, is_def = et.load_thresholds(db)
    assert is_def is True
    assert t == DEFAULT_THRESHOLDS


def test_load_from_meta_merges_partial() -> None:
    db = MagicMock()
    db.execute.return_value.scalar.return_value = json.dumps({"recession_limit_down": 40})
    t, is_def = et.load_thresholds(db)
    assert is_def is False
    assert t.recession_limit_down == 40
    assert t.ice_max_boards == DEFAULT_THRESHOLDS.ice_max_boards


def test_save_thresholds_persists_merged() -> None:
    db = MagicMock()
    db.execute.return_value.scalar.return_value = None
    out = et.save_thresholds(db, {"recession_limit_down": 35})
    assert out.recession_limit_down == 35
    assert db.execute.call_count == 2
    db.commit.assert_called_once()
    insert_call = db.execute.call_args_list[1]
    assert insert_call.args[1]["k"] == et.META_KEY
    stored = json.loads(insert_call.args[1]["v"])
    assert stored["recession_limit_down"] == 35


def test_save_thresholds_merges_over_existing() -> None:
    db = MagicMock()
    db.execute.return_value.scalar.return_value = json.dumps(
        {"recession_limit_down": 30, "climax_limit_up": 90}
    )
    out = et.save_thresholds(db, {"recession_limit_down": 45})
    assert out.recession_limit_down == 45
    assert out.climax_limit_up == 90


def test_reset_thresholds_deletes_meta() -> None:
    db = MagicMock()
    out = et.reset_thresholds(db)
    assert out == DEFAULT_THRESHOLDS
    db.execute.assert_called_once()
    assert "DELETE" in str(db.execute.call_args.args[0])
    db.commit.assert_called_once()


def test_save_invalidates_cache(monkeypatch) -> None:
    from app.services import emotion_cycle_cache as c

    store = MagicMock()
    store.available.return_value = False
    monkeypatch.setattr(c, "get_quote_store", lambda: store)

    c.cache_set({"stage": "x"})
    db = MagicMock()
    db.execute.return_value.scalar.return_value = None
    et.save_thresholds(db, {"recession_limit_down": 25})
    assert c.cache_get() is None


def test_reset_invalidates_cache(monkeypatch) -> None:
    from app.services import emotion_cycle_cache as c

    store = MagicMock()
    store.available.return_value = False
    monkeypatch.setattr(c, "get_quote_store", lambda: store)

    c.cache_set({"stage": "x"})
    db = MagicMock()
    et.reset_thresholds(db)
    assert c.cache_get() is None
