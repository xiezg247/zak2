import pytest

from app.schemas.backtest import BacktestRunRequest
from app.services.backtest.backtest_settings import build_strategy_setting, min_bars_for_request
from app.strategies.cta.registry import get_strategy_class

NEW_STRATEGIES = {
    "donchian": {"entry_window": 20, "exit_window": 10},
    "rsi_reversal": {"rsi_period": 14, "oversold": 30, "overbought": 70},
    "bollinger": {"boll_period": 20, "boll_dev": 2.0},
    "ma_band": {"ma_fast": 5, "ma_mid": 10, "ma_slow": 20, "ma_long": 60},
    "atr_breakout": {"channel_period": 20, "atr_period": 14, "atr_mult": 2.0},
}


@pytest.mark.parametrize("strategy_id", sorted(NEW_STRATEGIES))
def test_build_setting_extra_strategy(strategy_id):
    req = BacktestRunRequest(vt_symbol="600519.SSE", strategy=strategy_id)
    setting = build_strategy_setting(req)
    for key, default in NEW_STRATEGIES[strategy_id].items():
        assert setting[key] == default
    assert setting["trade_volume"] == 100


@pytest.mark.parametrize("strategy_id", sorted(NEW_STRATEGIES))
def test_min_bars_extra_strategy(strategy_id):
    req = BacktestRunRequest(vt_symbol="600519.SSE", strategy=strategy_id)
    assert min_bars_for_request(req) >= 30


def test_schema_defaults_for_new_fields():
    req = BacktestRunRequest(vt_symbol="600519.SSE")
    assert req.entry_window == 20
    assert req.exit_window == 10
    assert req.rsi_period == 14
    assert req.oversold == 30
    assert req.overbought == 70
    assert req.boll_period == 20
    assert req.boll_dev == 2.0
    assert req.ma_fast == 5
    assert req.ma_mid == 10
    assert req.ma_slow == 20
    assert req.ma_long == 60
    assert req.channel_period == 20
    assert req.atr_period == 14
    assert req.atr_mult == 2.0


@pytest.mark.vnpy
@pytest.mark.parametrize(
    ("strategy_id", "class_name"),
    [
        ("donchian", "DonchianStrategy"),
        ("rsi_reversal", "RsiReversalStrategy"),
        ("bollinger", "BollingerStrategy"),
        ("ma_band", "MaBandStrategy"),
        ("atr_breakout", "AtrBreakoutStrategy"),
    ],
)
def test_registry_extra_strategy(strategy_id, class_name):
    pytest.importorskip("vnpy_ctastrategy")
    assert get_strategy_class(strategy_id).__name__ == class_name
