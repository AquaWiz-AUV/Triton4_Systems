"""Web API endpoints for dive history."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_session
from ..models import Dive
from ..web_schemas import DiveDetail, DiveListItem, DiveListResponse

router = APIRouter(prefix="/api/v1/dives", tags=["Dives"])


@router.get("", response_model=DiveListResponse)
async def get_dives(
    mid: Optional[str] = Query(default=None),
    start_date: Optional[datetime] = Query(default=None),
    end_date: Optional[datetime] = Query(default=None),
    ok: Optional[bool] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> DiveListResponse:
    """Get list of dives."""
    query = select(Dive)

    if mid:
        query = query.where(Dive.mid == mid)

    if start_date:
        query = query.where(Dive.created_at >= start_date)

    if end_date:
        query = query.where(Dive.created_at <= end_date)

    if ok is not None:
        query = query.where(Dive.ok == ok)

    count_query = select(func.count()).select_from(query.subquery())
    total_result = await session.execute(count_query)
    total = total_result.scalar_one()

    query = query.order_by(Dive.created_at.desc()).limit(limit).offset(offset)
    result = await session.execute(query)
    dives = result.scalars().all()

    items = [
        DiveListItem(
            dive_id=dive.id,
            mid=dive.mid,
            cmd_seq=dive.cmd_seq,
            ok=dive.ok,
            summary=dive.summary,
            started_at=dive.started_at,
            ended_at=dive.ended_at,
            created_at=dive.created_at,
        )
        for dive in dives
    ]

    return DiveListResponse(total=total, items=items)


@router.get("/{dive_id}", response_model=DiveDetail)
async def get_dive(
    dive_id: int,
    session: AsyncSession = Depends(get_session),
) -> DiveDetail:
    """Get dive details."""
    query = select(Dive).where(Dive.id == dive_id)
    result = await session.execute(query)
    dive = result.scalar_one_or_none()

    if not dive:
        raise HTTPException(status_code=404, detail=f"Dive {dive_id} not found")

    return DiveDetail(
        dive_id=dive.id,
        mid=dive.mid,
        cmd_seq=dive.cmd_seq,
        ok=dive.ok,
        summary=dive.summary,
        started_at=dive.started_at,
        ended_at=dive.ended_at,
        created_at=dive.created_at,
    )
