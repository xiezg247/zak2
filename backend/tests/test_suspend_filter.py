from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.schemas.screener import HardFilterPrefs
from app.services.market import suspend as sus
from app.services.market.quotes import QuoteRow
from app.services.screener.hard_filters import apply_hard_filters


def _row(tf: str, name: str = "x") -> QuoteRow:
    return QuoteRow(symbol=tf, name=name, amount=1e9, total_mv=1e6)


def test_load_empty() -> None:
    db = MagicMock()
    res = MagicMock()
    res.mappings.return_value.all.return_value = []
    db.execute.return_value = res
    with patch("app.services.market.suspend.latest_open_yyyymmdd", return_value="20260813"):
        assert sus.load_suspended_vt_symbols(db) == set()


def test_load_maps_vt() -> None:
    db = MagicMock()
    res = MagicMock()
    res.mappings.return_value.all.return_value = [
        {"symbol": "000001", "exchange": "SZSE", "cal_date": "2026-08-13", "suspend_type": "S"},
    ]
    db.execute.return_value = res
    out = sus.load_suspended_vt_symbols(db, "2026-08-13")
    assert out == {"000001.SZSE"}


def test_filter_excludes_when_set() -> None:
    prefs = HardFilterPrefs(
        exclude_st=False,
        exclude_suspended=True,
        min_amount_wan=0,
        min_total_mv_yi=0,
        exclude_new_listing=False,
        exclude_limit_board=False,
    )
    rows = [_row("SZSE.000001"), _row("SHSE.600519")]
    out = apply_hard_filters(rows, prefs, suspended_vts={"000001.SZSE"})
    assert [r.symbol for r in out] == ["SHSE.600519"]


def test_filter_lenient_empty_set() -> None:
    prefs = HardFilterPrefs(
        exclude_st=False,
        exclude_suspended=True,
        min_amount_wan=0,
        min_total_mv_yi=0,
        exclude_new_listing=False,
        exclude_limit_board=False,
    )
    rows = [_row("SZSE.000001")]
    assert len(apply_hard_filters(rows, prefs, suspended_vts=set())) == 1
    assert len(apply_hard_filters(rows, prefs, suspended_vts=None)) == 1


def test_filter_respects_exclude_false() -> None:
    prefs = HardFilterPrefs(
        exclude_st=False,
        exclude_suspended=False,
        min_amount_wan=0,
        min_total_mv_yi=0,
        exclude_new_listing=False,
        exclude_limit_board=False,
    )
    rows = [_row("SZSE.000001")]
    assert len(apply_hard_filters(rows, prefs, suspended_vts={"000001.SZSE"})) == 1


def test_watchlist_item_default_suspended() -> None:
    from app.schemas.watchlist import WatchlistItemOut

    item = WatchlistItemOut(
        symbol="000001",
        exchange="SZSE",
        name="平安",
        sort_order=0,
        vt_symbol="000001.SZSE",
        tf_symbol="SZSE.000001",
    )
    assert item.suspended is False
