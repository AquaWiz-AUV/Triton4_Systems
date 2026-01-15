"""SQLAlchemy models for Triton-4 COM server."""

from __future__ import annotations

import enum
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum as SqlEnum,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from .database import Base

JSONType = JSONB().with_variant(JSON(), "sqlite")


class CommandStatus(str, enum.Enum):
    """Lifecycle for RUN_DIVE commands."""

    QUEUED = "QUEUED"
    ISSUED = "ISSUED"
    EXECUTING = "EXECUTING"
    COMPLETED = "COMPLETED"
    CANCELED = "CANCELED"
    ERROR = "ERROR"
    EXPIRED = "EXPIRED"


class Device(Base):
    __tablename__ = "devices"

    mid: Mapped[str] = mapped_column(String(32), primary_key=True)
    fw: Mapped[str] = mapped_column(String(64), nullable=False)
    last_state: Mapped[str] = mapped_column(String(32), nullable=False)
    last_hb_seq: Mapped[Optional[int]] = mapped_column(BigInteger)
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    last_exec_cmd_seq: Mapped[Optional[int]] = mapped_column(BigInteger)
    last_exec_status: Mapped[Optional[str]] = mapped_column(String(16))
    last_pos: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONType)
    last_pwr: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONType)
    last_env: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONType)
    last_net: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONType)
    recovery_reason: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONType)

    heartbeats: Mapped[list["Heartbeat"]] = relationship(back_populates="device")


class Heartbeat(Base):
    __tablename__ = "heartbeats"
    __table_args__ = (
        UniqueConstraint("mid", "hb_seq", name="uq_heartbeats_mid_seq"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    mid: Mapped[str] = mapped_column(String(32), ForeignKey("devices.mid"), nullable=False)
    hb_seq: Mapped[int] = mapped_column(BigInteger, nullable=False)
    ts_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    device: Mapped["Device"] = relationship(back_populates="heartbeats")


class Command(Base):
    __tablename__ = "commands"
    __table_args__ = (UniqueConstraint("mid", "seq", name="uq_commands_mid_seq"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    mid: Mapped[str] = mapped_column(String(32), nullable=False)
    seq: Mapped[int] = mapped_column(BigInteger, nullable=False)
    cmd: Mapped[str] = mapped_column(String(32), nullable=False, default="RUN_DIVE")
    args: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False)
    status: Mapped[CommandStatus] = mapped_column(
        SqlEnum(CommandStatus), default=CommandStatus.QUEUED, nullable=False
    )
    issued_by: Mapped[Optional[str]] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class DescentCheck(Base):
    __tablename__ = "descent_checks"
    __table_args__ = (UniqueConstraint("mid", "check_seq", name="uq_descent_mid_seq"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    mid: Mapped[str] = mapped_column(String(32), nullable=False)
    check_seq: Mapped[int] = mapped_column(BigInteger, nullable=False)
    cmd_seq: Mapped[int] = mapped_column(BigInteger, nullable=False)
    plan_hash: Mapped[str] = mapped_column(String(32), nullable=False)
    ok: Mapped[bool] = mapped_column(Boolean, nullable=False)
    reason: Mapped[Optional[str]] = mapped_column(String(128))
    payload: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Dive(Base):
    __tablename__ = "dives"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    mid: Mapped[str] = mapped_column(String(32), nullable=False)
    cmd_seq: Mapped[int] = mapped_column(BigInteger, nullable=False)
    ok: Mapped[Optional[bool]] = mapped_column(Boolean)
    summary: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONType)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class EventLog(Base):
    __tablename__ = "event_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    mid: Mapped[Optional[str]] = mapped_column(String(32))
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    detail: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
