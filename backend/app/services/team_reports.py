"""Web 投研研报落库（app.web_team_reports，与桌面表无关）。"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.symbols import parse_flexible_symbol, to_vt_symbol

_logger = logging.getLogger(__name__)

REPORT_MAX_BODY = 128_000
REPORT_MAX_TITLE = 200
SUMMARY_MAX = 240

_DDL = """
CREATE TABLE IF NOT EXISTS app.web_team_reports (
  id bigserial PRIMARY KEY,
  user_id uuid NOT NULL,
  symbol text NOT NULL,
  exchange text NOT NULL,
  vt_symbol text NOT NULL DEFAULT '',
  title text NOT NULL DEFAULT '',
  body text NOT NULL,
  summary text NOT NULL DEFAULT '',
  mode text NOT NULL DEFAULT 'fast',
  context_json text NOT NULL DEFAULT '',
  created_at text NOT NULL
)
"""


def ensure_web_team_reports_table(db: Session) -> None:
    db.execute(text(_DDL))
    db.execute(
        text(
            """
            CREATE INDEX IF NOT EXISTS ix_web_team_reports_user_vt
            ON app.web_team_reports (user_id, vt_symbol, created_at DESC)
            """
        )
    )


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


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
) -> dict[str, Any] | None:
    if not should_persist_report(body):
        return None
    try:
        symbol, exchange = parse_flexible_symbol(vt_symbol)
    except ValueError:
        _logger.warning("team report skip: bad vt_symbol=%s", vt_symbol)
        return None

    ensure_web_team_reports_table(db)
    head = (name or symbol).strip()
    title = _clip(f"{head} · 投研团队 · {_now_iso()}", REPORT_MAX_TITLE)
    body_clipped = _clip(body, REPORT_MAX_BODY)
    summary = _build_summary(body_clipped)
    vt = to_vt_symbol(symbol, exchange)
    ctx = json.dumps(context or {}, ensure_ascii=False)
    now = _now_iso()
    row = db.execute(
        text(
            """
            INSERT INTO app.web_team_reports (
              user_id, symbol, exchange, vt_symbol, title, body, summary, mode, context_json, created_at
            ) VALUES (
              CAST(:uid AS uuid), :symbol, :exchange, :vt, :title, :body, :summary, :mode, :ctx, :now
            )
            RETURNING id, title, vt_symbol, created_at, summary, mode
            """
        ),
        {
            "uid": user_id,
            "symbol": symbol,
            "exchange": exchange,
            "vt": vt,
            "title": title,
            "body": body_clipped,
            "summary": summary,
            "mode": mode if mode in {"fast", "deep"} else "fast",
            "ctx": ctx,
            "now": now,
        },
    ).mappings().first()
    db.commit()
    if not row:
        return None
    return {
        "id": int(row["id"]),
        "title": str(row["title"] or ""),
        "vt_symbol": str(row["vt_symbol"] or vt),
        "created_at": str(row["created_at"] or now),
        "summary": str(row["summary"] or ""),
        "mode": str(row["mode"] or mode),
    }


def list_reports(db: Session, user_id: str, vt_symbol: str, *, limit: int = 50) -> list[dict[str, Any]]:
    try:
        symbol, exchange = parse_flexible_symbol(vt_symbol)
    except ValueError as exc:
        raise ValueError(str(exc)) from exc
    ensure_web_team_reports_table(db)
    limit = max(1, min(int(limit), 100))
    rows = db.execute(
        text(
            """
            SELECT id, title, summary, mode, created_at, vt_symbol
            FROM app.web_team_reports
            WHERE user_id = CAST(:uid AS uuid) AND symbol = :s AND exchange = :e
            ORDER BY created_at DESC, id DESC
            LIMIT :lim
            """
        ),
        {"uid": user_id, "s": symbol, "e": exchange, "lim": limit},
    ).mappings().all()
    return [
        {
            "id": int(r["id"]),
            "title": str(r["title"] or ""),
            "summary": str(r["summary"] or ""),
            "mode": str(r["mode"] or ""),
            "created_at": str(r["created_at"] or ""),
            "vt_symbol": str(r["vt_symbol"] or to_vt_symbol(symbol, exchange)),
        }
        for r in rows
    ]


def get_report(db: Session, user_id: str, report_id: int) -> dict[str, Any] | None:
    ensure_web_team_reports_table(db)
    row = db.execute(
        text(
            """
            SELECT id, symbol, exchange, vt_symbol, title, body, summary, mode, context_json, created_at
            FROM app.web_team_reports
            WHERE id = :id AND user_id = CAST(:uid AS uuid)
            """
        ),
        {"id": int(report_id), "uid": user_id},
    ).mappings().first()
    if not row:
        return None
    return {
        "id": int(row["id"]),
        "symbol": str(row["symbol"]),
        "exchange": str(row["exchange"]),
        "vt_symbol": str(row["vt_symbol"] or ""),
        "title": str(row["title"] or ""),
        "body": str(row["body"] or ""),
        "summary": str(row["summary"] or ""),
        "mode": str(row["mode"] or ""),
        "context_json": str(row["context_json"] or ""),
        "created_at": str(row["created_at"] or ""),
    }
