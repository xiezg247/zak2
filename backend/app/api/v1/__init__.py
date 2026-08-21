from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import (
    ai,
    auto_schedules,
    backtest,
    content,
    jobs,
    ops,
    watchlist,
    ws,
)
from app.domains.auth.router import router as auth_router
from app.domains.channels.router import router as channels_router
from app.domains.market.router import router as market_router
from app.domains.screener.router import router as screener_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth_router)
api_router.include_router(jobs.router)
api_router.include_router(screener_router)
api_router.include_router(watchlist.router)
api_router.include_router(market_router)
api_router.include_router(content.router)
api_router.include_router(backtest.router)
api_router.include_router(ai.router)
api_router.include_router(ops.router)
api_router.include_router(channels_router)
api_router.include_router(auto_schedules.router)
api_router.include_router(ws.router)
