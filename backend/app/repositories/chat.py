from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import delete, desc, select
from sqlalchemy.orm import Session

from app.models.chat import ChatMessage, ChatSession
from app.repositories.pagination import Page, paginate
from app.schemas.chat import MessageOut, SessionOut
from app.services.ai_context import SYSTEM_PROMPT, build_context_brief
from app.services import ai_agent


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def list_sessions(db: Session, user_id: str, *, limit: int = 50) -> list[SessionOut]:
    rows = db.scalars(
        select(ChatSession)
        .where(ChatSession.user_id == user_id)
        .order_by(desc(ChatSession.updated_at))
        .limit(limit)
    )
    return [
        SessionOut(id=r.id, title=r.title, scene=r.scene, created_at=r.created_at, updated_at=r.updated_at)
        for r in rows
    ]


def list_sessions_page(db: Session, user_id: str, *, page: int = 1, page_size: int = 20) -> Page[SessionOut]:
    stmt = select(ChatSession).where(ChatSession.user_id == user_id).order_by(desc(ChatSession.updated_at))
    result = paginate(db, stmt, page=page, page_size=page_size)
    return Page(
        items=[
            SessionOut(id=r.id, title=r.title, scene=r.scene, created_at=r.created_at, updated_at=r.updated_at)
            for r in result.items
        ],
        total=result.total,
        page=result.page,
        page_size=result.page_size,
    )


def create_session(db: Session, user_id: str, *, title: str = "", scene: str = "general") -> SessionOut:
    now = _now()
    row = ChatSession(
        id=str(uuid4()),
        user_id=user_id,
        title=(title or "新对话").strip() or "新对话",
        scene=scene or "general",
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return SessionOut(id=row.id, title=row.title, scene=row.scene, created_at=row.created_at, updated_at=row.updated_at)


def get_session(db: Session, user_id: str, session_id: str) -> ChatSession:
    row = db.scalar(
        select(ChatSession).where(ChatSession.id == session_id, ChatSession.user_id == user_id)
    )
    if not row:
        raise HTTPException(status_code=404, detail="会话不存在")
    return row


def update_session(db: Session, user_id: str, session_id: str, *, title: str | None = None, scene: str | None = None) -> SessionOut:
    row = get_session(db, user_id, session_id)
    if title is not None:
        row.title = title.strip() or row.title
    if scene is not None:
        row.scene = scene
    row.updated_at = _now()
    db.commit()
    db.refresh(row)
    return SessionOut(id=row.id, title=row.title, scene=row.scene, created_at=row.created_at, updated_at=row.updated_at)


def delete_session(db: Session, user_id: str, session_id: str) -> None:
    get_session(db, user_id, session_id)
    db.execute(delete(ChatMessage).where(ChatMessage.session_id == session_id, ChatMessage.user_id == user_id))
    db.execute(delete(ChatSession).where(ChatSession.id == session_id, ChatSession.user_id == user_id))
    db.commit()


def list_messages(db: Session, user_id: str, session_id: str, *, limit: int = 200) -> list[MessageOut]:
    get_session(db, user_id, session_id)
    rows = db.scalars(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id, ChatMessage.user_id == user_id)
        .order_by(ChatMessage.id)
        .limit(limit)
    )
    return [
        MessageOut(id=int(r.id), session_id=r.session_id, role=r.role, content=r.content, created_at=r.created_at)
        for r in rows
    ]


def _add_message(db: Session, user_id: str, session_id: str, role: str, content: str) -> ChatMessage:
    row = ChatMessage(
        user_id=user_id,
        session_id=session_id,
        role=role,
        content=content,
        created_at=_now(),
    )
    db.add(row)
    session = get_session(db, user_id, session_id)
    session.updated_at = _now()
    if session.title in {"", "新对话"} and role == "user":
        session.title = content.strip().replace("\n", " ")[:40] or session.title
    db.commit()
    db.refresh(row)
    return row


def build_llm_messages(db: Session, user_id: str, session_id: str, *, include_context: bool) -> list[dict]:
    system = SYSTEM_PROMPT
    if include_context:
        brief = build_context_brief(db, user_id)
        system = f"{SYSTEM_PROMPT}\n\n## 当前用户上下文（摘要，详细请用工具）\n{brief}"
    history = list_messages(db, user_id, session_id, limit=40)
    msgs: list[dict] = [{"role": "system", "content": system}]
    for m in history:
        if m.role in {"user", "assistant", "system"}:
            msgs.append({"role": m.role, "content": m.content})
    return msgs


def send_message(
    db: Session,
    user_id: str,
    session_id: str,
    content: str,
    *,
    include_context: bool = True,
    use_tools: bool = True,
) -> MessageOut:
    get_session(db, user_id, session_id)
    _add_message(db, user_id, session_id, "user", content.strip())
    messages = build_llm_messages(db, user_id, session_id, include_context=include_context)
    reply, _events = ai_agent.complete_with_tools(db, user_id, messages, use_tools=use_tools)
    assistant = _add_message(db, user_id, session_id, "assistant", reply)
    return MessageOut(
        id=int(assistant.id),
        session_id=assistant.session_id,
        role=assistant.role,
        content=assistant.content,
        created_at=assistant.created_at,
    )


def prepare_stream(
    db: Session,
    user_id: str,
    session_id: str,
    content: str,
    *,
    include_context: bool = True,
) -> list[dict]:
    get_session(db, user_id, session_id)
    _add_message(db, user_id, session_id, "user", content.strip())
    return build_llm_messages(db, user_id, session_id, include_context=include_context)


def finalize_stream(db: Session, user_id: str, session_id: str, reply: str) -> MessageOut:
    assistant = _add_message(db, user_id, session_id, "assistant", reply)
    return MessageOut(
        id=int(assistant.id),
        session_id=assistant.session_id,
        role=assistant.role,
        content=assistant.content,
        created_at=assistant.created_at,
    )
