"""Descent check endpoint implementation."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from .. import models, schemas
from ..database import get_session

router = APIRouter(prefix="/v1", tags=["descent"])
logger = structlog.get_logger(__name__)


def _dump_optional(model: Any | None) -> dict[str, Any] | None:
    if model is None:
        return None
    return model.model_dump(mode="json", exclude_none=True)  # type: ignore[return-value]


@router.post("/descent_check", response_model=schemas.DescentCheckResponse)
async def post_descent_check(
    payload: schemas.DescentCheckRequest,
    session: AsyncSession = Depends(get_session),
) -> schemas.DescentCheckResponse:
    now = datetime.now(timezone.utc)

    async with session.begin():
        existing_stmt = select(models.DescentCheck).where(
            models.DescentCheck.mid == payload.mid,
            models.DescentCheck.check_seq == payload.check_seq,
        )
        existing = (await session.execute(existing_stmt)).scalar_one_or_none()
        if existing:
            return schemas.DescentCheckResponse(
                ok=existing.ok,
                accept_seq=payload.check_seq,
                reason=existing.reason,
            )

        device = await session.get(models.Device, payload.mid)
        if device is None:
            device = models.Device(
                mid=payload.mid,
                fw=payload.fw,
                last_state=schemas.VehicleState.DESCENT_CHECK.value,
                last_hb_seq=None,
                last_seen_at=now,
                last_exec_cmd_seq=None,
                last_exec_status=None,
                last_pos=_dump_optional(payload.hk.pos if payload.hk else None),
                last_pwr=_dump_optional(payload.hk.pwr if payload.hk else None),
                last_env=_dump_optional(payload.hk.env if payload.hk else None),
                last_net=_dump_optional(payload.hk.net if payload.hk else None),
                recovery_reason=None,
            )
            session.add(device)
        else:
            device.fw = payload.fw
            device.last_state = schemas.VehicleState.DESCENT_CHECK.value
            device.last_seen_at = now
            if payload.hk:
                device.last_pos = _dump_optional(payload.hk.pos)
                device.last_pwr = _dump_optional(payload.hk.pwr)
                device.last_env = _dump_optional(payload.hk.env)
                device.last_net = _dump_optional(payload.hk.net)

        cmd_stmt = select(models.Command).where(
            models.Command.mid == payload.mid,
            models.Command.seq == payload.plan.cmd_seq,
        )
        cmd = (await session.execute(cmd_stmt)).scalar_one_or_none()

        ok = False
        reason: str | None = None

        if cmd is None:
            reason = "command_not_found"
        elif cmd.cmd != "RUN_DIVE":
            reason = "unsupported_command"
        elif cmd.status not in (models.CommandStatus.QUEUED, models.CommandStatus.ISSUED):
            reason = f"command_not_available({cmd.status.value})"
        else:
            expected_args = schemas.RunDiveArgs.model_validate(cmd.args)
            plan_args = schemas.RunDiveArgs(
                target_depth_m=payload.plan.target_depth_m,
                hold_at_depth_s=payload.plan.hold_at_depth_s,
                cycles=payload.plan.cycles,
            )
            if expected_args != plan_args:
                reason = "plan_mismatch"
            else:
                ok = True
                cmd.status = models.CommandStatus.EXECUTING
                cmd.updated_at = now
                device.last_exec_cmd_seq = cmd.seq
                device.last_exec_status = schemas.ExecStatus.RUNNING.value

        session.add(
            models.DescentCheck(
                mid=payload.mid,
                check_seq=payload.check_seq,
                cmd_seq=payload.plan.cmd_seq,
                plan_hash=payload.plan.plan_hash,
                ok=ok,
                reason=reason,
                payload=payload.model_dump(mode="json"),
            )
        )

        session.add(
            models.EventLog(
                mid=payload.mid,
                event_type="DESCENT_CHECK",
                detail={
                    "check_seq": payload.check_seq,
                    "cmd_seq": payload.plan.cmd_seq,
                    "ok": ok,
                    "reason": reason,
                },
            )
        )

    logger.info(
        "descent_check_processed",
        mid=payload.mid,
        check_seq=payload.check_seq,
        cmd_seq=payload.plan.cmd_seq,
        ok=ok,
    )

    return schemas.DescentCheckResponse(ok=ok, accept_seq=payload.check_seq, reason=reason)
