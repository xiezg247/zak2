"""AI 写操作 proposal：进程内 TTL 存储，确认后才落库。"""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

PROPOSAL_TTL_SEC = 600

_lock = threading.Lock()
_STORE: dict[str, Proposal] = {}


@dataclass
class Proposal:
    id: str
    user_id: str
    tool: str
    args: dict[str, Any]
    summary: str
    created_at: float = field(default_factory=time.time)
    status: str = "pending"  # pending | confirmed | rejected


def _purge_expired_locked(now: float | None = None) -> None:
    ts = now if now is not None else time.time()
    dead = [pid for pid, p in _STORE.items() if ts - p.created_at > PROPOSAL_TTL_SEC]
    for pid in dead:
        del _STORE[pid]


def clear_all() -> None:
    """仅供测试。"""
    with _lock:
        _STORE.clear()


def create_proposal(
    *,
    user_id: str,
    tool: str,
    args: dict[str, Any],
    summary: str,
) -> Proposal:
    proposal = Proposal(
        id=str(uuid.uuid4()),
        user_id=user_id,
        tool=tool,
        args=dict(args),
        summary=summary.strip() or tool,
    )
    with _lock:
        _purge_expired_locked()
        _STORE[proposal.id] = proposal
    return proposal


def get_proposal(proposal_id: str, user_id: str) -> Proposal:
    with _lock:
        _purge_expired_locked()
        proposal = _STORE.get(proposal_id)
    if proposal is None:
        raise HTTPException(status_code=404, detail="确认项不存在或已过期")
    if proposal.user_id != user_id:
        raise HTTPException(status_code=404, detail="确认项不存在或已过期")
    if time.time() - proposal.created_at > PROPOSAL_TTL_SEC:
        with _lock:
            _STORE.pop(proposal_id, None)
        raise HTTPException(status_code=404, detail="确认项不存在或已过期")
    return proposal


def reject_proposal(proposal_id: str, user_id: str) -> Proposal:
    proposal = get_proposal(proposal_id, user_id)
    if proposal.status != "pending":
        raise HTTPException(status_code=409, detail=f"确认项状态为 {proposal.status}，无法拒绝")
    proposal.status = "rejected"
    return proposal


def confirm_proposal(db: Session, proposal_id: str, user_id: str) -> dict[str, Any]:
    proposal = get_proposal(proposal_id, user_id)
    if proposal.status != "pending":
        raise HTTPException(status_code=409, detail=f"确认项状态为 {proposal.status}，无法确认")

    from app.services import ai_tools

    result = ai_tools.execute_write_tool(db, user_id, proposal.tool, proposal.args)
    if isinstance(result, dict) and result.get("error"):
        raise HTTPException(status_code=400, detail=str(result["error"]))
    proposal.status = "confirmed"
    return {
        "ok": True,
        "proposal_id": proposal.id,
        "tool": proposal.tool,
        "summary": proposal.summary,
        "result": result,
    }


def proposal_public(proposal: Proposal) -> dict[str, Any]:
    return {
        "proposal_id": proposal.id,
        "tool": proposal.tool,
        "summary": proposal.summary,
        "args": proposal.args,
        "status": proposal.status,
    }
