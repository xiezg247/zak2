"""兼容壳：实现已迁至 app.domains.watchlist.signal_panel_repo。"""

from app.domains.watchlist.signal_panel_repo import (
    NAMESPACE,
    PREF_KEY,
    SIGNAL_PANEL_MAX_SYMBOLS,
    SignalPanelRepository,
    normalize_symbols,
)

__all__ = [
    "NAMESPACE",
    "PREF_KEY",
    "SIGNAL_PANEL_MAX_SYMBOLS",
    "SignalPanelRepository",
    "normalize_symbols",
]
