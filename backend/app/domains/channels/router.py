from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.db import get_db
from app.domains.channels.schemas import (
    ChannelCreate,
    ChannelListOut,
    ChannelOut,
    ChannelTestOut,
    ChannelUpdate,
)
from app.domains.channels.service import ChannelService
from app.models.user import User
from app.schemas.common import ApiResponse, OkOut

router = APIRouter(prefix="/channels", tags=["channels"])


@router.get("", response_model=ApiResponse[ChannelListOut])
def list_channels(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[ChannelListOut]:
    return ApiResponse(data=ChannelService.list_channels(db, str(user.id)))


@router.post("", response_model=ApiResponse[ChannelOut])
def create_channel(
    body: ChannelCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[ChannelOut]:
    return ApiResponse(data=ChannelService.create_channel(db, str(user.id), body))


@router.patch("/{channel_id}", response_model=ApiResponse[ChannelOut])
def update_channel(
    channel_id: str,
    body: ChannelUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[ChannelOut]:
    return ApiResponse(
        data=ChannelService.update_channel(db, str(user.id), channel_id, body)
    )


@router.delete("/{channel_id}", response_model=ApiResponse[OkOut])
def delete_channel(
    channel_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[OkOut]:
    ChannelService.delete_channel(db, str(user.id), channel_id)
    return ApiResponse(data=OkOut())


@router.post("/{channel_id}/test", response_model=ApiResponse[ChannelTestOut])
def test_channel(
    channel_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[ChannelTestOut]:
    return ApiResponse(data=ChannelService.test_channel(db, str(user.id), channel_id))
