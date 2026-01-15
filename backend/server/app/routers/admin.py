"""Admin API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import engine, get_session
from ..models import Command, DescentCheck, Device, Dive, EventLog, Heartbeat
from ..schemas import SimpleMessage

router = APIRouter(prefix="/api/v1/admin", tags=["Admin"])


@router.post("/reset-db", response_model=SimpleMessage)
async def reset_db(
    session: AsyncSession = Depends(get_session),
) -> SimpleMessage:
    """Delete all data from the database and reset sequences."""
    try:
        # List of tables to delete in order (to avoid foreign key constraints)
        tables_to_delete = [
            EventLog,
            DescentCheck,
            Dive,
            Command,
            Heartbeat,
            Device,
        ]

        # Delete all data
        for model in tables_to_delete:
            await session.execute(model.__table__.delete())

        # Reset auto-increment sequences
        is_sqlite = "sqlite" in str(engine.url)

        if is_sqlite:
            # SQLite: delete from sqlite_sequence to reset AUTOINCREMENT
            for model in tables_to_delete:
                table_name = model.__tablename__
                await session.execute(
                    text(f"DELETE FROM sqlite_sequence WHERE name = :table_name"),
                    {"table_name": table_name},
                )
        else:
            # PostgreSQL: reset sequences
            sequence_tables = ["event_logs", "descent_checks", "dives", "commands", "heartbeats"]
            for table_name in sequence_tables:
                await session.execute(
                    text(f"ALTER SEQUENCE {table_name}_id_seq RESTART WITH 1")
                )

        await session.commit()
        return SimpleMessage(message="Database reset complete (including sequences)")
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to reset database: {str(e)}")
