from app.services.strategy.position_risk_tags import compute_position_risk_tags, primary_risk_tag


def test_sell_and_float_loss_order() -> None:
    tags = compute_position_risk_tags(
        exit_signal="sell",
        unrealized_pnl_pct=-6.0,
        change_pct=None,
        volume_ratio=None,
    )
    assert tags == ["卖出信号", "浮亏"]
    assert primary_risk_tag(tags) == "卖出信号"


def test_intraday_drop_surge_volume() -> None:
    tags = compute_position_risk_tags(
        exit_signal="na",
        unrealized_pnl_pct=None,
        change_pct=-3.0,
        volume_ratio=1.5,
    )
    assert "急跌" in tags
    assert "放量" in tags
    assert tags.index("急跌") < tags.index("放量")

    tags2 = compute_position_risk_tags(
        exit_signal=None,
        unrealized_pnl_pct=None,
        change_pct=5.0,
        volume_ratio=None,
    )
    assert tags2 == ["大涨"]


def test_float_gain() -> None:
    tags = compute_position_risk_tags(
        exit_signal="hold",
        unrealized_pnl_pct=15.0,
        change_pct=0.0,
        volume_ratio=1.0,
    )
    assert tags == ["浮盈"]


def test_missing_fields_empty() -> None:
    assert (
        compute_position_risk_tags(
            exit_signal=None,
            unrealized_pnl_pct=None,
            change_pct=None,
            volume_ratio=None,
        )
        == []
    )
