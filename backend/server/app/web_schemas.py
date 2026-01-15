"""Pydantic schemas for Web API endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

from .schemas import Environment, Network, Position, Power


class PaginationInfo(BaseModel):
    """Pagination metadata."""

    limit: int
    offset: int
    has_more: bool


class DeviceListItem(BaseModel):
    """Device list item."""

    mid: str
    fw: str
    state: str
    last_hb_seq: int | None
    last_seen_at: datetime
    last_exec_status: str | None
    online: bool


class DeviceListResponse(BaseModel):
    """Device list response."""

    total: int
    items: list[DeviceListItem]
    pagination: PaginationInfo


class DeviceDetail(BaseModel):
    """Device detail response."""

    mid: str
    fw: str
    state: str
    last_hb_seq: int | None
    last_seen_at: datetime
    last_exec_cmd_seq: int | None
    last_exec_status: str | None
    position: Position | None
    power: Power | None
    environment: Environment | None
    network: Network | None
    online: bool
    last_online_at: datetime


class DeviceStatus(BaseModel):
    """Device status response (lightweight)."""

    mid: str
    state: str
    online: bool
    last_seen_at: datetime
    exec_status: str | None


class RunDiveArgsResponse(BaseModel):
    """RUN_DIVE command arguments for response."""

    target_depth_m: float
    hold_at_depth_s: int
    cycles: int


class CommandRequest(BaseModel):
    """Command creation request."""

    mid: str
    cmd: Literal["RUN_DIVE"] = "RUN_DIVE"
    args: RunDiveArgsResponse


class CommandResponse(BaseModel):
    """Command response."""

    command_id: int
    mid: str
    seq: int
    cmd: str
    args: dict[str, Any]
    status: str
    created_at: datetime
    issued_by: str | None


class CommandListItem(BaseModel):
    """Command list item."""

    command_id: int
    mid: str
    seq: int
    cmd: str
    status: str
    created_at: datetime
    updated_at: datetime
    issued_by: str | None


class CommandListResponse(BaseModel):
    """Command list response."""

    total: int
    items: list[CommandListItem]


class HeartbeatItem(BaseModel):
    """Heartbeat item."""

    hb_seq: int
    ts_utc: datetime
    state: str
    position: Position | None
    power: Power | None
    environment: Environment | None
    network: Network | None
    received_at: datetime


class HeartbeatListResponse(BaseModel):
    """Heartbeat list response."""

    mid: str
    total: int
    items: list[HeartbeatItem]


class LatestTelemetryResponse(BaseModel):
    """Latest telemetry response."""

    mid: str
    hb_seq: int | None
    ts_utc: datetime | None
    state: str
    position: Position | None
    power: Power | None
    environment: Environment | None
    network: Network | None


class TrajectoryPointProperties(BaseModel):
    """GeoJSON Point properties."""

    timestamp: datetime
    hb_seq: int
    state: str
    position: Position
    power: Power | None
    environment: Environment | None
    network: Network | None


class TrajectoryDeploymentProperties(BaseModel):
    """GeoJSON Deployment marker properties."""

    type: Literal["deployment"] = "deployment"
    timestamp: datetime
    label: str = "放流開始地点"


class TrajectoryCurrentProperties(BaseModel):
    """GeoJSON Current position marker properties."""

    type: Literal["current"] = "current"
    timestamp: datetime
    label: str = "現在地"
    state: str


class TrajectoryLineProperties(BaseModel):
    """GeoJSON LineString properties."""

    mid: str
    start_time: datetime
    end_time: datetime
    total_distance_m: float
    max_depth_m: float | None
    avg_rsrp_dbm: float | None
    point_count: int


class GeoJSONGeometry(BaseModel):
    """GeoJSON Geometry."""

    type: str
    coordinates: list[Any]


class GeoJSONFeature(BaseModel):
    """GeoJSON Feature."""

    type: Literal["Feature"] = "Feature"
    geometry: GeoJSONGeometry
    properties: dict[str, Any]


class GeoJSONFeatureCollection(BaseModel):
    """GeoJSON FeatureCollection."""

    type: Literal["FeatureCollection"] = "FeatureCollection"
    features: list[GeoJSONFeature]


class TrajectoryStatistics(BaseModel):
    """Trajectory statistics."""

    avg_depth_m: float | None
    max_depth_m: float | None
    avg_battery_soc: float | None
    avg_rsrp_dbm: float | None
    min_rsrp_dbm: float | None
    max_rsrp_dbm: float | None
    avg_water_temp_c: float | None


class TrajectoryDetailedPoint(BaseModel):
    """Detailed trajectory point."""

    timestamp: datetime
    hb_seq: int
    state: str
    position: Position
    power: Power | None
    environment: Environment | None
    network: Network | None


class DeploymentPoint(BaseModel):
    """Deployment point information."""

    lat: float
    lon: float
    timestamp: datetime


class TrajectoryDetailedResponse(BaseModel):
    """Detailed trajectory response."""

    mid: str
    start_time: datetime
    end_time: datetime
    total_distance_m: float
    point_count: int
    deployment_point: DeploymentPoint | None
    points: list[TrajectoryDetailedPoint]
    statistics: TrajectoryStatistics


class DiveSummary(BaseModel):
    """Dive summary."""

    ok: bool | None
    cycles_done: int | None
    max_depth_m: float | None
    duration_s: int | None


class DiveListItem(BaseModel):
    """Dive list item."""

    dive_id: int
    mid: str
    cmd_seq: int
    ok: bool | None
    summary: dict[str, Any] | None
    started_at: datetime | None
    ended_at: datetime | None
    created_at: datetime


class DiveListResponse(BaseModel):
    """Dive list response."""

    total: int
    items: list[DiveListItem]


class DiveDetail(BaseModel):
    """Dive detail response."""

    dive_id: int
    mid: str
    cmd_seq: int
    ok: bool | None
    summary: dict[str, Any] | None
    started_at: datetime | None
    ended_at: datetime | None
    created_at: datetime


class EventListItem(BaseModel):
    """Event list item."""

    event_id: int
    mid: str | None
    event_type: str
    detail: dict[str, Any]
    created_at: datetime


class EventListResponse(BaseModel):
    """Event list response."""

    total: int
    items: list[EventListItem]
