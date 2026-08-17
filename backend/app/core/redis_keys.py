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
ARQ_JOBS_RECENT_ZSET = f"{KEY_PREFIX}:arq:jobs:recent"
ARQ_JOBS_META_KEY_FMT = f"{KEY_PREFIX}:arq:jobs:meta:{{job_id}}"
ARQ_JOBS_RECENT_MAX = 100
ARQ_BARS_LOCK_KEY = f"{KEY_PREFIX}:arq:lock:bars"
AUTH_FAIL_USER_KEY_FMT = f"{KEY_PREFIX}:auth:fail:user:{{username}}"
AUTH_FAIL_IP_KEY_FMT = f"{KEY_PREFIX}:auth:fail:ip:{{ip}}"
