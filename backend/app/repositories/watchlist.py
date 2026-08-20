"""兼容壳：实现已迁至 app.domains.watchlist.repository。"""

from app.domains.watchlist.repository import (
    GROUPS_MAX,
    WATCHLIST_MAX,
    WatchlistGroupMemberRepository,
    WatchlistGroupRepository,
    WatchlistItemRepository,
    item_keys,
    resolve_symbol_pair,
)

__all__ = [
    "GROUPS_MAX",
    "WATCHLIST_MAX",
    "WatchlistGroupMemberRepository",
    "WatchlistGroupRepository",
    "WatchlistItemRepository",
    "item_keys",
    "resolve_symbol_pair",
]
