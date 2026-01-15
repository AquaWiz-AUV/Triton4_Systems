"""Web API endpoints for device management."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_session
from ..models import Device
from ..schemas import Environment, Network, Position, Power
from ..web_schemas import (
    DeviceDetail,
    DeviceListItem,
    DeviceListResponse,
    DeviceStatus,
    PaginationInfo,
)

router = APIRouter(prefix="/api/v1/devices", tags=["Devices"])

ONLINE_THRESHOLD_SECONDS = 60


def is_device_online(last_seen_at: datetime) -> bool:
    """Check if device is online based on last_seen_at."""
    return (datetime.now(last_seen_at.tzinfo) - last_seen_at).total_seconds() < ONLINE_THRESHOLD_SECONDS


@router.get("", response_model=DeviceListResponse)
async def get_devices(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    state: Optional[str] = Query(default=None),
    sort: str = Query(default="last_seen_at:desc"),
    session: AsyncSession = Depends(get_session),
) -> DeviceListResponse:
    """Get list of devices."""
    query = select(Device)

    if state:
        query = query.where(Device.last_state == state)

    count_query = select(func.count()).select_from(query.subquery())
    total_result = await session.execute(count_query)
    total = total_result.scalar_one()

    if sort == "last_seen_at:desc":
        query = query.order_by(Device.last_seen_at.desc())
    elif sort == "last_seen_at:asc":
        query = query.order_by(Device.last_seen_at.asc())
    elif sort == "mid:asc":
        query = query.order_by(Device.mid.asc())
    elif sort == "mid:desc":
        query = query.order_by(Device.mid.desc())

    query = query.limit(limit).offset(offset)
    result = await session.execute(query)
    devices = result.scalars().all()

    items = [
        DeviceListItem(
            mid=device.mid,
            fw=device.fw,
            state=device.last_state,
            last_hb_seq=device.last_hb_seq,
            last_seen_at=device.last_seen_at,
            last_exec_status=device.last_exec_status,
            online=is_device_online(device.last_seen_at),
        )
        for device in devices
    ]

    has_more = offset + limit < total

    return DeviceListResponse(
        total=total,
        items=items,
        pagination=PaginationInfo(limit=limit, offset=offset, has_more=has_more),
    )


@router.get("/{mid}", response_model=DeviceDetail)
async def get_device(
    mid: str,
    session: AsyncSession = Depends(get_session),
) -> DeviceDetail:
    """Get device details."""
    query = select(Device).where(Device.mid == mid)
    result = await session.execute(query)
    device = result.scalar_one_or_none()

    if not device:
        raise HTTPException(status_code=404, detail=f"Device {mid} not found")

    position = Position(**device.last_pos) if device.last_pos else None
    power = Power(**device.last_pwr) if device.last_pwr else None
    environment = Environment(**device.last_env) if device.last_env else None
    network = Network(**device.last_net) if device.last_net else None

    return DeviceDetail(
        mid=device.mid,
        fw=device.fw,
        state=device.last_state,
        last_hb_seq=device.last_hb_seq,
        last_seen_at=device.last_seen_at,
        last_exec_cmd_seq=device.last_exec_cmd_seq,
        last_exec_status=device.last_exec_status,
        position=position,
        power=power,
        environment=environment,
        network=network,
        online=is_device_online(device.last_seen_at),
        last_online_at=device.last_seen_at,
    )


@router.get("/{mid}/status", response_model=DeviceStatus)
async def get_device_status(
    mid: str,
    session: AsyncSession = Depends(get_session),
) -> DeviceStatus:
    """Get device status (lightweight)."""
    query = select(Device).where(Device.mid == mid)
    result = await session.execute(query)
    device = result.scalar_one_or_none()

    if not device:
        raise HTTPException(status_code=404, detail=f"Device {mid} not found")

    return DeviceStatus(
        mid=device.mid,
        state=device.last_state,
        online=is_device_online(device.last_seen_at),
        last_seen_at=device.last_seen_at,
        exec_status=device.last_exec_status,
    )
