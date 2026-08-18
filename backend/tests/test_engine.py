from __future__ import annotations

from app.schemas.screener import ConditionRunRequest, HardFilterPrefs
from app.services.market.quotes import QuoteRow
from app.services.screener.engine import run_condition_screen
from app.services.screener.hard_filters import apply_hard_filters


def _row(symbol: str, **kwargs) -> QuoteRow:  # type: ignore[no-untyped-def]
    base = {
        "symbol": symbol,
        "name": "测试",
        "change_pct": 6.0,
        "turnover_rate": 3.0,
        "amount": 1e8,
        "volume": 1e6,
        "volume_ratio": 2.0,
    }
    base.update(kwargs)
    return QuoteRow(**base)  # type: ignore[arg-type]


def test_hard_filter_excludes_st() -> None:
    rows = [_row("SHSE.1", name="ST退市"), _row("SHSE.2", name="茅台")]
    out = apply_hard_filters(rows, HardFilterPrefs(exclude_st=True, min_amount_wan=0, min_total_mv_yi=0))
    assert len(out) == 1
    assert out[0].symbol == "SHSE.2"


def test_hard_filter_min_amount_and_mv() -> None:
    rows = [
        _row("SHSE.1", name="小票", amount=1e6, total_mv=10_000),  # 1e6 元=100万；市值 1 亿万?
        _row("SHSE.2", name="大票", amount=1e9, total_mv=800_000),  # 800000 万 = 80 亿
    ]
    # min 3000 万成交额；市值 ≥ 50 亿 → 500000 万
    out = apply_hard_filters(
        rows,
        HardFilterPrefs(exclude_st=False, min_amount_wan=3000, min_total_mv_yi=50),
    )
    assert len(out) == 1
    assert out[0].symbol == "SHSE.2"


def test_condition_custom_range() -> None:
    result = run_condition_screen(
        ConditionRunRequest(
            preset="自定义筛选",
            top_n=10,
            min_change_pct=2.0,
            max_change_pct=5.0,
            hard_filter=HardFilterPrefs(min_amount_wan=0, min_total_mv_yi=0),
        ),
        store=_FakeStore(),  # type: ignore[arg-type]
    )
    assert result["row_count"] == 1
    assert result["rows"][0]["symbol"] == "SHSE.600519"


class _FakeStore:
    def available(self) -> bool:
        return True

    def meta(self) -> dict:
        return {"quote_count": 2, "available": True}

    def load_ranked_quotes(self, field: str, *, pool: int = 500) -> list[QuoteRow]:
        _ = field, pool
        return [
            _row("SHSE.600519", name="贵州茅台", change_pct=3.0),
            _row("SZSE.000001", name="平安银行", change_pct=6.5),
            _row("SHSE.600000", name="浦发银行", change_pct=1.0),
        ]


def test_condition_strong_up() -> None:
    result = run_condition_screen(
        ConditionRunRequest(
            preset="强势上涨", top_n=10, hard_filter=HardFilterPrefs(min_amount_wan=0, min_total_mv_yi=0)
        ),
        store=_FakeStore(),  # type: ignore[arg-type]
    )
    assert result["row_count"] == 1
    assert result["rows"][0]["symbol"] == "SZSE.000001"


def test_condition_limit_up() -> None:
    class _LimitStore(_FakeStore):
        def load_ranked_quotes(self, field: str, *, pool: int = 500) -> list[QuoteRow]:
            _ = field, pool
            return [
                _row("SZSE.1", name="连板", change_pct=10.0, limit_times=2),
                _row("SZSE.2", name="普涨", change_pct=3.0, limit_times=0),
                _row("SZSE.3", name="一字", change_pct=9.8, limit_times=0),
            ]

    result = run_condition_screen(
        ConditionRunRequest(
            preset="涨停股", top_n=10, hard_filter=HardFilterPrefs(min_amount_wan=0, min_total_mv_yi=0)
        ),
        store=_LimitStore(),  # type: ignore[arg-type]
    )
    assert result["row_count"] == 2
    assert result["rows"][0]["symbol"] == "SZSE.1"


def test_recipe_enriches_empty_industry_before_filter() -> None:
    from unittest.mock import MagicMock, patch

    from app.schemas.screener import RecipeRunRequest
    from app.services.screener.engine import run_recipe_screen

    class _Store:
        def available(self):
            return True

        def meta(self):
            return {"quote_count": 1, "available": True}

        def load_ranked_quotes(self, field, *, pool=500):
            return [QuoteRow(symbol="SHSE.600519", name="茅台", change_pct=5.0, industry="")]

    with patch(
        "app.services.market.stock_industry.load_industry_map",
        return_value={"SHSE.600519": "白酒"},
    ):
        result = run_recipe_screen(
            RecipeRunRequest(
                recipe_id="intraday_multi",
                top_n=5,
                hard_filter=HardFilterPrefs(
                    min_amount_wan=0,
                    min_total_mv_yi=0,
                    allowed_industries="白酒",
                ),
            ),
            store=_Store(),  # type: ignore[arg-type]
            db=MagicMock(),
            user_id="u1",
        )
    assert result["row_count"] >= 1
    assert result["rows"][0]["industry"] == "白酒"


def test_recipe_post_close_multi() -> None:
    from app.schemas.screener import RecipeRunRequest
    from app.services.screener.engine import run_recipe_screen

    class _MfStore(_FakeStore):
        def load_ranked_quotes(self, field: str, *, pool: int = 500) -> list[QuoteRow]:
            _ = pool
            if field == "net_mf_amount":
                return [
                    _row("SHSE.A", name="强流入", change_pct=4.0, turnover_rate=8.0, net_mf_amount=8000),
                    _row("SHSE.B", name="弱流入", change_pct=6.0, turnover_rate=3.0, net_mf_amount=500),
                    _row("SHSE.C", name="无流入", change_pct=9.0, turnover_rate=10.0, net_mf_amount=0),
                ]
            return []

    result = run_recipe_screen(
        RecipeRunRequest(
            recipe_id="post_close_multi",
            top_n=2,
            hard_filter=HardFilterPrefs(min_amount_wan=0, min_total_mv_yi=0),
        ),
        store=_MfStore(),  # type: ignore[arg-type]
    )
    assert result["condition"] == "盘后多因子"
    assert result["row_count"] == 2
    assert result["rows"][0]["symbol"] == "SHSE.A"
