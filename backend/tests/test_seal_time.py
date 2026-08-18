from app.services.market.seal_time import format_seal_time_label, parse_clock_minutes, seal_time_score


def test_parse_and_score_bands():
    assert parse_clock_minutes("0935") == 9 * 60 + 35
    assert seal_time_score("0930") == 1.0
    assert seal_time_score("1100") == 0.7
    assert seal_time_score("1400") == 0.5
    assert seal_time_score("1501") == 0.0
    assert seal_time_score("") == 0.0
    assert format_seal_time_label("0935") == "09:35 封板"
