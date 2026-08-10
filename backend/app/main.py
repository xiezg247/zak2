from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import api_router
from app.core.settings import get_settings
from app.services.quote_notify_hub import get_quote_notify_hub


@asynccontextmanager
async def lifespan(app: FastAPI):
    import asyncio

    hub = get_quote_notify_hub()
    hub.start(asyncio.get_running_loop())
    from app.services.embedded_scheduler import start_embedded_scheduler, stop_embedded_scheduler

    start_embedded_scheduler()
    yield
    stop_embedded_scheduler()
    hub.stop()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="zak2 API", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(api_router)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
