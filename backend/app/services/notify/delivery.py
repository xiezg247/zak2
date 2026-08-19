"""通知投递：遍历启用渠道发送并写入 notify_delivery_log。"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.channel import NotifyChannel
from app.models.notify import NotifyDeliveryLog
from app.services.notify.feishu import FeishuSendError, send_feishu_webhook


def _now_str() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")


def _webhook_of(channel: NotifyChannel) -> str:
    try:
        cfg = json.loads(channel.config_json or "{}")
        return str(cfg.get("webhook_url") or "")
    except (json.JSONDecodeError, TypeError):
        return ""


def send_to_channel(
    db: Session,
    channel: NotifyChannel,
    *,
    event_type: str,
    title: str,
    text: str,
) -> tuple[bool, str]:
    """向单个渠道发送并写投递日志，返回 (ok, error_message)。"""
    webhook_url = _webhook_of(channel)
    if not webhook_url:
        status, error = "error", "渠道缺少 webhook_url"
    else:
        try:
            send_feishu_webhook(webhook_url, title, text)
            status, error = "ok", ""
        except FeishuSendError as exc:
            status, error = "error", exc.message
    db.add(
        NotifyDeliveryLog(
            id=str(uuid4()),
            user_id=channel.user_id,
            event_type=event_type,
            channel=channel.channel_type,
            payload_json=json.dumps(
                {"channel_id": channel.id, "channel_name": channel.name, "title": title},
                ensure_ascii=False,
            ),
            status=status,
            error=error,
            created_at=_now_str(),
        )
    )
    db.commit()
    return status == "ok", error


def deliver_text(
    db: Session,
    *,
    user_id: str,
    event_type: str,
    title: str,
    text: str,
) -> dict[str, Any]:
    """遍历用户启用渠道发送，永不抛异常；返回 {sent, failed, errors}。"""
    channels = list(
        db.scalars(
            select(NotifyChannel).where(
                NotifyChannel.user_id == user_id,
                NotifyChannel.enabled.is_(True),
            )
        )
    )
    sent, failed = 0, 0
    errors: list[dict[str, str]] = []
    for channel in channels:
        ok, message = send_to_channel(
            db,
            channel,
            event_type=event_type,
            title=title,
            text=text,
        )
        if ok:
            sent += 1
        else:
            failed += 1
            errors.append({"channel_id": channel.id, "message": message})
    return {"sent": sent, "failed": failed, "errors": errors}
