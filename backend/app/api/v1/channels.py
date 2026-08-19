"""消息渠道管理：CRUD + 测试发送。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.db import get_db
from app.models.user import User
from app.repositories.channel import ChannelRepository
from app.schemas.channel import (
    ChannelCreate,
    ChannelListOut,
    ChannelOut,
    ChannelTestOut,
    ChannelUpdate,
)
from app.schemas.common import ApiResponse, OkOut
from app.services.notify import delivery as notify_delivery

router = APIRouter(prefix="/channels", tags=["channels"])


@router.get("", response_model=ApiResponse[ChannelListOut])
def list_channels(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[ChannelListOut]:
    repo = ChannelRepository(db, str(user.id))
    channels = repo.list_all()
    return ApiResponse(data=ChannelListOut(items=[repo.to_out(ch) for ch in channels]))


@router.post("", response_model=ApiResponse[ChannelOut])
def create_channel(
    body: ChannelCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[ChannelOut]:
    repo = ChannelRepository(db, str(user.id))
    channel = repo.create_channel(
        name=body.name.strip(),
        webhook_url=body.webhook_url.strip(),
        enabled=body.enabled,
    )
    return ApiResponse(data=repo.to_out(channel))


def _get_owned(db: Session, user_id: str, channel_id: str):
    repo = ChannelRepository(db, user_id)
    channel = repo.get(channel_id)
    if channel is None:
        raise HTTPException(status_code=404, detail="渠道不存在")
    return repo, channel


@router.patch("/{channel_id}", response_model=ApiResponse[ChannelOut])
def update_channel(
    channel_id: str,
    body: ChannelUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[ChannelOut]:
    repo, _ = _get_owned(db, str(user.id), channel_id)
    values = body.model_dump(exclude_none=True)
    if not values:
        raise HTTPException(status_code=400, detail="没有需要更新的字段")
    if "name" in values:
        values["name"] = str(values["name"]).strip()
    if "webhook_url" in values:
        values["webhook_url"] = str(values["webhook_url"]).strip()
    channel = repo.update_channel(channel_id, values)
    if channel is None:
        raise HTTPException(status_code=404, detail="渠道不存在")
    return ApiResponse(data=repo.to_out(channel))


@router.delete("/{channel_id}", response_model=ApiResponse[OkOut])
def delete_channel(
    channel_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[OkOut]:
    repo, _ = _get_owned(db, str(user.id), channel_id)
    repo.delete(channel_id)
    return ApiResponse(data=OkOut())


@router.post("/{channel_id}/test", response_model=ApiResponse[ChannelTestOut])
def test_channel(
    channel_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[ChannelTestOut]:
    repo, channel = _get_owned(db, str(user.id), channel_id)
    ok, message = notify_delivery.send_to_channel(
        db,
        channel,
        event_type="channel.test",
        title="消息渠道测试",
        text="这是一条测试消息：zak2 消息渠道已成功接入飞书。",
    )
    return ApiResponse(
        data=ChannelTestOut(
            ok=ok,
            message=message if not ok else "测试消息发送成功",
        )
    )
