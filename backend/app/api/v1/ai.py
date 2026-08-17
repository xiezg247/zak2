from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Literal

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.db import SessionLocal, get_db
from app.models.user import User
from app.repositories import chat as repo
from app.schemas.chat import (
    ChatRequest,
    LlmStatus,
    MessageOut,
    ProposalConfirmOut,
    ProposalRejectOut,
    SessionCreate,
    SessionOut,
    SessionUpdate,
    TeamStreamRequest,
)
from app.schemas.common import ApiResponse, OkOut, PageOut
from app.services import ai_agent, ai_proposals, team_orchestrator
from app.services import llm as llm_svc

router = APIRouter(prefix="/ai", tags=["ai"])


@router.get("/status", response_model=ApiResponse[LlmStatus])
def get_status(user: User = Depends(get_current_user)) -> ApiResponse[LlmStatus]:
    _ = user
    return ApiResponse(data=LlmStatus(**llm_svc.llm_status()))


@router.get("/sessions", response_model=ApiResponse[list[SessionOut]])
def get_sessions(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> ApiResponse[list[SessionOut]]:
    return ApiResponse(data=repo.ChatRepository(db, str(user.id)).list_sessions())


@router.get("/sessions/page", response_model=ApiResponse[PageOut[SessionOut]])
def get_sessions_page(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[PageOut[SessionOut]]:
    result = repo.ChatRepository(db, str(user.id)).list_sessions_page(page=page, page_size=page_size)
    return ApiResponse(data=PageOut.from_page(result))


@router.post("/sessions", response_model=ApiResponse[SessionOut])
def post_session(
    body: SessionCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[SessionOut]:
    return ApiResponse(data=repo.ChatRepository(db, str(user.id)).create_session(title=body.title, scene=body.scene))


@router.patch("/sessions/{session_id}", response_model=ApiResponse[SessionOut])
def patch_session(
    session_id: str,
    body: SessionUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[SessionOut]:
    return ApiResponse(
        data=repo.ChatRepository(db, str(user.id)).update_session(session_id, title=body.title, scene=body.scene)
    )


@router.delete("/sessions/{session_id}", response_model=ApiResponse[OkOut])
def remove_session(
    session_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[OkOut]:
    repo.ChatRepository(db, str(user.id)).delete_session(session_id)
    return ApiResponse(data=OkOut())


@router.get("/sessions/{session_id}/messages", response_model=ApiResponse[list[MessageOut]])
def get_messages(
    session_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[list[MessageOut]]:
    return ApiResponse(data=repo.ChatRepository(db, str(user.id)).list_messages(session_id))


@router.post("/sessions/{session_id}/chat", response_model=ApiResponse[MessageOut])
def post_chat(
    session_id: str,
    body: ChatRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[MessageOut]:
    return ApiResponse(
        data=repo.ChatRepository(db, str(user.id)).send_message(
            session_id,
            body.content,
            include_context=body.include_context,
            use_tools=body.use_tools,
        )
    )


@router.post("/proposals/{proposal_id}/confirm", response_model=ApiResponse[ProposalConfirmOut])
def post_confirm_proposal(
    proposal_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[ProposalConfirmOut]:
    return ApiResponse(data=ai_proposals.confirm_proposal(db, proposal_id, str(user.id)))


@router.post("/proposals/{proposal_id}/reject", response_model=ApiResponse[ProposalRejectOut])
def post_reject_proposal(
    proposal_id: str,
    user: User = Depends(get_current_user),
) -> ApiResponse[ProposalRejectOut]:
    proposal = ai_proposals.reject_proposal(proposal_id, str(user.id))
    return ApiResponse(data=ai_proposals.proposal_public(proposal))


@router.post("/team/stream")
def post_team_stream(
    body: TeamStreamRequest,
    user: User = Depends(get_current_user),
) -> StreamingResponse:
    user_id = str(user.id)
    vt_symbol = body.vt_symbol.strip()
    session_id = (body.session_id or "").strip() or None
    mode: Literal["fast", "deep"] = "deep" if (body.mode or "").strip().lower() == "deep" else "fast"

    def event_gen() -> Iterator[str]:
        report = ""
        weighted = None
        name = ""
        vt = vt_symbol
        db = SessionLocal()
        try:
            for event in team_orchestrator.stream_team_analysis_with_persist(db, user_id, vt_symbol, mode=mode):
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
                msg = repo.ChatRepository(db, user_id).finalize_stream(session_id, f"{title}\n\n{report}")
                yield f"data: {json.dumps({'type': 'done', 'message': msg.model_dump(mode='json')}, ensure_ascii=False)}\n\n"
            else:
                yield f"data: {json.dumps({'type': 'done'}, ensure_ascii=False)}\n\n"
        except Exception as exc:
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
        messages = repo.ChatRepository(db, user_id).prepare_stream(
            session_id,
            body.content,
            include_context=body.include_context,
        )
    finally:
        db.close()

    def event_gen() -> Iterator[str]:
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
            msg = repo.ChatRepository(db2, user_id).finalize_stream(session_id, reply)
            yield f"data: {json.dumps({'type': 'done', 'message': msg.model_dump(mode='json')}, ensure_ascii=False)}\n\n"
        except Exception as exc:
            yield f"data: {json.dumps({'type': 'error', 'detail': str(exc)}, ensure_ascii=False)}\n\n"
        finally:
            db2.close()

    return StreamingResponse(event_gen(), media_type="text/event-stream")
