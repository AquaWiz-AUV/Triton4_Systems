"""Web API endpoints for command management."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_session
from ..models import Command, CommandStatus, Device
from ..web_schemas import CommandListItem, CommandListResponse, CommandRequest, CommandResponse

router = APIRouter(prefix="/api/v1/commands", tags=["Commands"])


@router.post("", response_model=CommandResponse, status_code=201)
async def create_command(
    cmd_request: CommandRequest,
    session: AsyncSession = Depends(get_session),
) -> CommandResponse:
    """Create and queue a new command."""
    device_query = select(Device).where(Device.mid == cmd_request.mid)
    device_result = await session.execute(device_query)
    device = device_result.scalar_one_or_none()

    if not device:
        raise HTTPException(status_code=404, detail=f"Device {cmd_request.mid} not found")

    seq_query = select(func.max(Command.seq)).where(Command.mid == cmd_request.mid)
    seq_result = await session.execute(seq_query)
    max_seq = seq_result.scalar_one_or_none()
    new_seq = (max_seq or 0) + 1

    new_command = Command(
        mid=cmd_request.mid,
        seq=new_seq,
        cmd=cmd_request.cmd,
        args={
            "target_depth_m": cmd_request.args.target_depth_m,
            "hold_at_depth_s": cmd_request.args.hold_at_depth_s,
            "cycles": cmd_request.args.cycles,
        },
        status=CommandStatus.QUEUED,
        issued_by="web_api",
    )

    session.add(new_command)
    await session.commit()
    await session.refresh(new_command)

    return CommandResponse(
        command_id=new_command.id,
        mid=new_command.mid,
        seq=new_command.seq,
        cmd=new_command.cmd,
        args=new_command.args,
        status=new_command.status.value,
        created_at=new_command.created_at,
        issued_by=new_command.issued_by,
    )


@router.get("", response_model=CommandListResponse)
async def get_commands(
    mid: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> CommandListResponse:
    """Get list of commands."""
    query = select(Command)

    if mid:
        query = query.where(Command.mid == mid)

    if status:
        try:
            status_enum = CommandStatus(status)
            query = query.where(Command.status == status_enum)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")

    count_query = select(func.count()).select_from(query.subquery())
    total_result = await session.execute(count_query)
    total = total_result.scalar_one()

    query = query.order_by(Command.created_at.desc()).limit(limit).offset(offset)
    result = await session.execute(query)
    commands = result.scalars().all()

    items = [
        CommandListItem(
            command_id=cmd.id,
            mid=cmd.mid,
            seq=cmd.seq,
            cmd=cmd.cmd,
            status=cmd.status.value,
            created_at=cmd.created_at,
            updated_at=cmd.updated_at,
            issued_by=cmd.issued_by,
        )
        for cmd in commands
    ]

    return CommandListResponse(total=total, items=items)


@router.get("/{command_id}", response_model=CommandResponse)
async def get_command(
    command_id: int,
    session: AsyncSession = Depends(get_session),
) -> CommandResponse:
    """Get command details."""
    query = select(Command).where(Command.id == command_id)
    result = await session.execute(query)
    command = result.scalar_one_or_none()

    if not command:
        raise HTTPException(status_code=404, detail=f"Command {command_id} not found")

    return CommandResponse(
        command_id=command.id,
        mid=command.mid,
        seq=command.seq,
        cmd=command.cmd,
        args=command.args,
        status=command.status.value,
        created_at=command.created_at,
        issued_by=command.issued_by,
    )
