from app.services.backtest_map import map_vnpy_statistics


def test_map_strips_percent_and_builds_curve():
    out = map_vnpy_statistics(
        {
            "total_return": "12.5%",
            "max_drawdown": "-3.2%",
            "sharpe_ratio": 1.1,
            "total_trade_count": 4,
        },
        trades=[],
        daily_rows=[{"date": "2024-01-02", "balance": 101000}],
    )
    assert out["total_return"] == 12.5
    assert out["max_drawdown"] == -3.2
    assert out["trade_count"] == 4
    assert out["equity_curve"][0]["equity"] == 101000
    assert out["statistics"]["total_return"] == 12.5
