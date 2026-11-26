"""Opt-in search implementation for LiDAR planners using the distance layer."""

import time

import numpy as np

from tapp.collision import path_lethal_cells
from tapp.config import RESOLUTION
from tapp.distance_clearance import connector_clear
from tapp.goal_region import in_grid
from tapp.online_mission import OnlinePlanner
from tapp.planners import astar


class DistancePlanner(OnlinePlanner):
    tracking_clearance = None
    tracking_relaxed_layers = frozenset()

    def planning_maps(self):
        blocked, mult = super().planning_maps()
        steep_cost = getattr(self, 'steep_cost', None)
        if steep_cost is not None and self.tracking_clearance is None:
            # The current steep layer contributes around inferred hazards as
            # well, without turning those unobserved cells into observations.
            mult += self.w*steep_cost
        return blocked, mult

    def update(self, pos_xy, *, distance_m=None):
        if self.tracking_clearance is not None and self.path:
            from .overlap_goal import handoff_lethal

            pos = np.asarray(pos_xy, float)/RESOLUTION
            if (self.goal is None or pos.shape != (2,) or not np.isfinite(pos).all()
                    or (distance_m is not None and (not np.isfinite(distance_m) or distance_m < 0))):
                return super().update(pos_xy, distance_m=distance_m)
            previous = self.pos
            self.pos = pos
            remaining = self._remaining()
            self.pos = previous
            if len(path_lethal_cells(remaining, handoff_lethal(self))):
                self.pos = pos
                return self._plan('tracking_margin_blocked')
        return super().update(pos_xy, distance_m=distance_m)

    def _plan(self, reason, initial=False):
        blocked, mult = self.planning_maps()
        start = tuple(int(round(v)) for v in self.pos)
        began = time.perf_counter()
        tracking = self.tracking_clearance
        if tracking is not None:
            blocked, mult, labels, self.tracking_relaxed_layers, _ = tracking.project(
                blocked, mult, start, self.goal, self.w)
        # A* allows leaving a blocked start. Task070 requires a clear start
        # after applying its explicit plan-local exception.
        path = None
        start_ok = tracking is None or (in_grid(start, blocked.shape) and not blocked[start])
        if start_ok and in_grid(self.goal, blocked.shape) and not blocked[self.goal]:
            result = astar(blocked, start, self.goal, mult)
            if result['success']:
                path, _ = self.distance_geometry.smooth(result['path'], blocked, mult, los=self.los)
        self.plan_times.append(time.perf_counter()-began)
        self.since_replan = 0.
        if path is not None:
            self.path = [np.asarray(point, float) for point in path]
            if not initial:
                known_lethal = blocked if tracking is not None else self.known & self.lethal
                rest = self.path[1:]
                if not rest or not connector_clear(self, known_lethal, self.pos, start, rest[0]):
                    rest = [np.asarray(start, float)]+rest
                self.path = [self.pos.copy()]+rest
            self.seg = 0
        self.pending_new.fill(False)
        event = dict(reason=reason, success=path is not None, plan_time_s=self.plan_times[-1],
                     n_plans=len(self.plan_times))
        if tracking is not None:
            event['tracking_margin_relaxed'] = labels
        self.events.append(event)
        return dict(event, path=[p.tolist() for p in self.path] if path is not None else [], replanned=True)
