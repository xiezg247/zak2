"""信号名单业务。"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.domains.watchlist.schemas import (
    SignalPanelMemberRequest,
    SignalPanelOut,
    SignalPanelReplaceRequest,
)
from app.domains.watchlist.signal_panel_repo import (
    SIGNAL_PANEL_MAX_SYMBOLS,
    SignalPanelRepository,
)


def _panel_out(symbols: list[str]) -> SignalPanelOut:
    return SignalPanelOut(
        symbols=symbols,
        max_symbols=SIGNAL_PANEL_MAX_SYMBOLS,
        count=len(symbols),
    )


class SignalPanelService:
    @staticmethod
    def get(db: Session, user_id: str) -> SignalPanelOut:
        return SignalPanelRepository(db, user_id).panel_payload()

    @staticmethod
    def replace(db: Session, user_id: str, body: SignalPanelReplaceRequest) -> SignalPanelOut:
        symbols = SignalPanelRepository(db, user_id).save_symbols(body.symbols)
        return _panel_out(symbols)

    @staticmethod
    def add(db: Session, user_id: str, body: SignalPanelMemberRequest) -> SignalPanelOut:
        symbols = SignalPanelRepository(db, user_id).add_symbol(body.symbol)
        return _panel_out(symbols)

    @staticmethod
    def remove(db: Session, user_id: str, vt_symbol: str) -> SignalPanelOut:
        symbols = SignalPanelRepository(db, user_id).remove_symbol(vt_symbol)
        return _panel_out(symbols)
