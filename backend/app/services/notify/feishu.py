"""飞书自定义机器人 webhook 发送。"""

from __future__ import annotations

import httpx

FEISHU_WEBHOOK_TIMEOUT_S = 10.0


class FeishuSendError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


def send_feishu_webhook(webhook_url: str, title: str, text: str) -> None:
    """向飞书群机器人发送卡片消息；失败抛 FeishuSendError。"""
    payload = {
        "msg_type": "interactive",
        "card": {
            "header": {"title": {"tag": "plain_text", "content": title}},
            "elements": [{"tag": "div", "text": {"tag": "lark_md", "content": text}}],
        },
    }
    try:
        resp = httpx.post(webhook_url, json=payload, timeout=FEISHU_WEBHOOK_TIMEOUT_S)
    except httpx.HTTPError as exc:
        raise FeishuSendError(f"网络错误：{exc}") from exc
    if resp.status_code >= 400:
        raise FeishuSendError(f"HTTP {resp.status_code}：{(resp.text or '')[:200]}")
    try:
        data = resp.json()
    except ValueError as exc:
        raise FeishuSendError(f"响应解析失败：{(resp.text or '')[:200]}") from exc
    if data.get("code") != 0:
        raise FeishuSendError(f"飞书返回错误：{data.get('msg') or data}")
