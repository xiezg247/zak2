from app.services.off_plan import build_plan_symbol_statuses, list_off_plan_vt_symbols


def test_no_plan_means_none_off() -> None:
    assert list_off_plan_vt_symbols(["600519.SSE"], None) == []


def test_off_plan_diff() -> None:
    assert list_off_plan_vt_symbols(
        ["600519.SSE", "000001.SZSE"],
        {"600519.SSE"},
    ) == ["000001.SZSE"]


def test_build_plan_symbol_statuses_empty() -> None:
    assert (
        build_plan_symbol_statuses(
            ordered_vt_symbols=[],
            watchlist_vts=set(),
            position_vts=set(),
            name_by_vt={},
        )
        == []
    )


def test_build_plan_symbol_statuses_three_states() -> None:
    rows = build_plan_symbol_statuses(
        ordered_vt_symbols=["600519.SSE", "000001.SZSE", "300750.SZSE"],
        watchlist_vts={"600519.SSE", "000001.SZSE"},
        position_vts={"600519.SSE"},
        name_by_vt={"600519.SSE": "茅台", "000001.SZSE": "平安"},
    )
    assert rows == [
        {
            "vt_symbol": "600519.SSE",
            "name": "茅台",
            "in_watchlist": True,
            "in_position": True,
        },
        {
            "vt_symbol": "000001.SZSE",
            "name": "平安",
            "in_watchlist": True,
            "in_position": False,
        },
        {
            "vt_symbol": "300750.SZSE",
            "name": "",
            "in_watchlist": False,
            "in_position": False,
        },
    ]
