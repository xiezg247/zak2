"""notify/delivery 投递服务单测。"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.domains.channels.notify.delivery import deliver_text, send_to_channel
from app.domains.channels.notify.feishu import FeishuSendError


def _channel(id_: str, name: str, webhook: str) -> SimpleNamespace:
    return SimpleNamespace(
        id=id_,
        user_id="u1",
        channel_type="feishu",
        name=name,
        config_json=f'{{"webhook_url": "{webhook}"}}',
    )


def test_send_to_channel_ok() -> None:
    db = MagicMock()
    ch = _channel("c1", "组群", "https://hook")
    with patch("app.domains.channels.notify.delivery.send_feishu_webhook") as send:
        ok, msg = send_to_channel(db, ch, event_type="ops.screen", title="t", text="x")
    assert ok is True and msg == ""
    send.assert_called_once_with("https://hook", "t", "x")
    assert db.add.called and db.commit.called
    row = db.add.call_args.args[0]
    assert row.channel == "feishu"
    assert row.status == "ok"


def test_send_to_channel_error_logged() -> None:
    db = MagicMock()
    ch = _channel("c1", "组群", "https://hook")
    with patch("app.domains.channels.notify.delivery.send_feishu_webhook", side_effect=FeishuSendError("HTTP 500")):
        ok, msg = send_to_channel(db, ch, event_type="ops.screen", title="t", text="x")
    assert ok is False and msg == "HTTP 500"
    row = db.add.call_args.args[0]
    assert row.status == "error"
    assert row.error == "HTTP 500"


def test_send_to_channel_missing_webhook() -> None:
    db = MagicMock()
    ch = _channel("c1", "组群", "")
    with patch("app.domains.channels.notify.delivery.send_feishu_webhook") as send:
        ok, msg = send_to_channel(db, ch, event_type="ops.screen", title="t", text="x")
    assert ok is False
    assert "webhook" in msg
    send.assert_not_called()


def test_deliver_text_skips_when_no_channels() -> None:
    db = MagicMock()
    db.scalars.return_value = []
    out = deliver_text(db, user_id="u1", event_type="e", title="t", text="x")
    assert out == {"sent": 0, "failed": 0, "errors": []}


def test_deliver_text_counts_mixed() -> None:
    db = MagicMock()
    db.scalars.return_value = [
        _channel("c1", "a", "https://a"),
        _channel("c2", "b", "https://b"),
    ]
    with patch(
        "app.domains.channels.notify.delivery.send_to_channel",
        side_effect=[(True, ""), (False, "HTTP 500")],
    ):
        out = deliver_text(db, user_id="u1", event_type="e", title="t", text="x")
    assert out["sent"] == 1 and out["failed"] == 1
    assert out["errors"] == [{"channel_id": "c2", "message": "HTTP 500"}]
