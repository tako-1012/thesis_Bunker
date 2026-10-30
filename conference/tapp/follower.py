"""ROS-free Pure Pursuit wrapper with terminal states and a motion watchdog."""

import math
import numpy as np
from .pure_pursuit import PurePursuit


class MissionFollower:
    def __init__(
        self,
        path_xy,
        lookahead_m=1.0,
        v_max=1.0,
        w_max=1.0,
        goal_tol_m=0.3,
        *,
        stall_timeout_s=10.0,
        stall_distance_m=0.1
    ):
        if any(
            not math.isfinite(v) or v <= 0 for v in (stall_timeout_s, stall_distance_m)
        ):
            raise ValueError("watchdog thresholds must be positive")
        self.controller = PurePursuit(path_xy, lookahead_m, v_max, w_max, goal_tol_m)
        self.stall_timeout_s, self.stall_distance_m = stall_timeout_s, stall_distance_m
        self.status = "running"
        self._anchor = None
        self._motion_t = None
        self._last_t = None

    def step(self, t, pose):
        pose = np.asarray(pose, dtype=float)
        if not math.isfinite(t) or pose.shape != (3,) or not np.isfinite(pose).all():
            raise ValueError("time and pose must be finite")
        if self._last_t is not None and t < self._last_t:
            raise ValueError("time moved backwards")
        self._last_t = t
        if self.status != "running":
            return 0.0, 0.0, True
        v, w, done = self.controller.command(pose)
        if done:
            self.status = "completed"
            return 0.0, 0.0, True
        turn = (
            0
            if self._anchor is None
            else abs((pose[2] - self._anchor[2] + math.pi) % (2 * math.pi) - math.pi)
        )
        moved = (
            self._anchor is None
            or np.linalg.norm(pose[:2] - self._anchor[:2]) >= self.stall_distance_m
        )
        if moved or (v == 0 and turn >= 0.1):
            self._anchor, self._motion_t = pose.copy(), t
        elif t - self._motion_t >= self.stall_timeout_s:
            self.status = "stuck"
            return 0.0, 0.0, True
        return v, w, False

    def log_row(self, t, pose3d, imu_rpy, v, w):
        x, y, z, roll, pitch, yaw = pose3d
        if imu_rpy is not None:
            roll, pitch = imu_rpy[:2]
        return dict(
            t=float(t),
            x=float(x),
            y=float(y),
            z=float(z),
            roll=float(roll),
            pitch=float(pitch),
            yaw=float(yaw),
            v=float(v),
            w=float(w),
        )
