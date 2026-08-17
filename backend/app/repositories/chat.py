from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import delete, desc, select

from app.models.chat import ChatMessage, ChatSession
from app.repositories.base import BaseRepository
from app.repositories.pagination import Page
from app.schemas.chat import MessageOut, SessionOut
from app.services import ai_agent
from app.services.ai_context import SYSTEM_PROMPT, build_context_brief


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _session_out(row: ChatSession) -> SessionOut:
    return SessionOut(
        id=row.id, title=row.title, scene=row.scene, created_at=row.created_at, updated_at=row.updated_at
    )


def _message_out(row: ChatMessage) -> MessageOut:
    return MessageOut(
        id=int(row.id),
        session_id=row.session_id,
        role=row.role,
        content=row.content,
        created_at=row.created_at,
    )


class ChatRepository(BaseRepository[ChatSession]):
    """会话 + 消息仓库（会话为主模型，消息按 session 关联）。"""

    model = ChatSession
    order_by = (desc(ChatSession.updated_at),)

    # ---- 会话 ----

    def list_sessions(self, *, limit: int = 50) -> list[SessionOut]:
        rows = self.list_all(limit=limit)
        return [_session_out(r) for r in rows]

    def list_sessions_page(self, *, page: int = 1, page_size: int = 20) -> Page[SessionOut]:
        result = self.paginate(page=page, page_size=page_size)
        return Page(
            items=[_session_out(r) for r in result.items],
            total=result.total,
            page=result.page,
            page_size=result.page_size,
        )

    def create_session(self, *, title: str = "", scene: str = "general") -> SessionOut:
        now = _now()
        row = self.create(
            id=str(uuid4()),
            title=(title or "新对话").strip() or "新对话",
            scene=scene or "general",
            created_at=now,
            updated_at=now,
        )
        return _session_out(row)

    def get_session(self, session_id: str) -> ChatSession:
        row = self.get(session_id)
        if not row:
            raise HTTPException(status_code=404, detail="会话不存在")
        return row

    def update_session(
        self, session_id: str, *, title: str | None = None, scene: str | None = None
    ) -> SessionOut:
        row = self.get_session(session_id)
        if title is not None:
            row.title = title.strip() or row.title
        if scene is not None:
            row.scene = scene
        row.updated_at = _now()
        self.db.commit()
        self.db.refresh(row)
        return _session_out(row)

    def delete_session(self, session_id: str) -> None:
        self.get_session(session_id)
        self.db.execute(delete(ChatMessage).where(ChatMessage.session_id == session_id, ChatMessage.user_id == self.user_id))
        self.db.execute(delete(ChatSession).where(ChatSession.id == session_id, ChatSession.user_id == self.user_id))
        self.db.commit()

    # ---- 消息 ----

    def list_messages(self, session_id: str, *, limit: int = 200) -> list[MessageOut]:
        self.get_session(session_id)
        rows = self.db.scalars(
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id, ChatMessage.user_id == self.user_id)
            .order_by(ChatMessage.id)
            .limit(limit)
        )
        return [_message_out(r) for r in rows]

    def _add_message(self, session_id: str, role: str, content: str) -> ChatMessage:
        row = ChatMessage(
            user_id=self.user_id,
            session_id=session_id,
            role=role,
            content=content,
            created_at=_now(),
        )
        self.db.add(row)
        session = self.get_session(session_id)
        session.updated_at = _now()
        if session.title in {"", "新对话"} and role == "user":
            session.title = content.strip().replace("\n", " ")[:40] or session.title
        self.db.commit()
        self.db.refresh(row)
        return row

    def build_llm_messages(self, session_id: str, *, include_context: bool) -> list[dict]:
        system = SYSTEM_PROMPT
        if include_context:
            brief = build_context_brief(self.db, self.user_id)
            system = f"{SYSTEM_PROMPT}\n\n## 当前用户上下文（摘要，详细请用工具）\n{brief}"
        history = self.list_messages(session_id, limit=40)
        msgs: list[dict] = [{"role": "system", "content": system}]
        for m in history:
            if m.role in {"user", "assistant", "system"}:
                msgs.append({"role": m.role, "content": m.content})
        return msgs

    def send_message(
        self,
        session_id: str,
        content: str,
        *,
        include_context: bool = True,
        use_tools: bool = True,
    ) -> MessageOut:
        self.get_session(session_id)
        self._add_message(session_id, "user", content.strip())
        messages = self.build_llm_messages(session_id, include_context=include_context)
        reply, _events = ai_agent.complete_with_tools(self.db, self.user_id, messages, use_tools=use_tools)
        assistant = self._add_message(session_id, "assistant", reply)
        return _message_out(assistant)

    def prepare_stream(
        self,
        session_id: str,
        content: str,
        *,
        include_context: bool = True,
    ) -> list[dict]:
        self.get_session(session_id)
        self._add_message(session_id, "user", content.strip())
        return self.build_llm_messages(session_id, include_context=include_context)

    def finalize_stream(self, session_id: str, reply: str) -> MessageOut:
        assistant = self._add_message(session_id, "assistant", reply)
        return _message_out(assistant)
