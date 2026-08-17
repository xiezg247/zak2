from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.db import get_db
from app.models.user import User
from app.schemas.common import ApiResponse, OkOut, PageOut
from app.schemas.content import (
    BilibiliSearchOut,
    DisciplineCheckOut,
    DisciplineUpdate,
    FeedItemOut,
    FeedSubCreate,
    FeedSubOut,
    NoteEntryCreate,
    NoteEntryOut,
    NoteMemoOut,
    NoteMemoUpdate,
    NoteSymbolOut,
    PlanDraftAppendIn,
    PlanDraftAppendOut,
    PlanOut,
    PlanUpdate,
    PlaybookSectionOut,
    PlaybookSectionUpdate,
    TeamReportListItem,
    TeamReportOut,
)
from app.services import feed as feed_svc
from app.services import notes as notes_svc
from app.services import plan_draft as plan_draft_svc
from app.services import plan_manage as plan_manage_svc
from app.services import playbook as playbook_svc
from app.services import team_reports

router = APIRouter(tags=["content"])


@router.get("/playbook/sections", response_model=ApiResponse[list[PlaybookSectionOut]])
def get_sections(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> ApiResponse[list[PlaybookSectionOut]]:
    _ = user
    return ApiResponse(data=playbook_svc.list_sections(db))


@router.patch("/playbook/sections/{section_id}", response_model=ApiResponse[PlaybookSectionOut])
def patch_section(
    section_id: str,
    body: PlaybookSectionUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[PlaybookSectionOut]:
    _ = user
    return ApiResponse(data=playbook_svc.update_section(db, section_id, body))


@router.get("/playbook/discipline", response_model=ApiResponse[list[DisciplineCheckOut]])
def get_discipline(
    trade_date: str | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[list[DisciplineCheckOut]]:
    return ApiResponse(data=playbook_svc.list_discipline(db, str(user.id), trade_date))


@router.put("/playbook/discipline/{check_id}", response_model=ApiResponse[DisciplineCheckOut])
def put_discipline(
    check_id: str,
    body: DisciplineUpdate,
    trade_date: str | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[DisciplineCheckOut]:
    return ApiResponse(data=playbook_svc.set_discipline(db, str(user.id), check_id, body.checked, trade_date))


@router.get("/playbook/plans", response_model=ApiResponse[list[PlanOut]])
def get_plans(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> ApiResponse[list[PlanOut]]:
    return ApiResponse(data=feed_svc.list_plans(db, str(user.id)))


@router.post("/playbook/plans/draft-append", response_model=ApiResponse[PlanDraftAppendOut])
def post_draft_append(
    body: PlanDraftAppendIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[PlanDraftAppendOut]:
    result = plan_draft_svc.append_symbol_to_draft(
        db,
        str(user.id),
        vt_symbol=body.vt_symbol,
        name=body.name,
        source=body.source,
    )
    return ApiResponse(data=PlanDraftAppendOut(**result))


@router.patch("/playbook/plans/{plan_id}", response_model=ApiResponse[PlanOut])
def patch_plan(
    plan_id: str,
    body: PlanUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[PlanOut]:
    return ApiResponse(
        data=plan_manage_svc.update_plan(
            db,
            str(user.id),
            plan_id,
            notes=body.notes,
            max_position_pct=body.max_position_pct,
            symbols=body.symbols,
        )
    )


@router.post("/playbook/plans/{plan_id}/activate", response_model=ApiResponse[PlanOut])
def post_activate_plan(
    plan_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[PlanOut]:
    return ApiResponse(data=plan_manage_svc.activate_plan(db, str(user.id), plan_id))


@router.post("/playbook/plans/{plan_id}/abandon", response_model=ApiResponse[PlanOut])
def post_abandon_plan(
    plan_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[PlanOut]:
    return ApiResponse(data=plan_manage_svc.abandon_plan(db, str(user.id), plan_id))


@router.get("/notes/symbols", response_model=ApiResponse[list[NoteSymbolOut]])
def get_note_symbols(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> ApiResponse[list[NoteSymbolOut]]:
    return ApiResponse(data=notes_svc.list_note_symbols(db, str(user.id)))


@router.get("/notes/reports/{report_id}", response_model=ApiResponse[TeamReportOut])
def get_team_report(
    report_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[TeamReportOut]:
    row = team_reports.get_report(db, str(user.id), report_id)
    if not row:
        raise HTTPException(status_code=404, detail="研报不存在")
    return ApiResponse(data=TeamReportOut(**row))


@router.get("/notes/{vt_symbol}/reports", response_model=ApiResponse[list[TeamReportListItem]])
def list_team_reports(
    vt_symbol: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[list[TeamReportListItem]]:
    try:
        rows = team_reports.list_reports(db, str(user.id), vt_symbol)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ApiResponse(data=[TeamReportListItem(**r) for r in rows])


@router.get("/notes/{vt_symbol}/reports/page", response_model=ApiResponse[PageOut[TeamReportListItem]])
def list_team_reports_page(
    vt_symbol: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[PageOut[TeamReportListItem]]:
    try:
        result = team_reports.list_reports_page(db, str(user.id), vt_symbol, page=page, page_size=page_size)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ApiResponse(data=PageOut.from_page(result.map(lambda r: TeamReportListItem(**r))))


@router.get("/notes/{vt_symbol}/memo", response_model=ApiResponse[NoteMemoOut])
def get_note_memo(
    vt_symbol: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[NoteMemoOut]:
    return ApiResponse(data=notes_svc.get_memo(db, str(user.id), vt_symbol))


@router.put("/notes/{vt_symbol}/memo", response_model=ApiResponse[NoteMemoOut])
def put_note_memo(
    vt_symbol: str,
    body: NoteMemoUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[NoteMemoOut]:
    return ApiResponse(data=notes_svc.upsert_memo(db, str(user.id), vt_symbol, body.body))


@router.get("/notes/{vt_symbol}/entries", response_model=ApiResponse[list[NoteEntryOut]])
def get_note_entries(
    vt_symbol: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[list[NoteEntryOut]]:
    return ApiResponse(data=notes_svc.list_entries(db, str(user.id), vt_symbol))


@router.get("/notes/{vt_symbol}/entries/page", response_model=ApiResponse[PageOut[NoteEntryOut]])
def get_note_entries_page(
    vt_symbol: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[PageOut[NoteEntryOut]]:
    result = notes_svc.list_entries_page(db, str(user.id), vt_symbol, page=page, page_size=page_size)
    return ApiResponse(data=PageOut.from_page(result))


@router.post("/notes/{vt_symbol}/entries", response_model=ApiResponse[NoteEntryOut])
def post_note_entry(
    vt_symbol: str,
    body: NoteEntryCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[NoteEntryOut]:
    return ApiResponse(data=notes_svc.add_entry(db, str(user.id), vt_symbol, body.body))


@router.delete("/notes/entries/{entry_id}", response_model=ApiResponse[OkOut])
def delete_note_entry(
    entry_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[OkOut]:
    if not notes_svc.delete_entry(db, str(user.id), entry_id):
        raise HTTPException(status_code=404, detail="流水不存在")
    return ApiResponse(data=OkOut())


@router.get("/feed/bilibili/search", response_model=ApiResponse[BilibiliSearchOut])
def get_bilibili_search(
    q: str = Query(""),
    limit: int = Query(default=8, ge=1, le=20),
    user: User = Depends(get_current_user),
) -> ApiResponse[BilibiliSearchOut]:
    rows = feed_svc.search_bilibili_ups(q, limit=limit)
    return ApiResponse(data=BilibiliSearchOut(results=rows))


@router.get("/feed/subscriptions", response_model=ApiResponse[list[FeedSubOut]])
def get_feed_subs(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> ApiResponse[list[FeedSubOut]]:
    return ApiResponse(data=feed_svc.list_subscriptions(db, str(user.id)))


@router.post("/feed/subscriptions", response_model=ApiResponse[FeedSubOut])
def post_feed_sub(
    body: FeedSubCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[FeedSubOut]:
    return ApiResponse(data=feed_svc.add_bilibili_up(db, str(user.id), body.mid, sync_now=body.sync_now))


@router.patch("/feed/subscriptions/{sub_id}", response_model=ApiResponse[FeedSubOut])
def patch_feed_sub(
    sub_id: str,
    enabled: bool = Query(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[FeedSubOut]:
    return ApiResponse(data=feed_svc.set_subscription_enabled(db, str(user.id), sub_id, enabled))


@router.delete("/feed/subscriptions/{sub_id}", response_model=ApiResponse[OkOut])
def delete_feed_sub(
    sub_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[OkOut]:
    feed_svc.delete_subscription(db, str(user.id), sub_id)
    return ApiResponse(data=OkOut())


@router.get("/feed/items", response_model=ApiResponse[list[FeedItemOut]])
def get_feed_items(
    subscription_id: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[list[FeedItemOut]]:
    return ApiResponse(data=feed_svc.list_feed_items(db, str(user.id), subscription_id=subscription_id, limit=limit))


@router.get("/feed/items/page", response_model=ApiResponse[PageOut[FeedItemOut]])
def get_feed_items_page(
    subscription_id: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[PageOut[FeedItemOut]]:
    result = feed_svc.list_feed_items_page(
        db, str(user.id), subscription_id=subscription_id, page=page, page_size=page_size
    )
    return ApiResponse(data=PageOut.from_page(result))


@router.post("/feed/items/{item_id}/read", response_model=ApiResponse[OkOut])
def post_feed_read(
    item_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[OkOut]:
    return ApiResponse(data=OkOut(**feed_svc.mark_feed_read(db, str(user.id), item_id)))
