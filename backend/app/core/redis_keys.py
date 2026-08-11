"""zak2 Redis 键常量（行情 / 排行 / 通知）。"""

from __future__ import annotations

KEY_PREFIX = "zak2"
RANK_KEY_FMT = f"{KEY_PREFIX}:rank:{{field}}"
QUOTE_KEY_FMT = f"{KEY_PREFIX}:quote:{{symbol}}"
QUOTE_BLOB_KEY_FMT = f"{KEY_PREFIX}:quote:b:{{symbol}}"
META_UPDATED_AT_KEY = f"{KEY_PREFIX}:meta:updated_at"
META_QUOTE_COUNT_KEY = f"{KEY_PREFIX}:meta:quote_count"
META_SEQ_KEY = f"{KEY_PREFIX}:meta:seq"
NOTIFY_CHANNEL = f"{KEY_PREFIX}:notify:quotes"
