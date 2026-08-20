"""消息推送渠道仓库（app.notify_channel）。"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from app.domains.channels.schemas import ChannelOut
from app.models.channel import NotifyChannel
from app.repositories.base import BaseRepository


def _now_str() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")


def _webhook_of(channel: NotifyChannel) -> str:
    try:
        cfg = json.loads(channel.config_json or "{}")
        return str(cfg.get("webhook_url") or "")
    except (json.JSONDecodeError, TypeError):
        return ""


class ChannelRepository(BaseRepository[NotifyChannel]):
    model = NotifyChannel
    order_by = (NotifyChannel.created_at,)

    def _id_is_autoincrement(self) -> bool:
        # UUID 主键无自增；base 对 autoincrement="auto" 的误判会导致 id 为空
        return False

    def to_out(self, channel: NotifyChannel) -> ChannelOut:
        return ChannelOut(
            id=channel.id,
            channel_type=channel.channel_type,
            name=channel.name,
            webhook_url=_webhook_of(channel),
            enabled=channel.enabled,
            created_at=channel.created_at,
            updated_at=channel.updated_at,
        )

    def create_channel(self, *, name: str, webhook_url: str, enabled: bool) -> NotifyChannel:
        now = _now_str()
        return self.create(
            channel_type="feishu",
            name=name,
            config_json=json.dumps({"webhook_url": webhook_url}, ensure_ascii=False),
            enabled=enabled,
            created_at=now,
            updated_at=now,
        )

    def update_channel(self, key: str, values: dict[str, Any]) -> NotifyChannel | None:
        row = self.get(key)
        if row is None:
            return None
        now = _now_str()
        name = values.get("name")
        if name is not None:
            row.name = name
        webhook_url = values.get("webhook_url")
        if webhook_url is not None:
            row.config_json = json.dumps({"webhook_url": webhook_url}, ensure_ascii=False)
        enabled = values.get("enabled")
        if enabled is not None:
            row.enabled = bool(enabled)
        row.updated_at = now
        self.db.commit()
        self.db.refresh(row)
        return row
