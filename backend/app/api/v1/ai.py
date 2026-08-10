from __future__ import annotations

import json

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.db import SessionLocal, get_db
from app.models.user import User
from app.schemas.chat import (
    ChatRequest,
    LlmStatus,
    MessageOut,
    SessionCreate,
    SessionOut,
    SessionUpdate,
    TeamStreamRequest,
)
from app.services import ai_agent, ai_proposals, chat_repo as repo, team_orchestrator
from app.services import llm as llm_svc

router = APIRouter(prefix="/ai", tags=["ai"])


@router.get("/status", response_model=LlmStatus)
def get_status(user: User = Depends(get_current_user)) -> LlmStatus:
    _ = user
    return LlmStatus(**llm_svc.llm_status())


@router.get("/sessions", response_model=list[SessionOut])
def get_sessions(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[SessionOut]:
    return repo.list_sessions(db, str(user.id))


@router.post("/sessions", response_model=SessionOut)
def post_session(
    body: SessionCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SessionOut:
    return repo.create_session(db, str(user.id), title=body.title, scene=body.scene)


@router.patch("/sessions/{session_id}", response_model=SessionOut)
def patch_session(
    session_id: str,
    body: SessionUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SessionOut:
    return repo.update_session(db, str(user.id), session_id, title=body.title, scene=body.scene)


@router.delete("/sessions/{session_id}")
def remove_session(
    session_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    repo.delete_session(db, str(user.id), session_id)
    return {"ok": True}


@router.get("/sessions/{session_id}/messages", response_model=list[MessageOut])
def get_messages(
    session_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[MessageOut]:
    return repo.list_messages(db, str(user.id), session_id)


@router.post("/sessions/{session_id}/chat", response_model=MessageOut)
def post_chat(
    session_id: str,
    body: ChatRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MessageOut:
    return repo.send_message(
        db,
        str(user.id),
        session_id,
        body.content,
        include_context=body.include_context,
        use_tools=body.use_tools,
    )


@router.post("/proposals/{proposal_id}/confirm")
def post_confirm_proposal(
    proposal_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    return ai_proposals.confirm_proposal(db, proposal_id, str(user.id))


@router.post("/proposals/{proposal_id}/reject")
def post_reject_proposal(
    proposal_id: str,
    user: User = Depends(get_current_user),
) -> dict:
    proposal = ai_proposals.reject_proposal(proposal_id, str(user.id))
    return {"ok": True, **ai_proposals.proposal_public(proposal)}


@router.post("/team/stream")
def post_team_stream(
    body: TeamStreamRequest,
    user: User = Depends(get_current_user),
) -> StreamingResponse:
    user_id = str(user.id)
    vt_symbol = body.vt_symbol.strip()
    session_id = (body.session_id or "").strip() or None
    mode = "deep" if (body.mode or "").strip().lower() == "deep" else "fast"

    def event_gen():
        report = ""
        weighted = None
        name = ""
        vt = vt_symbol
        db = SessionLocal()
        try:
            for event in team_orchestrator.stream_team_analysis_with_persist(
                db, user_id, vt_symbol, mode=mode
            ):
                if event.get("agent") == "system" and event.get("kind") == "done":
                    report = str(event.get("report") or "")
                    weighted = event.get("weighted")
                    name = str(event.get("name") or "")
                    vt = str(event.get("vt_symbol") or vt_symbol)
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
            if session_id and report:
                title = f"团队分析{'·深度' if mode == 'deep' else ''} {name or vt}"
                if weighted is not None:
                    title += f" · 加权 {weighted}"
                msg = repo.finalize_stream(db, user_id, session_id, f"{title}\n\n{report}")
                yield f"data: {json.dumps({'type': 'done', 'message': msg.model_dump(mode='json')}, ensure_ascii=False)}\n\n"
            else:
                yield f"data: {json.dumps({'type': 'done'}, ensure_ascii=False)}\n\n"
        except Exception as exc:  # noqa: BLE001
            yield f"data: {json.dumps({'type': 'error', 'detail': str(exc)}, ensure_ascii=False)}\n\n"
        finally:
            db.close()

    return StreamingResponse(event_gen(), media_type="text/event-stream")


@router.post("/sessions/{session_id}/chat/stream")
def post_chat_stream(
    session_id: str,
    body: ChatRequest,
    user: User = Depends(get_current_user),
) -> StreamingResponse:
    user_id = str(user.id)
    use_tools = body.use_tools
    db = SessionLocal()
    try:
        messages = repo.prepare_stream(
            db,
            user_id,
            session_id,
            body.content,
            include_context=body.include_context,
        )
    finally:
        db.close()

    def event_gen():
        reply = ""
        db2 = SessionLocal()
        try:
            for event in ai_agent.stream_with_tools(db2, user_id, messages, use_tools=use_tools):
                et = event.get("type")
                if et in {"tool_started", "tool_finished", "confirm_required"}:
                    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                elif et == "delta":
                    yield f"data: {json.dumps({'type': 'delta', 'content': event.get('content')}, ensure_ascii=False)}\n\n"
                elif et == "reply_done":
                    reply = str(event.get("content") or "")
            msg = repo.finalize_stream(db2, user_id, session_id, reply)
            yield f"data: {json.dumps({'type': 'done', 'message': msg.model_dump(mode='json')}, ensure_ascii=False)}\n\n"
        except Exception as exc:  # noqa: BLE001
            yield f"data: {json.dumps({'type': 'error', 'detail': str(exc)}, ensure_ascii=False)}\n\n"
        finally:
            db2.close()

    return StreamingResponse(event_gen(), media_type="text/event-stream")
