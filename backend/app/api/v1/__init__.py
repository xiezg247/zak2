from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import (
    ai,
    auth,
    auto_schedules,
    backtest,
    channels,
    content,
    jobs,
    market,
    ops,
    screener,
    watchlist,
    ws,
)

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(jobs.router)
api_router.include_router(screener.router)
api_router.include_router(watchlist.router)
api_router.include_router(market.router)
api_router.include_router(content.router)
api_router.include_router(backtest.router)
api_router.include_router(ai.router)
api_router.include_router(ops.router)
api_router.include_router(channels.router)
api_router.include_router(auto_schedules.router)
api_router.include_router(ws.router)
