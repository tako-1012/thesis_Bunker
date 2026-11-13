"""Task034 opt-in known-cell replanning and pose/path stopping; legacy untouched."""

import math
import numpy as np
from .collision import segment_cells
from .config import RESOLUTION, Robot
from .follower import MissionFollower
from .online_mission import OnlinePlanner
from .pure_pursuit import path_distance

ONLINE_FIXES = ('none', 'v1')
JOIN_TIMEOUT_S = 10.
OFF_PATH_M = .75
SAFETY_STATES = ('unsafe_tilt', 'off_path')


def validate_fixes(value):
    if value not in ONLINE_FIXES:
        raise ValueError('unknown online fixes')
    return value


class SafetyOnlinePlanner(OnlinePlanner):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.pending_changed = None

    def observe(self, mask, cost, lethal):
        known = None if self.known is None else self.known.copy()
        old = None if known is None else self.lethal.copy()
        new = super().observe(mask, cost, lethal)
        if self.pending_changed is None:
            self.pending_changed = np.zeros(self.known.shape, bool)
        if known is not None:
            self.pending_changed |= np.asarray(mask, bool) & known & ~old & self.lethal
        return new

    def _plan(self, reason, initial=False):
        result = super()._plan(reason, initial=initial)
        self.pending_changed.fill(False)
        return result

    def update(self, pos_xy, *, distance_m=None):
        pos = np.asarray(pos_xy, float)/RESOLUTION
        if self.goal is None or pos.shape != (2,) or not np.isfinite(pos).all():
            return super().update(pos_xy, distance_m=distance_m)
        moved = float(np.linalg.norm(pos-self.pos)*RESOLUTION) if distance_m is None else float(distance_m)
        if not math.isfinite(moved) or moved < 0:
            raise ValueError('invalid travelled distance')
        previous = self.pos
        self.pos = pos
        remaining = self._remaining()
        self.pos = previous
        changed = self.pending_changed & self.lethal
        for a, b in zip(remaining[:-1], remaining[1:]):
            cells = segment_cells(a, b, self.known.shape)
            if changed[tuple(cells.T)].any():
                self.pos = pos.copy()
                self.since_replan += moved
                return self._plan('lethal_changed')
        return super().update(pos_xy, distance_m=distance_m)


class SafetyMissionFollower(MissionFollower):
    def step(self, t, pose, *, imu_rpy=None):
        pose = np.asarray(pose, float)
        if pose.shape not in ((3,), (6,)) or not np.isfinite(pose).all() or not math.isfinite(t):
            raise ValueError('time and pose must be finite xy/yaw or xyz/rpy')
        if self._last_t is not None and t < self._last_t:
            raise ValueError('time moved backwards')
        xy_yaw = pose if len(pose) == 3 else pose[[0, 1, 5]]
        tilt = np.zeros(2) if len(pose) == 3 else pose[3:5]
        if imu_rpy is not None:
            imu = np.asarray(imu_rpy, float)
            if imu.shape != (3,) or not np.isfinite(imu).all():
                raise ValueError('IMU orientation must be finite rpy')
            # Either source can stop the robot; a stale level IMU must not
            # conceal an unsafe ground-truth/model attitude.
            tilt = np.maximum(np.abs(tilt), np.abs(imu[:2]))
        if self.status == 'running':
            if (np.abs(tilt) > math.radians(Robot().max_slope_deg)).any():
                self.status = 'unsafe_tilt'
            elif path_distance(xy_yaw[:2], self.controller.path) > OFF_PATH_M:
                self.status = 'off_path'
        if self.status in SAFETY_STATES:
            self._last_t = t
            return 0., 0., True
        return super().step(t, xy_yaw)


def make_follower(*args, online_fixes='none', **kwargs):
    validate_fixes(online_fixes)
    cls = SafetyMissionFollower if online_fixes == 'v1' else MissionFollower
    return cls(*args, **kwargs)
