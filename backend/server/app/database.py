"""Database session and metadata helpers."""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


def _build_engine() -> AsyncEngine:
    database_url = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./triton_com.db")
    return create_async_engine(
        database_url,
        echo=bool(os.getenv("SQLALCHEMY_ECHO")),
        pool_pre_ping=True,
    )


engine = _build_engine()
SessionMaker = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields a DB session."""

    async with SessionMaker() as session:
        yield session


async def init_db() -> None:
    """Create tables for development usage (production uses Alembic)."""

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
