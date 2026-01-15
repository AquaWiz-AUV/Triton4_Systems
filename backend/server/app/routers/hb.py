"""Heartbeat endpoint implementation."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from .. import models, schemas
from ..database import get_session

router = APIRouter(prefix="/v1", tags=["heartbeat"])
logger = structlog.get_logger(__name__)


def _dump_optional(model: Any | None) -> dict[str, Any] | None:
    if model is None:
        return None
    return model.model_dump(mode="json", exclude_none=True)  # type: ignore[return-value]


@router.post("/hb", response_model=schemas.HeartbeatResponse)
async def post_heartbeat(
    payload: schemas.HeartbeatRequest,
    session: AsyncSession = Depends(get_session),
) -> schemas.HeartbeatResponse:
    now = datetime.now(timezone.utc)
    ack = schemas.HeartbeatAck(hb_seq=payload.hb_seq, server_time=now)
    commands_payload: list[schemas.CommandEnvelope] = []

    async with session.begin():
        device = await session.get(models.Device, payload.mid)
        if device is None:
            device = models.Device(
                mid=payload.mid,
                fw=payload.fw,
                last_state=payload.state.value,
                last_hb_seq=payload.hb_seq,
                last_seen_at=now,
                last_exec_cmd_seq=payload.exec.last_cmd_seq if payload.exec else None,
                last_exec_status=payload.exec.status.value if payload.exec else None,
                last_pos=_dump_optional(payload.pos),
                last_pwr=_dump_optional(payload.pwr),
                last_env=_dump_optional(payload.env),
                last_net=_dump_optional(payload.net),
                recovery_reason=payload.x or None,
            )
            session.add(device)
        else:
            device.fw = payload.fw
            device.last_state = payload.state.value
            device.last_hb_seq = payload.hb_seq
            device.last_seen_at = now
            device.last_exec_cmd_seq = payload.exec.last_cmd_seq if payload.exec else None
            device.last_exec_status = payload.exec.status.value if payload.exec else None
            device.last_pos = _dump_optional(payload.pos)
            device.last_pwr = _dump_optional(payload.pwr)
            device.last_env = _dump_optional(payload.env)
            device.last_net = _dump_optional(payload.net)
            device.recovery_reason = payload.x or None

        hb_exists = await session.execute(
            select(models.Heartbeat.id).where(
                models.Heartbeat.mid == payload.mid,
                models.Heartbeat.hb_seq == payload.hb_seq,
            )
        )
        if hb_exists.scalar_one_or_none() is None:
            session.add(
                models.Heartbeat(
                    mid=payload.mid,
                    hb_seq=payload.hb_seq,
                    ts_utc=payload.ts_utc,
                    payload=payload.model_dump(mode="json"),
                    received_at=now,
                )
            )

        should_issue = (
            payload.state == schemas.VehicleState.SURFACE_WAIT
            and (payload.exec is None or payload.exec.status != schemas.ExecStatus.RUNNING)
        )

        cmd_stmt = (
            select(models.Command)
            .where(
                models.Command.mid == payload.mid,
                models.Command.status.in_([models.CommandStatus.QUEUED, models.CommandStatus.ISSUED]),
            )
            .order_by(models.Command.seq.asc())
        )
        commands = list((await session.execute(cmd_stmt)).scalars())

        # Expire commands older than 2 minutes
        command_timeout = timedelta(minutes=2)
        expired_commands: list[models.Command] = []
        active_commands: list[models.Command] = []

        for command in commands:
            age = now - command.created_at.replace(tzinfo=timezone.utc)
            if age > command_timeout:
                command.status = models.CommandStatus.EXPIRED
                command.updated_at = now
                expired_commands.append(command)
                logger.info(
                    "command_expired",
                    mid=payload.mid,
                    cmd_seq=command.seq,
                    age_seconds=age.total_seconds(),
                )
            else:
                active_commands.append(command)

        # Log expired commands as events
        for cmd in expired_commands:
            session.add(
                models.EventLog(
                    mid=payload.mid,
                    event_type="CMD_EXPIRED",
                    detail={
                        "cmd_seq": cmd.seq,
                        "cmd": cmd.cmd,
                        "created_at": cmd.created_at.isoformat(),
                        "reason": "timeout_2min",
                    },
                )
            )

        # If multiple commands exist, keep only the latest one and cancel older ones
        # Commands are sorted by seq ASC, so the last one is the latest
        if len(active_commands) > 1:
            latest_command = active_commands[-1]
            older_commands = active_commands[:-1]

            for cmd in older_commands:
                cmd.status = models.CommandStatus.CANCELED
                cmd.updated_at = now
                session.add(
                    models.EventLog(
                        mid=payload.mid,
                        event_type="CMD_CANCELED",
                        detail={
                            "cmd_seq": cmd.seq,
                            "cmd": cmd.cmd,
                            "created_at": cmd.created_at.isoformat(),
                            "reason": "superseded_by_newer_command",
                            "superseded_by_seq": latest_command.seq,
                        },
                    )
                )
                logger.info(
                    "command_canceled",
                    mid=payload.mid,
                    cmd_seq=cmd.seq,
                    reason="superseded_by_newer_command",
                    superseded_by_seq=latest_command.seq,
                )

            active_commands = [latest_command]

        if should_issue:
            for command in active_commands:
                if command.status == models.CommandStatus.QUEUED:
                    command.status = models.CommandStatus.ISSUED
                    command.updated_at = now
                    break

        commands_payload = [
            schemas.CommandEnvelope(
                seq=command.seq,
                args=schemas.RunDiveArgs.model_validate(command.args),
            )
            for command in active_commands
            if command.status == models.CommandStatus.ISSUED
        ]

        session.add(
            models.EventLog(
                mid=payload.mid,
                event_type="HB",
                detail={
                    "hb_seq": payload.hb_seq,
                    "state": payload.state.value,
                    "commands_returned": len(commands_payload),
                },
            )
        )

    logger.info(
        "hb_processed",
        mid=payload.mid,
        hb_seq=payload.hb_seq,
        commands=len(commands_payload),
    )

    return schemas.HeartbeatResponse(ack=ack, commands=commands_payload, next_hb_s=15)
