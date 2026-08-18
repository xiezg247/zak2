"""运维健康检查。"""

from __future__ import annotations

from urllib.parse import urlparse

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.settings import get_settings
from app.schemas.ops import (
    HealthCollectorOut,
    HealthLlmOut,
    HealthMcpOut,
    HealthOut,
    HealthPostgresOut,
    HealthRedisOut,
    HealthSchedulerLockOut,
)
from app.services.ai import mcp_client
from app.services.market.quotes import get_quote_store
from app.services.ops import scheduler_lock
from app.services.quote_collect.control import collector_health


def _mask_url(url: str) -> str:
    if not url:
        return ""
    try:
        p = urlparse(url)
        host = p.hostname or ""
        port = f":{p.port}" if p.port else ""
        path = p.path or ""
        user = f"{p.username}@" if p.username else ""
        return f"{p.scheme}://{user}{host}{port}{path}"
    except Exception:
        return "(invalid)"


def health_snapshot(db: Session) -> HealthOut:
    settings = get_settings()
    pg_ok = False
    pg_error = ""
    try:
        db.execute(text("SELECT 1"))
        pg_ok = True
    except Exception as exc:
        pg_error = str(exc)

    store = get_quote_store()
    redis_meta = store.meta()
    redis_ok = bool(redis_meta.get("available"))

    return HealthOut(
        postgres=HealthPostgresOut(
            ok=pg_ok,
            error=pg_error,
            url=_mask_url(settings.database_url.replace("postgresql+psycopg", "postgresql")),
        ),
        redis=HealthRedisOut(
            ok=redis_ok,
            url=_mask_url(settings.redis_url),
            updated_at=redis_meta.get("updated_at"),
            quote_count=int(redis_meta.get("quote_count") or 0),
        ),
        llm=HealthLlmOut(
            configured=bool(settings.llm_api_key.strip()),
            model=settings.llm_model,
            api_base=settings.llm_api_base.rstrip("/"),
        ),
        tushare_configured=bool(settings.tushare_token.strip()),
        mcp=HealthMcpOut(**mcp_client.probe_connection(settings)),
        scheduler_lock=HealthSchedulerLockOut(
            ok=redis_ok,
            backend="redis",
            ttl_seconds=scheduler_lock.clamp_ttl(settings.scheduler_lock_ttl_seconds),
            key_prefix=scheduler_lock.LOCK_KEY_PREFIX,
        ),
        quote_collector=HealthCollectorOut(**collector_health()),
        note="可跑：purge / 日历 / 板块 / limit_list / 日 K 补全 / 选股；行情采集见独立进程 python -m app.quote_collector；MCP 可接 Streamable HTTP 诊断工具。",
    )
