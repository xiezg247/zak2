from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.errors import NotFound, ValidationFailed
from app.domains.content.schemas import TeamReportListItem, TeamReportOut
from app.repositories.pagination import Page
from app.services.team import team_reports


def get_team_report(db: Session, user_id: str, report_id: int) -> TeamReportOut:
    row = team_reports.get_report(db, user_id, report_id)
    if not row:
        raise NotFound("研报不存在")
    return row


def list_team_reports(db: Session, user_id: str, vt_symbol: str) -> list[TeamReportListItem]:
    try:
        return team_reports.list_reports(db, user_id, vt_symbol)
    except ValueError as exc:
        raise ValidationFailed(str(exc)) from exc


def list_team_reports_page(
    db: Session, user_id: str, vt_symbol: str, *, page: int, page_size: int
) -> Page[TeamReportListItem]:
    try:
        return team_reports.list_reports_page(db, user_id, vt_symbol, page=page, page_size=page_size)
    except ValueError as exc:
        raise ValidationFailed(str(exc)) from exc
