from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import (
    ai,
    jobs,
    ops,
    ws,
)
from app.domains.auth.router import router as auth_router
from app.domains.auto_schedules.router import router as auto_schedules_router
from app.domains.backtest.router import router as backtest_router
from app.domains.channels.router import router as channels_router
from app.domains.content.router import router as content_router
from app.domains.market.router import router as market_router
from app.domains.screener.router import router as screener_router
from app.domains.watchlist.router import router as watchlist_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth_router)
api_router.include_router(jobs.router)
api_router.include_router(screener_router)
api_router.include_router(watchlist_router)
api_router.include_router(market_router)
api_router.include_router(content_router)
api_router.include_router(backtest_router)
api_router.include_router(ai.router)
api_router.include_router(ops.router)
api_router.include_router(channels_router)
api_router.include_router(auto_schedules_router)
api_router.include_router(ws.router)
