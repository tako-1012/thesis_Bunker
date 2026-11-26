"""Opt-in search implementation for LiDAR planners using the distance layer."""

import time

import numpy as np

from tapp.distance_clearance import connector_clear
from tapp.online_mission import OnlinePlanner
from tapp.planners import astar


class DistancePlanner(OnlinePlanner):
    def planning_maps(self):
        blocked, mult = super().planning_maps()
        steep_cost = getattr(self, 'steep_cost', None)
        if steep_cost is not None:
            # The current steep layer contributes around inferred hazards as
            # well, without turning those unobserved cells into observations.
            mult += self.w*steep_cost
        return blocked, mult

    def _plan(self, reason, initial=False):
        blocked, mult = self.planning_maps()
        start = tuple(int(round(v)) for v in self.pos)
        began = time.perf_counter()
        # A* allows leaving a blocked start. A coincident blocked goal must
        # still be rejected.
        path = None
        if all(0 <= i < size for i, size in zip(self.goal, blocked.shape)) and not blocked[self.goal]:
            result = astar(blocked, start, self.goal, mult)
            if result['success']:
                path, _ = self.distance_geometry.smooth(result['path'], blocked, mult, los=self.los)
        self.plan_times.append(time.perf_counter()-began)
        self.since_replan = 0.
        if path is not None:
            self.path = [np.asarray(point, float) for point in path]
            if not initial:
                known_lethal = self.known & self.lethal
                rest = self.path[1:]
                if not rest or not connector_clear(self, known_lethal, self.pos, start, rest[0]):
                    rest = [np.asarray(start, float)]+rest
                self.path = [self.pos.copy()]+rest
            self.seg = 0
        self.pending_new.fill(False)
        event = dict(reason=reason, success=path is not None, plan_time_s=self.plan_times[-1],
                     n_plans=len(self.plan_times))
        self.events.append(event)
        return dict(event, path=[p.tolist() for p in self.path] if path is not None else [], replanned=True)
