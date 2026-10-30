"""Single-robot mission mailbox and timestamped telemetry, without ROS imports."""

import copy
import threading
import time
import numpy as np
from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, Field
from tapp.mission import load_map
from tapp.config import RESOLUTION

router = APIRouter()
_lock = threading.Lock()
_mission = None
_state = None
_number = 0


class RobotMission(BaseModel):
    map_id: str
    path: list[tuple[float, float]] = Field(min_length=1, max_length=20000)
    lookahead_m: float = Field(default=1.0, ge=0.5, le=3.0)
    points: list[tuple[float, float]] = Field(default_factory=list, max_length=12)


class RobotState(BaseModel):
    map_id: str
    mission_id: int = Field(default=0, ge=0)
    status: str
    pose: tuple[float, float, float, float, float, float] | None = None
    sim_time: float = 0.0
    message: str = ""
    current_path: list[tuple[float, float]] | None = Field(
        default=None, max_length=20000
    )
    n_replans: int = Field(default=0, ge=0)


@router.post("/api/robot/mission")
def send_mission(request: RobotMission):
    global _mission, _number
    try:
        sc = load_map(request.map_id)
    except (ValueError, OSError) as exc:
        raise HTTPException(422, "地図が不正です") from exc
    path = np.asarray(request.path)
    points = np.asarray(request.points).reshape(-1, 2)
    for values in (path, points):
        if (
            not np.isfinite(values).all()
            or (values < 0).any()
            or (values > (np.asarray(sc["tmap"].shape) - 1) * RESOLUTION).any()
        ):
            raise HTTPException(422, "経路・地点は地図内の有限な座標にしてください")
    with _lock:
        _number += 1
        _mission = dict(request.model_dump(), id=_number)
        return copy.deepcopy(_mission)


@router.get("/api/robot/mission")
def get_mission(after: int = 0):
    with _lock:
        if _mission is None or _mission["id"] <= after:
            return Response(status_code=204)
        return copy.deepcopy(_mission)


@router.post("/api/robot/state")
def send_state(request: RobotState):
    global _state
    if request.pose is not None and not np.isfinite(request.pose).all():
        raise HTTPException(422, "姿勢は有限値にしてください")
    if not np.isfinite(request.sim_time):
        raise HTTPException(422, "時刻は有限値にしてください")
    if request.current_path is not None and not np.isfinite(request.current_path).all():
        raise HTTPException(422, "経路は有限値にしてください")
    payload = request.model_dump()
    for key in ("current_path", "n_replans"):
        if key not in request.model_fields_set:
            payload.pop(key)
    with _lock:
        _state = dict(payload, received_at=time.time())
    return dict(ok=True)


@router.get("/api/robot/state")
def get_state():
    with _lock:
        if _state is None:
            return dict(connected=False)
        age = max(0.0, time.time() - _state["received_at"])
        return dict(copy.deepcopy(_state), connected=age <= 3.0, age_s=age)
