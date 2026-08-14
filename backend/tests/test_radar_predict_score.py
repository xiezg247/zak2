from app.services.radar_predict import score_predict_rows


def test_score_predict_rules_table():
    rows = [
        {
            "vt_symbol": "600519.SSE",
            "name": "茅台",
            "resonance_score": 2.5,
            "card_count": 4,
            "card_titles": ["A", "B", "C", "D"],
            "change_pct": 8.0,
            "seal_time_label": "早盘",
        },
        {
            "vt_symbol": "000001.SZSE",
            "name": "平安",
            "resonance_score": 2.0,
            "card_count": 2,
            "card_titles": ["A", "B"],
            "change_pct": -1.0,
            "seal_time_label": "",
        },
    ]
    out, missing = score_predict_rows(rows, has_daily_bars={"600519.SSE"}, top_n=30)
    assert missing == 1
    assert out[0]["vt_symbol"] == "600519.SSE"
    # 2.5 +1.0 +0.8 +0.6 +0.3 = 5.2
    assert abs(out[0]["predict_score"] - 5.2) < 1e-6
    assert "出现≥4卡" in out[0]["reasons"]
    assert "近5日K可用" in out[0]["reasons"]
    # 2.0 -0.5 = 1.5，无 K
    assert out[1]["vt_symbol"] == "000001.SZSE"
    assert abs(out[1]["predict_score"] - 1.5) < 1e-6
    assert "涨幅为负" in out[1]["reasons"]


def test_score_predict_empty():
    out, missing = score_predict_rows([], has_daily_bars=set())
    assert out == []
    assert missing == 0
