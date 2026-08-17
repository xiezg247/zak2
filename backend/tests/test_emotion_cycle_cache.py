from __future__ import annotations

from unittest.mock import MagicMock, patch


def _patch_no_redis():
    store = MagicMock()
    store.available.return_value = False
    return patch("app.services.emotion_cycle_cache.get_quote_store", return_value=store)


def test_cache_ttl_sec_defaults_and_clamps(monkeypatch) -> None:
    from app.services import emotion_cycle_cache as c

    monkeypatch.delenv("EMOTION_CYCLE_CACHE_TTL_SEC", raising=False)
    assert c.cache_ttl_sec() == 60

    monkeypatch.setenv("EMOTION_CYCLE_CACHE_TTL_SEC", "3")
    assert c.cache_ttl_sec() == 5

    monkeypatch.setenv("EMOTION_CYCLE_CACHE_TTL_SEC", "9999")
    assert c.cache_ttl_sec() == 600

    monkeypatch.setenv("EMOTION_CYCLE_CACHE_TTL_SEC", "120")
    assert c.cache_ttl_sec() == 120


def test_mem_cache_roundtrip(monkeypatch) -> None:
    monkeypatch.setenv("EMOTION_CYCLE_CACHE_TTL_SEC", "60")
    with _patch_no_redis():
        from app.services import emotion_cycle_cache as c

        c.cache_invalidate()
        assert c.cache_get() is None
        c.cache_set({"stage": "ice"})
        assert c.cache_get()["stage"] == "ice"
        c.cache_invalidate()
        assert c.cache_get() is None


def test_build_uses_cache(monkeypatch) -> None:
    with _patch_no_redis():
        from app.services import emotion_cycle as ec
        from app.services import emotion_cycle_cache as c

        c.cache_invalidate()
        c.cache_set({"stage": "ice", "stage_label": "冰点", "cached_stub": True})
        db = MagicMock()
        out = ec.build_emotion_cycle(db, force=False)
        assert out.get("cached_stub") is True


def test_build_force_bypasses_cache(monkeypatch) -> None:
    with _patch_no_redis():
        from app.services import emotion_cycle as ec
        from app.services import emotion_cycle_cache as c

        c.cache_set({"stage": "ice", "from_cache": True})
        db = MagicMock()
        with (
            patch.object(ec, "_breadth_from_redis", return_value=None),
            patch.object(ec, "_ladder_rows", return_value=[]),
            patch.object(ec, "_index_above_ma5", return_value=None),
            patch("app.services.emotion_thresholds.load_thresholds", return_value=(ec.DEFAULT_THRESHOLDS, True)),
        ):
            out = ec.build_emotion_cycle(db, force=True)
        assert out.get("from_cache") is not True
        assert "stage" in out


def test_build_sets_cache_after_compute(monkeypatch) -> None:
    with _patch_no_redis():
        from app.services import emotion_cycle as ec
        from app.services import emotion_cycle_cache as c

        c.cache_invalidate()
        db = MagicMock()
        with (
            patch.object(ec, "_breadth_from_redis", return_value=None),
            patch.object(ec, "_ladder_rows", return_value=[]),
            patch.object(ec, "_index_above_ma5", return_value=None),
            patch("app.services.emotion_thresholds.load_thresholds", return_value=(ec.DEFAULT_THRESHOLDS, True)),
        ):
            out = ec.build_emotion_cycle(db, force=True)
        cached = c.cache_get()
        assert cached is not None
        assert cached["stage"] == out["stage"]
