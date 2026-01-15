"""Ascent notification endpoint implementation."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from .. import models, schemas
from ..database import get_session

router = APIRouter(prefix="/v1", tags=["ascent"])
logger = structlog.get_logger(__name__)


def _dump_optional(model: Any | None) -> dict[str, Any] | None:
    if model is None:
        return None
    return model.model_dump(mode="json", exclude_none=True)  # type: ignore[return-value]


@router.post("/ascent_notify", response_model=schemas.SimpleMessage)
async def post_ascent_notify(
    payload: schemas.AscentNotifyRequest,
    session: AsyncSession = Depends(get_session),
) -> schemas.SimpleMessage:
    now = datetime.now(timezone.utc)

    async with session.begin():
        device = await session.get(models.Device, payload.mid)
        if device is None:
            device = models.Device(
                mid=payload.mid,
                fw=payload.fw,
                last_state=schemas.VehicleState.SURFACE_WAIT.value,
                last_hb_seq=None,
                last_seen_at=now,
                last_exec_cmd_seq=payload.exec.last_cmd_seq,
                last_exec_status=payload.exec.status.value,
                last_pos=_dump_optional(payload.pos),
                last_pwr=_dump_optional(payload.pwr),
                last_env=_dump_optional(payload.env),
                last_net=_dump_optional(payload.net),
                recovery_reason=None,
            )
            session.add(device)
        else:
            device.fw = payload.fw
            device.last_state = schemas.VehicleState.SURFACE_WAIT.value
            device.last_seen_at = now
            device.last_exec_cmd_seq = payload.exec.last_cmd_seq
            device.last_exec_status = payload.exec.status.value
            device.last_pos = _dump_optional(payload.pos)
            device.last_pwr = _dump_optional(payload.pwr)
            device.last_env = _dump_optional(payload.env)
            device.last_net = _dump_optional(payload.net)

        cmd = None
        if payload.exec.last_cmd_seq is not None:
            cmd_stmt = select(models.Command).where(
                models.Command.mid == payload.mid,
                models.Command.seq == payload.exec.last_cmd_seq,
            )
            cmd = (await session.execute(cmd_stmt)).scalar_one_or_none()
            if cmd:
                if payload.exec.status == schemas.ExecStatus.DONE:
                    cmd.status = models.CommandStatus.COMPLETED
                elif payload.exec.status == schemas.ExecStatus.RUNNING:
                    cmd.status = models.CommandStatus.EXECUTING
                elif payload.exec.status == schemas.ExecStatus.ERROR:
                    cmd.status = models.CommandStatus.ERROR
                elif payload.exec.status == schemas.ExecStatus.ABORTED:
                    cmd.status = models.CommandStatus.CANCELED
                else:  # IDLE or others fallback
                    cmd.status = models.CommandStatus.ISSUED
                cmd.updated_at = now

        if payload.exec.last_cmd_seq is not None:
            # Check for existing dive to avoid duplicates
            dive_stmt = select(models.Dive).where(
                models.Dive.mid == payload.mid,
                models.Dive.cmd_seq == payload.exec.last_cmd_seq,
            )
            existing_dive = (await session.execute(dive_stmt)).scalar_one_or_none()

            if existing_dive:
                # Update existing dive
                existing_dive.ok = payload.exec.status == schemas.ExecStatus.DONE
                existing_dive.summary = payload.exec.summary
                existing_dive.ended_at = payload.ts_utc
            else:
                # Create new dive
                session.add(
                    models.Dive(
                        mid=payload.mid,
                        cmd_seq=payload.exec.last_cmd_seq,
                        ok=payload.exec.status == schemas.ExecStatus.DONE,
                        summary=payload.exec.summary,
                        ended_at=payload.ts_utc,
                    )
                )

        session.add(
            models.EventLog(
                mid=payload.mid,
                event_type="ASCENT_NOTIFY",
                detail={
                    "cmd_seq": payload.exec.last_cmd_seq,
                    "status": payload.exec.status.value,
                    "has_summary": payload.exec.summary is not None,
                },
            )
        )

    logger.info(
        "ascent_notified",
        mid=payload.mid,
        cmd_seq=payload.exec.last_cmd_seq,
        status=payload.exec.status.value,
    )

    return schemas.SimpleMessage(message="acknowledged")
