from __future__ import annotations

from pydantic import BaseModel, Field


class SessionOut(BaseModel):
    id: str
    title: str
    scene: str
    created_at: str
    updated_at: str


class SessionCreate(BaseModel):
    title: str = ""
    scene: str = "general"


class SessionUpdate(BaseModel):
    title: str | None = None
    scene: str | None = None


class MessageOut(BaseModel):
    id: int
    session_id: str
    role: str
    content: str
    created_at: str


class ChatRequest(BaseModel):
    content: str = Field(min_length=1)
    include_context: bool = True
    use_tools: bool = True


class LlmStatus(BaseModel):
    configured: bool
    model: str
    api_base: str


class TeamStreamRequest(BaseModel):
    vt_symbol: str = Field(min_length=1, description="如 600519.SSE")
    session_id: str | None = Field(default=None, description="可选：完成后写入该会话一条助手消息")
    mode: str = Field(default="fast", description="fast=规则分+首席；deep=三分析师并行 LLM+首席")
