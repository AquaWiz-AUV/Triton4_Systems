"""Web API endpoints for telemetry data."""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_session
from ..models import DescentCheck, Device, Dive, Heartbeat
from ..schemas import Environment, Network, Position, Power
from ..web_schemas import (
    DeploymentPoint,
    GeoJSONFeature,
    GeoJSONFeatureCollection,
    GeoJSONGeometry,
    HeartbeatItem,
    HeartbeatListResponse,
    LatestTelemetryResponse,
    TrajectoryDetailedPoint,
    TrajectoryDetailedResponse,
    TrajectoryStatistics,
)

router = APIRouter(prefix="/api/v1/telemetry", tags=["Telemetry"])


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance between two points using Haversine formula (in meters)."""
    R = 6371000

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = math.sin(delta_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c


@router.get("/heartbeats", response_model=HeartbeatListResponse)
async def get_heartbeats(
    mid: str = Query(..., description="Machine ID"),
    start_time: Optional[datetime] = Query(default=None),
    end_time: Optional[datetime] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> HeartbeatListResponse:
    """Get heartbeat history for a device."""
    query = select(Heartbeat).where(Heartbeat.mid == mid)

    if start_time:
        query = query.where(Heartbeat.ts_utc >= start_time)
    if end_time:
        query = query.where(Heartbeat.ts_utc <= end_time)

    count_query = select(func.count()).select_from(query.subquery())
    total_result = await session.execute(count_query)
    total = total_result.scalar_one()

    query = query.order_by(Heartbeat.ts_utc.desc()).limit(limit).offset(offset)
    result = await session.execute(query)
    heartbeats = result.scalars().all()

    items = []
    for hb in heartbeats:
        payload = hb.payload
        position = Position(**payload["pos"]) if payload.get("pos") else None
        power = Power(**payload["pwr"]) if payload.get("pwr") else None
        environment = Environment(**payload["env"]) if payload.get("env") else None
        network = Network(**payload["net"]) if payload.get("net") else None

        items.append(
            HeartbeatItem(
                hb_seq=hb.hb_seq,
                ts_utc=hb.ts_utc,
                state=payload.get("state", "UNKNOWN"),
                position=position,
                power=power,
                environment=environment,
                network=network,
                received_at=hb.received_at,
            )
        )

    return HeartbeatListResponse(mid=mid, total=total, items=items)


@router.get("/latest/{mid}", response_model=LatestTelemetryResponse)
async def get_latest_telemetry(
    mid: str,
    session: AsyncSession = Depends(get_session),
) -> LatestTelemetryResponse:
    """Get latest telemetry for a device."""
    device_query = select(Device).where(Device.mid == mid)
    device_result = await session.execute(device_query)
    device = device_result.scalar_one_or_none()

    if not device:
        raise HTTPException(status_code=404, detail=f"Device {mid} not found")

    hb_query = (
        select(Heartbeat).where(Heartbeat.mid == mid).order_by(Heartbeat.ts_utc.desc()).limit(1)
    )
    hb_result = await session.execute(hb_query)
    latest_hb = hb_result.scalar_one_or_none()

    if latest_hb:
        payload = latest_hb.payload
        position = Position(**payload["pos"]) if payload.get("pos") else None
        power = Power(**payload["pwr"]) if payload.get("pwr") else None
        environment = Environment(**payload["env"]) if payload.get("env") else None
        network = Network(**payload["net"]) if payload.get("net") else None

        return LatestTelemetryResponse(
            mid=mid,
            hb_seq=latest_hb.hb_seq,
            ts_utc=latest_hb.ts_utc,
            state=payload.get("state", "UNKNOWN"),
            position=position,
            power=power,
            environment=environment,
            network=network,
        )
    else:
        position = Position(**device.last_pos) if device.last_pos else None
        power = Power(**device.last_pwr) if device.last_pwr else None
        environment = Environment(**device.last_env) if device.last_env else None
        network = Network(**device.last_net) if device.last_net else None

        return LatestTelemetryResponse(
            mid=mid,
            hb_seq=device.last_hb_seq,
            ts_utc=device.last_seen_at,
            state=device.last_state,
            position=position,
            power=power,
            environment=environment,
            network=network,
        )


@router.get("/trajectory/{mid}")
async def get_trajectory(
    mid: str,
    start_time: Optional[datetime] = Query(default=None),
    end_time: Optional[datetime] = Query(default=None),
    format: Literal["geojson", "detailed"] = Query(default="geojson"),
    include_sensors: bool = Query(default=True),
    sampling: Optional[int] = Query(default=None, ge=1),
    session: AsyncSession = Depends(get_session),
) -> GeoJSONFeatureCollection | TrajectoryDetailedResponse:
    """Get GPS trajectory and sensor data for a device."""
    device_query = select(Device).where(Device.mid == mid)
    device_result = await session.execute(device_query)
    device = device_result.scalar_one_or_none()

    if not device:
        raise HTTPException(status_code=404, detail=f"Device {mid} not found")

    query = select(Heartbeat).where(Heartbeat.mid == mid)

    if start_time:
        query = query.where(Heartbeat.ts_utc >= start_time)
    if end_time:
        query = query.where(Heartbeat.ts_utc <= end_time)

    query = query.order_by(Heartbeat.ts_utc.asc())
    result = await session.execute(query)
    heartbeats = result.scalars().all()

    if sampling and sampling > 1:
        heartbeats = heartbeats[::sampling]

    if not heartbeats:
        if format == "geojson":
            return GeoJSONFeatureCollection(features=[])
        else:
            return TrajectoryDetailedResponse(
                mid=mid,
                start_time=datetime.now(timezone.utc),
                end_time=datetime.now(timezone.utc),
                total_distance_m=0.0,
                point_count=0,
                deployment_point=None,
                points=[],
                statistics=TrajectoryStatistics(
                    avg_depth_m=None,
                    max_depth_m=None,
                    avg_battery_soc=None,
                    avg_rsrp_dbm=None,
                    min_rsrp_dbm=None,
                    max_rsrp_dbm=None,
                    avg_water_temp_c=None,
                ),
            )

    # Fetch DescentChecks to identify dive start points
    descent_query = select(DescentCheck).where(DescentCheck.mid == mid).order_by(DescentCheck.created_at.asc())
    descent_result = await session.execute(descent_query)
    descents = descent_result.scalars().all()

    # Map cmd_seq to DescentCheck for easy lookup
    descent_map = {d.cmd_seq: d for d in descents if d.ok}

    dive_query = select(Dive).where(Dive.mid == mid).order_by(Dive.created_at.asc())
    dive_result = await session.execute(dive_query)
    dives = dive_result.scalars().all()
    max_dive_depth = max((d.summary.get("max_depth_m", 0) for d in dives if d.summary), default=None)

    coordinates = []
    points_data = []
    depths = []
    battery_socs = []
    rsrps = []
    water_temps = []

    for hb in heartbeats:
        payload = hb.payload
        pos = payload.get("pos")
        if not pos or pos.get("lat") is None or pos.get("lon") is None:
            continue

        position = Position(**pos)
        power = Power(**payload["pwr"]) if payload.get("pwr") else None
        environment = Environment(**payload["env"]) if payload.get("env") else None
        network = Network(**payload["net"]) if payload.get("net") else None

        coordinates.append([position.lon, position.lat, environment.depth_m if environment else 0.0])

        if include_sensors:
            points_data.append(
                {
                    "timestamp": hb.ts_utc,
                    "hb_seq": hb.hb_seq,
                    "state": payload.get("state", "UNKNOWN"),
                    "position": position,
                    "power": power,
                    "environment": environment,
                    "network": network,
                }
            )

        if environment and environment.depth_m is not None:
            depths.append(environment.depth_m)
        if power and power.soc is not None:
            battery_socs.append(power.soc)
        if network and network.rsrp_dbm is not None:
            rsrps.append(network.rsrp_dbm)
        if environment and environment.water_temp_c is not None:
            water_temps.append(environment.water_temp_c)

    total_distance = 0.0
    for i in range(len(coordinates) - 1):
        lon1, lat1, _ = coordinates[i]
        lon2, lat2, _ = coordinates[i + 1]
        total_distance += haversine_distance(lat1, lon1, lat2, lon2)

    statistics = TrajectoryStatistics(
        avg_depth_m=sum(depths) / len(depths) if depths else None,
        max_depth_m=max_dive_depth if max_dive_depth else (max(depths) if depths else None),
        avg_battery_soc=sum(battery_socs) / len(battery_socs) if battery_socs else None,
        avg_rsrp_dbm=sum(rsrps) / len(rsrps) if rsrps else None,
        min_rsrp_dbm=min(rsrps) if rsrps else None,
        max_rsrp_dbm=max(rsrps) if rsrps else None,
        avg_water_temp_c=sum(water_temps) / len(water_temps) if water_temps else None,
    )

    if format == "geojson":
        features = []
        print(f"[DEBUG] MID={mid}, HBs={len(heartbeats)}, Coords={len(coordinates)}")

        # 1. Standard Trajectory Line (Split by dives)
        if coordinates:
            # Sort dives by time to process sequentially
            sorted_dives = sorted([d for d in dives if d.ok and d.summary], key=lambda x: x.created_at)
            
            # Pre-calculate timestamps for dives
            for dive in sorted_dives:
                if not dive.started_at and dive.ended_at and dive.summary.get("duration_s"):
                    from datetime import timedelta
                    dive.started_at = dive.ended_at - timedelta(seconds=dive.summary["duration_s"])

            # Build segments
            segments = []
            current_segment = []
            
            # We need to iterate through heartbeats to check timestamps
            # coordinates list aligns with heartbeats list
            for i, hb in enumerate(heartbeats):
                current_segment.append(coordinates[i])
                
                # Check if this HB is the start of a gap (i.e., next HB is after a dive)
                if i < len(heartbeats) - 1:
                    next_hb = heartbeats[i+1]
                    
                    # Is there a dive that starts after this HB and ends before the next HB?
                    is_gap = False
                    for dive in sorted_dives:
                        if dive.started_at and dive.ended_at:
                            # Relaxed condition: if dive overlaps significantly with the interval
                            # But strictly: dive should be contained within HB interval
                            if hb.ts_utc <= dive.started_at and next_hb.ts_utc >= dive.ended_at:
                                is_gap = True
                                break
                    
                    if is_gap:
                        if len(current_segment) >= 2:
                            segments.append(current_segment)
                        current_segment = []

            # Append the last segment
            if len(current_segment) >= 2:
                segments.append(current_segment)
            elif len(current_segment) == 1 and not segments:
                 # If only one point total, or just one point left, maybe show it?
                 # But LineString needs 2 points.
                 pass

            # Create features for each segment
            for i, segment in enumerate(segments):
                linestring_feature = GeoJSONFeature(
                    geometry=GeoJSONGeometry(type="LineString", coordinates=segment),
                    properties={
                        "mid": mid,
                        "type": "trajectory",
                        "segment_index": i,
                        "start_time": heartbeats[0].ts_utc.isoformat(), # Approximate
                        "end_time": heartbeats[-1].ts_utc.isoformat(),
                    },
                )
                features.append(linestring_feature)

        # 2. Dive Segments (Dashed Lines)
        print(f"[DEBUG] Dives found: {len(dives)}")
        for dive in dives:
            if not dive.ok or not dive.summary:
                continue
            
            # Find start point (from DescentCheck)
            descent = descent_map.get(dive.cmd_seq)
            if not descent:
                continue
            
            start_pos = descent.payload.get("hk", {}).get("pos")
            if not start_pos:
                continue

            # Find end point (first HB after dive ended)
            # We look for the first HB where ts_utc > dive.ended_at
            end_hb = next((hb for hb in heartbeats if hb.ts_utc > dive.ended_at), None)
            
            end_pos = None
            if end_hb:
                end_pos = end_hb.payload.get("pos")
            elif device.last_pos and device.last_seen_at > dive.ended_at:
                # Fallback to device's last known position if it's fresher than the dive end
                # This handles the case where the next heartbeat hasn't arrived yet
                end_pos = device.last_pos

            if not end_pos:
                continue

            dive_coords = [
                [start_pos["lon"], start_pos["lat"]],
                [end_pos["lon"], end_pos["lat"]]
            ]

            # Calculate started_at if missing
            started_at = dive.started_at
            if not started_at and dive.ended_at and dive.summary.get("duration_s"):
                from datetime import timedelta
                started_at = dive.ended_at - timedelta(seconds=dive.summary["duration_s"])

            dive_feature = GeoJSONFeature(
                geometry=GeoJSONGeometry(type="LineString", coordinates=dive_coords),
                properties={
                    "type": "dive",
                    "mid": mid,
                    "dive_id": dive.id,
                    "cmd_seq": dive.cmd_seq,
                    "max_depth_m": dive.summary.get("max_depth_m"),
                    "duration_s": dive.summary.get("duration_s"),
                    "started_at": started_at.isoformat() if started_at else None,
                    "ended_at": dive.ended_at.isoformat() if dive.ended_at else None,
                },
            )
            features.append(dive_feature)

            # Add Dive Start Marker
            features.append(GeoJSONFeature(
                geometry=GeoJSONGeometry(type="Point", coordinates=[start_pos["lon"], start_pos["lat"]]),
                properties={
                    "type": "dive_marker",
                    "marker_type": "start",
                    "mid": mid,
                    "dive_id": dive.id,
                    "timestamp": started_at.isoformat() if started_at else None,
                }
            ))

            # Add Dive End Marker
            features.append(GeoJSONFeature(
                geometry=GeoJSONGeometry(type="Point", coordinates=[end_pos["lon"], end_pos["lat"]]),
                properties={
                    "type": "dive_marker",
                    "marker_type": "end",
                    "mid": mid,
                    "dive_id": dive.id,
                    "timestamp": dive.ended_at.isoformat() if dive.ended_at else None,
                }
            ))

        if include_sensors:
            for point_data in points_data:
                pos = point_data["position"]
                point_feature = GeoJSONFeature(
                    geometry=GeoJSONGeometry(
                        type="Point",
                        coordinates=[
                            pos.lon,
                            pos.lat,
                            point_data["environment"].depth_m if point_data["environment"] else 0.0,
                        ],
                    ),
                    properties={
                        "timestamp": point_data["timestamp"].isoformat(),
                        "hb_seq": point_data["hb_seq"],
                        "state": point_data["state"],
                        "position": pos.model_dump() if pos else None,
                        "power": point_data["power"].model_dump() if point_data["power"] else None,
                        "environment": (
                            point_data["environment"].model_dump()
                            if point_data["environment"]
                            else None
                        ),
                        "network": (
                            point_data["network"].model_dump() if point_data["network"] else None
                        ),
                    },
                )
                features.append(point_feature)

            if coordinates:
                deployment_feature = GeoJSONFeature(
                    geometry=GeoJSONGeometry(type="Point", coordinates=coordinates[0]),
                    properties={
                        "type": "deployment",
                        "timestamp": heartbeats[0].ts_utc.isoformat(),
                        "label": "放流開始地点",
                    },
                )
                features.append(deployment_feature)

                current_feature = GeoJSONFeature(
                    geometry=GeoJSONGeometry(type="Point", coordinates=coordinates[-1]),
                    properties={
                        "type": "current",
                        "timestamp": heartbeats[-1].ts_utc.isoformat(),
                        "label": "現在地",
                        "state": heartbeats[-1].payload.get("state", "UNKNOWN"),
                    },
                )
                features.append(current_feature)

        print(f"[DEBUG] Total features: {len(features)}")
        return GeoJSONFeatureCollection(features=features)

    else:
        detailed_points = [
            TrajectoryDetailedPoint(
                timestamp=point_data["timestamp"],
                hb_seq=point_data["hb_seq"],
                state=point_data["state"],
                position=point_data["position"],
                power=point_data["power"],
                environment=point_data["environment"],
                network=point_data["network"],
            )
            for point_data in points_data
        ]

        deployment_point = None
        if coordinates:
            first_hb = heartbeats[0]
            first_pos = first_hb.payload.get("pos")
            if first_pos:
                deployment_point = DeploymentPoint(
                    lat=first_pos["lat"], lon=first_pos["lon"], timestamp=first_hb.ts_utc
                )

        return TrajectoryDetailedResponse(
            mid=mid,
            start_time=heartbeats[0].ts_utc,
            end_time=heartbeats[-1].ts_utc,
            total_distance_m=total_distance,
            point_count=len(coordinates),
            deployment_point=deployment_point,
            points=detailed_points,
            statistics=statistics,
        )
