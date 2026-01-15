"""Pydantic schemas shared across API endpoints."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class VehicleState(str, Enum):
    SURFACE_WAIT = "SURFACE_WAIT"
    DESCENT_CHECK = "DESCENT_CHECK"
    DIVE = "DIVE"
    RECOVERY = "RECOVERY"


class ExecStatus(str, Enum):
    IDLE = "IDLE"
    RUNNING = "RUNNING"
    DONE = "DONE"
    ABORTED = "ABORTED"
    ERROR = "ERROR"


class Position(BaseModel):
    lat: float
    lon: float
    alt_m: float | None = None
    fix: int | None = None
    nsat: int | None = None


class Power(BaseModel):
    soc: float | None = Field(None, ge=0, le=100)
    v_batt: float | None = None
    i_a: float | None = None
    temp_c: float | None = None


class Environment(BaseModel):
    depth_m: float | None = None
    water_temp_c: float | None = None


class Network(BaseModel):
    rat: str | None = None
    rsrp_dbm: float | None = None
    rsrq_db: float | None = None
    snr_db: float | None = None
    cell_id: int | None = None
    earfcn: int | None = None
    tac: int | None = None


class ExecReport(BaseModel):
    last_cmd_seq: int | None = Field(default=None, ge=0)
    status: ExecStatus
    summary: dict[str, Any] | None = None


class RunDiveArgs(BaseModel):
    target_depth_m: float = Field(..., gt=0)
    hold_at_depth_s: int = Field(..., gt=0)
    cycles: int = Field(..., gt=0)


class CommandEnvelope(BaseModel):
    t: Literal["CMD"] = "CMD"
    v: int = 1
    seq: int = Field(..., ge=0)
    cmd: Literal["RUN_DIVE"] = "RUN_DIVE"
    args: RunDiveArgs


class HeartbeatRequest(BaseModel):
    mid: str
    fw: str
    hb_seq: int = Field(..., ge=0)
    ts_utc: datetime
    state: VehicleState
    pos: Position | None = None
    pwr: Power | None = None
    env: Environment | None = None
    net: Network | None = None
    exec: ExecReport | None = None
    x: dict[str, Any] | None = None


class HeartbeatAck(BaseModel):
    hb_seq: int
    server_time: datetime


class HeartbeatResponse(BaseModel):
    ack: HeartbeatAck
    commands: list[CommandEnvelope] = Field(default_factory=list)
    next_hb_s: int = 15


class DescentPlan(BaseModel):
    cmd_seq: int = Field(..., ge=0)
    target_depth_m: float = Field(..., gt=0)
    hold_at_depth_s: int = Field(..., gt=0)
    cycles: int = Field(..., gt=0)
    plan_hash: str = Field(..., min_length=4, max_length=32)


class DescentHK(BaseModel):
    model_config = ConfigDict(extra="allow")

    pos: Position | None = None
    pwr: Power | None = None
    env: Environment | None = None
    net: Network | None = None


class DescentCheckRequest(BaseModel):
    mid: str
    fw: str
    ts_utc: datetime
    check_seq: int = Field(..., ge=0)
    plan: DescentPlan
    hk: DescentHK


class DescentCheckResponse(BaseModel):
    ok: bool
    accept_seq: int
    reason: str | None = None


class AscentNotifyRequest(BaseModel):
    mid: str
    fw: str
    ts_utc: datetime
    exec: ExecReport
    pos: Position | None = None
    pwr: Power | None = None
    env: Environment | None = None
    net: Network | None = None


class SimpleMessage(BaseModel):
    message: str
