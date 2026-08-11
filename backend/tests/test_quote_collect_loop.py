from datetime import datetime
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

from app.services.quote_collect.loop import collect_once
from app.services.quote_collect.models import QuoteSnapshot

TZ = ZoneInfo("Asia/Shanghai")


def test_skip_off_hours() -> None:
    db, writer, provider, client = MagicMock(), MagicMock(), MagicMock(), MagicMock()
    out = collect_once(
        db=db,
        writer=writer,
        provider=provider,
        client=client,
        force=False,
        now=datetime(2026, 8, 11, 12, 0, tzinfo=TZ),
    )
    assert out["skipped"] is True
    provider.fetch.assert_not_called()


def test_force_off_hours_collects(monkeypatch) -> None:
    from app.services.quote_collect import loop as loop_mod

    monkeypatch.setattr(loop_mod, "load_tf_symbols", lambda db: ["SHSE.600519"])
    db, client = MagicMock(), MagicMock()
    writer = MagicMock()
    writer.write_quotes.return_value = 1
    provider = MagicMock()
    provider.name = "tickflow"
    provider.fetch.return_value = {"SHSE.600519": QuoteSnapshot(symbol="SHSE.600519", last_price=1.0)}
    out = collect_once(
        db=db,
        writer=writer,
        provider=provider,
        client=client,
        force=True,
        now=datetime(2026, 8, 11, 12, 0, tzinfo=TZ),
    )
    assert out["skipped"] is False
    assert out["count"] == 1
    provider.fetch.assert_called_once()
