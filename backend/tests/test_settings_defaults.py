from app.core.settings import Settings


def test_default_database_targets_zak2(monkeypatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    s = Settings(_env_file=None)
    assert "/zak2" in s.database_url
    assert s.database_url.endswith("/zak2") or "/zak2?" in s.database_url
