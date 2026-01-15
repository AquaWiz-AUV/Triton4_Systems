"""Web API endpoints for event logs."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_session
from ..models import EventLog
from ..web_schemas import EventListItem, EventListResponse

router = APIRouter(prefix="/api/v1/events", tags=["Events"])


@router.get("", response_model=EventListResponse)
async def get_events(
    mid: Optional[str] = Query(default=None),
    event_type: Optional[str] = Query(default=None),
    start_time: Optional[datetime] = Query(default=None),
    end_time: Optional[datetime] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> EventListResponse:
    """Get list of events."""
    query = select(EventLog)

    if mid:
        query = query.where(EventLog.mid == mid)

    if event_type:
        query = query.where(EventLog.event_type == event_type)

    if start_time:
        query = query.where(EventLog.created_at >= start_time)

    if end_time:
        query = query.where(EventLog.created_at <= end_time)

    count_query = select(func.count()).select_from(query.subquery())
    total_result = await session.execute(count_query)
    total = total_result.scalar_one()

    query = query.order_by(EventLog.created_at.desc()).limit(limit).offset(offset)
    result = await session.execute(query)
    events = result.scalars().all()

    items = [
        EventListItem(
            event_id=event.id,
            mid=event.mid,
            event_type=event.event_type,
            detail=event.detail,
            created_at=event.created_at,
        )
        for event in events
    ]

    return EventListResponse(total=total, items=items)
