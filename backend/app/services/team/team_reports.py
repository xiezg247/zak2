"""Web 投研研报落库（app.web_team_reports，与桌面表无关）。"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.report import WebTeamReport
from app.repositories.pagination import Page, paginate
from app.domains.content.schemas import TeamReportListItem, TeamReportOut
from app.services.symbols import parse_flexible_symbol, to_vt_symbol

_logger = logging.getLogger(__name__)

REPORT_MAX_BODY = 128_000
REPORT_MAX_TITLE = 200
SUMMARY_MAX = 240


def _now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _clip(text_v: str, max_len: int) -> str:
    cleaned = text_v.strip()
    if len(cleaned) <= max_len:
        return cleaned
    return cleaned[:max_len]


def _build_summary(body: str) -> str:
    flat = " ".join(line.strip() for line in body.strip().splitlines() if line.strip())
    if len(flat) <= SUMMARY_MAX:
        return flat
    return flat[:SUMMARY_MAX] + "…"


def should_persist_report(body: str) -> bool:
    text_v = (body or "").strip()
    return bool(text_v) and "综合研判" in text_v


def persist_team_report(
    db: Session,
    user_id: str,
    *,
    vt_symbol: str,
    name: str,
    body: str,
    mode: str = "fast",
    context: dict[str, Any] | None = None,
) -> TeamReportListItem | None:
    if not should_persist_report(body):
        return None
    try:
        symbol, exchange = parse_flexible_symbol(vt_symbol)
    except ValueError:
        _logger.warning("team report skip: bad vt_symbol=%s", vt_symbol)
        return None

    head = (name or symbol).strip()
    title = _clip(f"{head} · 投研团队 · {_now_iso()}", REPORT_MAX_TITLE)
    body_clipped = _clip(body, REPORT_MAX_BODY)
    summary = _build_summary(body_clipped)
    vt = to_vt_symbol(symbol, exchange)
    ctx = json.dumps(context or {}, ensure_ascii=False)
    now = _now_iso()
    row = WebTeamReport(
        user_id=user_id,
        symbol=symbol,
        exchange=exchange,
        vt_symbol=vt,
        title=title,
        body=body_clipped,
        summary=summary,
        mode=mode if mode in {"fast", "deep"} else "fast",
        context_json=ctx,
        created_at=now,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return TeamReportListItem(
        id=int(row.id),
        title=str(row.title or ""),
        vt_symbol=str(row.vt_symbol or vt),
        created_at=str(row.created_at or now),
        summary=str(row.summary or ""),
        mode=str(row.mode or mode),
    )


def _report_list_item(r: WebTeamReport, symbol: str, exchange: str) -> TeamReportListItem:
    return TeamReportListItem(
        id=int(r.id),
        title=str(r.title or ""),
        summary=str(r.summary or ""),
        mode=str(r.mode or ""),
        created_at=str(r.created_at or ""),
        vt_symbol=str(r.vt_symbol or to_vt_symbol(symbol, exchange)),
    )


def list_reports(db: Session, user_id: str, vt_symbol: str, *, limit: int = 50) -> list[TeamReportListItem]:
    try:
        symbol, exchange = parse_flexible_symbol(vt_symbol)
    except ValueError as exc:
        raise ValueError(str(exc)) from exc
    limit = max(1, min(int(limit), 100))
    rows = db.scalars(
        select(WebTeamReport)
        .where(
            WebTeamReport.user_id == user_id,
            WebTeamReport.symbol == symbol,
            WebTeamReport.exchange == exchange,
        )
        .order_by(WebTeamReport.created_at.desc(), WebTeamReport.id.desc())
        .limit(limit)
    )
    return [_report_list_item(r, symbol, exchange) for r in rows]


def list_reports_page(
    db: Session,
    user_id: str,
    vt_symbol: str,
    *,
    page: int = 1,
    page_size: int = 20,
) -> Page[TeamReportListItem]:
    try:
        symbol, exchange = parse_flexible_symbol(vt_symbol)
    except ValueError as exc:
        raise ValueError(str(exc)) from exc
    stmt = (
        select(WebTeamReport)
        .where(
            WebTeamReport.user_id == user_id,
            WebTeamReport.symbol == symbol,
            WebTeamReport.exchange == exchange,
        )
        .order_by(WebTeamReport.created_at.desc(), WebTeamReport.id.desc())
    )
    result = paginate(db, stmt, page=page, page_size=page_size)
    return result.map(lambda r: _report_list_item(r, symbol, exchange))


def get_report(db: Session, user_id: str, report_id: int) -> TeamReportOut | None:
    row = db.scalar(
        select(WebTeamReport).where(
            WebTeamReport.id == int(report_id),
            WebTeamReport.user_id == user_id,
        )
    )
    if not row:
        return None
    return TeamReportOut(
        id=int(row.id),
        symbol=str(row.symbol),
        exchange=str(row.exchange),
        vt_symbol=str(row.vt_symbol or ""),
        title=str(row.title or ""),
        body=str(row.body or ""),
        summary=str(row.summary or ""),
        mode=str(row.mode or ""),
        context_json=str(row.context_json or ""),
        created_at=str(row.created_at or ""),
    )
