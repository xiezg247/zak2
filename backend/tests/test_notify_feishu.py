"""notify/feishu 飞书 webhook 发送单测。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import pytest

from app.domains.channels.notify.feishu import FeishuSendError, send_feishu_webhook


def test_send_ok() -> None:
    with patch(
        "app.domains.channels.notify.feishu.httpx.post",
        return_value=MagicMock(status_code=200, json=lambda: {"code": 0, "msg": "success"}),
    ) as post:
        send_feishu_webhook("https://hook", "标题", "正文")
    post.assert_called_once()
    payload = post.call_args.kwargs["json"]
    assert payload["msg_type"] == "interactive"
    assert payload["card"]["header"]["title"]["content"] == "标题"


def test_send_network_error() -> None:
    with patch("app.domains.channels.notify.feishu.httpx.post", side_effect=httpx.ConnectError("boom")), pytest.raises(
        FeishuSendError
    ) as exc:
        send_feishu_webhook("https://hook", "标题", "正文")
    assert "网络错误" in str(exc.value)


def test_send_feishu_code_error() -> None:
    with patch(
        "app.domains.channels.notify.feishu.httpx.post",
        return_value=MagicMock(status_code=200, json=lambda: {"code": 19001, "msg": "bad"}),
    ), pytest.raises(FeishuSendError) as exc:
        send_feishu_webhook("https://hook", "标题", "正文")
    assert "19001" in str(exc.value) or "bad" in str(exc.value)


def test_send_non_200() -> None:
    with patch(
        "app.domains.channels.notify.feishu.httpx.post",
        return_value=MagicMock(status_code=500, text="err"),
    ), pytest.raises(FeishuSendError) as exc:
        send_feishu_webhook("https://hook", "标题", "正文")
    assert "500" in str(exc.value)


def test_send_invalid_json() -> None:
    with patch(
        "app.domains.channels.notify.feishu.httpx.post",
        return_value=MagicMock(status_code=200, text="not-json", json=lambda: (_ for _ in ()).throw(ValueError("bad json"))),
    ), pytest.raises(FeishuSendError):
        send_feishu_webhook("https://hook", "标题", "正文")
