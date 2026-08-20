"""消息渠道 schema。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ChannelOut(BaseModel):
    id: str
    channel_type: str
    name: str
    webhook_url: str = ""
    enabled: bool = True
    created_at: str
    updated_at: str


class ChannelListOut(BaseModel):
    items: list[ChannelOut] = Field(default_factory=list)


class ChannelCreate(BaseModel):
    channel_type: str = Field(default="feishu", description="当前仅支持 feishu")
    name: str = Field(min_length=1, max_length=40)
    webhook_url: str = Field(min_length=1, description="飞书自定义机器人 webhook 地址")
    enabled: bool = True


class ChannelUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=40)
    webhook_url: str | None = Field(default=None, min_length=1)
    enabled: bool | None = None


class ChannelTestOut(BaseModel):
    ok: bool
    message: str
