from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.errors import NotFound, ValidationFailed
from app.domains.channels.notify import delivery as notify_delivery
from app.domains.channels.repository import ChannelRepository
from app.domains.channels.schemas import (
    ChannelCreate,
    ChannelListOut,
    ChannelOut,
    ChannelTestOut,
    ChannelUpdate,
)


class ChannelService:
    @staticmethod
    def list_channels(db: Session, user_id: str) -> ChannelListOut:
        repo = ChannelRepository(db, user_id)
        return ChannelListOut(items=[repo.to_out(ch) for ch in repo.list_all()])

    @staticmethod
    def create_channel(db: Session, user_id: str, body: ChannelCreate) -> ChannelOut:
        repo = ChannelRepository(db, user_id)
        channel = repo.create_channel(
            name=body.name.strip(),
            webhook_url=body.webhook_url.strip(),
            enabled=body.enabled,
        )
        return repo.to_out(channel)

    @staticmethod
    def update_channel(
        db: Session, user_id: str, channel_id: str, body: ChannelUpdate
    ) -> ChannelOut:
        values = body.model_dump(exclude_none=True)
        if not values:
            raise ValidationFailed("没有需要更新的字段")
        if "name" in values:
            values["name"] = str(values["name"]).strip()
        if "webhook_url" in values:
            values["webhook_url"] = str(values["webhook_url"]).strip()
        repo = ChannelRepository(db, user_id)
        if repo.get(channel_id) is None:
            raise NotFound("渠道不存在")
        channel = repo.update_channel(channel_id, values)
        if channel is None:
            raise NotFound("渠道不存在")
        return repo.to_out(channel)

    @staticmethod
    def delete_channel(db: Session, user_id: str, channel_id: str) -> None:
        repo = ChannelRepository(db, user_id)
        if repo.get(channel_id) is None:
            raise NotFound("渠道不存在")
        repo.delete(channel_id)

    @staticmethod
    def test_channel(db: Session, user_id: str, channel_id: str) -> ChannelTestOut:
        repo = ChannelRepository(db, user_id)
        channel = repo.get(channel_id)
        if channel is None:
            raise NotFound("渠道不存在")
        ok, message = notify_delivery.send_to_channel(
            db,
            channel,
            event_type="channel.test",
            title="消息渠道测试",
            text="这是一条测试消息：zak2 消息渠道已成功接入飞书。",
        )
        return ChannelTestOut(ok=ok, message=message if not ok else "测试消息发送成功")
