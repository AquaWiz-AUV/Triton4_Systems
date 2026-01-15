"""FastAPI application for Triton-4 COM server."""

from __future__ import annotations

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from .database import get_session, init_db
from .logging_config import configure_logging
from .routers import admin, ascent, descent, hb, web_commands, web_devices, web_dives, web_events, web_telemetry


def create_app() -> FastAPI:
    configure_logging()
    app = FastAPI(
        title="Triton-4 COM Server",
        version="0.1.0",
        description="Server-side API handling Triton-4 vehicle communications and Web API.",
        docs_url="/api/v1/docs",
        redoc_url="/api/v1/redoc",
        openapi_url="/api/v1/openapi.json",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.on_event("startup")
    async def startup_event() -> None:
        await init_db()

    app.include_router(hb.router)
    app.include_router(descent.router)
    app.include_router(ascent.router)

    app.include_router(web_devices.router)
    app.include_router(web_commands.router)
    app.include_router(web_telemetry.router)
    app.include_router(web_dives.router)
    app.include_router(web_events.router)
    app.include_router(admin.router)

    @app.get("/health")
    async def healthcheck(session: AsyncSession = Depends(get_session)) -> dict[str, bool]:
        result = await session.execute(text("SELECT 1"))
        return {"status": True, "db": bool(result.scalar_one_or_none())}

    return app


app = create_app()
